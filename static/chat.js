// ==================== CHATBOT ====================
import { deps, generateSessionId, checkDependencies } from './config.js';
import { saveSessionState, getAuthHeaders } from './auth.js';
import { showNotification } from './notifications.js';
import { showAuthOverlay } from './auth.js';

const { STATE, DOM, CONFIG } = deps;

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

    DOM.chatMessages.innerHTML = `
        <div style="padding: 10px; text-align: center; color: #6b7280; font-size: 0.9rem;">
            Welcome to the AI Stock Chatbot!
            <p style="margin-top: 5px;">Ask about the current stock's performance or analysis.</p>
        </div>
    `;
    updateChatContextIndicator(STATE.currentSymbol);
    STATE.chatHistory = []; // Clear history on initialization
}

function toggleChatWindow() {
    DOM.chatWindow.classList.toggle('active');
}

function refreshChatContext() {
    STATE.chatContextSymbols = []; // Clear multi-context
    STATE.currentSymbol = null; // Also clear single context
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
        // Temporarily add a system message without saving it to history
        const systemMessage = appendMessage({ role: 'system', content: 'Please sign in to use the AI Chatbot.' }, true);
        setTimeout(() => {
            systemMessage?.remove();
        }, 5000); // Remove the message after 5 seconds
        showAuthOverlay();
        return;
    }

    if (STATE.chatContextSymbols.length === 0 && !STATE.currentSymbol) {
        appendMessage({ role: 'system', content: 'Please select one or more stocks from your portfolio menu (💼) to set the chat context.' });
        return;
    }

    appendMessage({ role: 'user', content: text });
    DOM.chatInput.value = '';

    const typingIndicator = appendMessage({ role: 'bot', content: '...' });

    const usePortfolio = document.getElementById('chat-use-portfolio')?.checked || false;
    
    // Use multi-context if available, otherwise fall back to single context
    const contextSymbols = STATE.chatContextSymbols.length > 0 ? STATE.chatContextSymbols : (STATE.currentSymbol ? [STATE.currentSymbol] : []);

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
                session_id: STATE.currentSessionId,
                context_symbols: contextSymbols, // New: send array of symbols
                history: STATE.chatHistory
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
                appendMessage({ role: 'system', content: 'Sorry, I couldn\'t get a response. Try rephrasing or refreshing the context.' });
            }
        })
        .catch(err => {
            typingIndicator.remove();
            appendMessage({ role: 'system', content: `An error occurred: ${err.message}.` });
            console.error('❌ Chat error:', err);
        });
    } catch (err) {
        typingIndicator.remove();
        appendMessage({ role: 'system', content: 'A connection error occurred. Please check your network.' });
        console.error('❌ Chat error:', err);
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
    // This function is now multi-purpose. If a symbol is passed, it sets single context.
    // If not, it reads from the multi-context array.
    if (symbol) STATE.chatContextSymbols = [symbol];

    const contextIndicator = document.getElementById('chat-context-header');
    if (contextIndicator) {
        const symbolsText = STATE.chatContextSymbols.join(', ');
        contextIndicator.textContent = `Context: ${symbolsText || 'None'}`;
    }
}