// ==================== CONFIGURATION & CONSTANTS ====================
const IS_LOCALHOST = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE_URL = IS_LOCALHOST ? 'http://localhost:5000' : 'https://stock-dashboard-fqtn.onrender.com';

// ==================== LOGGER ====================
const LOG_LEVELS = {
    DEBUG: 0,
    INFO: 1,
    WARN: 2,
    ERROR: 3,
};

const CURRENT_LOG_LEVEL = IS_LOCALHOST ? LOG_LEVELS.DEBUG : LOG_LEVELS.INFO;

export const log = {
    debug: (...args) => {
        if (CURRENT_LOG_LEVEL <= LOG_LEVELS.DEBUG) console.log('%c🐛 DEBUG', 'color: #9ca3af;', ...args);
    },
    info: (...args) => {
        if (CURRENT_LOG_LEVEL <= LOG_LEVELS.INFO) console.log('%cℹ️ INFO', 'color: #3b82f6; font-weight: bold;', ...args);
    },
    warn: (...args) => {
        if (CURRENT_LOG_LEVEL <= LOG_LEVELS.WARN) console.warn('%c⚠️ WARN', 'color: #f97316; font-weight: bold;', ...args);
    },
    error: (...args) => {
        if (CURRENT_LOG_LEVEL <= LOG_LEVELS.ERROR) console.error('%c❌ ERROR', 'color: #ef4444; font-weight: bold;', ...args);
    }
};

export const CONFIG = {
    API_BASE_URL: API_BASE_URL,
    DEBOUNCE_DELAY: 300,
    MAX_AUTOCOMPLETE_ITEMS: 8,
    MAX_CHART_POINTS: 30,
    SESSION_STORAGE_KEY: 'userSession',
    OAUTH_STATE_KEY: 'oauthState'
};

log.info(`App initialized. Backend set to: ${CONFIG.API_BASE_URL}`);

export const STATE = {
    stockDatabase: [],
    selectedIndex: -1,
    filteredStocks: [],
    isSidebarCollapsed: false,
    charts: { ohlcv: null, rsi: null, movingAverages: null, macd: null },
    currentSessionId: generateSessionId(),
    currentSymbol: null,
    isLoading: false,
    isAuthenticated: false,
    user: null,
    chatHistory: [] // Add chat history to the global state
};

export const DOM = {};

export let sessionTimerInterval = null;

// ==================== DEPENDENCY CONTAINER ====================
// This object will hold all shared state and functions, acting as a
// centralized service locator to simplify dependency management.
export const deps = {
    STATE,
    DOM,
    CONFIG,
    log
};

// ==================== UTILITY FUNCTIONS ====================
export function generateSessionId() {
    return `session_${Math.random().toString(36).substr(2, 9)}_${Date.now()}`;
}

/**
 * Checks if required DOM elements exist in the DOM container.
 * Throws a detailed error if a dependency is missing.
 * @param {string} moduleName - The name of the module checking its dependencies.
 * @param {string[]} requiredDomElements - An array of keys to check for in the DOM object.
 */
export function checkDependencies(moduleName, requiredDomElements) {
    for (const key of requiredDomElements) {
        if (!DOM[key]) {
            throw new Error(`[${moduleName}] Missing DOM dependency: 'DOM.${key}'. Check if the element with id="${key}" exists in the HTML or is created before this module is initialized.`);
        }
    }
}

export function debounce(func, wait) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}

export function formatPrice(price) { 
    return price != null ? `$${price.toFixed(2)}` : 'N/A'; 
}

export function formatNumber(num) { 
    return num != null ? num.toLocaleString() : 'N/A'; 
}

export function getRsiColor(rsi) {
    if (rsi == null) return '#6b7280';
    if (rsi > 70) return '#ef4444';
    if (rsi < 30) return '#10b981';
    return '#6b7280';
}

export function getRsiBackground(rsi) {
    if (rsi == null) return '#f3f4f6';
    if (rsi > 70) return '#fef2f2';
    if (rsi < 30) return '#f0fdf4';
    return '#f8fafc';
}