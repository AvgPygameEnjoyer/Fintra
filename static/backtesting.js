import { deps, getAuthHeaders, handleLogout } from './config.js';
import { showNotification } from './notifications.js';
import { handleAutocompleteInput, handleAutocompleteKeydown, hideAutocomplete } from './autocomplete.js';

const { DOM, CONFIG, STATE } = deps;

let currentMode = 'beginner';

export function initializeBacktesting() {
    const { DOM } = deps;
    
    DOM.backtestingTabBtn?.addEventListener('click', showBacktestingView);
    
    DOM.beginnerModeBtn?.addEventListener('click', () => setMode('beginner'));
    DOM.advancedModeBtn?.addEventListener('click', () => setMode('advanced'));
    
    DOM.backtestingForm?.addEventListener('submit', handleBacktestSubmit);
    DOM.clearBacktestingBtn?.addEventListener('click', () => {
        DOM.backtestingSymbol.value = '';
        handleBacktestingInput({ target: DOM.backtestingSymbol });
        hideAutocomplete(DOM.backtestingAutocomplete);
    });
    
    DOM.backtestingSymbol.addEventListener('input', handleBacktestingInput);
    DOM.backtestingSymbol.addEventListener('keydown', (e) => handleAutocompleteKeydown(e, DOM.backtestingAutocomplete));
    
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.input-wrapper')) {
            hideAutocomplete(DOM.backtestingAutocomplete);
        }
    });
    
    setDefaultDateRange();
}

function handleBacktestingInput(e) {
    const hasText = e.target.value.trim().length > 0;
    DOM.clearBacktestingBtn?.classList.toggle('visible', hasText);
    handleAutocompleteInput(e, DOM.backtestingAutocomplete);
}

function setMode(mode) {
    currentMode = mode;
    
    if (mode === 'beginner') {
        DOM.beginnerModeBtn?.classList.add('active');
        DOM.advancedModeBtn?.classList.remove('active');
        DOM.advancedParams?.style.display = 'none';
    } else {
        DOM.advancedModeBtn?.classList.add('active');
        DOM.beginnerModeBtn?.classList.remove('active');
        DOM.advancedParams?.style.display = 'block';
    }
}

function setDefaultDateRange() {
    const today = new Date();
    const oneYearAgo = new Date(today);
    oneYearAgo.setFullYear(today.getFullYear() - 1);
    
    const formatDate = (date) => date.toISOString().split('T')[0];
    
    if (DOM.startDate) DOM.startDate.value = formatDate(oneYearAgo);
    if (DOM.endDate) DOM.endDate.value = formatDate(today);
}

async function handleBacktestSubmit(e) {
    e.preventDefault();
    
    const symbol = DOM.backtestingSymbol.value.trim().toUpperCase();
    if (!symbol) {
        showNotification('Please enter a stock symbol', 'error');
        return;
    }
    
    const formData = new FormData(DOM.backtestingForm);
    const params = Object.fromEntries(formData.entries());
    
    const backtestData = {
        symbol: symbol,
        strategy: params.strategy,
        initial_balance: parseFloat(params.initial_balance),
        start_date: params.start_date,
        end_date: params.end_date,
        mode: currentMode,
        atr_multiplier: currentMode === 'advanced' ? parseFloat(params.atr_multiplier) : 3.0,
        risk_per_trade: currentMode === 'advanced' ? parseFloat(params.risk_per_trade) / 100 : 0.02
    };
    
    showLoading();
    hideError();
    hideResults();
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/backtest`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            credentials: 'include',
            body: JSON.stringify(backtestData)
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                showNotification('Session expired. Please sign in again.', 'error');
                handleLogout(false);
                return;
            }
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to run backtest');
        }
        
        const results = await response.json();
        displayBacktestResults(results, backtestData);
        showNotification('Backtest completed successfully!', 'success');
        
    } catch (error) {
        console.error('❌ Backtest error:', error);
        showError(error.message);
        showNotification('Backtest failed. Please try again.', 'error');
    } finally {
        hideLoading();
    }
}

function displayBacktestResults(results, params) {
    const container = DOM.backtestingResults;
    if (!container) return;
    
    container.style.display = 'block';
    
    const roiClass = results.strategy_return_pct >= 0 ? 'positive' : 'negative';
    const marketRoiClass = results.market_return_pct >= 0 ? 'positive' : 'negative';
    const roiSign = results.strategy_return_pct >= 0 ? '+' : '';
    const marketRoiSign = results.market_return_pct >= 0 ? '+' : '';
    
    const trades = results.trades || [];
    const winningTrades = trades.filter(t => t.result === 'Win').length;
    const losingTrades = trades.filter(t => t.result === 'Loss').length;
    const winRate = trades.length > 0 ? (winningTrades / trades.length * 100).toFixed(1) : 0;
    
    let aiSummary = '';
    if (results.ai_analysis) {
        aiSummary = `
            <div class="backtest-ai-summary">
                <h3>🤖 AI Strategy Analysis</h3>
                <div class="ai-content">${results.ai_analysis}</div>
            </div>
        `;
    }
    
    let tradesSection = '';
    if (trades.length > 0) {
        tradesSection = `
            <div class="trades-section">
                <h3>📋 Trade History</h3>
                <div class="trades-summary">
                    <div class="trade-stat">
                        <span>Total Trades</span>
                        <strong>${trades.length}</strong>
                    </div>
                    <div class="trade-stat">
                        <span>Winning</span>
                        <strong class="positive">${winningTrades}</strong>
                    </div>
                    <div class="trade-stat">
                        <span>Losing</span>
                        <strong class="negative">${losingTrades}</strong>
                    </div>
                    <div class="trade-stat">
                        <span>Win Rate</span>
                        <strong>${winRate}%</strong>
                    </div>
                </div>
                <div class="trades-table-wrapper">
                    <table class="trades-table">
                        <thead>
                            <tr>
                                <th>Entry Date</th>
                                <th>Exit Date</th>
                                <th>Entry Price</th>
                                <th>Exit Price</th>
                                <th>P&L %</th>
                                <th>Result</th>
                                <th>Reason</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${trades.map(trade => `
                                <tr class="${trade.result === 'Win' ? 'win-row' : 'loss-row'}">
                                    <td>${trade.entry_date}</td>
                                    <td>${trade.exit_date}</td>
                                    <td>₹${trade.entry_price.toFixed(2)}</td>
                                    <td>₹${trade.exit_price.toFixed(2)}</td>
                                    <td class="${trade.pnl_pct >= 0 ? 'positive' : 'negative'}">
                                        ${trade.pnl_pct >= 0 ? '+' : ''}${trade.pnl_pct.toFixed(2)}%
                                    </td>
                                    <td class="${trade.result === 'Win' ? 'positive' : 'negative'}">${trade.result}</td>
                                    <td>${trade.reason}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }
    
    container.innerHTML = `
        <div class="backtest-results-container">
            <div class="backtest-summary">
                <h2>📊 Backtest Results for ${params.symbol}</h2>
                <p class="backtest-period">
                    ${params.start_date} to ${params.end_date} | 
                    Strategy: ${params.strategy.replace('_', ' ').toUpperCase()}
                </p>
                
                <div class="metrics-grid">
                    <div class="metric-card primary">
                        <div class="metric-label">Strategy Final Value</div>
                        <div class="metric-value">₹${results.final_portfolio_value.toLocaleString('en-IN', {maximumFractionDigits: 2})}</div>
                        <div class="metric-change ${roiClass}">
                            ${roiSign}${results.strategy_return_pct.toFixed(2)}% ROI
                        </div>
                    </div>
                    
                    <div class="metric-card secondary">
                        <div class="metric-label">Buy & Hold Value</div>
                        <div class="metric-value">₹${results.market_buy_hold_value.toLocaleString('en-IN', {maximumFractionDigits: 2})}</div>
                        <div class="metric-change ${marketRoiClass}">
                            ${marketRoiSign}${results.market_return_pct.toFixed(2)}% ROI
                        </div>
                    </div>
                    
                    <div class="metric-card">
                        <div class="metric-label">Sharpe Ratio</div>
                        <div class="metric-value">${results.sharpe_ratio.toFixed(2)}</div>
                        <div class="metric-sub">Risk-adjusted return</div>
                    </div>
                    
                    <div class="metric-card">
                        <div class="metric-label">Max Drawdown</div>
                        <div class="metric-value negative">${results.max_drawdown_pct.toFixed(2)}%</div>
                        <div class="metric-sub">Worst drop from peak</div>
                    </div>
                </div>
            </div>
            
            ${aiSummary}
            ${tradesSection}
        </div>
    `;
}

function showLoading() {
    if (DOM.backtestingLoading) {
        DOM.backtestingLoading.style.display = 'flex';
    }
}

function hideLoading() {
    if (DOM.backtestingLoading) {
        DOM.backtestingLoading.style.display = 'none';
    }
}

function showError(message) {
    if (DOM.backtestingError) {
        DOM.backtestingError.innerHTML = `<strong>Error:</strong> ${message}`;
        DOM.backtestingError.style.display = 'block';
    }
}

function hideError() {
    if (DOM.backtestingError) {
        DOM.backtestingError.style.display = 'none';
    }
}

function hideResults() {
    if (DOM.backtestingResults) {
        DOM.backtestingResults.style.display = 'none';
    }
}

function showBacktestingView() {
    DOM.searchView.style.display = 'none';
    DOM.portfolioView.style.display = 'none';
    DOM.backtestingView.style.display = 'block';
    
    DOM.searchTabBtn?.classList.remove('active');
    DOM.portfolioTabBtn?.classList.remove('active');
    DOM.backtestingTabBtn?.classList.add('active');
}