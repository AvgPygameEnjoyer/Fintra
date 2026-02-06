/**
 * Data Transparency Module
 * Prominent UI elements showing data lag and historical nature
 */

import { CONFIG } from './config.js';

/**
 * Create and inject a prominent data lag banner
 */
export function createDataLagBanner(effectiveDate) {
    // Remove existing banner if any
    const existingBanner = document.getElementById('data-lag-banner');
    if (existingBanner) {
        existingBanner.remove();
    }

    const banner = document.createElement('div');
    banner.id = 'data-lag-banner';
    banner.className = 'data-lag-banner';
    banner.innerHTML = `
        <div class="banner-content">
            <span class="banner-icon">⏰</span>
            <div class="banner-text">
                <strong>Historical Data Only</strong>
                <span>Displaying data through <span class="date-highlight">${effectiveDate || 'N/A'}</span> (30+ day SEBI compliance lag)</span>
            </div>
            <button class="banner-close" onclick="this.parentElement.parentElement.style.display='none'" title="Dismiss">×</button>
        </div>
    `;

    // Insert at top of main container
    const mainContainer = document.querySelector('.main-container');
    if (mainContainer) {
        mainContainer.insertBefore(banner, mainContainer.firstChild);
    }
}

/**
 * Update analysis header with data date
 */
export function updateAnalysisHeader(symbol, effectiveDate) {
    const analysisSection = document.getElementById('analysis-section');
    if (!analysisSection) return;

    // Check if header already exists
    let dateHeader = analysisSection.querySelector('.analysis-date-header');
    if (!dateHeader) {
        dateHeader = document.createElement('div');
        dateHeader.className = 'analysis-date-header';
        analysisSection.insertBefore(dateHeader, analysisSection.firstChild);
    }

    dateHeader.innerHTML = `
        <div class="historical-data-badge">
            <span class="badge-icon">📊</span>
            <div class="badge-content">
                <span class="badge-label">Historical Analysis</span>
                <span class="badge-date">Data as of: <strong>${effectiveDate || 'N/A'}</strong></span>
                <span class="badge-lag">31-day SEBI compliance lag enforced</span>
            </div>
        </div>
    `;
}

/**
 * Add historical context to chart
 */
export function addChartHistoricalContext(chartContainerId, effectiveDate) {
    const container = document.getElementById(chartContainerId);
    if (!container) return;

    // Add overlay badge
    let overlay = container.querySelector('.chart-historical-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'chart-historical-overlay';
        container.style.position = 'relative';
        container.appendChild(overlay);
    }

    overlay.innerHTML = `
        <div class="historical-watermark">
            <span class="watermark-text">HISTORICAL DATA</span>
            <span class="watermark-date">As of ${effectiveDate || 'N/A'}</span>
            <span class="watermark-lag">30+ day lag</span>
        </div>
    `;
}

/**
 * Show data freshness indicator
 */
export function showDataFreshnessIndicator(containerId, effectiveDate, dataFreshness) {
    const container = document.getElementById(containerId);
    if (!container) return;

    let indicator = container.querySelector('.data-freshness-indicator');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.className = 'data-freshness-indicator';
        container.insertBefore(indicator, container.firstChild);
    }

    const freshnessClass = dataFreshness > 35 ? 'stale' : 'fresh';
    const freshnessIcon = dataFreshness > 35 ? '⚠️' : '✓';

    indicator.innerHTML = `
        <div class="freshness-badge ${freshnessClass}">
            <span class="freshness-icon">${freshnessIcon}</span>
            <div class="freshness-content">
                <span class="freshness-label">Data Status</span>
                <span class="freshness-text">Effective Date: <strong>${effectiveDate || 'N/A'}</strong></span>
                <span class="freshness-subtext">${dataFreshness} days old • SEBI Compliant</span>
            </div>
        </div>
    `;
}

/**
 * Add transparency notice to AI analysis
 */
export function addAIAnalysisTransparency(analysisContainerId, effectiveDate) {
    const container = document.getElementById(analysisContainerId);
    if (!container) return;

    let notice = container.querySelector('.ai-transparency-notice');
    if (!notice) {
        notice = document.createElement('div');
        notice.className = 'ai-transparency-notice';
        container.insertBefore(notice, container.firstChild);
    }

    notice.innerHTML = `
        <div class="transparency-banner">
            <div class="transparency-icon">🔍</div>
            <div class="transparency-content">
                <h4>AI Analysis Transparency</h4>
                <p>This analysis is based on <strong>historical data only</strong> (as of ${effectiveDate || 'N/A'}) and includes a mandatory 31-day lag per SEBI regulations.</p>
                <ul class="transparency-points">
                    <li>📅 <strong>Data Date:</strong> ${effectiveDate || 'N/A'} (not current)</li>
                    <li>⏱️ <strong>Time Lag:</strong> Minimum 31 days behind real-time</li>
                    <li>📊 <strong>Analysis Type:</strong> Historical retrospective only</li>
                    <li>🚫 <strong>Not Current:</strong> This is NOT a current market assessment</li>
                </ul>
                <p class="transparency-disclaimer">The AI interprets historical patterns and trends. It does not provide current market analysis or investment advice.</p>
            </div>
        </div>
    `;
}

/**
 * Update data info in analysis results
 */
export function updateAnalysisDataInfo(response) {
    if (!response || !response.sebi_compliance) return;

    const compliance = response.sebi_compliance;
    
    // Create banner
    createDataLagBanner(compliance.effective_last_date);
    
    // Update analysis header
    updateAnalysisHeader(response.ticker, compliance.effective_last_date);
    
    // Add chart overlay
    const chartContainer = document.querySelector('.chart-container') || document.getElementById('chart-container');
    if (chartContainer) {
        addChartHistoricalContext(chartContainer.id || 'chart-container', compliance.effective_last_date);
    }
    
    // Add AI transparency notice
    const aiContainer = document.getElementById('ai-review') || document.querySelector('.ai-review');
    if (aiContainer) {
        addAIAnalysisTransparency(aiContainer.id || 'ai-review', compliance.effective_last_date);
    }
}

/**
 * Initialize all transparency elements
 */
export function initializeDataTransparency() {
    // Add global CSS for transparency elements
    addTransparencyStyles();
}

/**
 * Add CSS styles for transparency elements
 */
function addTransparencyStyles() {
    if (document.getElementById('transparency-styles')) return;

    const style = document.createElement('style');
    style.id = 'transparency-styles';
    style.textContent = `
        /* Data Lag Banner */
        .data-lag-banner {
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
            color: white;
            padding: 16px 24px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .banner-content {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .banner-icon {
            font-size: 24px;
        }

        .banner-text {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .banner-text strong {
            font-size: 1.1em;
        }

        .date-highlight {
            background: rgba(255, 255, 255, 0.2);
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 600;
        }

        .banner-close {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 18px;
            line-height: 1;
            transition: background 0.2s;
        }

        .banner-close:hover {
            background: rgba(255, 255, 255, 0.3);
        }

        /* Analysis Date Header */
        .analysis-date-header {
            background: #fef3c7;
            border: 2px solid #f59e0b;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 20px;
        }

        .historical-data-badge {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .badge-icon {
            font-size: 32px;
        }

        .badge-content {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .badge-label {
            font-weight: 700;
            color: #92400e;
            font-size: 1.1em;
        }

        .badge-date {
            color: #78350f;
        }

        .badge-lag {
            font-size: 0.85em;
            color: #b45309;
            font-style: italic;
        }

        /* Chart Historical Overlay */
        .chart-historical-overlay {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(30, 58, 138, 0.9);
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 0.85em;
            pointer-events: none;
            z-index: 10;
        }

        .historical-watermark {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
        }

        .watermark-text {
            font-weight: 700;
            font-size: 0.9em;
        }

        .watermark-date {
            font-size: 0.8em;
            opacity: 0.9;
        }

        .watermark-lag {
            font-size: 0.75em;
            opacity: 0.8;
        }

        /* Data Freshness Indicator */
        .data-freshness-indicator {
            margin-bottom: 16px;
        }

        .freshness-badge {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            border-radius: 8px;
            border: 2px solid;
        }

        .freshness-badge.fresh {
            background: #ecfdf5;
            border-color: #10b981;
            color: #065f46;
        }

        .freshness-badge.stale {
            background: #fef3c7;
            border-color: #f59e0b;
            color: #92400e;
        }

        .freshness-icon {
            font-size: 24px;
        }

        .freshness-content {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .freshness-label {
            font-weight: 600;
            font-size: 0.9em;
        }

        .freshness-subtext {
            font-size: 0.8em;
            opacity: 0.8;
        }

        /* AI Transparency Notice */
        .ai-transparency-notice {
            background: #eff6ff;
            border: 2px solid #3b82f6;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .transparency-banner {
            display: flex;
            gap: 16px;
        }

        .transparency-icon {
            font-size: 32px;
            flex-shrink: 0;
        }

        .transparency-content h4 {
            color: #1e40af;
            margin: 0 0 8px 0;
            font-size: 1.2em;
        }

        .transparency-content p {
            color: #1e40af;
            margin: 0 0 12px 0;
            line-height: 1.5;
        }

        .transparency-points {
            list-style: none;
            padding: 0;
            margin: 0 0 12px 0;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 8px;
        }

        .transparency-points li {
            color: #1e40af;
            font-size: 0.9em;
        }

        .transparency-disclaimer {
            font-style: italic;
            font-size: 0.9em;
            padding-top: 12px;
            border-top: 1px solid #bfdbfe;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .banner-content {
                flex-wrap: wrap;
            }

            .transparency-banner {
                flex-direction: column;
            }

            .transparency-points {
                grid-template-columns: 1fr;
            }
        }
    `;

    document.head.appendChild(style);
}

export default {
    createDataLagBanner,
    updateAnalysisHeader,
    addChartHistoricalContext,
    showDataFreshnessIndicator,
    addAIAnalysisTransparency,
    updateAnalysisDataInfo,
    initializeDataTransparency
};
