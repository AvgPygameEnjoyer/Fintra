let stockDatabase = [];
let selectedIndex = -1;
let filteredStocks = [];
let isSidebarCollapsed = false;

// DOM Elements
const symbolInput = document.getElementById('symbol');
const autocompleteDiv = document.getElementById('autocomplete');
const outputDiv = document.getElementById('output');
const loadingDiv = document.getElementById('loading');
const errorDiv = document.getElementById('error');
const searchBtn = document.getElementById('searchBtn');

// Initialize the application
document.addEventListener('DOMContentLoaded', async () => {
    errorDiv.style.display = 'none';
    loadingDiv.style.display = 'none';

    // Load stock database from JSON
    try {
        const response = await fetch('stock-data.json');
        const data = await response.json();
        stockDatabase = data.stocks;
        console.log('Loaded', stockDatabase.length, 'stocks');
    } catch (error) {
        console.error('Error loading stock data:', error);
        stockDatabase = []; // Fallback to empty array
    }

    initializeEventListeners();
    initializeSidebar();
});

function initializeEventListeners() {
    // Autocomplete functionality
    symbolInput.addEventListener('input', function(e) {
        const query = e.target.value.trim().toUpperCase();
        if (query.length === 0) {
            hideAutocomplete();
            return;
        }

        filteredStocks = stockDatabase.filter(stock =>
            stock.symbol.toUpperCase().includes(query) ||
            stock.name.toUpperCase().includes(query)
        ).slice(0, 8);

        if (filteredStocks.length > 0) {
            showAutocomplete(filteredStocks);
        } else {
            hideAutocomplete();
        }
    });

    symbolInput.addEventListener('keydown', function(e) {
        const items = autocompleteDiv.querySelectorAll('.autocomplete-item');
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
            updateSelection(items);
        }
        else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = Math.max(selectedIndex - 1, -1);
            updateSelection(items);
        }
        else if (e.key === 'Enter') {
            e.preventDefault();
            if (selectedIndex >= 0) {
                items[selectedIndex].click();
            } else {
                // Trigger search if no autocomplete item is selected
                const form = document.querySelector('.search-form');
                if (form) form.requestSubmit();
            }
        }
        else if (e.key === 'Escape') {
            hideAutocomplete();
        }
    });

    document.addEventListener('click', function(e) {
        if (!e.target.closest('.input-wrapper')) {
            hideAutocomplete();
        }
    });

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', function(e) {
        if (window.matchMedia('(max-width: 768px)').matches) {
            const sidebar = document.getElementById('sidebar');
            const mobileToggle = document.querySelector('.mobile-sidebar-toggle');
            
            if (!sidebar.contains(e.target) && 
                !mobileToggle.contains(e.target) && 
                !isSidebarCollapsed) {
                setSidebarCollapsed(true);
            }
        }
    });

    // Handle escape key to close sidebar
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && !isSidebarCollapsed) {
            setSidebarCollapsed(true);
        }
    });
}

// ==================== SIDEBAR FUNCTIONS - COMPLETELY FIXED ====================

function initializeSidebar() {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarSearch = document.getElementById('sidebarSearch');

    // Create mobile toggle button (for mobile devices)
    const mobileToggle = document.createElement('button');
    mobileToggle.innerHTML = '☰';
    mobileToggle.className = 'mobile-sidebar-toggle';
    mobileToggle.setAttribute('aria-label', 'Toggle sidebar');
    mobileToggle.addEventListener('click', toggleSidebar);
    document.body.appendChild(mobileToggle);

    // Create desktop toggle button (always visible on desktop)
    const desktopToggle = document.createElement('button');
    desktopToggle.innerHTML = '☰';
    desktopToggle.className = 'desktop-sidebar-toggle';
    desktopToggle.setAttribute('aria-label', 'Toggle sidebar');
    desktopToggle.addEventListener('click', toggleSidebar);
    document.body.appendChild(desktopToggle);

    // Sidebar toggle event
    sidebarToggle.addEventListener('click', toggleSidebar);

    // Sidebar search functionality
    sidebarSearch.addEventListener('input', function(e) {
        filterSidebarStocks(e.target.value.trim());
    });

    // Load stocks into sidebar
    loadSidebarStocks();

    // Set initial sidebar state based on viewport
    const isMobile = window.matchMedia('(max-width: 768px)').matches;
    setSidebarCollapsed(isMobile);

    // Handle viewport changes
    window.matchMedia('(max-width: 768px)').addEventListener('change', (e) => {
        setSidebarCollapsed(e.matches);
    });

    console.log('Sidebar initialized - Mobile:', isMobile, 'Collapsed:', isMobile);
}

function setSidebarCollapsed(collapsed) {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.querySelector('.container');
    const mobileToggle = document.querySelector('.mobile-sidebar-toggle');
    const desktopToggle = document.querySelector('.desktop-sidebar-toggle');

    isSidebarCollapsed = collapsed;

    // Update sidebar state
    if (sidebar) {
        if (collapsed) {
            sidebar.classList.add('sidebar-collapsed');
        } else {
            sidebar.classList.remove('sidebar-collapsed');
        }
    }
    
    // Update main content state
    if (mainContent) {
        if (collapsed) {
            mainContent.classList.add('sidebar-collapsed');
        } else {
            mainContent.classList.remove('sidebar-collapsed');
        }
    }
    
    // Update toggle buttons
    if (mobileToggle) {
        mobileToggle.innerHTML = isSidebarCollapsed ? '☰' : '✕';
        if (!isSidebarCollapsed && window.matchMedia('(max-width: 768px)').matches) {
            mobileToggle.style.left = '300px';
        } else {
            mobileToggle.style.left = '20px';
        }
    }

    if (desktopToggle) {
        desktopToggle.innerHTML = isSidebarCollapsed ? '☰' : '✕';
        if (!isSidebarCollapsed && window.matchMedia('(min-width: 769px)').matches) {
            desktopToggle.style.left = '340px';
        } else {
            desktopToggle.style.left = '20px';
        }
    }

    console.log('Sidebar collapsed:', isSidebarCollapsed);
}
function toggleSidebar() {
    setSidebarCollapsed(!isSidebarCollapsed);
}

function loadSidebarStocks() {
    const sidebarStocks = document.getElementById('sidebarStocks');

    if (!stockDatabase || stockDatabase.length === 0) {
        sidebarStocks.innerHTML = `
            <div style="padding: 30px; text-align: center; color: #6b7280;">
                <div style="font-size: 2rem; margin-bottom: 10px;">📈</div>
                <div>Loading stocks database...</div>
            </div>
        `;
        return;
    }

    // Group stocks by category for better organization
    const groupedStocks = groupStocksByCategory(stockDatabase);
    let html = '';

    // Add Most Popular ETFs group
    if (groupedStocks.mostPopular.length > 0) {
        html += `
            <div class="sidebar-stock-group">
                <div class="sidebar-group-header">🌟 Most Popular ETFs</div>
                ${groupedStocks.mostPopular.map(stock => createSidebarStockItem(stock)).join('')}
            </div>
        `;
    }

    // Add Major Fund Houses group
    if (groupedStocks.majorFundHouses.length > 0) {
        html += `
            <div class="sidebar-stock-group">
                <div class="sidebar-group-header">🏦 Major Fund Houses</div>
                ${groupedStocks.majorFundHouses.map(stock => createSidebarStockItem(stock)).join('')}
            </div>
        `;
    }

    // Add other groups
    const otherGroups = [
        'kotak', 'icici', 'mirae', 'motilal', 'international', 
        'sector', 'gold', 'midSmall', 'factor', 'liquid', 
        'bond', 'niche', 'bse', 'internationalStocks'
    ];

    otherGroups.forEach(group => {
        if (groupedStocks[group] && groupedStocks[group].length > 0) {
            const groupName = getGroupDisplayName(group);
            html += `
                <div class="sidebar-stock-group">
                    <div class="sidebar-group-header">${groupName}</div>
                    ${groupedStocks[group].map(stock => createSidebarStockItem(stock)).join('')}
                </div>
            `;
        }
    });

    sidebarStocks.innerHTML = html;

    // Add click events to sidebar items
    sidebarStocks.querySelectorAll('.sidebar-stock-item').forEach(item => {
        item.addEventListener('click', function() {
            const symbol = this.getAttribute('data-symbol');
            selectStockFromSidebar(symbol);
        });
    });

    console.log('Sidebar stocks loaded:', stockDatabase.length, 'stocks in', Object.keys(groupedStocks).length, 'groups');
}

function groupStocksByCategory(stocks) {
    const groups = {
        mostPopular: [],
        majorFundHouses: [],
        kotak: [],
        icici: [],
        mirae: [],
        motilal: [],
        international: [],
        sector: [],
        gold: [],
        midSmall: [],
        factor: [],
        liquid: [],
        bond: [],
        niche: [],
        bse: [],
        internationalStocks: []
    };

    stocks.forEach(stock => {
        // Most Popular ETFs
        if (['NIFTYBEES.NS', 'BANKBEES.NS', 'ITBEES.NS', 'GOLDBEES.NS', 'JUNIORBEES.NS', 'SILVERBEES.NS'].includes(stock.symbol)) {
            groups.mostPopular.push(stock);
        }
        // Major Fund Houses
        else if (stock.symbol.includes('UTI') || stock.symbol.includes('HDFC') || stock.symbol.includes('SBI') || stock.symbol.includes('AXIS') || stock.symbol === 'ICICIB22.NS') {
            groups.majorFundHouses.push(stock);
        }
        // Kotak
        else if (stock.symbol.includes('1.NS') || stock.name.includes('Kotak')) {
            groups.kotak.push(stock);
        }
        // ICICI
        else if (stock.symbol.includes('IETF') || stock.name.includes('ICICI')) {
            groups.icici.push(stock);
        }
        // Mirae Asset
        else if (stock.symbol.includes('MA') || stock.name.includes('Mirae')) {
            groups.mirae.push(stock);
        }
        // Motilal Oswal
        else if (stock.symbol.includes('MO') || stock.name.includes('Motilal')) {
            groups.motilal.push(stock);
        }
        // International ETFs
        else if (stock.symbol.includes('HKG') || stock.name.includes('Hang Seng') || stock.name.includes('NASDAQ') || stock.name.includes('S&P')) {
            groups.international.push(stock);
        }
        // Sector & Theme ETFs
        else if (stock.name.includes('IT') || stock.name.includes('Consumption') || stock.name.includes('EV') || stock.name.includes('Manufacturing') || stock.name.includes('Pharma') || stock.name.includes('Infrastructure')) {
            groups.sector.push(stock);
        }
        // Gold & Silver
        else if (stock.name.includes('Gold') || stock.name.includes('Silver')) {
            groups.gold.push(stock);
        }
        // Mid & Small Cap
        else if (stock.name.includes('Midcap') || stock.name.includes('Smallcap')) {
            groups.midSmall.push(stock);
        }
        // Factor & Smart Beta
        else if (stock.name.includes('Alpha') || stock.name.includes('Value') || stock.name.includes('Low Volatility') || stock.name.includes('Momentum') || stock.name.includes('Quality')) {
            groups.factor.push(stock);
        }
        // Liquid & Debt
        else if (stock.name.includes('Liquid') || stock.name.includes('Debt')) {
            groups.liquid.push(stock);
        }
        // Bond ETFs
        else if (stock.name.includes('Bond') || stock.name.includes('Gilt') || stock.symbol.includes('BBETF') || stock.symbol.includes('EBBETF')) {
            groups.bond.push(stock);
        }
        // BSE-specific
        else if (stock.symbol.includes('.BO') || stock.name.includes('BSE') || stock.name.includes('Sensex')) {
            groups.bse.push(stock);
        }
        // International Stocks
        else if (['AAPL', 'MSFT', 'GOOGL', 'TSLA'].includes(stock.symbol)) {
            groups.internationalStocks.push(stock);
        }
        // Niche ETFs
        else {
            groups.niche.push(stock);
        }
    });

    return groups;
}

function getGroupDisplayName(groupKey) {
    const names = {
        mostPopular: '🌟 Most Popular ETFs',
        majorFundHouses: '🏦 Major Fund Houses',
        kotak: '📊 Kotak ETFs',
        icici: '🔷 ICICI Prudential ETFs',
        mirae: '🚀 Mirae Asset ETFs',
        motilal: '📈 Motilal Oswal ETFs',
        international: '🌍 International ETFs',
        sector: '🏭 Sector & Theme ETFs',
        gold: '🥇 Gold & Silver ETFs',
        midSmall: '📊 Mid & Small Cap ETFs',
        factor: '🎯 Factor & Smart Beta ETFs',
        liquid: '💧 Liquid & Debt ETFs',
        bond: '📋 Bond & G-Sec ETFs',
        niche: '🔍 Niche ETFs',
        bse: '📈 BSE ETFs',
        internationalStocks: '🌎 International Stocks'
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
    const sidebarStocks = document.getElementById('sidebarStocks');
    const allItems = sidebarStocks.querySelectorAll('.sidebar-stock-item');
    const groupHeaders = sidebarStocks.querySelectorAll('.sidebar-group-header');

    if (!query) {
        // Show all items and groups if no query
        allItems.forEach(item => {
            item.style.display = 'flex';
        });
        groupHeaders.forEach(header => {
            header.parentElement.style.display = 'block';
        });
        return;
    }

    const lowerQuery = query.toLowerCase();

    // First, hide all items and show only matching ones
    allItems.forEach(item => {
        const symbol = item.querySelector('.sidebar-stock-symbol').textContent.toLowerCase();
        const name = item.querySelector('.sidebar-stock-name').textContent.toLowerCase();

        if (symbol.includes(lowerQuery) || name.includes(lowerQuery)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });

    // Show/hide group headers based on whether they have visible items
    groupHeaders.forEach(header => {
        const group = header.parentElement;
        const itemsInGroup = group.querySelectorAll('.sidebar-stock-item');
        const hasVisibleInGroup = Array.from(itemsInGroup).some(item => 
            item.style.display !== 'none'
        );
        
        group.style.display = hasVisibleInGroup ? 'block' : 'none';
    });
}

function selectStockFromSidebar(symbol) {
    // Populate the search bar
    symbolInput.value = symbol;

    // Hide autocomplete if open
    hideAutocomplete();

    // Clear any existing results
    outputDiv.innerHTML = '';
    errorDiv.style.display = 'none';

    // Highlight the selected item in sidebar
    const allItems = document.querySelectorAll('.sidebar-stock-item');
    allItems.forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('data-symbol') === symbol) {
            item.classList.add('active');
            // Scroll into view
            item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    });

    // Auto-collapse sidebar on mobile after selection
    if (window.matchMedia('(max-width: 768px)').matches) {
        setSidebarCollapsed(true);
    }

    // Auto-fetch data for the selected stock
    fetchDataForSymbol(symbol);
}

async function fetchDataForSymbol(symbol) {
    // Show loading state
    loadingDiv.style.display = 'block';
    searchBtn.disabled = true;
    searchBtn.textContent = 'Loading...';

    try {
        const response = await fetch('https://stock-dashboard-fqtn.onrender.com/get_data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ symbol: symbol }),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || `Server responded with status ${response.status}`);
        }

        displayData(result);
    } catch (error) {
        errorDiv.textContent = `Error: ${error.message}`;
        errorDiv.style.display = 'block';
        console.error('Fetch error:', error);
    } finally {
        loadingDiv.style.display = 'none';
        searchBtn.disabled = false;
        searchBtn.textContent = 'Get Data';
    }
}

// ==================== AUTCOMPLETE FUNCTIONS ====================

function showAutocomplete(stocks) {
    selectedIndex = -1;
    autocompleteDiv.innerHTML = stocks.map((stock) => `
        <div class="autocomplete-item" onclick="selectStock('${stock.symbol}')">
            <div class="ticker-symbol">${stock.symbol}</div>
            <div class="company-name">${stock.name}</div>
        </div>
    `).join('');
    autocompleteDiv.classList.add('active');
}

function hideAutocomplete() {
    autocompleteDiv.classList.remove('active');
    selectedIndex = -1;
}

function updateSelection(items) {
    items.forEach((item, index) => {
        if (index === selectedIndex) {
            item.classList.add('selected');
            item.scrollIntoView({ block: 'nearest' });
        }
        else {
            item.classList.remove('selected');
        }
    });
    if (selectedIndex >= 0) {
        symbolInput.value = items[selectedIndex].querySelector('.ticker-symbol').textContent;
    }
}

function selectStock(symbol) {
    symbolInput.value = symbol;
    hideAutocomplete();
    symbolInput.focus();

    // Also highlight in sidebar
    const sidebarItem = document.querySelector(`.sidebar-stock-item[data-symbol="${symbol}"]`);
    if (sidebarItem) {
        const allItems = document.querySelectorAll('.sidebar-stock-item');
        allItems.forEach(item => item.classList.remove('active'));
        sidebarItem.classList.add('active');
        sidebarItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// ==================== DATA DISPLAY FUNCTIONS ====================

// API call to fetch stock data
async function fetchData(event) {
    if (event) event.preventDefault();

    const symbol = symbolInput.value.toUpperCase().trim();

    if (!symbol) {
        errorDiv.textContent = 'Please enter a stock symbol';
        errorDiv.style.display = 'block';
        return;
    }

    outputDiv.innerHTML = '';
    errorDiv.style.display = 'none';
    loadingDiv.style.display = 'block';
    searchBtn.disabled = true;
    searchBtn.textContent = 'Loading...';
    hideAutocomplete();

    try {
        const response = await fetch('https://stock-dashboard-fqtn.onrender.com/get_data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ symbol: symbol }),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || `Server responded with status ${response.status}`);
        }

        displayData(result);
    } catch (error) {
        errorDiv.textContent = `Error: ${error.message}`;
        errorDiv.style.display = 'block';
        console.error('Fetch error:', error);
    } finally {
        loadingDiv.style.display = 'none';
        searchBtn.disabled = false;
        searchBtn.textContent = 'Get Data';
    }
}

// Display the fetched data
function displayData(data) {
    const companyInfo = stockDatabase.find(s => s.symbol === data.ticker) || { name: 'Technical Analysis Data' };
    const companyName = companyInfo.name;

    outputDiv.innerHTML = `
        <div class="ticker-display">
            <div class="ticker-symbol-main">${data.ticker}</div>
            <div class="ticker-name-main">${companyName}</div>
        </div>
    `;

    const grid = document.createElement('div');
    grid.className = 'data-grid';

    // 1. Rule-Based Analysis (Primary Analysis - Always Available)
    const ruleBasedCard = createDataCard({
        id: 'rule-based-card',
        title: 'Technical Analysis',
        icon: '📊',
        contentHtml: createAnalysisContent(data.Rule_Based_Analysis),
        isOpen: false
    });
    ruleBasedCard.classList.add('full-width');
    ruleBasedCard.querySelector('.card-header').addEventListener('click', () => toggleCard(ruleBasedCard));
    grid.appendChild(ruleBasedCard);

    // 2. AI Review (Optional - May be unavailable)
    if (data.AI_Review) {
        const aiReviewCard = createDataCard({
            id: 'ai-review-card',
            title: 'AI Review & Summary',
            icon: '🤖',
            contentHtml: createAnalysisContent(data.AI_Review),
            isOpen: false
        });
        aiReviewCard.classList.add('full-width');
        aiReviewCard.querySelector('.card-header').addEventListener('click', () => toggleCard(aiReviewCard));
        grid.appendChild(aiReviewCard);
    }

    // 3. OHLCV Card
    const ohlcvCard = createDataCard({
        id: 'ohlcv-card',
        title: 'Candlestick Data (OHLCV)',
        icon: '📈',
        contentHtml: createOhlcvTable(data.OHLCV),
        isOpen: false
    });
    ohlcvCard.classList.add('full-width');
    ohlcvCard.querySelector('.card-header').addEventListener('click', () => toggleCard(ohlcvCard));
    grid.appendChild(ohlcvCard);

    // 4. MA & RSI Card
    const maRsiCard = createDataCard({
        id: 'ma-rsi-card',
        title: 'Moving Averages & RSI',
        icon: '📉',
        contentHtml: createMaRsiContent(data.MA, data.RSI),
        isOpen: false
    });
    maRsiCard.classList.add('full-width');
    maRsiCard.querySelector('.card-header').addEventListener('click', () => toggleCard(maRsiCard));
    grid.appendChild(maRsiCard);

    // 5. MACD Card
    const macdCard = createDataCard({
        id: 'macd-card',
        title: 'MACD, Signal & Histogram',
        icon: '🎯',
        contentHtml: createMacdTable(data.MACD),
        isOpen: false
    });
    macdCard.classList.add('full-width');
    macdCard.querySelector('.card-header').addEventListener('click', () => toggleCard(macdCard));
    grid.appendChild(macdCard);

    outputDiv.appendChild(grid);

    // Auto-expand the first card for better UX
    setTimeout(() => {
        const firstCard = grid.querySelector('.data-card');
        if (firstCard) toggleCard(firstCard);
    }, 100);
}

// Card creation and management
function createDataCard({ id, title, icon, contentHtml, isOpen = false }) {
    const card = document.createElement('div');
    card.className = 'data-card';
    if (id) {
        card.id = id;
    }

    const contentClass = isOpen ? '' : 'collapsed';
    const iconClass = isOpen ? '' : 'collapsed';

    card.innerHTML = `
        <div class="card-header">
            <h2><span role="img" aria-label="${title} icon">${icon}</span> ${title}</h2>
            <span class="dropdown-icon ${iconClass}">▼</span>
        </div>
        <div class="card-content ${contentClass}">
            ${contentHtml}
        </div>
    `;
    return card;
}

function toggleCard(cardElement) {
    const content = cardElement.querySelector('.card-content');
    const icon = cardElement.querySelector('.dropdown-icon');

    const isCurrentlyCollapsed = content.classList.contains('collapsed');

    if (isCurrentlyCollapsed) {
        content.classList.remove('collapsed');
        icon.classList.remove('collapsed');
    } else {
        content.classList.add('collapsed');
        icon.classList.add('collapsed');
    }
}

// Data table creation functions
function createOhlcvTable(data) {
    if (!data || data.length === 0) {
        return '<div class="unavailable-notice"><strong>⚠️ Data Unavailable</strong><p>No OHLCV data available for this stock.</p></div>';
    }

    const limitedData = data.slice(0, 7);
    return `
        <div class="table-scroll-wrapper">
            <div class="data-table">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Open</th>
                            <th>High</th>
                            <th>Low</th>
                            <th>Close</th>
                            <th>Volume</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${limitedData.map(item => `
                            <tr>
                                <td>${item.Date || 'N/A'}</td>
                                <td>${item.Open != null ? '$' + item.Open.toFixed(2) : 'N/A'}</td>
                                <td>${item.High != null ? '$' + item.High.toFixed(2) : 'N/A'}</td>
                                <td>${item.Low != null ? '$' + item.Low.toFixed(2) : 'N/A'}</td>
                                <td>${item.Close != null ? '$' + item.Close.toFixed(2) : 'N/A'}</td>
                                <td>${item.Volume != null ? item.Volume.toLocaleString() : 'N/A'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
        <p style="font-size: 0.9rem; color: #6b7280; margin-top: 10px;">Showing latest ${limitedData.length} trading sessions</p>
    `;
}

function createMaRsiContent(maData, rsiData) {
    if (!maData || maData.length === 0) {
        return '<div class="unavailable-notice"><strong>⚠️ Data Unavailable</strong><p>No Moving Average data available for this stock.</p></div>';
    }

    const limitedMaData = maData.slice(0, 7);
    const combinedData = limitedMaData.map((maItem, index) => {
        const rsiValue = rsiData && rsiData[index] ? rsiData[index] : null;
        return {
            Date: maItem.Date,
            MA5: maItem.MA5,
            MA10: maItem.MA10,
            RSI: rsiValue
        };
    });

    return `
        <div class="table-scroll-wrapper">
            <div class="data-table">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>MA5 (Short)</th>
                            <th>MA10 (Long)</th>
                            <th>RSI</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${combinedData.map(item => `
                            <tr>
                                <td>${item.Date}</td>
                                <td>${item.MA5 != null ? '$' + item.MA5.toFixed(2) : 'N/A'}</td>
                                <td>${item.MA10 != null ? '$' + item.MA10.toFixed(2) : 'N/A'}</td>
                                <td style="font-weight: 600; color: ${getRsiColor(item.RSI)}">${item.RSI != null ? item.RSI.toFixed(2) : 'N/A'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>

        <div style="padding-top: 20px;">
            <h3 style="color: var(--primary-purple); font-size: 1.1rem; margin-bottom: 15px;">RSI Overview (Latest ${combinedData.length} Days)</h3>
            <div class="rsi-grid">
                ${combinedData.map(item => `
                    <div class="rsi-item">
                        <strong>${item.Date ? item.Date.substring(5) : 'N/A'}</strong>
                        <span class="rsi-value" style="color: ${getRsiColor(item.RSI)}; background: ${getRsiBackground(item.RSI)}">
                            ${item.RSI != null ? item.RSI.toFixed(2) : 'N/A'}
                        </span>
                    </div>
                `).join('')}
            </div>
            <div style="margin-top: 15px; padding: 12px; background: #f0f9ff; border-radius: 8px; border-left: 4px solid var(--primary-purple);">
                <p style="font-size: 0.9rem; color: #374151; margin: 0;">
                    <strong>RSI Guide:</strong> 
                    <span style="color: #ef4444;">Above 70 = Overbought</span> • 
                    <span style="color: #10b981;">Below 30 = Oversold</span> • 
                    <span style="color: #6b7280;">30-70 = Neutral</span>
                </p>
            </div>
        </div>
    `;
}

function getRsiColor(rsi) {
    if (rsi === null || rsi === undefined) return '#6b7280';
    if (rsi > 70) return '#ef4444';
    if (rsi < 30) return '#10b981';
    return '#6b7280';
}

function getRsiBackground(rsi) {
    if (rsi === null || rsi === undefined) return '#f3f4f6';
    if (rsi > 70) return '#fef2f2';
    if (rsi < 30) return '#f0fdf4';
    return '#f8fafc';
}

function createMacdTable(data) {
    if (!data || data.length === 0) {
        return '<div class="unavailable-notice"><strong>⚠️ Data Unavailable</strong><p>No MACD data available for this stock.</p></div>';
    }

    const limitedData = data.slice(0, 7);
    return `
        <div class="table-scroll-wrapper">
            <div class="data-table">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>MACD Line</th>
                            <th>Signal Line</th>
                            <th>Histogram</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${limitedData.map(item => {
                            const histClass = item.Histogram > 0 ? 'positive-hist' : (item.Histogram < 0 ? 'negative-hist' : '');
                            return `
                            <tr>
                                <td>${item.Date || 'N/A'}</td>
                                <td>${item.MACD != null ? item.MACD.toFixed(3) : 'N/A'}</td>
                                <td>${item.Signal != null ? item.Signal.toFixed(3) : 'N/A'}</td>
                                <td class="${histClass}">${item.Histogram != null ? item.Histogram.toFixed(3) : 'N/A'}</td>
                            </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        </div>
        <div style="margin-top: 15px; padding: 12px; background: #f8fafc; border-radius: 8px;">
            <p style="font-size: 0.9rem; color: #374151; margin: 0;">
                <strong>MACD Signals:</strong> 
                <span style="color: var(--accent-green);">Positive Histogram = Bullish</span> • 
                <span style="color: #ef4444;">Negative Histogram = Bearish</span>
            </p>
        </div>
    `;
}

function createAnalysisContent(text) {
    if (!text) {
        return `<div class="unavailable-notice">
            <strong>⚠️ Analysis Unavailable</strong>
            <p>This analysis is currently unavailable. Please check the technical data in other sections.</p>
        </div>`;
    }

    let htmlContent = text;

    // Convert markdown to HTML
    htmlContent = htmlContent.replace(/###\s*(.*)/g, '<h3>$1</h3>');
    htmlContent = htmlContent.replace(/####\s*(.*)/g, '<h4>$1</h4>');
    htmlContent = htmlContent.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    htmlContent = htmlContent.replace(/\*(.*?)\*/g, '<em>$1</em>');
    htmlContent = htmlContent.replace(/---/g, '<hr>');
    htmlContent = htmlContent.replace(/\n\n/g, '</p><p>');
    htmlContent = htmlContent.replace(/\n/g, '<br>');

    // Wrap in paragraph if not already wrapped
    if (!htmlContent.startsWith('<')) {
        htmlContent = '<p>' + htmlContent + '</p>';
    }

    return `<div class="analysis-content">${htmlContent}</div>`;
}

// Export functions for global access
window.selectStock = selectStock;
window.fetchData = fetchData;
window.toggleCard = toggleCard;

