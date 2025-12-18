import { deps } from './config.js';
import { showNotification } from './notifications.js';

const { DOM, CONFIG, STATE } = deps;

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
                const positionId = e.target.closest('button').dataset.id;
                handleDeletePosition(positionId);
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

async function handleDeletePosition(positionId) {
    if (!confirm('Are you sure you want to delete this position?')) {
        return;
    }

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

function createPositionCard(pos) {
    const pnlClass = pos.pnl >= 0 ? 'positive' : 'negative';
    const pnlSign = pos.pnl >= 0 ? '+' : '';
    const company = STATE.stockDatabase.find(s => s.symbol === pos.symbol);

    return `
        <div class="position-card">
            <div class="position-card-header">
                <div>
                    <div class="position-symbol">${pos.symbol}</div>
                    <div class="position-company-name">${company?.name || 'N/A'}</div>
                </div>
                <button class="delete-position-btn" data-id="${pos.id}" title="Delete Position">×</button>
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
            </div>
        </div>
    `;
}