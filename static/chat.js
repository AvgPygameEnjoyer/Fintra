// ==================== CHATBOT ====================
import { deps, generateSessionId, checkDependencies } from './config.js';
import { saveSessionState, getAuthHeaders } from './auth.js';
import { showNotification } from './notifications.js';
import { showAuthOverlay } from './auth.js';

const { STATE, DOM, CONFIG } = deps;

let selectedPositionId = null;
let portfolioPositions = [];

export function initializeChat() {
    // Defensively check that all required DOM elements are available before proceeding.
    checkDependencies('initializeChat', [
        'chatToggle', 'chatClose', 'chatSend', 'chatInput', 'chatRefresh', 'chatMessages'
    ]);

    DOM.chatToggle.addEventListener('click', toggleChatWindow);
    DOM.chatClose.addEventListener('click', toggleChatWindow);
    DOM.chatSend.addEventListener('click', handleChatSubmit);
    DOM.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleChatSubmit();
    });
    DOM.chatRefresh.addEventListener('click', refreshChatContext);

    // Add position selector to chat footer
    addPositionSelector();

    // Fetch portfolio positions on initialization
    fetchPortfolioPositions();

    DOM.chatMessages.innerHTML = `
        <div style="padding: 10px; text-align: center; color: #6b7280; font-size: 0.9rem;">
            Welcome to the AI Stock Chatbot!
            <p style="margin-top: 5px;">Ask about stock performance or select a portfolio position for context.</p>
        </div>
    `;
    updateChatContextIndicator(STATE.currentSymbol);
    STATE.chatHistory = []; // Clear history on initialization
}

function addPositionSelector() {
    const chatFooter = document.getElementById('chat-footer');
    if (!chatFooter) return;

    // Add position selector before the existing input
    const selectorDiv = document.createElement('div');
    selectorDiv.id = 'position-selector-container';
    selectorDiv.style.cssText = 'display: flex; gap: 8px; align-items: center; margin-bottom: 8px;';

    selectorDiv.innerHTML = `
        <select id="position-selector" style="flex: 1; padding: 8px; border: 1px solid #374151; border-radius: 6px; background: #1f2937; color: #e5e7eb; font-size: 0.9rem;">
            <option value="">No position selected</option>
            <option value="" disabled>Loading positions...</option>
        </select>
        <button id="clear-position-btn" style="padding: 8px 12px; background: #374151; border: none; border-radius: 6px; color: #9ca3af; cursor: pointer; font-size: 0.8rem;">✕ Clear</button>
    `;

    chatFooter.insertBefore(selectorDiv, chatFooter.firstChild);

    // Add event listeners
    document.getElementById('position-selector').addEventListener('change', handlePositionChange);
    document.getElementById('clear-position-btn').addEventListener('click', clearPositionSelection);
}

async function fetchPortfolioPositions() {
    const selector = document.getElementById('position-selector');
    if (!selector) return;

    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/portfolio/positions/list`, {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            console.warn('Failed to fetch portfolio positions');
            selector.innerHTML = '<option value="">No position selected</option><option value="" disabled>Error loading positions</option>';
            return;
        }

        portfolioPositions = await response.json();

        // Update selector
        if (portfolioPositions.length === 0) {
            selector.innerHTML = '<option value="">No position selected</option><option value="" disabled>No positions in portfolio</option>';
        } else {
            let options = '<option value="">No position selected</option>';
            options += '<option value="" disabled>--- Positions ---</option>';
            portfolioPositions.forEach(p => {
                options += `<option value="${p.id}">${p.symbol} - ${p.quantity} shares @ ₹${p.entry_price.toFixed(2)}</option>`;
            });
            selector.innerHTML = options;
        }

    } catch (error) {
        console.error('Error fetching portfolio positions:', error);
        selector.innerHTML = '<option value="">No position selected</option><option value="" disabled>Error loading positions</option>';
    }
}

function handlePositionChange(event) {
    selectedPositionId = event.target.value || null;
    updateChatContextIndicator();
    
    if (selectedPositionId) {
        const position = portfolioPositions.find(p => p.id === parseInt(selectedPositionId));
        if (position) {
            showNotification(`Selected ${position.symbol} position for context`, 'info');
        }
    } else {
        showNotification('Position context cleared', 'info');
    }
}

function clearPositionSelection() {
    const selector = document.getElementById('position-selector');
    if (selector) {
        selector.value = '';
        selectedPositionId = null;
        updateChatContextIndicator();
        showNotification('Position context cleared', 'info');
    }
}

function toggleChatWindow() {
    DOM.chatWindow.classList.toggle('active');
}

function refreshChatContext() {
    STATE.chatContextSymbols = []; // Clear multi-context
    STATE.currentSymbol = null; // Also clear single context
    clearPositionSelection();
    STATE.chatHistory = []; // Clear history on refresh
    updateChatContextIndicator(); // Update UI

    DOM.chatMessages.innerHTML = `
        <div style="padding: 10px; text-align: center; color: #6b7280; font-size: 0.9rem;">
            Chat context refreshed. Session ID: ${STATE.currentSessionId}.
        </div>
    `;
    showNotification('Chat context refreshed. You can start a new topic.', 'info');
}

function handleChatSubmit() {
    const text = DOM.chatInput.value.trim();
    if (!text) return;

    if (!STATE.isAuthenticated) {
        const systemMessage = appendMessage({ role: 'system', content: 'Please sign in to use the AI Chatbot.' }, true);
        setTimeout(() => {
            systemMessage?.remove();
        }, 5000);
        showAuthOverlay();
        return;
    }

    if (STATE.chatContextSymbols.length === 0 && !STATE.currentSymbol && !selectedPositionId) {
        appendMessage({ role: 'system', content: 'Please select a stock or a portfolio position for context.' });
        return;
    }

    appendMessage({ role: 'user', content: text });
    DOM.chatInput.value = '';

    const typingIndicator = appendMessage({ role: 'bot', content: '...' });

    try {
        fetch(`${CONFIG.API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify({
                query: text,
                position_id: selectedPositionId  // Only sent if position is selected
            }),
            credentials: 'include'
        })
        .then(response => {
            if (!response.ok) {
                if (response.status === 401) {
                    showAuthOverlay();
                    throw new Error('Unauthorized. Please sign in again.');
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            typingIndicator.remove();
            if (data.response) {
                appendMessage({ role: 'bot', content: data.response });
            } else {
                appendMessage({ role: 'system', content: 'Sorry, I couldn\'t get a response. Try rephrasing.' });
            }
        })
        .catch(err => {
            typingIndicator.remove();
            appendMessage({ role: 'system', content: `An error occurred: ${err.message}.` });
            console.error('Chat error:', err);
        });
    } catch (err) {
        typingIndicator.remove();
        appendMessage({ role: 'system', content: 'A connection error occurred. Please check your network.' });
        console.error('Chat error:', err);
    }
}

function appendMessage(message, isTemporary = false) {
    const { role, content } = message;

    // Add to state, unless it's a temporary message or typing indicator
    if (content !== '...' && !isTemporary) {
        STATE.chatHistory.push({ role, content });
    }

    const div = document.createElement('div');
    div.className = `msg msg-${role}`;

    if (role === 'bot' || role === 'system') {
        // Use marked.parse() which is now available globally
        const html = marked.parse(content);
        div.innerHTML = html;
    } else { // Handle user messages
        div.textContent = content;
    }

    DOM.chatMessages.appendChild(div);
    DOM.chatMessages.scrollTop = DOM.chatMessages.scrollHeight;
    return div;
}

export function updateChatContextIndicator(symbol) {
    if (symbol) STATE.chatContextSymbols = [symbol];

    const contextIndicator = document.getElementById('chat-context-header');
    if (!contextIndicator) return;

    let contextText = '';

    // Show position context first if selected
    if (selectedPositionId) {
        const position = portfolioPositions.find(p => p.id === parseInt(selectedPositionId));
        if (position) {
            contextText = `Position: ${position.symbol} (${position.quantity} shares)`;
        }
    } else {
        // Otherwise show stock context
        const symbolsText = STATE.chatContextSymbols.join(', ');
        contextText = `Context: ${symbolsText || 'None'}`;
    }

    contextIndicator.textContent = contextText;
}
