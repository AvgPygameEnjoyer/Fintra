import { deps, debounce } from './config.js';
import { groupStocksByCategory, getGroupName, createSidebarStockItem } from './sidebar-helpers.js';
import { saveSessionState } from './session.js';
import { hideAutocomplete } from './autocomplete.js';
import { fetchData } from './data.js';
import { updateChatContextIndicator } from './chat.js';

const { STATE, DOM, CONFIG } = deps;

// The main initialization function that receives dependencies
export function initialize() {
    // This function now ONLY creates the dynamic elements and returns them.
    return createSidebarToggles();
}

// This new function will set up the rest of the sidebar logic AFTER the DOM is cached.
export function setupSidebar() {
    if (DOM.sidebarSearch) {
        DOM.sidebarSearch.addEventListener('input', debounce((e) => {
            filterSidebarStocks(e.target.value.trim());
        }, CONFIG.DEBOUNCE_DELAY));
    }

    loadSidebarStocks();

    const isMobile = window.matchMedia('(max-width: 768px)').matches;
    setSidebarCollapsed(isMobile);

    window.matchMedia('(max-width: 768px)').addEventListener('change', (e) => {
        setSidebarCollapsed(e.matches);
    });

    document.addEventListener('click', (e) => {
        if (window.matchMedia('(max-width: 768px)').matches) {
            const mobileToggle = document.querySelector('.mobile-sidebar-toggle');
            if (!DOM.sidebar || !mobileToggle) return;

            if (!STATE.isSidebarCollapsed && !DOM.sidebar.contains(e.target) && !mobileToggle.contains(e.target)) {
                setSidebarCollapsed(true);
            }
        }
    });
}

function createSidebarToggles() { // This function will now return the elements it creates
    const mainContent = document.querySelector('.container');

    let mobileToggle = document.querySelector('.mobile-sidebar-toggle');
    if (!mobileToggle) {
        mobileToggle = document.createElement('button');
        mobileToggle.className = 'mobile-sidebar-toggle';
        mobileToggle.title = 'Toggle Sidebar';
        mobileToggle.style.cssText = `
            position: fixed; top: 20px; left: 20px; z-index: 1000;
            background: rgba(255, 255, 255, 0.2); color: white; border: none;
            padding: 10px 15px; border-radius: 8px; font-size: 1.2rem;
            cursor: pointer; transition: all 0.3s ease; display: none;
        `;
        document.body.appendChild(mobileToggle);
    }
    mobileToggle.addEventListener('click', toggleSidebar);

    let desktopToggle = document.querySelector('.desktop-sidebar-toggle');
    if (!desktopToggle) {
        desktopToggle = document.createElement('button');
        desktopToggle.className = 'desktop-sidebar-toggle';
        desktopToggle.title = 'Toggle Sidebar';
        desktopToggle.style.cssText = `
            position: fixed; top: 20px; left: 300px; z-index: 1000;
            background: var(--primary-purple); color: white; border: none;
            padding: 10px 15px; border-radius: 8px; font-size: 1.2rem;
            cursor: pointer; transition: all 0.3s ease; display: none;
        `;
        document.body.appendChild(desktopToggle);
    }
    desktopToggle.addEventListener('click', toggleSidebar);

    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) sidebarToggle.addEventListener('click', toggleSidebar);

    return { mobileToggle, desktopToggle };
}

function toggleSidebar() {
    setSidebarCollapsed(!STATE.isSidebarCollapsed);
}

export function setSidebarCollapsed(collapsed) {
    STATE.isSidebarCollapsed = collapsed;
    saveSessionState();
    const mainContent = document.querySelector('.container');
    const mobileToggle = document.querySelector('.mobile-sidebar-toggle');
    const desktopToggle = document.querySelector('.desktop-sidebar-toggle');

    DOM.sidebar?.classList.toggle('sidebar-collapsed', collapsed);
    mainContent?.classList.toggle('sidebar-collapsed', collapsed);

    if (mobileToggle) {
        mobileToggle.innerHTML = collapsed ? '☰' : '✕';
        mobileToggle.style.left = !collapsed && window.matchMedia('(max-width: 768px)').matches ? '300px' : '20px';
        mobileToggle.style.display = window.matchMedia('(max-width: 768px)').matches ? 'block' : 'none';
    }
    if (desktopToggle) {
        desktopToggle.innerHTML = collapsed ? '☰' : '✕';
        desktopToggle.style.left = !collapsed && window.matchMedia('(min-width: 769px)').matches ? '340px' : '20px';
        desktopToggle.style.display = window.matchMedia('(min-width: 769px)').matches ? 'block' : 'none';
    }
}

function loadSidebarStocks() {
    if (!STATE.stockDatabase.length) {
        if (DOM.sidebarStocks) {
            DOM.sidebarStocks.innerHTML = `
                <div style="padding: 30px; text-align: center; color: #6b7280;">
                    <div style="font-size: 2rem; margin-bottom: 10px;">📈</div>
                    <div>Loading securities database...</div>
                </div>
            `;
        }
        return;
    }

    const grouped = groupStocksByCategory(STATE.stockDatabase);
    const groupOrder = [
        'mostPopular', 'nifty50', 'usStocks', 'banking', 'tech', 'pharma',
        'auto', 'energy', 'fmcg', 'metals', 'realty', 'midCap', 'smallCap',
        'debtEtf', 'sectorETF', 'goldSilverETF', 'factor', 'liquid', 'bond',
        'thematic', 'bse', 'other'
    ];
    let html = '';

    groupOrder.forEach(groupKey => {
        const stocks = grouped[groupKey];
        if (stocks?.length) {
            html += `
                <div class="sidebar-stock-group">
                    <div class="sidebar-group-header">${getGroupName(groupKey)}</div>
                    ${stocks.map(createSidebarStockItem).join('')}
                </div>
            `;
        }
    });

    if (DOM.sidebarStocks) {
        DOM.sidebarStocks.innerHTML = html;

        DOM.sidebarStocks.querySelectorAll('.sidebar-stock-item').forEach(item => {
            item.addEventListener('click', function() {
                selectStockFromSidebar(this.dataset.symbol);
                if (window.matchMedia('(max-width: 768px)').matches) {
                    setSidebarCollapsed(true);
                }
            });
        });
    }

    if (STATE.currentSymbol) {
        selectStockFromSidebar(STATE.currentSymbol);
    } else if (STATE.stockDatabase.length > 0) {
        selectStockFromSidebar(STATE.stockDatabase[0].symbol);
    }
}

function filterSidebarStocks(query) {
    const allItems = DOM.sidebarStocks.querySelectorAll('.sidebar-stock-item');
    const groupHeaders = DOM.sidebarStocks.querySelectorAll('.sidebar-group-header');

    if (!query) {
        allItems.forEach(item => item.style.display = 'flex');
        groupHeaders.forEach(header => header.parentElement.style.display = 'block');
        return;
    }

    const lowerQuery = query.toLowerCase();
    allItems.forEach(item => {
        const symbol = item.querySelector('.sidebar-stock-symbol').textContent.toLowerCase();
        const name = item.querySelector('.sidebar-stock-name').textContent.toLowerCase();
        item.style.display = (symbol.includes(lowerQuery) || name.includes(lowerQuery)) ? 'flex' : 'none';
    });

    groupHeaders.forEach(header => {
        const group = header.parentElement;
        const hasVisible = Array.from(group.querySelectorAll('.sidebar-stock-item'))
            .some(item => item.style.display !== 'none');
        group.style.display = hasVisible ? 'block' : 'none';
    });
}

function selectStockFromSidebar(symbol) {
    if (DOM.symbol) {
        DOM.symbol.value = symbol;
    }
    hideAutocomplete();
    if (DOM.symbol) {
        DOM.symbol.focus();
    }

    document.querySelectorAll('.sidebar-stock-item').forEach(item => item.classList.remove('active'));
    const sidebarItem = document.querySelector(`.sidebar-stock-item[data-symbol="${symbol}"]`);
    if (sidebarItem) {
        sidebarItem.classList.add('active');
        sidebarItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    if (STATE.currentSymbol !== symbol) {
        STATE.currentSymbol = symbol;
        saveSessionState();
        updateChatContextIndicator(symbol);
        fetchData();
    }
}
