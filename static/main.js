import { deps } from './config.js';
import { handleGoogleLogin, checkAuthStatus, handleLogout, updateAuthUI, loadSessionState, saveSessionState, showWelcomeMessage, log } from './auth.js';
import { initialize as initializeDOM } from './dom.js';
import { initialize as initializeEvents } from './events.js';
import { setupSidebar } from './sidebar.js';
import { initializeChat, updateChatContextIndicator } from './chat.js';
import { fetchData, loadStockDatabase } from './data.js';
import { hideAutocomplete, selectStock } from './autocomplete.js';

async function init() {
    log.info('Initializing application...');

    // Step 1: Populate the dependency container.
    deps.log = log;
    deps.updateAuthUI = updateAuthUI;

    // Step 2: Load critical data.
    log.debug('Step 2: Loading stock database...');
    await loadStockDatabase();

    // Step 3: Initialize UI now that the DOM is ready.
    log.debug('Step 3: Caching DOM elements...');
    initializeDOM();

    log.debug('Step 4: Initializing UI components and event listeners...');
    initializeEvents();
    setupSidebar();
    initializeChat();

    // Step 5: Load session and check auth status to update the UI.
    log.debug('Step 5: Loading local session state...');
    loadSessionState();
    
    log.debug('Step 6: Checking authentication status...');
    await checkAuthStatus();
    
    showWelcomeMessage();

    log.info('✅ Application initialized successfully.');
}

// Make selectStock function global for event handlers
window.selectStock = selectStock;

document.addEventListener('DOMContentLoaded', init);
