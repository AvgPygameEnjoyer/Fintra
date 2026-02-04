/**
 * Simplified Monte Carlo Front-end Controller
 */

import { CONFIG } from './config.js';
import { getAuthHeaders } from './auth.js';
import { showNotification } from './notifications.js';

// Monte Carlo State
let mcResults = null;
let isRunning = false;

/**
 * Initialize Monte Carlo functionality
 */
export function initializeMonteCarlo() {
    const quickBtn = document.getElementById('mc-quick-btn');
    const fullBtn = document.getElementById('mc-full-btn');
    
    if (quickBtn) {
        quickBtn.addEventListener('click', () => runMonteCarloAnalysis(1000));
    }
    
    if (fullBtn) {
        fullBtn.addEventListener('click', () => runMonteCarloAnalysis(10000));
    }
}

/**
 * Run Monte Carlo analysis
 */
async function runMonteCarloAnalysis(numSimulations) {
    if (isRunning) {
        showNotification('Analysis in progress...', 'warning');
        return;
    }
    
    // Get backtest data from global storage
    const backtestData = window.currentBacktestData;
    
    if (!backtestData || !backtestData.trades || backtestData.trades.length === 0) {
        showNotification('Please run a backtest first', 'error');
        return;
    }
    
    if (backtestData.trades.length < 2) {
        showNotification('Need at least 2 trades for Monte Carlo analysis', 'error');
        return;
    }
    
    isRunning = true;
    
    // Disable buttons during analysis
    const quickBtn = document.getElementById('mc-quick-btn');
    const fullBtn = document.getElementById('mc-full-btn');
    if (quickBtn) quickBtn.disabled = true;
    if (fullBtn) fullBtn.disabled = true;
    
    // Show loading
    const loadingEl = document.getElementById('mc-loading');
    const errorEl = document.getElementById('mc-error');
    const resultsEl = document.getElementById('mc-results');
    
    if (loadingEl) loadingEl.classList.remove('hidden');
    if (errorEl) errorEl.textContent = '';
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/backtest/monte_carlo`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify({
                trades: backtestData.trades,
                prices: backtestData.prices || [],
                num_simulations: numSimulations,
                seed: 0,
                initial_capital: backtestData.initial_balance || 100000,
                original_return: backtestData.strategy_return_pct || 0,
                original_sharpe: backtestData.sharpe_ratio || 0,
                original_max_dd: backtestData.max_drawdown_pct || 0
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Monte Carlo analysis failed');
        }
        
        mcResults = await response.json();
        
        // Render results
        renderMCResults(mcResults);
        
        // Show results section
        const mcSection = document.getElementById('monte-carlo-section');
        if (mcSection) mcSection.classList.remove('hidden');
        
        showNotification('Monte Carlo analysis complete!', 'success');
        
    } catch (error) {
        console.error('Monte Carlo error:', error);
        if (errorEl) errorEl.textContent = error.message;
        showNotification('Monte Carlo analysis failed', 'error');
    } finally {
        isRunning = false;
        if (loadingEl) loadingEl.classList.add('hidden');
        
        // Re-enable buttons
        if (quickBtn) quickBtn.disabled = false;
        if (fullBtn) fullBtn.disabled = false;
    }
}

/**
 * Render Monte Carlo results
 */
function renderMCResults(data) {
    const resultsEl = document.getElementById('mc-results');
    if (!resultsEl || !data) return;
    
    const stats = data.statistics || {};
    const summary = data.summary || {};
    const risk = data.risk_metrics || {};
    const orig = data.original_strategy || {};
    
    const riskRating = summary.risk_rating || 'UNKNOWN';
    const riskColor = riskRating === 'GREEN' ? '#10b981' : (riskRating === 'AMBER' ? '#f59e0b' : '#ef4444');
    
    resultsEl.innerHTML = `
        <div class="mc-header-bar">
            <div class="mc-risk-badge" style="background-color: ${riskColor};">
                ${riskRating}
            </div>
            <div class="mc-meta">
                <span>🎲 ${data.metadata?.num_trials || 0} simulations</span>
                <span>⏱️ ${data.performance?.elapsed_time_seconds?.toFixed(2) || 0}s</span>
            </div>
        </div>
        
        <div class="mc-interpretation">
            <p>${summary.interpretation || 'No interpretation available.'}</p>
        </div>
        
        <div class="mc-metrics">
            <div class="mc-metric-card highlight">
                <label>P-Value</label>
                <value>${(stats.p_value_vs_random || 0).toFixed(2)}%</value>
                <small>Probability random beats your strategy</small>
            </div>
            
            <div class="mc-metric-card">
                <label>Your Return</label>
                <value class="${orig.return_pct >= 0 ? 'positive' : 'negative'}">${(orig.return_pct || 0).toFixed(2)}%</value>
            </div>
            
            <div class="mc-metric-card">
                <label>Mean Random</label>
                <value>${(summary.mean_return || 0).toFixed(2)}%</value>
            </div>
            
            <div class="mc-metric-card">
                <label>Best 5%</label>
                <value class="positive">${(stats.percentiles?.p95 || 0).toFixed(2)}%</value>
            </div>
            
            <div class="mc-metric-card">
                <label>Worst 5%</label>
                <value class="negative">${(stats.percentiles?.p5 || 0).toFixed(2)}%</value>
            </div>
            
            <div class="mc-metric-card">
                <label>VaR (95%)</label>
                <value class="negative">${(risk.var_95 || 0).toFixed(2)}%</value>
            </div>
        </div>
        
        <div class="mc-analysis-text">
            <h4>Analysis</h4>
            <p>Your strategy's <strong>${(orig.return_pct || 0).toFixed(2)}%</strong> return vs <strong>${stats.percentiles?.p5 || 0}% to ${stats.percentiles?.p95 || 0}%</strong> random range.</p>
            <p>P-Value of <strong>${(stats.p_value_vs_random || 0).toFixed(2)}%</strong> means only <strong>${(stats.p_value_vs_random || 0).toFixed(2)}%</strong> of random strategies performed similarly or better.</p>
            <p>Conditional VaR: <strong>${(risk.cvar_95 || 0).toFixed(2)}%</strong> (average loss in worst 5% cases)</p>
            <p>Probability of >50% loss: <strong>${(risk.probability_of_ruin || 0).toFixed(2)}%</strong></p>
        </div>
    `;
}

// Export for manual initialization
export { runMonteCarloAnalysis };

