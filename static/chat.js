// ==================== CHATBOT ====================
import { deps, generateSessionId, checkDependencies } from './config.js';
import { saveSessionState } from './session.js';
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
}

function toggleChatWindow() {
    DOM.chatWindow.classList.toggle('active');
}

function refreshChatContext() {
    STATE.currentSessionId = generateSessionId();
    saveSessionState();
    updateChatContextIndicator(STATE.currentSymbol);
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
        appendMessage('system', 'Please sign in to use the AI Chatbot.');
        showAuthOverlay();
        return;
    }

    if (!STATE.currentSymbol) {
        appendMessage('system', 'Please search or select a stock first to set the chat context.');
        return;
    }

    appendMessage('user', text);
    DOM.chatInput.value = '';

    const typingIndicator = appendMessage('bot', '...');

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
                history: Array.from(DOM.chatMessages.children)
                    .filter(el => el.classList.contains('msg'))
                    .map(el => ({
                        role: el.classList.contains('msg-user') ? 'user' : 'bot',
                        content: el.textContent
                    }))
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
                appendMessage('bot', data.response);
            } else {
                appendMessage('system', 'Sorry, I couldn\'t get a response. Try rephrasing or refreshing the context.');
            }
        })
        .catch(err => {
            typingIndicator.remove();
            appendMessage('system', `An error occurred: ${err.message}.`);
            console.error('❌ Chat error:', err);
        });
    } catch (err) {
        typingIndicator.remove();
        appendMessage('system', 'A connection error occurred. Please check your network.');
        console.error('❌ Chat error:', err);
    }
}

function appendMessage(sender, text) {
    const div = document.createElement('div');
    div.className = sender === 'user' ? 'msg msg-user' :
                     sender === 'bot' ? 'msg msg-bot' : 'msg msg-system';

    if (sender === 'bot') {
        let html = text;
        html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/`(.+?)`/g, '<code>$1</code>');
        html = html.replace(/~~(.+?)~~/g, '<del>$1</del>');
        html = html.replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');
        if (!html.startsWith('<p>')) html = '<p>' + html + '</p>';
        div.innerHTML = html;
    } else {
        div.textContent = text;
    }

    DOM.chatMessages.appendChild(div);
    DOM.chatMessages.scrollTop = DOM.chatMessages.scrollHeight;
    return div;
}

export function updateChatContextIndicator(symbol) {
    if (DOM.contextSymbol) {
        DOM.contextSymbol.textContent = symbol || 'None';
        DOM.contextSymbol.style.color = symbol ? '#667eea' : '#ef4444';
    }
}