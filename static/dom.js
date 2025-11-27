// ==================== DOM MANAGEMENT ====================
import { DOM } from './config.js';

export function initialize() {
    const ids = [
        'symbol', 'autocomplete', 'output', 'loading', 'error', 'searchBtn', 
        'sidebar', 'sidebarStocks', 'sidebarSearch', 'chat-toggle', 'chat-window', 
        'chat-messages', 'chat-input', 'chat-send', 'chat-close', 'chat-refresh',
        'mobile-sidebar-toggle', 'desktop-sidebar-toggle',
        'context-symbol'
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