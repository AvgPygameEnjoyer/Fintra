// ==================== CONFIGURATION & STATE ====================
const IS_LOCALHOST = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE_URL = IS_LOCALHOST ? 'http://localhost:5000' : 'https://stock-dashboard-fqtn.onrender.com';

const CONFIG = {
    API_BASE_URL: API_BASE_URL,
    DEBOUNCE_DELAY: 300,
    MAX_AUTOCOMPLETE_ITEMS: 8,
    MAX_CHART_POINTS: 30,
    SESSION_STORAGE_KEY: 'userSession',
    OAUTH_STATE_KEY: 'oauthState'
};

console.log(`🚀 App initialized. Backend set to: ${CONFIG.API_BASE_URL}`);

const STATE = {
    stockDatabase: [],
    selectedIndex: -1,
    filteredStocks: [],
    isSidebarCollapsed: false,
    charts: { ohlcv: null, rsi: null, movingAverages: null, macd: null },
    currentSessionId: generateSessionId(),
    currentSymbol: null,
    isLoading: false,
    isAuthenticated: false,
    user: null
};
const DOM = {};

let sessionTimerInterval = null;

// ==================== UTILITY FUNCTIONS ====================
function generateSessionId() {
    return `session_${Math.random().toString(36).substr(2, 9)}_${Date.now()}`;
}

function debounce(func, wait) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}

function formatPrice(price) { return price != null ? `$${price.toFixed(2)}` : 'N/A'; }
function formatNumber(num) { return num != null ? num.toLocaleString() : 'N/A'; }
function getRsiColor(rsi) {
    if (rsi == null) return '#6b7280';
    if (rsi > 70) return '#ef4444';
    if (rsi < 30) return '#10b981';
    return '#6b7280';
}
function getRsiBackground(rsi) {
    if (rsi == null) return '#f3f4f6';
    if (rsi > 70) return '#fef2f2';
    if (rsi < 30) return '#f0fdf4';
    return '#f8fafc';
}

// ==================== OAUTH AUTHENTICATION (STATELESS FLOW) ====================
async function handleGoogleLogin() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/auth/login`, { credentials: 'include' });
        const data = await response.json();
        if (data.auth_url && data.state) {
            localStorage.setItem(CONFIG.OAUTH_STATE_KEY, data.state); // Store state
            window.location.href = data.auth_url;
        } else {
            showNotification('Could not initiate login. Please try again.', 'error');
        }
    } catch (error) {
        console.error('Login error:', error);
        showNotification('Login failed. Please try again.', 'error');
    }
}

async function handleOAuthCallback() {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');
    const storedState = localStorage.getItem(CONFIG.OAUTH_STATE_KEY);

    if (!code || !state) {
        // This is not a callback, just a normal page load
        return;
    }

    // Clean the URL
    window.history.replaceState({}, document.title, "/");
    localStorage.removeItem(CONFIG.OAUTH_STATE_KEY);

    if (state !== storedState) {
        showNotification('Authentication failed: State mismatch. Please try again.', 'error');
        return;
    }

    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/oauth2callback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, state, stored_state: storedState }),
            credentials: 'include'
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showNotification('Login successful!', 'success');
            await checkAuthStatus(); // Refresh user state and UI
        } else {
            throw new Error(data.error || 'Callback failed');
        }
    } catch (error) {
        console.error('OAuth callback error:', error);
        showNotification(`Authentication failed: ${error.message}`, 'error');
    }
}

async function checkAuthStatus() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/auth/status`, { credentials: 'include' });
        const data = await response.json();
        STATE.isAuthenticated = data.authenticated;
        STATE.user = data.user || null;
        updateAuthUI();
        return data.authenticated;
    } catch (error) {
        console.error('Auth check error:', error);
        STATE.isAuthenticated = false;
        STATE.user = null;
        updateAuthUI();
        return false;
    }
}

async function handleLogout(showNotify = true) {
    try {
        await fetch(`${CONFIG.API_BASE_URL}/auth/logout`, { method: 'POST', credentials: 'include' });
    } catch (error) {
        console.error('Logout request failed:', error);
    } finally {
        STATE.isAuthenticated = false;
        STATE.user = null;
        updateAuthUI();
        if (showNotify) showNotification('Logged out successfully', 'success');
    }
}

function updateAuthUI() {
    if (STATE.isAuthenticated && STATE.user) {
        document.getElementById('auth-overlay')?.classList.add('hidden');
        const userInfoBar = document.getElementById('user-info-bar');
        if (userInfoBar) {
            userInfoBar.classList.remove('hidden');
            document.getElementById('user-name').textContent = STATE.user.name;
            document.getElementById('user-avatar').src = STATE.user.picture || `data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='%23e2e8f0'/><text x='50' y='55' font-size='40' fill='%2394a3b8' text-anchor='middle' dominant-baseline='middle'>👤</text></svg>`;
        }
    } else {
        document.getElementById('auth-overlay')?.classList.remove('hidden');
        document.getElementById('user-info-bar')?.classList.add('hidden');
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 5000);
}

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', init);

async function init() {
    cacheDOMElements();
    await handleOAuthCallback(); // Handle redirect before anything else
    await loadStockDatabase();
    initializeEventListeners();
    initializeSidebar();
    initializeChat();
    loadSessionState();
    await checkAuthStatus();
    showWelcomeMessage();
}

function cacheDOMElements() {
    const ids = ['symbol', 'autocomplete', 'output', 'loading', 'error', 'searchBtn', 'sidebar', 'sidebarStocks', 'sidebarSearch', 'chat-toggle', 'chat-window', 'chat-messages', 'chat-input', 'chat-send', 'chat-close', 'chat-refresh', 'context-symbol'];
    ids.forEach(id => DOM[id] = document.getElementById(id));
    if (DOM.error) DOM.error.style.display = 'none';
    if (DOM.loading) DOM.loading.style.display = 'none';
}

async function loadStockDatabase() {
    try {
        const response = await fetch('stock-data.json');
        const data = await response.json();
        STATE.stockDatabase = data.stocks || [];
        console.log(`✅ Loaded ${STATE.stockDatabase.length} stocks`);
    } catch (error) {
        console.error('❌ Error loading stock data:', error);
    }
}

function saveSessionState() {
    try {
        const sessionToSave = {
            currentSessionId: STATE.currentSessionId,
            currentSymbol: STATE.currentSymbol,
            isSidebarCollapsed: STATE.isSidebarCollapsed,
        };
        localStorage.setItem(CONFIG.SESSION_STORAGE_KEY, JSON.stringify(sessionToSave));
    } catch (error) {
        console.error('Could not save session state:', error);
    }
}

function loadSessionState() {
    try {
        const savedSession = JSON.parse(localStorage.getItem(CONFIG.SESSION_STORAGE_KEY));
        if (savedSession) {
            STATE.currentSessionId = savedSession.currentSessionId || STATE.currentSessionId;
            STATE.currentSymbol = savedSession.currentSymbol || null;
            STATE.isSidebarCollapsed = savedSession.isSidebarCollapsed || false;
            if (STATE.currentSymbol) DOM.symbol.value = STATE.currentSymbol;
        }
    } catch (error) {
        console.error('Could not load session state:', error);
    }
    saveSessionState();
}

function showWelcomeMessage() {
    if (!STATE.currentSymbol && DOM.output) {
        DOM.output.innerHTML = `
            <div style="text-align: center; padding: 60px 20px; color: #6b7280;">
                <div style="font-size: 4rem; margin-bottom: 20px;">📊</div>
                <h2 style="color: #374151; margin-bottom: 10px;">Welcome to Stock Analysis</h2>
                <p>Search for a stock symbol or select from the sidebar to get started</p>
            </div>
        `;
    }
}

// ==================== EVENT LISTENERS & UI ====================
function initializeEventListeners() {
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

function handleAutocompleteInput(e) {
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

function handleAutocompleteKeydown(e) {
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

function handleSearchSubmit(e) {
    e.preventDefault();
    fetchData();
}

function showAutocomplete(stocks) {
    STATE.selectedIndex = -1;
    DOM.autocomplete.innerHTML = stocks.map(stock => `
        <div class="autocomplete-item" onclick="selectStock('${stock.symbol}')">
            <div class="ticker-symbol">${stock.symbol}</div>
            <div class="company-name">${stock.name}</div>
        </div>
    `).join('');
    DOM.autocomplete.classList.add('active');
}

function hideAutocomplete() {
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

function selectStock(symbol) {
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

// ==================== SIDEBAR ====================
function initializeSidebar() {
    createSidebarToggles();

    DOM.sidebarSearch.addEventListener('input', debounce((e) => {
        filterSidebarStocks(e.target.value.trim());
    }, CONFIG.DEBOUNCE_DELAY));

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

            // Check if click is outside of the sidebar and outside of the toggle button when sidebar is open
            if (!STATE.isSidebarCollapsed && !DOM.sidebar.contains(e.target) && !mobileToggle.contains(e.target)) {
                setSidebarCollapsed(true);
            }
        }
    });
}

function createSidebarToggles() {
    const mainContent = document.querySelector('.container');

    // Mobile Toggle
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

    // Desktop Toggle (hidden behind sidebar on load)
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

    // Button inside sidebar
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) sidebarToggle.addEventListener('click', toggleSidebar);
}

function toggleSidebar() {
    setSidebarCollapsed(!STATE.isSidebarCollapsed);
}

function setSidebarCollapsed(collapsed) {
    STATE.isSidebarCollapsed = collapsed;
    saveSessionState(); // Persist sidebar state
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
        DOM.sidebarStocks.innerHTML = `
            <div style="padding: 30px; text-align: center; color: #6b7280;">
                <div style="font-size: 2rem; margin-bottom: 10px;">📈</div>
                <div>Loading securities database...</div>
            </div>
        `;
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

    DOM.sidebarStocks.innerHTML = html;

    // Attach click listeners to new elements
    DOM.sidebarStocks.querySelectorAll('.sidebar-stock-item').forEach(item => {
        item.addEventListener('click', function() {
            selectStockFromSidebar(this.dataset.symbol);
            // On mobile, collapse sidebar after selection
            if (window.matchMedia('(max-width: 768px)').matches) {
                setSidebarCollapsed(true);
            }
        });
    });

    // Load the last symbol if it exists
    if (STATE.currentSymbol) {
        selectStockFromSidebar(STATE.currentSymbol);
    } else if (STATE.stockDatabase.length > 0) {
        // Default to the first stock if no current symbol is set
        selectStockFromSidebar(STATE.stockDatabase[0].symbol);
    }
}

function groupStocksByCategory(stocks) {
    const groups = {
        mostPopular: [], nifty50: [], usStocks: [], banking: [], tech: [], pharma: [],
        auto: [], energy: [], fmcg: [], metals: [], realty: [], midCap: [],
        smallCap: [], sectorETF: [], debtEtf: [], goldSilverETF: [], factor: [],
        liquid: [], bond: [], thematic: [], bse: [], other: []
    };

    stocks.forEach(stock => {
        const symbolUpper = stock.symbol.toUpperCase();
        const nameUpper = stock.name.toUpperCase();
        const isStockETF = symbolUpper.endsWith('ETF') || nameUpper.includes('ETF') || nameUpper.includes('EXCHANGE TRADED FUND');

        if (symbolUpper === 'RELIANCE' || symbolUpper === 'TCS' || symbolUpper === 'HDFCBANK' || symbolUpper === 'INFY' || symbolUpper === 'AAPL' || symbolUpper === 'MSFT') {
            groups.mostPopular.push(stock);
        }

        if (symbolUpper.includes('NIFTY') || symbolUpper.includes('BANKNIFTY')) {
            groups.nifty50.push(stock);
        } else if (symbolUpper.length <= 4 && symbolUpper.match(/^[A-Z]+$/)) {
            groups.usStocks.push(stock);
        } else if (nameUpper.includes('BANK') || nameUpper.includes('FINANCE') || nameUpper.includes('NBFC')) {
            (isStockETF ? groups.sectorETF : groups.banking).push(stock);
        } else if (nameUpper.includes('TECH') || nameUpper.includes('INFO') || nameUpper.includes('SOFTWARE')) {
            (isStockETF ? groups.sectorETF : groups.tech).push(stock);
        } else if (nameUpper.includes('PHARMA') || nameUpper.includes('HEALTH') || nameUpper.includes('DRUG')) {
            (isStockETF ? groups.sectorETF : groups.pharma).push(stock);
        } else if (nameUpper.includes('AUTO') || nameUpper.includes('MOTOR') || nameUpper.includes('VEHICLE')) {
            (isStockETF ? groups.sectorETF : groups.auto).push(stock);
        } else if (nameUpper.includes('ENERGY') || nameUpper.includes('POWER') || nameUpper.includes('OIL')) {
            (isStockETF ? groups.sectorETF : groups.energy).push(stock);
        } else if (!isStockETF && (nameUpper.includes('CONSUMER') || nameUpper.includes('FMCG'))) {
            groups.fmcg.push(stock);
        } else if (nameUpper.includes('METAL') || nameUpper.includes('STEEL') || nameUpper.includes('MINING')) {
            (isStockETF ? groups.sectorETF : groups.metals).push(stock);
        } else if (!isStockETF && nameUpper.includes('REAL')) {
            groups.realty.push(stock);
        } else if (nameUpper.includes('MIDCAP')) {
            (isStockETF ? groups.sectorETF : groups.midCap).push(stock);
        } else if (nameUpper.includes('SMALLCAP')) {
            (isStockETF ? groups.sectorETF : groups.smallCap).push(stock);
        } else if (isStockETF && (symbolUpper.includes('GOLD') || symbolUpper.includes('SILVER') || nameUpper.includes('GOLD') || nameUpper.includes('SILVER'))) {
            groups.goldSilverETF.push(stock);
        } else if (isStockETF && (nameUpper.includes('FACTOR') || nameUpper.includes('SMART BETA'))) {
            groups.factor.push(stock);
        } else if (isStockETF && (nameUpper.includes('LIQUID') || nameUpper.includes('DEBT'))) {
            groups.liquid.push(stock);
        } else if (isStockETF && (nameUpper.includes('BOND') || nameUpper.includes('G-SEC'))) {
            groups.bond.push(stock);
        } else if (isStockETF && (nameUpper.includes('THEMATIC'))) {
            groups.thematic.push(stock);
        } else if (symbolUpper.endsWith('BSE') || nameUpper.includes('BSE')) {
            groups.bse.push(stock);
        } else if (isStockETF) {
            groups.sectorETF.push(stock);
        } else {
            groups.other.push(stock);
        }
    });

    // Custom sorting for Nifty50 and Most Popular
    groups.nifty50.sort((a, b) => a.symbol.localeCompare(b.symbol));
    groups.mostPopular.sort((a, b) => a.symbol.localeCompare(b.symbol));

    return groups;
}

function getGroupName(groupKey) {
    const names = {
        mostPopular: '🔥 Most Popular', nifty50: '🇮🇳 Nifty 50 & Indices',
        banking: '🏦 Banking & Finance', tech: '💻 Technology (IT/Software)',
        pharma: '💊 Pharma & Healthcare', auto: '🚗 Automobile', energy: '⚡ Energy',
        fmcg: '🛒 FMCG & Consumer Goods', metals: '⚙️ Metals & Mining',
        realty: '🏙️ Realty', midCap: '🟡 MidCap', smallCap: '🔵 SmallCap',
        sectorETF: '📊 Sector ETFs', debtEtf: '💸 Debt ETFs', goldSilverETF: '🪙 Gold & Silver ETFs',
        factor: '🎯 Factor & Smart Beta', liquid: '💧 Liquid & Debt ETFs', bond: '📋 Bond & G-Sec ETFs',
        thematic: '🎨 Thematic ETFs', bse: '📈 BSE Listed', usStocks: '🇺🇸 US Stocks',
        other: '📂 Other Securities'
    };
    return names[groupKey] || groupKey;
}

function createSidebarStockItem(stock) {
    return `
        <div class="sidebar-stock-item" data-symbol="${stock.symbol}">
            <div class="sidebar-stock-symbol">${stock.symbol}</div>
            <div class="sidebar-stock-name">${stock.name}</div>
        </div>
    `;
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
    // 1. Update the search input
    DOM.symbol.value = symbol;
    hideAutocomplete();
    DOM.symbol.focus();

    // 2. Update the active state in the sidebar
    document.querySelectorAll('.sidebar-stock-item').forEach(item => item.classList.remove('active'));
    const sidebarItem = document.querySelector(`.sidebar-stock-item[data-symbol="${symbol}"]`);
    if (sidebarItem) {
        sidebarItem.classList.add('active');
        sidebarItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // 3. Set the current symbol and fetch data
    if (STATE.currentSymbol !== symbol) {
        STATE.currentSymbol = symbol;
        saveSessionState(); // Persist the new symbol
        updateChatContextIndicator(symbol); // Update chat context
        fetchData();
    }
}

// ==================== DATA FETCHING ====================

async function fetchData() {
    if (!STATE.currentSymbol) return;

    showLoading();
    hideError();
    DOM.output.innerHTML = '';

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

function showLoading() {
    DOM.loading.style.display = 'block';
}

function hideLoading() {
    DOM.loading.style.display = 'none';
}

function hideError() {
    DOM.error.style.display = 'none';
}

function showError(message) {
    DOM.error.innerHTML = `<strong>Error:</strong> ${message}`;
    DOM.error.style.display = 'block';
}

// ==================== DATA DISPLAY & CHARTS ====================

function displayData(data) {
    const companyInfo = STATE.stockDatabase.find(s => s.symbol === data.ticker) || { name: 'Technical Analysis Data' };
    DOM.output.innerHTML = `
        <div class="ticker-display">
            <div class="ticker-symbol-main">${data.ticker}</div>
            <div class="ticker-name-main">${companyInfo.name}</div>
        </div>
    `;

    const grid = document.createElement('div');
    grid.className = 'data-grid';

    const cards = [
        { id: 'visualization-card', title: 'Technical Charts & Visualizations', icon: '📊', contentHtml: createVisualizationContent(data), isOpen: false },
        { id: 'rule-based-card', title: 'Technical Analysis', icon: '🔍', contentHtml: createAnalysisContent(data.Rule_Based_Analysis), isOpen: false },
        ...(data.AI_Review ? [{ id: 'ai-review-card', title: 'AI Review & Summary', icon: '🤖', contentHtml: createAnalysisContent(data.AI_Review), isOpen: false }] : []),
        { id: 'ohlcv-card', title: 'Raw OHLCV Data', icon: '📈', contentHtml: createOhlcvTable(data.OHLCV), isOpen: false },
        { id: 'ma-rsi-card', title: 'Raw Technical Indicators', icon: '📉', contentHtml: createMaRsiContent(data.MA, data.RSI), isOpen: false },
        { id: 'macd-card', title: 'Raw MACD Data', icon: '🎯', contentHtml: createMacdTable(data.MACD), isOpen: false }
    ];

    cards.forEach(cardData => {
        const card = createDataCard(cardData);
        card.classList.add('full-width');
        card.querySelector('.card-header').addEventListener('click', function() {
            const content = card.querySelector('.card-content');
            const icon = card.querySelector('.dropdown-icon');
            const isCollapsed = content.classList.contains('collapsed');

            content.classList.toggle('collapsed', !isCollapsed);
            icon.classList.toggle('collapsed', !isCollapsed);

            // Re-render charts when their container becomes visible
            if (cardData.id === 'visualization-card' && isCollapsed) {
                renderCharts(data);
            }
        });
        grid.appendChild(card);
    });

    DOM.output.appendChild(grid);
    renderCharts(data);
}

function createDataCard({ id, title, icon, contentHtml, isOpen }) {
    const card = document.createElement('div');
    card.id = id;
    card.className = 'data-card';
    card.innerHTML = `
        <div class="card-header">
            <h2><span>${icon}</span>${title}</h2>
            <span class="dropdown-icon ${isOpen ? '' : 'collapsed'}">▼</span>
        </div>
        <div class="card-content ${isOpen ? '' : 'collapsed'}">
            ${contentHtml}
        </div>
    `;
    return card;
}

function createVisualizationContent(data) {
    if (!data.OHLCV?.length) {
        return '<div class="unavailable-notice"><strong>⚠️ Data Unavailable</strong><p>Cannot generate charts without OHLCV data.</p></div>';
    }

    const tabsHtml = `
        <div class="chart-tabs">
            <button class="chart-tab active" data-chart="ohlcv">Price & Volume</button>
            <button class="chart-tab" data-chart="movingAverages">Moving Averages</button>
            ${data.RSI?.length ? `<button class="chart-tab" data-chart="rsi">RSI</button>` : ''}
            ${data.MACD?.length ? `<button class="chart-tab" data-chart="macd">MACD</button>` : ''}
        </div>
    `;

    const chartContainers = `
        <div class="chart-container active" id="chart-ohlcv">
            <canvas id="ohlcvChart"></canvas>
            <canvas id="volumeChart" style="height: 100px; margin-top: 10px;"></canvas>
        </div>
        <div class="chart-container" id="chart-movingAverages">
            <canvas id="movingAveragesChart"></canvas>
        </div>
        ${data.RSI?.length ? `<div class="chart-container" id="chart-rsi"><canvas id="rsiChart"></canvas></div>` : ''}
        ${data.MACD?.length ? `<div class="chart-container" id="chart-macd"><canvas id="macdChart"></canvas></div>` : ''}
    `;

    setTimeout(() => {
        const chartTabs = document.querySelector('#visualization-card .chart-tabs');
        chartTabs?.addEventListener('click', (e) => {
            const button = e.target.closest('.chart-tab');
            if (!button) return;

            chartTabs.querySelectorAll('.chart-tab').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            const chartId = button.dataset.chart;

            document.querySelectorAll('#visualization-card .chart-container').forEach(container => {
                container.classList.remove('active');
            });
            document.getElementById(`chart-${chartId}`)?.classList.add('active');

            // Redraw the chart when its tab is clicked
            if (STATE.charts[chartId]) {
                STATE.charts[chartId].resize();
            }
        });
    }, 0); // Use setTimeout to ensure DOM elements are rendered

    return tabsHtml + chartContainers;
}

function createAnalysisContent(content) {
    if (!content) {
        return '<div class="unavailable-notice"><strong>⚠️ Analysis Unavailable</strong><p>Could not retrieve rule-based or AI analysis for this security.</p></div>';
    }
    // Convert markdown/text to HTML format
    let html = content.trim()
        .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>') // bold italic
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')           // bold
        .replace(/\*(.+?)\*/g, '<em>$1</em>')                     // italic
        .replace(/`(.+?)`/g, '<code>$1</code>')                   // code
        .replace(/~~(.+?)~~/g, '<del>$1</del>')                   // strikethrough
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');

    if (!html.startsWith('<')) html = '<p>' + html + '</p>';

    return `<div class="analysis-content">${html}</div>`;
}

function createOhlcvTable(data) {
    if (!data?.length) {
        return '<div class="unavailable-notice"><strong>⚠️ Data Unavailable</strong><p>No OHLCV data available.</p></div>';
    }

    return `
        <div class="table-scroll-wrapper">
            <div class="data-table">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.map(item => `
                            <tr>
                                <td>${item.Date || 'N/A'}</td>
                                <td>${formatPrice(item.Open)}</td>
                                <td>${formatPrice(item.High)}</td>
                                <td>${formatPrice(item.Low)}</td>
                                <td>${formatPrice(item.Close)}</td>
                                <td>${formatNumber(item.Volume)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
        <p style="font-size: 0.9rem; color: #6b7280; margin-top: 10px;">Showing latest ${data.length} trading sessions</p>
    `;
}

function createMaRsiContent(maData, rsiData) {
    let content = '';

    if (maData?.length) {
        content += `
            <h4>Moving Averages (Latest)</h4>
            <div class="data-table data-table-ma">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th><th>MA5</th><th>MA10</th><th>MA20</th><th>MA50</th><th>MA200</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${maData.slice(-CONFIG.MAX_CHART_POINTS).map(item => `
                            <tr>
                                <td>${item.Date || 'N/A'}</td>
                                <td>${formatPrice(item.MA5)}</td>
                                <td>${formatPrice(item.MA10)}</td>
                                <td>${formatPrice(item.MA20)}</td>
                                <td>${formatPrice(item.MA50)}</td>
                                <td>${formatPrice(item.MA200)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    if (rsiData?.length) {
        content += createRsiTable(rsiData);
    }

    if (!content) {
        return '<div class="unavailable-notice"><strong>⚠️ Data Unavailable</strong><p>No Moving Average or RSI data available.</p></div>';
    }

    return content;
}

function createRsiTable(rsiData) {
    return `
        <h4>Relative Strength Index (RSI) - Latest</h4>
        <div class="data-table data-table-rsi">
            <table>
                <thead>
                    <tr>
                        <th>Date</th><th>RSI</th><th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${rsiData.slice(-CONFIG.MAX_CHART_POINTS).map(item => {
                        const rsi = item.RSI;
                        const color = getRsiColor(rsi);
                        const background = getRsiBackground(rsi);
                        let status = 'Neutral';
                        if (rsi > 70) status = 'Overbought';
                        if (rsi < 30) status = 'Oversold';

                        return `
                            <tr>
                                <td>${item.Date || 'N/A'}</td>
                                <td style="color: ${color}; font-weight: 700;">${rsi != null ? rsi.toFixed(2) : 'N/A'}</td>
                                <td style="background: ${background}; color: ${color}; font-weight: 600; border-radius: 6px; padding: 4px 8px; font-size: 0.9em; text-align: center;">${status}</td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        </div>
        <p style="font-size: 0.85rem; color: #6b7280; margin-top: 10px;">RSI above 70 is considered Overbought, below 30 is Oversold.</p>
    `;
}

function createMacdTable(data) {
    if (!data?.length) {
        return '<div class="unavailable-notice"><strong>⚠️ Data Unavailable</strong><p>No MACD data available.</p></div>';
    }

    return `
        <h4>Moving Average Convergence Divergence (MACD) - Latest</h4>
        <div class="data-table data-table-macd">
            <table>
                <thead>
                    <tr>
                        <th>Date</th><th>MACD</th><th>Signal</th><th>Histogram</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.slice(-CONFIG.MAX_CHART_POINTS).map(item => {
                        const histClass = item.Histogram > 0 ? 'positive-hist' : (item.Histogram < 0 ? 'negative-hist' : '');
                        return `
                            <tr>
                                <td>${item.Date || 'N/A'}</td>
                                <td>${item.MACD != null ? item.MACD.toFixed(2) : 'N/A'}</td>
                                <td>${item.Signal != null ? item.Signal.toFixed(2) : 'N/A'}</td>
                                <td class="${histClass}">${item.Histogram != null ? item.Histogram.toFixed(2) : 'N/A'}</td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        </div>
        <p style="font-size: 0.85rem; color: #6b7280; margin-top: 10px;">Histogram is MACD minus Signal line. Positive suggests upward momentum.</p>
    `;
}


function renderCharts(data) {
    destroyExistingCharts();
    const latestData = data.OHLCV.slice(-CONFIG.MAX_CHART_POINTS);

    createOHLCVChart(latestData);
    if (data.RSI?.length) {
        const latestRSI = data.RSI.slice(-CONFIG.MAX_CHART_POINTS);
        createRSIChart(latestRSI, latestData);
    }
    if (data.MA?.length) {
        const latestMA = data.MA.slice(-CONFIG.MAX_CHART_POINTS);
        createMovingAveragesChart(latestMA, latestData);
    }
    if (data.MACD?.length) {
        const latestMACD = data.MACD.slice(-CONFIG.MAX_CHART_POINTS);
        createMACDChart(latestMACD, latestData);
    }
}

function destroyExistingCharts() {
    Object.values(STATE.charts).forEach(chart => chart?.destroy());
    STATE.charts = { ohlcv: null, rsi: null, movingAverages: null, macd: null };
}

function createOHLCVChart(ohlcvData) {
    const priceCtx = document.getElementById('ohlcvChart')?.getContext('2d');
    const volumeCtx = document.getElementById('volumeChart')?.getContext('2d');
    if (!priceCtx || !volumeCtx) return;

    const dates = ohlcvData.map(item => item.Date?.substring(5) || 'N/A');
    const closes = ohlcvData.map(item => item.Close);
    const volumes = ohlcvData.map(item => item.Volume);

    // Price Chart
    STATE.charts.ohlcv = new Chart(priceCtx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Close Price',
                    data: closes,
                    borderColor: 'rgb(102, 126, 234)', // var(--primary-purple)
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: 'origin',
                    pointRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: { display: true, text: 'Price Movement', color: '#374151' }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Date' }
                },
                y: {
                    title: { display: true, text: 'Price ($)' },
                    position: 'right'
                }
            }
        }
    });

    // Volume Chart
    STATE.charts.volume = new Chart(volumeCtx, {
        type: 'bar',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Volume',
                    data: volumes,
                    backgroundColor: 'rgba(55, 65, 81, 0.5)',
                    borderColor: 'rgba(55, 65, 81, 0.8)',
                    borderWidth: 1,
                    barPercentage: 0.8,
                    categoryPercentage: 0.8,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: { display: true, text: 'Trading Volume', color: '#374151', padding: { top: 0, bottom: 0 } }
            },
            scales: {
                x: {
                    display: false // Hide x-axis labels to align with price chart
                },
                y: {
                    title: { display: false },
                    position: 'right',
                    ticks: {
                        callback: function(value) {
                            return value.toExponential(0); // Display volume in exponential notation
                        }
                    }
                }
            }
        }
    });
}

function createRSIChart(rsiData, ohlcvData) {
    const ctx = document.getElementById('rsiChart')?.getContext('2d');
    if (!ctx) return;

    const dates = ohlcvData.map(item => item.Date?.substring(5) || 'N/A');
    const rsiValues = rsiData.map(item => item.RSI);

    STATE.charts.rsi = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'RSI (14)',
                    data: rsiValues,
                    borderColor: '#10b981', // var(--accent-green)
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    tension: 0.2,
                    pointRadius: 4,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: { display: true, text: 'Relative Strength Index (RSI)', color: '#374151' },
                annotation: {
                    annotations: {
                        overbought: {
                            type: 'line',
                            yMin: 70, yMax: 70, borderColor: '#ef4444', borderWidth: 1, borderDash: [5, 5]
                        },
                        oversold: {
                            type: 'line',
                            yMin: 30, yMax: 30, borderColor: '#ef4444', borderWidth: 1, borderDash: [5, 5]
                        }
                    }
                }
            },
            scales: {
                y: {
                    title: { display: true, text: 'RSI Value' },
                    min: 0,
                    max: 100
                }
            }
        }
    });
}

function createMovingAveragesChart(maData, ohlcvData) {
    const ctx = document.getElementById('movingAveragesChart')?.getContext('2d');
    if (!ctx) return;

    const dates = ohlcvData.map(item => item.Date?.substring(5) || 'N/A');
    const closes = ohlcvData.map(item => item.Close);

    STATE.charts.movingAverages = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Close Price',
                    data: closes,
                    borderColor: 'rgb(55, 65, 81)',
                    backgroundColor: 'rgba(55, 65, 81, 0.1)',
                    borderWidth: 2,
                    tension: 0.4
                },
                {
                    label: 'MA5',
                    data: maData.map(item => item.MA5),
                    borderColor: '#ef4444',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.4
                },
                {
                    label: 'MA10',
                    data: maData.map(item => item.MA10),
                    borderColor: '#10b981',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: 'Price & Moving Averages', color: '#374151' }
            },
            scales: {
                y: {
                    title: { display: true, text: 'Price ($)' }
                }
            }
        }
    });
}

function createMACDChart(macdData, ohlcvData) {
    const ctx = document.getElementById('macdChart')?.getContext('2d');
    if (!ctx) return;

    const dates = ohlcvData.map(item => item.Date?.substring(5) || 'N/A');
    const histogramData = macdData.map(item => item.Histogram);

    STATE.charts.macd = new Chart(ctx, {
        data: {
            labels: dates,
            datasets: [
                {
                    type: 'bar',
                    label: 'Histogram',
                    data: histogramData,
                    backgroundColor: histogramData.map(h => h > 0 ? 'rgba(16, 185, 129, 0.7)' : 'rgba(239, 68, 68, 0.7)')
                },
                {
                    type: 'line',
                    label: 'MACD Line',
                    data: macdData.map(item => item.MACD),
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    pointRadius: 4,
                },
                {
                    type: 'line',
                    label: 'Signal Line',
                    data: macdData.map(item => item.Signal),
                    borderColor: '#764ba2',
                    backgroundColor: 'rgba(118, 75, 162, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    pointRadius: 4,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: 'MACD Indicator', color: '#374151' }
            },
            scales: {
                y: {
                    title: { display: true, text: 'Value' }
                }
            }
        }
    });
}

// ==================== CHATBOT ====================

function initializeChat() {
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
    saveSessionState(); // Persist the new chat session ID
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
                    showAuthOverlay(); // Redirect to login on unauthorized
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

function updateChatContextIndicator(symbol) {
    if (DOM.contextSymbol) {
        DOM.contextSymbol.textContent = symbol || 'None';
        DOM.contextSymbol.style.color = symbol ? '#667eea' : '#ef4444';
    }
}
