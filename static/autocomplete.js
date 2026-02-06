// ==================== AUTOCOMPLETE ====================
import { CONFIG, STATE, DOM } from './config.js';

export function handleAutocompleteInput(e, dropdownElement) {
    const query = e.target.value.trim().toUpperCase();
    if (!query) {
        hideAutocomplete(dropdownElement);
        return;
    }
    
    // Prioritize ticker symbol matches, then name matches
    const tickerMatches = STATE.stockDatabase
        .filter(stock => stock.symbol.toUpperCase().startsWith(query))
        .sort((a, b) => a.symbol.length - b.symbol.length);
    
    const nameMatches = STATE.stockDatabase
        .filter(stock => !stock.symbol.toUpperCase().startsWith(query) && stock.name.toUpperCase().includes(query));
    
    // Combine: ticker matches first, then name matches
    STATE.filteredStocks = [...tickerMatches, ...nameMatches]
        .slice(0, CONFIG.MAX_AUTOCOMPLETE_ITEMS);
    
    STATE.filteredStocks.length > 0 ? showAutocomplete(STATE.filteredStocks, dropdownElement, e.target, query) : hideAutocomplete(dropdownElement);
}

export function handleAutocompleteKeydown(e, dropdownElement) {
    const items = dropdownElement.querySelectorAll('.autocomplete-item');
    if (!items.length) return;
    switch(e.key) {
        case 'ArrowDown':
            e.preventDefault();
            STATE.selectedIndex = Math.min(STATE.selectedIndex + 1, items.length - 1);
            updateAutocompleteSelection(items, e.target);
            break;
        case 'ArrowUp':
            e.preventDefault();
            STATE.selectedIndex = Math.max(STATE.selectedIndex - 1, -1);
            updateAutocompleteSelection(items, e.target);
            break;
        case 'Enter':
            e.preventDefault();
            if (STATE.selectedIndex >= 0) items[STATE.selectedIndex].click();
            else document.querySelector('.search-form')?.requestSubmit();
            break;
        case 'Escape': hideAutocomplete(dropdownElement); break;
    }
}

export function showAutocomplete(stocks, dropdownElement, inputElement, query = '') {
    STATE.selectedIndex = -1;
    dropdownElement.innerHTML = stocks.map(stock => {
        // Highlight matching parts
        const highlightedSymbol = query ? stock.symbol.replace(new RegExp(`^(${query})`, 'i'), '<mark>$1</mark>') : stock.symbol;
        const highlightedName = query ? stock.name.replace(new RegExp(`(${query})`, 'gi'), '<mark>$1</mark>') : stock.name;
        
        return `
        <div class="autocomplete-item" data-symbol="${stock.symbol}">
            <div class="ticker-symbol">${highlightedSymbol}</div>
            <div class="company-name">${highlightedName}</div>
        </div>
    `}).join('');

    dropdownElement.querySelectorAll('.autocomplete-item').forEach(item => {
        item.addEventListener('click', () => {
            inputElement.value = item.dataset.symbol;
            hideAutocomplete(dropdownElement);
            
            if (inputElement.id === 'symbol') {
                // Main search behavior
                window.selectStock(item.dataset.symbol);
            } else {
                // Modal behavior: Trigger input event to fetch price
                inputElement.dispatchEvent(new Event('input'));
            }
        });
    });
    dropdownElement.classList.add('active');
}

export function hideAutocomplete(dropdownElement) {
    dropdownElement?.classList.remove('active');
    STATE.selectedIndex = -1;
}

function updateAutocompleteSelection(items, inputElement) {
    items.forEach((item, index) => {
        item.classList.toggle('selected', index === STATE.selectedIndex);
        if (index === STATE.selectedIndex) {
            item.scrollIntoView({ block: 'nearest' });
            inputElement.value = item.querySelector('.ticker-symbol').textContent;
        }
    });
}

export function selectStock(symbol) {
    DOM.symbol.value = symbol;
    hideAutocomplete(DOM.autocomplete);
    hideAutocomplete(DOM.modalAutocomplete);
    DOM.symbol.focus();
    // Trigger a search when a stock is selected from autocomplete
    const sidebarItem = document.querySelector(`.sidebar-stock-item[data-symbol="${symbol}"]`);
    if (sidebarItem) {
        document.querySelectorAll('.sidebar-stock-item').forEach(item => item.classList.remove('active'));
        sidebarItem.classList.add('active');
        sidebarItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}