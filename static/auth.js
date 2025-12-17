import { deps } from './config.js';
import { showNotification } from './notifications.js';

// ==================== LOGGER (MOVED) ====================
const IS_LOCALHOST = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
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

const { STATE, DOM, CONFIG } = deps;

export async function handleGoogleLogin() {
    try {
        deps.log.debug('Initiating Google login...');
        const response = await fetch(`${CONFIG.API_BASE_URL}/auth/login`, { credentials: 'include' });
        const data = await response.json();
        if (response.ok && data.success && data.auth_url && data.state_token) {
            localStorage.setItem(CONFIG.OAUTH_STATE_KEY, data.state_token);
            window.location.href = data.auth_url;
        } else {
            showNotification('Could not initiate login. Please try again.', 'error');
            deps.log.error('Failed to get auth URL from backend.', data);
        }
    } catch (error) {
        deps.log.error('Login error:', error);
        showNotification('Login failed due to a network or server error.', 'error');
    }
}

export async function checkAuthStatus() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/auth/status`, { credentials: 'include' });
        const data = await response.json();
        STATE.isAuthenticated = data.authenticated;
        STATE.user = data.user || null;
        updateAuthUI();
    } catch (error) {
        deps.log.error('Auth check error:', error);
        STATE.isAuthenticated = false;
        STATE.user = null;
        updateAuthUI();
    } finally {
        return STATE.isAuthenticated;
    }
}

export async function handleLogout(showNotify = true) {
    try {
        await fetch(`${CONFIG.API_BASE_URL}/auth/logout`, { method: 'POST', credentials: 'include' });
    } catch (error) {
        deps.log.warn('Logout request to backend failed, but logging out on client-side anyway.', error);
    } finally {
        STATE.isAuthenticated = false;
        STATE.user = null;
        localStorage.removeItem(CONFIG.SESSION_STORAGE_KEY); // Clear the persisted session
        updateAuthUI();
        if (showNotify) showNotification('Logged out successfully', 'success');
    }
}

export function updateAuthUI() {
    const authOverlay = document.getElementById('auth-overlay');
    const userInfoBar = document.getElementById('user-info-bar');
    const googleBtn = document.getElementById('google-signin-btn');
    const mainContainer = document.querySelector('.container');

    if (STATE.isAuthenticated && STATE.user) {
        authOverlay?.classList.add('hidden');
        if (userInfoBar) {
            userInfoBar.classList.remove('hidden');
            document.getElementById('user-name').textContent = STATE.user.name;
            document.getElementById('user-avatar').src = STATE.user.picture ||
                `data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='%23e2e8f0'/><text x='50' y='55' font-size='40' fill='%2394a3b8' text-anchor='middle' dominant-baseline='middle'>👤</text></svg>`;
        }
    } else {
        authOverlay?.classList.remove('hidden');
        mainContainer?.classList.add('hidden'); // Hide main content when auth overlay is visible
        userInfoBar?.classList.add('hidden');
        // The button is only visible when not authenticated, so we ensure it's not in a loading state.
        googleBtn?.classList.remove('loading');
    }
    
    // Once the auth state is determined, always show the main container.
    mainContainer?.classList.remove('hidden');
}

export function showAuthOverlay() {
    document.getElementById('auth-overlay')?.classList.remove('hidden');
}

// ==================== SESSION MANAGEMENT (MERGED) ====================

export function saveSessionState() {
    try {
        const sessionToSave = {
            currentSessionId: STATE.currentSessionId,
            isSidebarCollapsed: STATE.isSidebarCollapsed,
        };
        localStorage.setItem(CONFIG.SESSION_STORAGE_KEY, JSON.stringify(sessionToSave));
    } catch (error) {
        deps.log.error('Could not save session state:', error);
    }
}

export function loadSessionState() {
    try {
        const savedSession = JSON.parse(localStorage.getItem(CONFIG.SESSION_STORAGE_KEY));
        if (savedSession) {
            STATE.currentSessionId = savedSession.currentSessionId || STATE.currentSessionId; // Keep session ID
            STATE.isSidebarCollapsed = savedSession.isSidebarCollapsed ?? false; // Keep sidebar state
            STATE.currentSymbol = null; // Always reset the symbol on page load
        }
    } catch (error) {
        deps.log.error('Could not load session state:', error);
    }
    saveSessionState();
}

export function showWelcomeMessage() {
    if (!STATE.currentSymbol && DOM.output) {
        DOM.output.innerHTML = `
            <div style="text-align: center; padding: 40px 20px; background: rgba(10, 37, 64, 0.8); border-radius: 12px; margin-top: 20px;">
                <img src="/fintralogo.png" alt="Fintra Logo" style="width: 120px; height: 120px; margin-bottom: 15px;">
                <h2 style="color: #ffffff; margin-bottom: 10px; font-family: 'Space Grotesk', sans-serif;">Welcome to Fintra</h2>
                <p style="color: #e5e7eb; opacity: 0.9;">Your personal AI-powered market analyst.</p>
                <p style="color: #cbd5e1; margin-top: 20px;">Search for a stock symbol or select from the sidebar to get started.</p>
            </div>
        `;
    }
}
