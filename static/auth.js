import { STATE, CONFIG, DOM } from './config.js';
import { showNotification } from './notifications.js';
import * as deps from './main.js'; // Assuming main.js exports log

// ==================== AUTHENTICATION FLOW ====================

/**
 * Initiates the Google login flow by fetching the auth URL from the backend.
 */
export async function handleGoogleLogin() {
    try {
        deps.log.debug('Initiating Google login...');
        const response = await fetch(`${CONFIG.API_BASE_URL}/auth/login`, { credentials: 'include' });
        const data = await response.json();
        if (response.ok && data.success && data.auth_url && data.state_token) {
            // Store the state token to verify after the redirect
            localStorage.setItem(CONFIG.OAUTH_STATE_KEY, data.state_token);
            // Redirect the user to Google's authentication page
            window.location.href = data.auth_url;
        } else {
            deps.log.error('Failed to get auth URL from backend.', data);
            showNotification('Login initiation failed. Please try again.', 'error');
        }
    } catch (error) {
        deps.log.error('Login error:', error);
        showNotification('An error occurred during login. Please check the console.', 'error');
    }
}

/**
 * Checks the user's authentication status with the backend.
 * This is called on application startup.
 */
export async function checkAuthStatus() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/auth/status`, { credentials: 'include' });
        const data = await response.json();
        STATE.isAuthenticated = data.authenticated;
        STATE.user = data.user || null;
    } catch (error) {
        deps.log.error('Auth check error:', error);
    } finally {
        // Once the auth check is complete, remove the loading state from the sign-in button
        const signInButton = document.getElementById('google-signin-btn');
        signInButton?.classList.remove('loading');
    }
}

/**
 * Handles the user logout process.
 * @param {boolean} showNotify - Whether to show a notification on successful logout.
 */
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

// ==================== UI UPDATES ====================

/**
 * Updates the UI based on the user's authentication state.
 * Shows/hides the login overlay and user info bar.
 */
export function updateAuthUI() {
    if (STATE.isAuthenticated && STATE.user) {
        // User is authenticated
        document.getElementById('auth-overlay')?.classList.add('hidden');
        
        const userInfoBar = document.getElementById('user-info-bar');
        if (userInfoBar) {
            userInfoBar.classList.remove('hidden');
            document.getElementById('user-name').textContent = STATE.user.name;
            document.getElementById('user-avatar').src = STATE.user.picture || 
                `data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='%23e2e8f0'/><text x='50' y='55' font-size='40' fill='%2394a3b8' text-anchor='middle' dominant-baseline='middle'>👤</text></svg>`;
        }
        
        // Start session timer
        startSessionTimer();

    } else {
        // User is not authenticated
        document.getElementById('auth-overlay')?.classList.remove('hidden');
        document.getElementById('user-info-bar')?.classList.add('hidden');
        
        // Show welcome message if no stock is selected
        showWelcomeMessage();
    }
}

// ==================== SESSION MANAGEMENT ====================

let sessionTimerInterval;

/**
 * Starts a countdown timer to warn the user about session expiration.
 */
function startSessionTimer() {
    if (sessionTimerInterval) clearInterval(sessionTimerInterval);

    const sessionDuration = 15 * 60; // 15 minutes in seconds
    let remainingTime = sessionDuration;

    const timerElement = document.getElementById('session-timer');
    const warningElement = document.getElementById('session-warning');

    sessionTimerInterval = setInterval(() => {
        remainingTime--;
        const minutes = Math.floor(remainingTime / 60);
        const seconds = remainingTime % 60;
        
        if (timerElement) {
            timerElement.textContent = `Session: ${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }

        if (remainingTime <= 60 && remainingTime > 0) {
            // Show warning in the last minute
            if (warningElement) {
                warningElement.classList.remove('hidden');
                warningElement.textContent = `Your session will expire in ${remainingTime} seconds.`;
            }
        } else {
            if (warningElement) warningElement.classList.add('hidden');
        }

        if (remainingTime <= 0) {
            clearInterval(sessionTimerInterval);
            handleLogout(false); // Logout without notification
            showNotification('Your session has expired. Please sign in again.', 'warning');
        }
    }, 1000);
}

/**
 * Displays a welcome message in the main output area if no stock is selected.
 */
function showWelcomeMessage() {
    if (!STATE.currentSymbol && DOM.output) {
        DOM.output.innerHTML = `
            <div style="text-align: center; padding: 60px 20px; color: #6b7280;">
                <img src="/fintralogo.png" alt="Fintra Logo" style="width: 150px; height: 150px; margin-bottom: 20px;">
                <h2 style="color: #374151; margin-bottom: 10px;">Welcome to Fintra, your personal finance assistant.</h2>
                <p>Search for a stock symbol or select from the sidebar to get started</p>
            </div>
        `;
    }
}