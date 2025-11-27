// ==================== MAIN ENTRY POINT ====================
import { cacheDOMElements } from './dom.js';
import { handleOAuthCallback, checkAuthStatus } from './auth.js';
import { loadStockDatabase } from './data.js';
import { initializeEventListeners } from './events.js';
import { initializeSidebar } from './sidebar.js';
import { initializeChat } from './chat.js';
import { loadSessionState, showWelcomeMessage } from './session.js';

document.addEventListener('DOMContentLoaded', init);

async function init() {
    cacheDOMElements();
    await handleOAuthCallback();
    await loadStockDatabase();
    initializeEventListeners();
    initializeSidebar();
    initializeChat();
    loadSessionState();
    await checkAuthStatus();
    showWelcomeMessage();
}

// Make selectStock available globally for inline onclick handlers
import { selectStock } from './autocomplete.js';
window.selectStock = selectStock;