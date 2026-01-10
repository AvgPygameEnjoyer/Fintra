// ==================== DOM MANAGEMENT ====================
import { DOM } from './config.js';

export function initialize() {
    const ids = [
        'symbol', 'autocomplete', 'output', 'loading', 'error', 'searchBtn', 
        'sidebar', 'sidebarStocks', 'sidebarSearch', 'clearSearchBtn', 'chat-toggle', 'chat-window', 
        'chat-messages', 'chat-input', 'chat-send', 'chat-close', 'chat-refresh', 'sidebarToggle',
        'context-symbol', 'logout-btn', 'search-view', 'portfolio-view', 'add-position-symbol-input',
        'modal-autocomplete', 'add-position-entry-price', 'current-price-indicator',
        'search-tab-btn', 'portfolio-tab-btn', 'add-position-btn', 'portfolio-content',
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
    DOM.loading.style.display = 'block';
}

export function hideLoading() {
    DOM.loading.style.display = 'none';
}

export function hideError() {
    DOM.error.style.display = 'none';
}

export function showError(message) {
    DOM.error.innerHTML = `<strong>Error:</strong> ${message}`;
    DOM.error.style.display = 'block';
}