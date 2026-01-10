import { deps, debounce, getRsiColor } from './config.js';
import { showNotification } from './notifications.js';
import { updateChatContextIndicator } from './chat.js';
import { getAuthHeaders, handleLogout } from './auth.js';

const { DOM, CONFIG, STATE } = deps;

let positionToDeleteId = null;

export function initializePortfolio() {
    // Event Listeners for portfolio functionality
    DOM.portfolioTabBtn?.addEventListener('click', showPortfolioView);
    DOM.searchTabBtn?.addEventListener('click', showSearchView);
    DOM.addPositionBtn?.addEventListener('click', () => DOM.addPositionModal.showModal());
    DOM.closeModalBtn?.addEventListener('click', () => DOM.addPositionModal.close());
    DOM.addPositionForm?.addEventListener('submit', handleAddPosition);

    // Close modal if clicked outside the form
    DOM.addPositionModal?.addEventListener('click', (e) => {
        if (e.target.id === 'add-position-modal') {
            DOM.addPositionModal.close();
        }
    });

    // --- Delegated Event Listener for Portfolio Cards -
    DOM.portfolioContent?.addEventListener('click', (e) => {
        const deleteBtn = e.target.closest('.delete-position-btn');
        const searchBtn = e.target.closest('.search-position-btn');
        const header = e.target.closest('.position-card-header');

        if (deleteBtn) {
            e.stopPropagation();
            positionToDeleteId = deleteBtn.dataset.id;
            document.getElementById('delete-modal').showModal();
            return;
        }

        if (searchBtn) {
            e.stopPropagation();
            const card = searchBtn.closest('.position-card');
            const symbol = card.dataset.symbol;
            if (symbol) {
                // Switch to the search tab
                DOM.searchTabBtn.click();
                // Populate the search input
                DOM.symbol.value = symbol;
                // Manually trigger the search
                document.querySelector('.search-form').requestSubmit();
            }
            return;
        }

        if (header) {
            const cardBody = header.nextElementSibling;
            const card = header.closest('.position-card');
            const arrow = header.querySelector('.position-card-arrow');
            const isExpanded = cardBody.classList.toggle('expanded');
            arrow?.classList.toggle('rotated');

            if (isExpanded && !card.dataset.charted) {
                const positionId = card.dataset.id;
                const positionData = STATE.portfolio.find(p => p.id == positionId);
                if (positionData?.chart_data?.length > 0) {
                    renderPositionChart(positionData);
                    card.dataset.charted = 'true';
                }
            }
        }
    });

    // Delete Modal Listeners
    const deleteModal = document.getElementById('delete-modal');
    const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
    const cancelDeleteBtn = document.getElementById('cancel-delete-btn');

    cancelDeleteBtn?.addEventListener('click', () => deleteModal.close());
    
    confirmDeleteBtn?.addEventListener('click', () => {
        if (positionToDeleteId) {
            executeDeletePosition(positionToDeleteId);
        }
        deleteModal.close();
    });
    
    deleteModal?.addEventListener('click', (e) => {
        if (e.target === deleteModal) deleteModal.close();
    });

    // Initialize Chat Portfolio Menu
    setupChatPortfolioMenu();

    // --- New: Logic for current price indicator ---
    const debouncedPriceFetch = debounce(async (e) => {
        const symbol = e.target.value.trim().toUpperCase();
        if (!symbol) {
            DOM.currentPriceIndicator.style.display = 'none';
            return;
        }
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/price/${symbol}`);
            if (response.ok) {
                const data = await response.json();
                DOM.currentPriceIndicator.textContent = `Live: $${data.price.toFixed(2)}`;
                DOM.currentPriceIndicator.style.display = 'block';
            } else {
                DOM.currentPriceIndicator.style.display = 'none';
            }
        } catch (error) {
            DOM.currentPriceIndicator.style.display = 'none';
        }
    }, 1000); // Increased debounce to 1s to prevent 429 Rate Limit errors
    DOM.addPositionSymbolInput?.addEventListener('input', debouncedPriceFetch);
}

function showSearchView() {
    DOM.searchView.style.display = 'block';
    DOM.portfolioView.style.display = 'none';
    DOM.searchTabBtn.classList.add('active');
    DOM.portfolioTabBtn.classList.remove('active');
}

function showPortfolioView() {
    DOM.searchView.style.display = 'none';
    DOM.portfolioView.style.display = 'block';
    DOM.searchTabBtn.classList.remove('active');
    DOM.portfolioTabBtn.classList.add('active');
    fetchAndDisplayPortfolio();
}

async function fetchAndDisplayPortfolio() {
    const portfolioContent = DOM.portfolioContent;
    portfolioContent.innerHTML = '<div class="loading"><div class="spinner"></div>Fetching portfolio...</div>';

    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/portfolio`, {
            credentials: 'include',
            headers: getAuthHeaders()
        });
        if (!response.ok) {
            if (response.status === 401) {
                showNotification('Session expired or invalid. Please sign in again.', 'error');
                handleLogout(false); // Force logout to clear invalid token
                return;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const positions = await response.json();
        
        // Store in global state for chat context
        STATE.portfolio = positions;

        if (positions.length === 0) {
            portfolioContent.innerHTML = `
                <div class="empty-portfolio">
                    <h3>Your portfolio is empty.</h3>
                    <p>Click "Add Position" to start tracking your investments.</p>
                </div>
            `;
            return;
        }

        portfolioContent.innerHTML = `<div class="portfolio-grid">${positions.map(createPositionCard).join('')}</div>`;

    } catch (error) {
        console.error('❌ Error fetching portfolio:', error);
        portfolioContent.innerHTML = `<div class="error" style="display: block;">Failed to fetch portfolio data. Please try again.</div>`;
    }
}

async function handleAddPosition(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    const positionData = Object.fromEntries(formData.entries());

    if (parseFloat(positionData.quantity) < 0) {
        showNotification('Quantity cannot be negative.', 'error');
        return;
    }

    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/positions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            credentials: 'include',
            body: JSON.stringify(positionData)
        });

        const result = await response.json();

        if (!response.ok) {
            if (response.status === 401) {
                showNotification('Session expired. Please sign in again.', 'error');
                DOM.addPositionModal.close();
                handleLogout(false);
                return;
            }
            throw new Error(result.error || 'Failed to add position.');
        }

        showNotification('Position added successfully!', 'success');
        DOM.addPositionModal.close();
        e.target.reset();
        fetchAndDisplayPortfolio(); // Refresh the view

    } catch (error) {
        console.error('❌ Error adding position:', error);
        showNotification(error.message, 'error');
    }
}

async function executeDeletePosition(positionId) {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/positions/${positionId}`, {
            method: 'DELETE',
            credentials: 'include',
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            if (response.status === 401) {
                showNotification('Session expired.', 'error');
                handleLogout(false);
                return;
            }
            const result = await response.json();
            throw new Error(result.error || 'Failed to delete position.');
        }

        showNotification('Position deleted successfully.', 'success');
        fetchAndDisplayPortfolio(); // Refresh the view

    } catch (error) {
        console.error('❌ Error deleting position:', error);
        showNotification(error.message, 'error');
    }
}

function setupChatPortfolioMenu() {
    const btn = document.getElementById('chat-portfolio-btn');
    const menu = document.getElementById('chat-portfolio-menu');
    const checkbox = document.getElementById('chat-use-portfolio');
    const contextHeader = document.getElementById('chat-context-header');

    if (!btn || !menu) return;

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        // Repopulate menu on click to ensure fresh data
        renderChatPortfolioMenu(menu);
        menu.classList.toggle('active');
        btn.classList.toggle('active');
    });

    // Delegated listener for menu items
    menu.addEventListener('click', (e) => {
        e.stopPropagation(); // Prevent menu from closing
        const clearBtn = e.target.closest('[data-action="clear"]');
        const checkbox = e.target.closest('input[type="checkbox"]');

        if (clearBtn) {
            STATE.chatContextSymbols = [];
            updateChatContextIndicator();
            menu.classList.remove('active');
            btn.classList.remove('active');
        } else if (checkbox) {
            // The 'change' event will handle the logic
        }
    });

    menu.addEventListener('change', (e) => {
        if (e.target.type === 'checkbox') {
            const symbol = e.target.dataset.symbol;
            if (e.target.checked) {
                if (!STATE.chatContextSymbols.includes(symbol)) STATE.chatContextSymbols.push(symbol);
            } else {
                STATE.chatContextSymbols = STATE.chatContextSymbols.filter(s => s !== symbol);
            }
            updateChatContextIndicator();
        }
    });

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!menu.contains(e.target) && e.target !== btn) {
            menu.classList.remove('active');
            btn.classList.remove('active');
        }
    });
}

function renderChatPortfolioMenu(menu) {
    const positions = STATE.portfolio || [];
    
    let html = `<div class="chat-portfolio-item" data-action="clear"><label>None (Clear Context)</label></div>`;
    
    positions.forEach(pos => {
        const isSelected = STATE.chatContextSymbols.includes(pos.symbol);
        html += `
            <div class="chat-portfolio-item">
                <input type="checkbox" id="chat-ctx-${pos.symbol}" data-symbol="${pos.symbol}" ${isSelected ? 'checked' : ''}>
                <label for="chat-ctx-${pos.symbol}">${pos.symbol}</label>
            </div>
        `;
    });

    menu.innerHTML = html;
}

function renderPositionChart(pos) {
    const canvas = document.getElementById(`chart-${pos.id}`);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const chartData = pos.chart_data;
    const dates = chartData.map(d => d.Date.substring(5));
    const closes = chartData.map(d => d.Close);

    if (STATE.charts[`chart-${pos.id}`]) {
        STATE.charts[`chart-${pos.id}`].destroy();
    }

    STATE.charts[`chart-${pos.id}`] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [{
                label: 'Close Price',
                data: closes,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 2,
                tension: 0.1,
                fill: true,
                pointRadius: 0,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: { display: false }
            },
            scales: {
                x: { display: false },
                y: { display: false }
            }
        }
    });
}

function createPositionCard(pos) {
    const pnlClass = pos.pnl >= 0 ? 'positive' : 'negative';
    const pnlSign = pos.pnl >= 0 ? '+' : '';
    const company = STATE.stockDatabase.find(s => s.symbol === pos.symbol);

    // Use marked.parse for the AI summary. It will be available globally from index.html.
    const aiSummaryHtml = pos.ai_position_summary ? marked.parse(pos.ai_position_summary) : '<p>AI summary is being generated...</p>';

    return `
        <div class="position-card" data-id="${pos.id}" data-symbol="${pos.symbol}">
            <div class="position-card-header">
                <div class="position-card-title">
                    <div class="position-symbol">${pos.symbol}</div>
                    <div class="position-company-name">${company?.name || 'N/A'}</div>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <button class="icon-btn search-position-btn" title="Search ${pos.symbol}">🔍</button>
                    <button class="delete-position-btn" data-id="${pos.id}" title="Delete Position">×</button>
                    <div class="position-card-arrow">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    </div>
                </div>
            </div>
            <div class="position-card-body">
                <div class="position-pnl ${pnlClass}">
                    <div class="pnl-amount">${pnlSign}$${pos.pnl.toFixed(2)}</div>
                    <div class="pnl-percent">(${pnlSign}${pos.pnl_percent.toFixed(2)}%)</div>
                </div>
                <div class="position-details">
                    <div>
                        <span>Quantity</span>
                        <strong>${pos.quantity}</strong>
                    </div>
                    <div>
                        <span>Avg. Cost</span>
                        <strong>$${pos.entry_price.toFixed(2)}</strong>
                    </div>
                    <div>
                        <span>Mkt. Value</span>
                        <strong>$${pos.current_value.toFixed(2)}</strong>
                    </div>
                </div>
                <div class="position-indicators">
                    <div class="indicator-item">
                        <span>RSI (14)</span>
                        <strong style="color: ${getRsiColor(pos.rsi)}">${pos.rsi != null ? pos.rsi.toFixed(2) : 'N/A'}</strong>
                    </div>
                    <div class="indicator-item">
                        <span>MA5 / MA10</span>
                        <strong>${pos.ma5 != null ? '$'+pos.ma5.toFixed(2) : 'N/A'} / ${pos.ma10 != null ? '$'+pos.ma10.toFixed(2) : 'N/A'}</strong>
                    </div>
                    <div class="indicator-item">
                        <span>MACD Status</span>
                        <strong>${pos.macd_status || 'N/A'}</strong>
                    </div>
                </div>
                <div class="position-chart-container">
                    <canvas id="chart-${pos.id}"></canvas>
                </div>
                <div class="position-ai-summary">
                    ${aiSummaryHtml}
                </div>
            </div>
        </div>
    `;
}