// ==================== DATA FETCHING ====================
import { CONFIG, STATE } from './config.js';
import { showLoading, hideLoading, hideError, showError } from './dom.js';
import { displayData } from './display.js';
import { updateAuthUI } from './auth.js';

export async function loadStockDatabase() {
    try {
        const response = await fetch('stock-data.json');
        const data = await response.json();
        STATE.stockDatabase = data.stocks || [];
        console.log(`✅ Loaded ${STATE.stockDatabase.length} stocks`);
    } catch (error) {
        console.error('❌ Error loading stock data:', error);
    }
}

export async function fetchData() {
    if (!STATE.currentSymbol) return;

    showLoading();
    hideError();
    document.getElementById('output').innerHTML = '';

    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/get_data`, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                symbol: STATE.currentSymbol
            })
        });

        if (!response.ok) {
            if (response.status === 401) {
                showError('Authentication Required. Please sign in to view data.');
                updateAuthUI();
                return;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
            showError(data.error);
        } else {
            displayData(data);
        }

    } catch (error) {
        console.error('Fetch error:', error);
        showError(`Failed to fetch data for ${STATE.currentSymbol}. Please try another symbol.`);
    } finally {
        hideLoading();
    }
}