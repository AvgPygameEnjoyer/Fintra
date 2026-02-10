// ==================== DOM MANAGEMENT ====================
import { DOM } from './config.js';

export function initialize() {
    const ids = [
        'symbol', 'autocomplete', 'output', 'loading', 'error', 'searchBtn', 
        'sidebar', 'sidebarStocks', 'sidebarSearch', 'clearSearchBtn', 'chat-toggle', 'chat-window', 
        'chat-messages', 'chat-input', 'chat-send', 'chat-close', 'chat-refresh', 'sidebarToggle',
        'context-symbol', 'logout-btn', 'search-view', 'portfolio-view', 'backtesting-view', 'add-position-symbol-input',
        'modal-autocomplete', 'add-position-entry-price', 'current-price-indicator',
        'search-tab-btn', 'portfolio-tab-btn', 'backtesting-tab-btn', 'add-position-btn', 'portfolio-content',
        'backtesting-symbol', 'backtesting-autocomplete', 'clear-backtesting-btn', 'backtesting-form',
        'beginner-mode-btn', 'advanced-mode-btn', 'strategy-select', 'atr-multiplier', 'risk-per-trade',
        'start-date', 'end-date', 'initial-balance', 'run-backtest-btn', 'backtesting-loading',
        'backtesting-error', 'backtesting-results',
        'add-position-modal', 'add-position-form', 'close-modal-btn',
        // Add the missing sidebar toggle buttons
        'mobile-sidebar-toggle', 'desktop-sidebar-toggle'
    ];
    ids.forEach(id => {
        const camelCaseId = id.replace(/-(\w)/g, (_, c) => c.toUpperCase());
        DOM[camelCaseId] = document.getElementById(id);
    });
    if (DOM.error) DOM.error.style.display = 'none';
    if (DOM.loading) DOM.loading.style.display = 'none';
}

export function showLoading() {
    DOM.loading.style.display = 'flex';
    updateLoadingProgress(0, 'Initializing...');
}

export function hideLoading() {
    DOM.loading.style.display = 'none';
    updateLoadingProgress(0, '');
}

export function updateLoadingProgress(percent, phase) {
    const progressBar = document.getElementById('loading-progress-bar');
    const phaseText = document.getElementById('loading-phase');
    
    if (progressBar) {
        progressBar.style.width = percent + '%';
    }
    if (phaseText && phase) {
        phaseText.textContent = phase;
    }
}

export function hideError() {
    DOM.error.style.display = 'none';
}

export function showError(message) {
    DOM.error.innerHTML = `<strong>Error:</strong> ${message}`;
    DOM.error.style.display = 'block';
}