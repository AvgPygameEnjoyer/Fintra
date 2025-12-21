import { deps } from './config.js';
import { showNotification } from './notifications.js';

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
    }, 500);
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
        const response = await fetch(`${CONFIG.API_BASE_URL}/portfolio`, { credentials: 'include' });
        if (!response.ok) {
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

        // Render the portfolio cards
        portfolioContent.innerHTML = `
            <div class="portfolio-grid">
                ${positions.map(createPositionCard).join('')}
            </div>
        `;

        // Add event listeners for delete buttons
        portfolioContent.querySelectorAll('.delete-position-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent card expansion when clicking delete
                const positionId = e.target.closest('button').dataset.id;
                positionToDeleteId = positionId;
                document.getElementById('delete-modal').showModal();
            });
        });

        // --- New: Add event listeners for expandable cards ---
        portfolioContent.querySelectorAll('.position-card-header').forEach(header => {
            header.addEventListener('click', () => {
                const cardBody = header.nextElementSibling;
                const card = header.closest('.position-card');
                const arrow = header.querySelector('.position-card-arrow');
                const isExpanded = cardBody.classList.toggle('expanded');
                arrow?.classList.toggle('rotated');

                // If we are expanding the card and it's not already charted
                if (isExpanded && !card.dataset.charted) {
                    const positionId = card.dataset.posId;
                    const positionData = positions.find(p => p.id == positionId);
                    if (positionData && positionData.chart_data && positionData.chart_data.length > 0) {
                        renderPositionChart(positionData);
                        card.dataset.charted = 'true'; // Mark as charted
                    }
                }
            });
        });

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
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(positionData)
        });

        const result = await response.json();

        if (!response.ok) {
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
            credentials: 'include'
        });

        if (!response.ok) {
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
        renderChatPortfolioMenu(menu, checkbox, contextHeader, btn);
        menu.classList.toggle('active');
        btn.classList.toggle('active');
    });

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!menu.contains(e.target) && e.target !== btn) {
            menu.classList.remove('active');
            btn.classList.remove('active');
        }
    });
}

function renderChatPortfolioMenu(menu, checkbox, contextHeader, btn) {
    const positions = STATE.portfolio || [];
    
    let html = `<div class="chat-portfolio-item" data-symbol="">
                    <span>None (Clear Context)</span>
                </div>`;
    
    positions.forEach(pos => {
        const isSelected = STATE.currentSymbol === pos.symbol;
        html += `
            <div class="chat-portfolio-item ${isSelected ? 'selected' : ''}" data-symbol="${pos.symbol}">
                <span>${pos.symbol}</span>
                <span style="font-size: 0.8em; opacity: 0.8;">${pos.quantity} qty</span>
            </div>
        `;
    });

    menu.innerHTML = html;

    menu.querySelectorAll('.chat-portfolio-item').forEach(item => {
        item.addEventListener('click', () => {
            const symbol = item.dataset.symbol;
            STATE.currentSymbol = symbol || null;
            checkbox.checked = !!symbol; // Check hidden box if symbol selected
            contextHeader.textContent = symbol ? `Context: ${symbol}` : 'Context: None';
            menu.classList.remove('active');
            btn.classList.remove('active');
        });
    });
}

function renderPositionChart(pos) {
    const canvas = document.getElementById(`chart-pos-${pos.id}`);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const chartData = pos.chart_data;
    const dates = chartData.map(d => d.Date.substring(5));
    const closes = chartData.map(d => d.Close);

    if (STATE.charts[`pos-${pos.id}`]) {
        STATE.charts[`pos-${pos.id}`].destroy();
    }

    STATE.charts[`pos-${pos.id}`] = new Chart(ctx, {
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

function getRsiColor(rsi) {
    if (rsi == null) return '#6b7280';
    if (rsi > 70) return '#ef4444'; // Red for overbought
    if (rsi < 30) return '#10b981'; // Green for oversold
    return '#F0F4F8'; // Default white-ish for neutral
}

function createPositionCard(pos) {
    const pnlClass = pos.pnl >= 0 ? 'positive' : 'negative';
    const pnlSign = pos.pnl >= 0 ? '+' : '';
    const company = STATE.stockDatabase.find(s => s.symbol === pos.symbol);

    return `
        <div class="position-card" data-pos-id="${pos.id}" data-pos-symbol="${pos.symbol}">
            <div class="position-card-header">
                <div class="position-card-title">
                    <div class="position-symbol">${pos.symbol}</div>
                    <div class="position-company-name">${company?.name || 'N/A'}</div>
                </div>
                <div style="display: flex; align-items: center;">
                    <button class="delete-position-btn" data-id="${pos.id}" title="Delete Position">×</button>
                    <div class="position-card-arrow">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    </div>
                </div>
            </div>
            <div class="position-card-body">
                <div class="position-pnl ${pnlClass}">
                    <div class="pnl-amount">${pnlSign}${pos.pnl.toFixed(2)}</div>
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
                        <span>Current Price</span>
                        <strong>$${pos.current_price.toFixed(2)}</strong>
                    </div>
                </div>
                <div class="position-indicators">
                    <div class="indicator-item">
                        <span>RSI (14)</span>
                        <strong style="color: ${getRsiColor(pos.rsi)}">${pos.rsi ? pos.rsi.toFixed(2) : 'N/A'}</strong>
                    </div>
                    <div class="indicator-item">
                        <span>MA5 / MA10</span>
                        <strong>${pos.ma5 ? '$'+pos.ma5.toFixed(2) : 'N/A'} / ${pos.ma10 ? '$'+pos.ma10.toFixed(2) : 'N/A'}</strong>
                    </div>
                    <div class="indicator-item">
                        <span>MACD Status</span>
                        <strong>${pos.macd_status || 'N/A'}</strong>
                    </div>
                </div>
                <div class="position-chart-container">
                    <canvas id="chart-pos-${pos.id}"></canvas>
                </div>
            </div>
        </div>
    `;
}

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}