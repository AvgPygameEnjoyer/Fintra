import { API_BASE_URL, OAUTH_STATE_KEY } from './config.js';
import { handleGoogleLogin, handleOAuthCallback, checkAuthStatus, handleLogout } from './auth.js';
import { initialize as initializeDOM } from './dom.js';
import { initialize as initializeEvents } from './events.js';
import { initialize as initializeSidebar } from './sidebar.js';
import { initialize as initializeChat } from './chat.js';
import { loadStockDatabase } from './data.js';
import { showWelcomeMessage } from './display.js';
import { loadSessionState } from './session.js';

async function init() {
    initializeDOM();
    await handleOAuthCallback();
    await loadStockDatabase();
    initializeEvents();
    initializeSidebar();
    initializeChat();
    loadSessionState();
    await checkAuthStatus();
    showWelcomeMessage();
}

// Make login function global for onclick attribute
window.handleGoogleLogin = handleGoogleLogin;
window.handleLogout = handleLogout;

document.addEventListener('DOMContentLoaded', init);
