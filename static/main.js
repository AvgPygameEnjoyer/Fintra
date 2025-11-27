import { deps } from './config.js';
import { handleGoogleLogin, handleOAuthCallback, checkAuthStatus, handleLogout, updateAuthUI, loadSessionState, saveSessionState, showWelcomeMessage } from './auth.js';
import { initialize as initializeDOM } from './dom.js';
import { initialize as initializeEvents } from './events.js';
import { setupSidebar } from './sidebar.js';
import { initializeChat, updateChatContextIndicator } from './chat.js';
import { fetchData, loadStockDatabase } from './data.js';
import { hideAutocomplete } from './autocomplete.js';

async function init() {
    await handleOAuthCallback();
    await loadStockDatabase();

    // Step 1: Cache ALL DOM elements from the HTML
    initializeDOM();
    deps.updateAuthUI = updateAuthUI; // Add auth UI updater to deps

    // Step 2: Initialize all modules that depend on the DOM
    initializeEvents();
    setupSidebar();
    initializeChat();

    loadSessionState();
    await checkAuthStatus();
    showWelcomeMessage();
}

// Make login function global for onclick attribute
window.handleGoogleLogin = handleGoogleLogin;
window.handleLogout = handleLogout;

document.addEventListener('DOMContentLoaded', init);
