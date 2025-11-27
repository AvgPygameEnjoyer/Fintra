// ==================== SIDEBAR HELPER FUNCTIONS ====================

export function groupStocksByCategory(stocks) {
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

    groups.nifty50.sort((a, b) => a.symbol.localeCompare(b.symbol));
    groups.mostPopular.sort((a, b) => a.symbol.localeCompare(b.symbol));

    return groups;
}

export function getGroupName(groupKey) {
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

export function createSidebarStockItem(stock) {
    return `
        <div class="sidebar-stock-item" data-symbol="${stock.symbol}">
            <div class="sidebar-stock-symbol">${stock.symbol}</div>
            <div class="sidebar-stock-name">${stock.name}</div>
        </div>
    `;
}