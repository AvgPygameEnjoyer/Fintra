// ==================== AUTOCOMPLETE ====================
import { CONFIG, STATE, DOM } from './config.js';

export function handleAutocompleteInput(e) {
    const query = e.target.value.trim().toUpperCase();
    if (!query) {
        hideAutocomplete();
        return;
    }
    STATE.filteredStocks = STATE.stockDatabase
        .filter(stock => stock.symbol.toUpperCase().includes(query) || stock.name.toUpperCase().includes(query))
        .slice(0, CONFIG.MAX_AUTOCOMPLETE_ITEMS);
    STATE.filteredStocks.length > 0 ? showAutocomplete(STATE.filteredStocks) : hideAutocomplete();
}

export function handleAutocompleteKeydown(e) {
    const items = DOM.autocomplete.querySelectorAll('.autocomplete-item');
    if (!items.length) return;
    switch(e.key) {
        case 'ArrowDown':
            e.preventDefault();
            STATE.selectedIndex = Math.min(STATE.selectedIndex + 1, items.length - 1);
            updateAutocompleteSelection(items);
            break;
        case 'ArrowUp':
            e.preventDefault();
            STATE.selectedIndex = Math.max(STATE.selectedIndex - 1, -1);
            updateAutocompleteSelection(items);
            break;
        case 'Enter':
            e.preventDefault();
            if (STATE.selectedIndex >= 0) items[STATE.selectedIndex].click();
            else document.querySelector('.search-form')?.requestSubmit();
            break;
        case 'Escape': hideAutocomplete(); break;
    }
}

export function showAutocomplete(stocks) {
    STATE.selectedIndex = -1;
    DOM.autocomplete.innerHTML = stocks.map(stock => `
        <div class="autocomplete-item" onclick="selectStock('${stock.symbol}')">
            <div class="ticker-symbol">${stock.symbol}</div>
            <div class="company-name">${stock.name}</div>
        </div>
    `).join('');
    DOM.autocomplete.classList.add('active');
}

export function hideAutocomplete() {
    DOM.autocomplete.classList.remove('active');
    STATE.selectedIndex = -1;
}

function updateAutocompleteSelection(items) {
    items.forEach((item, index) => {
        item.classList.toggle('selected', index === STATE.selectedIndex);
        if (index === STATE.selectedIndex) {
            item.scrollIntoView({ block: 'nearest' });
            DOM.symbol.value = item.querySelector('.ticker-symbol').textContent;
        }
    });
}

export function selectStock(symbol) {
    DOM.symbol.value = symbol;
    hideAutocomplete();
    DOM.symbol.focus();
    const sidebarItem = document.querySelector(`.sidebar-stock-item[data-symbol="${symbol}"]`);
    if (sidebarItem) {
        document.querySelectorAll('.sidebar-stock-item').forEach(item => item.classList.remove('active'));
        sidebarItem.classList.add('active');
        sidebarItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}