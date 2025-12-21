// ==================== CHATBOT ====================
import { deps, generateSessionId, checkDependencies } from './config.js';
import { saveSessionState } from './auth.js';
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
    STATE.currentSessionId = generateSessionId();
    saveSessionState();
    updateChatContextIndicator(STATE.currentSymbol);
    STATE.chatHistory = []; // Clear history on refresh
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

    if (!STATE.currentSymbol) {
        appendMessage({ role: 'system', content: 'Please search or select a stock first to set the chat context.' });
        return;
    }

    appendMessage({ role: 'user', content: text });
    DOM.chatInput.value = '';

    const typingIndicator = appendMessage({ role: 'bot', content: '...' });

    const usePortfolio = document.getElementById('chat-use-portfolio')?.checked || false;

    try {
        fetch(`${CONFIG.API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                query: text,
                session_id: STATE.currentSessionId,
                current_symbol: STATE.currentSymbol,
                use_portfolio: usePortfolio,
                history: STATE.chatHistory // Use the state array for history
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
        let html = content;
        html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/`(.+?)`/g, '<code>$1</code>');
        html = html.replace(/~~(.+?)~~/g, '<del>$1</del>');
        html = html.replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>');
        if (!html.startsWith('<p>')) html = '<p>' + html + '</p>';
        div.innerHTML = html;
    } else {
        div.textContent = content;
    }

    DOM.chatMessages.appendChild(div);
    DOM.chatMessages.scrollTop = DOM.chatMessages.scrollHeight;
    return div;
}

export function updateChatContextIndicator(symbol) {
    const contextIndicator = document.getElementById('chat-context-header');
    if (contextIndicator) {
        contextIndicator.textContent = `Context: ${symbol || 'None'}`;
    }
}