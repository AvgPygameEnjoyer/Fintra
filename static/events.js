// ==================== EVENT LISTENERS ====================
import { DOM, debounce, CONFIG, STATE } from './config.js';
import { handleAutocompleteInput, handleAutocompleteKeydown, hideAutocomplete } from './autocomplete.js';
import { fetchData } from './data.js';
import { handleGoogleLogin, handleLogout } from './auth.js';
import { setSidebarCollapsed } from './sidebar.js';

export function initialize() {
    DOM.symbol.addEventListener('input', debounce(handleAutocompleteInput, CONFIG.DEBOUNCE_DELAY));
    DOM.symbol.addEventListener('keydown', handleAutocompleteKeydown);
    document.querySelector('.search-form')?.addEventListener('submit', handleSearchSubmit);
    DOM.googleSigninBtn?.addEventListener('click', handleGoogleLogin);
    DOM.logoutBtn?.addEventListener('click', handleLogout);
    DOM.sidebarToggle?.addEventListener('click', () => setSidebarCollapsed(true)); // Close button inside sidebar
    DOM.mobileSidebarToggle?.addEventListener('click', () => setSidebarCollapsed(!STATE.isSidebarCollapsed));
    DOM.desktopSidebarToggle?.addEventListener('click', () => setSidebarCollapsed(!STATE.isSidebarCollapsed));
    
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