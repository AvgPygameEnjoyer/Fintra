import { deps } from './config.js';
import { handleGoogleLogin, handleOAuthCallback, checkAuthStatus, handleLogout, updateAuthUI } from './auth.js';
import { initialize as initializeDOM } from './dom.js';
import { initialize as initializeEvents } from './events.js';
import { initialize as initializeSidebar, setupSidebar } from './sidebar.js';
import { initializeChat, updateChatContextIndicator } from './chat.js';
import { fetchData, loadStockDatabase } from './data.js';
import { loadSessionState, saveSessionState, showWelcomeMessage } from './session.js';
import { hideAutocomplete } from './autocomplete.js';

async function init() {
    await handleOAuthCallback();
    await loadStockDatabase();

    // Step 1: Create dynamic sidebar elements
    initializeSidebar();

    // Step 2: Cache ALL DOM elements, including the new ones
    initializeDOM();
    deps.updateAuthUI = updateAuthUI; // Add auth UI updater to deps

    // Step 3: Initialize all other modules that depend on the DOM
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
