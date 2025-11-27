// ==================== OAUTH AUTHENTICATION ====================
import { deps } from './config.js';
import { showNotification } from './notifications.js';

const { STATE, DOM, CONFIG } = deps;

export async function handleGoogleLogin() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/auth/login`, { credentials: 'include' });
        const data = await response.json();
        if (data.auth_url && data.state) {
            localStorage.setItem(CONFIG.OAUTH_STATE_KEY, data.state);
            window.location.href = data.auth_url;
        } else {
            showNotification('Could not initiate login. Please try again.', 'error');
        }
    } catch (error) {
        console.error('Login error:', error);
        showNotification('Login failed. Please try again.', 'error');
    }
}

export async function handleOAuthCallback() {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');
    const storedState = localStorage.getItem(CONFIG.OAUTH_STATE_KEY);

    if (!code || !state) {
        return;
    }

    window.history.replaceState({}, document.title, "/");
    localStorage.removeItem(CONFIG.OAUTH_STATE_KEY);

    if (state !== storedState) {
        showNotification('Authentication failed: State mismatch. Please try again.', 'error');
        return;
    }

    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/oauth2callback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, state, stored_state: storedState }),
            credentials: 'include'
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showNotification('Login successful!', 'success');
            await checkAuthStatus();
        } else {
            throw new Error(data.error || 'Callback failed');
        }
    } catch (error) {
        console.error('OAuth callback error:', error);
        showNotification(`Authentication failed: ${error.message}`, 'error');
    }
}

export async function checkAuthStatus() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/auth/status`, { credentials: 'include' });
        const data = await response.json();
        STATE.isAuthenticated = data.authenticated;
        STATE.user = data.user || null;
        updateAuthUI();
        return data.authenticated;
    } catch (error) {
        console.error('Auth check error:', error);
        STATE.isAuthenticated = false;
        STATE.user = null;
        updateAuthUI();
        return false;
    }
}

export async function handleLogout(showNotify = true) {
    try {
        await fetch(`${CONFIG.API_BASE_URL}/auth/logout`, { method: 'POST', credentials: 'include' });
    } catch (error) {
        console.error('Logout request failed:', error);
    } finally {
        STATE.isAuthenticated = false;
        STATE.user = null;
        updateAuthUI();
        if (showNotify) showNotification('Logged out successfully', 'success');
    }
}

export function updateAuthUI() {
    if (STATE.isAuthenticated && STATE.user) {
        document.getElementById('auth-overlay')?.classList.add('hidden');
        const userInfoBar = document.getElementById('user-info-bar');
        if (userInfoBar) {
            userInfoBar.classList.remove('hidden');
            document.getElementById('user-name').textContent = STATE.user.name;
            document.getElementById('user-avatar').src = STATE.user.picture || 
                `data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='%23e2e8f0'/><text x='50' y='55' font-size='40' fill='%2394a3b8' text-anchor='middle' dominant-baseline='middle'>👤</text></svg>`;
        }
    } else {
        document.getElementById('auth-overlay')?.classList.remove('hidden');
        document.getElementById('user-info-bar')?.classList.add('hidden');
    }
}

export function showAuthOverlay() {
    document.getElementById('auth-overlay')?.classList.remove('hidden');
}

// ==================== SESSION MANAGEMENT (MERGED) ====================

export function saveSessionState() {
    try {
        const sessionToSave = {
            currentSessionId: STATE.currentSessionId,
            currentSymbol: STATE.currentSymbol,
            isSidebarCollapsed: STATE.isSidebarCollapsed,
        };
        localStorage.setItem(CONFIG.SESSION_STORAGE_KEY, JSON.stringify(sessionToSave));
    } catch (error) {
        console.error('Could not save session state:', error);
    }
}

export function loadSessionState() {
    try {
        const savedSession = JSON.parse(localStorage.getItem(CONFIG.SESSION_STORAGE_KEY));
        if (savedSession) {
            STATE.currentSessionId = savedSession.currentSessionId || STATE.currentSessionId;
            STATE.currentSymbol = savedSession.currentSymbol || null;
            STATE.isSidebarCollapsed = savedSession.isSidebarCollapsed || false;
            if (STATE.currentSymbol && DOM.symbol) DOM.symbol.value = STATE.currentSymbol;
        }
    } catch (error) {
        console.error('Could not load session state:', error);
    }
    saveSessionState();
}

export function showWelcomeMessage() {
    if (!STATE.currentSymbol && DOM.output) {
        DOM.output.innerHTML = `
            <div style="text-align: center; padding: 60px 20px; color: #6b7280;">
                <div style="font-size: 4rem; margin-bottom: 20px;">📊</div>
                <h2 style="color: #374151; margin-bottom: 10px;">Welcome to Stock Analysis</h2>
                <p>Search for a stock symbol or select from the sidebar to get started</p>
            </div>
        `;
    }
}