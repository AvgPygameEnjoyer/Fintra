import { STATE, DOM, CONFIG, debounce } from './config.js';
import { handleGoogleLogin, handleOAuthCallback, checkAuthStatus, handleLogout } from './auth.js';
import { initialize as initializeDOM } from './dom.js';
import { initialize as initializeEvents } from './events.js';
import { initialize as initializeSidebar } from './sidebar.js';
import { initialize as initializeChat, updateChatContextIndicator } from './chat.js';
import { fetchData, loadStockDatabase } from './data.js';
import { showWelcomeMessage } from './display.js';
import { loadSessionState, saveSessionState } from './session.js';
import { hideAutocomplete } from './autocomplete.js';

async function init() {
    initializeDOM();
    await handleOAuthCallback();
    await loadStockDatabase();
    initializeEvents();
    initializeSidebar({
        STATE,
        DOM,
        CONFIG,
        debounce,
        saveSessionState,
        hideAutocomplete,
        fetchData,
        updateChatContextIndicator
    });
    initializeChat();
    loadSessionState();
    await checkAuthStatus();
    showWelcomeMessage();
}

// Make login function global for onclick attribute
window.handleGoogleLogin = handleGoogleLogin;
window.handleLogout = handleLogout;

document.addEventListener('DOMContentLoaded', init);
