import { deps } from './config.js';
import { handleGoogleLogin, handleOAuthCallback, checkAuthStatus, handleLogout, updateAuthUI, loadSessionState, saveSessionState, showWelcomeMessage, log } from './auth.js';
import { initialize as initializeDOM } from './dom.js';
import { initialize as initializeEvents } from './events.js';
import { setupSidebar } from './sidebar.js';
import { initializeChat, updateChatContextIndicator } from './chat.js';
import { fetchData, loadStockDatabase } from './data.js';
import { hideAutocomplete } from './autocomplete.js';

async function init() {
    log.info('Initializing application...');

    // Step 1: Populate the dependency container immediately.
    deps.log = log;
    deps.updateAuthUI = updateAuthUI;

    log.debug('Step 1: Handling OAuth callback...');
    await handleOAuthCallback();
    log.debug('Step 2: Loading stock database...');
    await loadStockDatabase();

    log.debug('Step 3: Caching DOM elements...');
    initializeDOM();

    log.debug('Step 4: Initializing event listeners...');
    initializeEvents();
    log.debug('Step 5: Setting up sidebar...');
    setupSidebar();
    log.debug('Step 6: Initializing chat...');
    initializeChat();

    log.debug('Step 7: Loading session state...');
    loadSessionState();
    log.debug('Step 8: Checking authentication status...');
    await checkAuthStatus();
    showWelcomeMessage();

    log.info('✅ Application initialized successfully.');
}

// Make logout function global for onclick attribute
window.handleLogout = handleLogout;

document.addEventListener('DOMContentLoaded', init);
