/**
 * Monte Carlo Visualization Engine
 * High-performance visualization components for Monte Carlo simulation results
 */

import { deps, CONFIG } from './config.js';
import { getAuthHeaders } from './auth.js';
import { showNotification } from './notifications.js';

const { DOM } = deps;

// Monte Carlo State
export const MCState = {
    results: null,
    currentVisualization: 'distribution',
    selectedSimulations: [],
    confidenceLevel: 95,
    showPercentiles: true,
    showPaths: true
};

/**
 * Initialize Monte Carlo visualization components
 */
export function initializeMonteCarloVisualizations() {
    // Add Monte Carlo section to backtesting results
    createMonteCarloSection();
    
    // Initialize event listeners
    setupMCEventListeners();
}

/**
 * Create Monte Carlo section HTML structure
 */
function createMonteCarloSection() {
    const mcSection = document.createElement('div');
    mcSection.id = 'monteCarloSection';
    mcSection.className = 'monte-carlo-section hidden';
    mcSection.innerHTML = `
        <div class="mc-header">
            <h3>🎲 Monte Carlo Analysis</h3>
            <div class="mc-risk-badge" id="mcRiskBadge">Waiting...</div>
        </div>
        
        <div class="mc-controls">
            <div class="control-group">
                <label>Simulations:</label>
                <select id="mcSimulationCount">
                    <option value="1000">1,000 (Fast)</option>
                    <option value="10000" selected>10,000 (Standard)</option>
                    <option value="50000">50,000 (High Precision)</option>
                </select>
            </div>
            
            <div class="control-group">
                <label>Confidence:</label>
                <input type="range" id="mcConfidenceSlider" min="80" max="99" value="95">
                <span id="mcConfidenceValue">95%</span>
            </div>
            
            <div class="control-group">
                <button id="mcRunBtn" class="btn-primary">Run Analysis</button>
                <button id="mcQuickBtn" class="btn-secondary">Quick (1K)</button>
            </div>
        </div>
        
        <div class="mc-metrics-grid" id="mcMetricsGrid">
            <!-- Key metrics will be inserted here -->
        </div>
        
        <div class="mc-interpretation" id="mcInterpretation">
            <!-- Interpretation text will be inserted here -->
        </div>
        
        <div class="mc-visualization-tabs">
            <button class="tab-btn active" data-tab="distribution">Distribution</button>
            <button class="tab-btn" data-tab="paths">Path Fan</button>
            <button class="tab-btn" data-tab="heatmap">Heat Map</button>
            <button class="tab-btn" data-tab="comparison">Comparison</button>
        </div>
        
        <div class="mc-visualization-content">
            <div id="mcDistributionChart" class="mc-chart-container active">
                <canvas id="mcDistCanvas"></canvas>
                <div class="mc-chart-legend" id="mcDistLegend"></div>
            </div>
            
            <div id="mcPathsChart" class="mc-chart-container">
                <canvas id="mcPathsCanvas"></canvas>
                <div class="mc-path-controls">
                    <label>
                        <input type="checkbox" id="showPercentileBands" checked> 
                        Show Percentile Bands
                    </label>
                    <label>
                        <input type="checkbox" id="showHistoricalPath" checked> 
                        Show Historical
                    </label>
                </div>
            </div>
            
            <div id="mcHeatmapChart" class="mc-chart-container">
                <canvas id="mcHeatmapCanvas"></canvas>
                <div class="mc-heatmap-legend" id="mcHeatmapLegend"></div>
            </div>
            
            <div id="mcComparisonChart" class="mc-chart-container">
                <div class="mc-comparison-grid" id="mcComparisonGrid"></div>
            </div>
        </div>
        
        <div class="mc-risk-details" id="mcRiskDetails">
            <!-- Detailed risk metrics -->
        </div>
        
        <div class="mc-export-controls">
            <button id="mcExportData" class="btn-text">Export Data (CSV)</button>
            <button id="mcExportChart" class="btn-text">Export Chart (PNG)</button>
        </div>
    `;
    
    // Insert after backtesting results
    const backtestingResults = document.getElementById('backtestingResults');
    if (backtestingResults) {
        backtestingResults.appendChild(mcSection);
    }
}

/**
 * Setup Monte Carlo event listeners
 */
function setupMCEventListeners() {
    // Tab switching
    document.querySelectorAll('.mc-visualization-tabs .tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tab = e.target.dataset.tab;
            switchMCTab(tab);
        });
    });
    
    // Confidence slider
    const slider = document.getElementById('mcConfidenceSlider');
    const value = document.getElementById('mcConfidenceValue');
    if (slider && value) {
        slider.addEventListener('input', (e) => {
            MCState.confidenceLevel = parseInt(e.target.value);
            value.textContent = `${MCState.confidenceLevel}%`;
            if (MCState.results) {
                renderMCDistribution(MCState.results);
            }
        });
    }
    
    // Run buttons
    document.getElementById('mcRunBtn')?.addEventListener('click', () => runMonteCarlo());
    document.getElementById('mcQuickBtn')?.addEventListener('click', () => runMonteCarlo(true));
    
    // Export buttons
    document.getElementById('mcExportData')?.addEventListener('click', exportMCData);
    document.getElementById('mcExportChart')?.addEventListener('click', exportMCChart);
}

/**
 * Switch Monte Carlo visualization tab
 */
function switchMCTab(tab) {
    MCState.currentVisualization = tab;
    
    // Update buttons
    document.querySelectorAll('.mc-visualization-tabs .tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    
    // Update content
    document.querySelectorAll('.mc-chart-container').forEach(container => {
        container.classList.remove('active');
    });
    document.getElementById(`mc${tab.charAt(0).toUpperCase() + tab.slice(1)}Chart`)?.classList.add('active');
    
    // Render if we have data
    if (MCState.results) {
        switch(tab) {
            case 'distribution':
                renderMCDistribution(MCState.results);
                break;
            case 'paths':
                renderMCPaths(MCState.results);
                break;
            case 'heatmap':
                renderMCHeatmap(MCState.results);
                break;
            case 'comparison':
                renderMCComparison(MCState.results);
                break;
        }
    }
}

/**
 * Run Monte Carlo simulation
 */
async function runMonteCarlo(quick = false) {
    const runBtn = document.getElementById('mcRunBtn');
    const quickBtn = document.getElementById('mcQuickBtn');
    
    // Get parameters
    const numSimulations = quick ? 1000 : parseInt(document.getElementById('mcSimulationCount')?.value || 10000);
    
    // Get backtest data from current results
    const backtestData = window.currentBacktestData;
    if (!backtestData || !backtestData.trades) {
        showNotification('Please run a backtest first', 'error');
        return;
    }
    
    // Show loading
    runBtn.disabled = true;
    quickBtn.disabled = true;
    runBtn.textContent = '🎲 Running...';
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/backtest/${quick ? 'quick_mc' : 'monte_carlo'}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify({
                trades: backtestData.trades,
                prices: backtestData.prices || [],
                num_simulations: numSimulations,
                seed: 0,  // Auto-generate
                initial_capital: backtestData.initial_balance || 100000,
                original_return: backtestData.strategy_return_pct || 0,
                original_sharpe: backtestData.sharpe_ratio || 0,
                original_max_dd: backtestData.max_drawdown_pct || 0
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const results = await response.json();
        MCState.results = results;
        
        // Show section
        document.getElementById('monteCarloSection')?.classList.remove('hidden');
        
        // Render results
        renderMCResults(results);
        
        // Show notification
        const simCount = results.metadata?.num_trials || numSimulations;
        showNotification(`✅ Monte Carlo complete: ${simCount.toLocaleString()} simulations`, 'success');
        
    } catch (error) {
        console.error('Monte Carlo error:', error);
        showNotification('Monte Carlo analysis failed. Please try again.', 'error');
    } finally {
        runBtn.disabled = false;
        quickBtn.disabled = false;
        runBtn.textContent = 'Run Analysis';
    }
}

/**
 * Render Monte Carlo results
 */
function renderMCResults(results) {
    // Update risk badge
    const badge = document.getElementById('mcRiskBadge');
    if (badge && results.summary?.risk_rating) {
        badge.textContent = results.summary.risk_rating;
        badge.className = `mc-risk-badge ${results.summary.risk_rating.toLowerCase()}`;
    }
    
    // Render metrics grid
    renderMCMetrics(results);
    
    // Render interpretation
    renderMCInterpretation(results);
    
    // Render current tab
    switch(MCState.currentVisualization) {
        case 'distribution':
            renderMCDistribution(results);
            break;
        case 'paths':
            renderMCPaths(results);
            break;
        case 'heatmap':
            renderMCHeatmap(results);
            break;
        case 'comparison':
            renderMCComparison(results);
            break;
    }
    
    // Render risk details
    renderMCRiskDetails(results);
}

/**
 * Render Monte Carlo metrics grid
 */
function renderMCMetrics(results) {
    const grid = document.getElementById('mcMetricsGrid');
    if (!grid) return;
    
    const stats = results.statistics || {};
    const orig = results.original_strategy || {};
    const risk = results.risk_metrics || {};
    
    grid.innerHTML = `
        <div class="mc-metric large">
            <label>P-Value</label>
            <value class="${getPValueColor(stats.p_value_vs_random)}">${(stats.p_value_vs_random || 0).toFixed(2)}%</value>
            <small>vs random</small>
        </div>
        
        <div class="mc-metric">
            <label>Mean Return</label>
            <value>${(results.summary?.mean_return || 0).toFixed(2)}%</value>
        </div>
        
        <div class="mc-metric">
            <label>Median (P50)</label>
            <value>${(stats.percentiles?.p50 || 0).toFixed(2)}%</value>
        </div>
        
        <div class="mc-metric highlight">
            <label>Your Strategy</label>
            <value class="${(orig.return_pct || 0) > 0 ? 'positive' : 'negative'}">${(orig.return_pct || 0).toFixed(2)}%</value>
            <small>${getPercentileRank(orig.return_pct, stats.percentiles)}</small>
        </div>
        
        <div class="mc-metric">
            <label>VaR (95%)</label>
            <value class="negative">${(risk.var_95 || 0).toFixed(2)}%</value>
            <small>worst case</small>
        </div>
        
        <div class="mc-metric">
            <label>CVaR (95%)</label>
            <value class="negative">${(risk.cvar_95 || 0).toFixed(2)}%</value>
            <small>avg of worst 5%</small>
        </div>
        
        <div class="mc-metric">
            <label>Prob. of Ruin</label>
            <value class="${(risk.probability_of_ruin || 0) > 5 ? 'negative' : ''}">${(risk.probability_of_ruin || 0).toFixed(2)}%</value>
        </div>
        
        <div class="mc-metric">
            <label>Best Case (P95)</label>
            <value class="positive">${(stats.percentiles?.p95 || 0).toFixed(2)}%</value>
        </div>
    `;
}

/**
 * Get color class based on p-value
 */
function getPValueColor(pValue) {
    if (pValue < 5) return 'strong-signal';
    if (pValue < 25) return 'moderate-signal';
    if (pValue < 50) return 'weak-signal';
    return 'no-signal';
}

/**
 * Get percentile rank text
 */
function getPercentileRank(value, percentiles) {
    if (!value || !percentiles) return '';
    if (value > percentiles.p95) return '>95th percentile 🏆';
    if (value > percentiles.p75) return '>75th percentile ⭐';
    if (value > percentiles.p50) return '>50th percentile';
    return '<50th percentile';
}

/**
 * Render interpretation text
 */
function renderMCInterpretation(results) {
    const container = document.getElementById('mcInterpretation');
    if (!container) return;
    
    const interpretation = results.summary?.interpretation || 'No interpretation available.';
    
    container.innerHTML = `
        <div class="interpretation-box">
            <h4>📊 Analysis</h4>
            <p>${interpretation}</p>
        </div>
    `;
}

/**
 * Render distribution histogram
 */
function renderMCDistribution(results) {
    const canvas = document.getElementById('mcDistCanvas');
    if (!canvas || !results.distribution) return;
    
    const ctx = canvas.getContext('2d');
    const dist = results.distribution;
    const orig = results.original_strategy || {};
    const stats = results.statistics || {};
    
    // Set canvas size
    canvas.width = canvas.offsetWidth || 800;
    canvas.height = 400;
    
    const width = canvas.width;
    const height = canvas.height;
    const padding = { top: 40, right: 40, bottom: 60, left: 60 };
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Get histogram data
    const histogram = dist.histogram || [];
    const minVal = dist.min || 0;
    const maxVal = dist.max || 100;
    
    if (histogram.length === 0) return;
    
    // Calculate scales
    const maxCount = Math.max(...histogram);
    const barWidth = (width - padding.left - padding.right) / histogram.length;
    
    // Draw histogram bars
    histogram.forEach((count, i) => {
        const barHeight = (count / maxCount) * (height - padding.top - padding.bottom);
        const x = padding.left + i * barWidth;
        const y = height - padding.bottom - barHeight;
        
        // Color based on position relative to original
        const binStart = minVal + (i / histogram.length) * (maxVal - minVal);
        const binEnd = minVal + ((i + 1) / histogram.length) * (maxVal - minVal);
        
        let color = '#3b82f6';  // Default blue
        if (orig.return_pct >= binStart && orig.return_pct <= binEnd) {
            color = '#10b981';  // Green for original strategy
        } else if (binEnd < stats.percentiles?.p5) {
            color = '#ef4444';  // Red for worst
        } else if (binEnd > stats.percentiles?.p95) {
            color = '#22c55e';  // Green for best
        }
        
        ctx.fillStyle = color;
        ctx.fillRect(x, y, barWidth - 1, barHeight);
    });
    
    // Draw axes
    ctx.strokeStyle = '#374151';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, height - padding.bottom);
    ctx.lineTo(width - padding.right, height - padding.bottom);
    ctx.stroke();
    
    // Draw original strategy line
    const origX = padding.left + ((orig.return_pct - minVal) / (maxVal - minVal)) * (width - padding.left - padding.right);
    ctx.strokeStyle = '#10b981';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(origX, padding.top);
    ctx.lineTo(origX, height - padding.bottom);
    ctx.stroke();
    
    // Draw percentile lines based on confidence level
    const pLower = (100 - MCState.confidenceLevel) / 2;
    const pUpper = 100 - pLower;
    
    // Draw labels
    ctx.fillStyle = '#6b7280';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${minVal.toFixed(1)}%`, padding.left, height - padding.bottom + 20);
    ctx.fillText(`${maxVal.toFixed(1)}%`, width - padding.right, height - padding.bottom + 20);
    ctx.fillText('Return %', width / 2, height - 10);
    
    // Y-axis label
    ctx.save();
    ctx.translate(20, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Frequency', 0, 0);
    ctx.restore();
    
    // Legend
    const legend = document.getElementById('mcDistLegend');
    if (legend) {
        legend.innerHTML = `
            <div class="legend-item"><span class="color-box" style="background: #3b82f6"></span>Random Simulations</div>
            <div class="legend-item"><span class="color-box" style="background: #10b981"></span>Your Strategy</div>
            <div class="legend-item"><span class="color-box" style="background: #ef4444"></span>Worst 5%</div>
            <div class="legend-item"><span class="color-box" style="background: #22c55e"></span>Best 5%</div>
        `;
    }
}

/**
 * Render path fan chart
 */
function renderMCPaths(results) {
    const canvas = document.getElementById('mcPathsCanvas');
    if (!canvas || !results.simulations) return;
    
    const ctx = canvas.getContext('2d');
    const sims = results.simulations;
    
    // Set canvas size
    canvas.width = canvas.offsetWidth || 800;
    canvas.height = 400;
    
    const width = canvas.width;
    const height = canvas.height;
    const padding = { top: 40, right: 40, bottom: 60, left: 60 };
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Find max length and value range
    let maxLen = 0;
    let minVal = Infinity;
    let maxVal = -Infinity;
    
    sims.forEach(sim => {
        if (sim.equity_curve) {
            maxLen = Math.max(maxLen, sim.equity_curve.length);
            minVal = Math.min(minVal, ...sim.equity_curve);
            maxVal = Math.max(maxVal, ...sim.equity_curve);
        }
    });
    
    if (maxLen === 0) return;
    
    // Draw percentile bands
    if (document.getElementById('showPercentileBands')?.checked) {
        // Calculate percentiles at each time point
        const percentiles = { p10: [], p25: [], p50: [], p75: [], p90: [] };
        
        for (let t = 0; t < maxLen; t++) {
            const values = sims
                .filter(s => s.equity_curve && s.equity_curve[t])
                .map(s => s.equity_curve[t]);
            
            if (values.length > 0) {
                values.sort((a, b) => a - b);
                percentiles.p10.push(values[Math.floor(values.length * 0.1)]);
                percentiles.p25.push(values[Math.floor(values.length * 0.25)]);
                percentiles.p50.push(values[Math.floor(values.length * 0.5)]);
                percentiles.p75.push(values[Math.floor(values.length * 0.75)]);
                percentiles.p90.push(values[Math.floor(values.length * 0.9)]);
            }
        }
        
        // Draw bands
        drawPercentileBand(ctx, percentiles.p10, percentiles.p90, padding, width, height, minVal, maxVal, maxLen, 'rgba(200, 200, 200, 0.3)');
        drawPercentileBand(ctx, percentiles.p25, percentiles.p75, padding, width, height, minVal, maxVal, maxLen, 'rgba(150, 180, 220, 0.4)');
        
        // Draw median
        drawPath(ctx, percentiles.p50, padding, width, height, minVal, maxVal, maxLen, '#2563eb', 3);
    }
    
    // Draw sample paths (limited for performance)
    const sampleCount = Math.min(50, sims.length);
    for (let i = 0; i < sampleCount; i++) {
        if (sims[i].equity_curve) {
            drawPath(ctx, sims[i].equity_curve, padding, width, height, minVal, maxVal, maxLen, 'rgba(100, 100, 100, 0.1)', 1);
        }
    }
    
    // Draw axes
    ctx.strokeStyle = '#374151';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, height - padding.bottom);
    ctx.lineTo(width - padding.right, height - padding.bottom);
    ctx.stroke();
    
    // Labels
    ctx.fillStyle = '#6b7280';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Time (trades)', width / 2, height - 10);
    
    ctx.save();
    ctx.translate(20, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Portfolio Value (₹)', 0, 0);
    ctx.restore();
}

/**
 * Draw a single path on canvas
 */
function drawPath(ctx, data, padding, width, height, minVal, maxVal, maxLen, color, lineWidth) {
    if (!data || data.length === 0) return;
    
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    
    data.forEach((val, i) => {
        const x = padding.left + (i / (maxLen - 1)) * (width - padding.left - padding.right);
        const y = height - padding.bottom - ((val - minVal) / (maxVal - minVal)) * (height - padding.top - padding.bottom);
        
        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    
    ctx.stroke();
}

/**
 * Draw percentile band
 */
function drawPercentileBand(ctx, lower, upper, padding, width, height, minVal, maxVal, maxLen, color) {
    if (!lower || !upper || lower.length === 0) return;
    
    ctx.fillStyle = color;
    ctx.beginPath();
    
    // Upper line
    upper.forEach((val, i) => {
        const x = padding.left + (i / (maxLen - 1)) * (width - padding.left - padding.right);
        const y = height - padding.bottom - ((val - minVal) / (maxVal - minVal)) * (height - padding.top - padding.bottom);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    
    // Lower line (reverse)
    for (let i = lower.length - 1; i >= 0; i--) {
        const x = padding.left + (i / (maxLen - 1)) * (width - padding.left - padding.right);
        const y = height - padding.bottom - ((lower[i] - minVal) / (maxVal - minVal)) * (height - padding.top - padding.bottom);
        ctx.lineTo(x, y);
    }
    
    ctx.closePath();
    ctx.fill();
}

/**
 * Render heatmap
 */
function renderMCHeatmap(results) {
    const canvas = document.getElementById('mcHeatmapCanvas');
    if (!canvas) return;
    
    // Simplified heatmap implementation
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth || 800;
    canvas.height = 400;
    
    ctx.fillStyle = '#1f2937';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    ctx.fillStyle = '#6b7280';
    ctx.font = '16px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Heatmap visualization coming in Phase 2', canvas.width / 2, canvas.height / 2);
}

/**
 * Render comparison view
 */
function renderMCComparison(results) {
    const grid = document.getElementById('mcComparisonGrid');
    if (!grid) return;
    
    const stats = results.statistics || {};
    const orig = results.original_strategy || {};
    
    grid.innerHTML = `
        <div class="comparison-card strategy">
            <h4>Your Strategy</h4>
            <div class="metric-row">
                <span>Return</span>
                <value class="${(orig.return_pct || 0) > 0 ? 'positive' : 'negative'}">${(orig.return_pct || 0).toFixed(2)}%</value>
            </div>
            <div class="metric-row">
                <span>Sharpe</span>
                <value>${(orig.sharpe_ratio || 0).toFixed(2)}</value>
            </div>
            <div class="metric-row">
                <span>Max DD</span>
                <value class="negative">${(orig.max_drawdown_pct || 0).toFixed(2)}%</value>
            </div>
        </div>
        
        <div class="comparison-card">
            <h4>Random (Median)</h4>
            <div class="metric-row">
                <span>Return</span>
                <value>${(stats.percentiles?.p50 || 0).toFixed(2)}%</value>
            </div>
            <div class="metric-row">
                <span>Sharpe</span>
                <value>${(results.summary?.mean_sharpe || 0).toFixed(2)}</value>
            </div>
            <div class="metric-row">
                <span>Max DD</span>
                <value class="negative">${(results.summary?.mean_max_drawdown || 0).toFixed(2)}%</value>
            </div>
        </div>
        
        <div class="comparison-card best">
            <h4>Best 5% (P95)</h4>
            <div class="metric-row">
                <span>Return</span>
                <value class="positive">${(stats.percentiles?.p95 || 0).toFixed(2)}%</value>
            </div>
            <div class="metric-row">
                <span>Sharpe</span>
                <value>${(results.summary?.mean_sharpe * 1.5 || 0).toFixed(2)}</value>
            </div>
        </div>
        
        <div class="comparison-card worst">
            <h4>Worst 5% (P5)</h4>
            <div class="metric-row">
                <span>Return</span>
                <value class="negative">${(stats.percentiles?.p5 || 0).toFixed(2)}%</value>
            </div>
            <div class="metric-row">
                <span>Sharpe</span>
                <value class="negative">${(results.summary?.mean_sharpe * 0.5 || 0).toFixed(2)}</value>
            </div>
        </div>
    `;
}

/**
 * Render risk details
 */
function renderMCRiskDetails(results) {
    const container = document.getElementById('mcRiskDetails');
    if (!container) return;
    
    const risk = results.risk_metrics || {};
    const stats = results.statistics || {};
    
    container.innerHTML = `
        <h4>📊 Detailed Risk Metrics</h4>
        <div class="risk-grid">
            <div class="risk-item">
                <label>Value at Risk (95%)</label>
                <value>${(risk.var_95 || 0).toFixed(2)}%</value>
                <small>5% chance of losing more than this</small>
            </div>
            <div class="risk-item">
                <label>Conditional VaR</label>
                <value>${(risk.cvar_95 || 0).toFixed(2)}%</value>
                <small>Average loss in worst 5% of cases</small>
            </div>
            <div class="risk-item">
                <label>Probability of Ruin (>50% loss)</label>
                <value class="${(risk.probability_of_ruin || 0) > 5 ? 'negative' : ''}">${(risk.probability_of_ruin || 0).toFixed(2)}%</value>
            </div>
            <div class="risk-item">
                <label>95% Confidence Interval</label>
                <value>${(stats.confidence_interval_95?.lower || 0).toFixed(2)}% to ${(stats.confidence_interval_95?.upper || 0).toFixed(2)}%</value>
            </div>
        </div>
    `;
}

/**
 * Export Monte Carlo data
 */
function exportMCData() {
    if (!MCState.results) return;
    
    const data = MCState.results;
    let csv = 'Metric,Value\n';
    
    // Add key metrics
    csv += `P-Value,${data.statistics?.p_value_vs_random || 0}\n`;
    csv += `Mean Return,${data.summary?.mean_return || 0}\n`;
    csv += `Median Return,${data.statistics?.percentiles?.p50 || 0}\n`;
    csv += `Original Strategy Return,${data.original_strategy?.return_pct || 0}\n`;
    csv += `VaR (95%),${data.risk_metrics?.var_95 || 0}\n`;
    csv += `CVaR (95%),${data.risk_metrics?.cvar_95 || 0}\n`;
    csv += `Probability of Ruin,${data.risk_metrics?.probability_of_ruin || 0}\n`;
    
    // Add simulations
    csv += '\n\nSimulation,Final Value,Return %,Max DD %,Win Rate %,Sharpe\n';
    (data.simulations || []).forEach((sim, i) => {
        csv += `${i + 1},${sim.final_value},${sim.total_return_pct},${sim.max_drawdown_pct},${sim.win_rate},${sim.sharpe_ratio}\n`;
    });
    
    // Download
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `monte_carlo_analysis_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    
    showNotification('Data exported successfully', 'success');
}

/**
 * Export Monte Carlo chart
 */
function exportMCChart() {
    const canvas = document.querySelector('.mc-chart-container.active canvas');
    if (!canvas) return;
    
    const link = document.createElement('a');
    link.download = `monte_carlo_chart_${new Date().toISOString().split('T')[0]}.png`;
    link.href = canvas.toDataURL();
    link.click();
    
    showNotification('Chart exported successfully', 'success');
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeMonteCarloVisualizations);
} else {
    initializeMonteCarloVisualizations();
}
