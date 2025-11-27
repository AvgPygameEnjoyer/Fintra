// ==================== SESSION MANAGEMENT ====================
import { CONFIG, STATE, DOM } from './config.js';

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
            if (STATE.currentSymbol) DOM.symbol.value = STATE.currentSymbol;
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