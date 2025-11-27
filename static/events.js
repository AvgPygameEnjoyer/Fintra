// ==================== EVENT LISTENERS ====================
import { DOM, debounce, CONFIG, STATE } from './config.js';
import { handleAutocompleteInput, handleAutocompleteKeydown, hideAutocomplete } from './autocomplete.js';
import { fetchData } from './data.js';
import { setSidebarCollapsed } from './sidebar.js';

export function initializeEventListeners() {
    DOM.symbol.addEventListener('input', debounce(handleAutocompleteInput, CONFIG.DEBOUNCE_DELAY));
    DOM.symbol.addEventListener('keydown', handleAutocompleteKeydown);
    document.querySelector('.search-form')?.addEventListener('submit', handleSearchSubmit);
    
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.input-wrapper')) hideAutocomplete();
    });
    
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            hideAutocomplete();
            if (!STATE.isSidebarCollapsed && window.matchMedia('(max-width: 768px)').matches) {
                setSidebarCollapsed(true);
            }
        }
    });
}

function handleSearchSubmit(e) {
    e.preventDefault();
    fetchData();
}