// ==================== DATA DISPLAY ====================
import { STATE, formatPrice, formatNumber, getRsiColor, getRsiBackground, CONFIG } from './config.js';
import { renderCharts } from './charts.js';

export function displayData(data) {
    const companyInfo = STATE.stockDatabase.find(s => s.symbol === data.ticker) || { name: 'Technical Analysis Data' };
    document.getElementById('output').innerHTML = `
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
        ...(data.AI_Review ? [{ id: 'ai-review-card', title: 'AI Review & Summary', icon: '🤖', contentHtml: createAnalysisContent(data.AI_Review), isOpen: true }] : []),
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

            if (cardData.id === 'visualization-card' && isCollapsed) {
                renderCharts(data);
            }
        });
        grid.appendChild(card);
    });

    document.getElementById('output').appendChild(grid);
    renderCharts(data);
}

function createDataCard({ id, title, icon, contentHtml, isOpen }) {
    const card = document.createElement('div');
    card.id = id;
    card.className = 'data-card';

    const periodSelectorHtml = (id === 'ohlcv-card' || id === 'ma-rsi-card' || id === 'macd-card') ? `
        <div class="period-selector">
            <label>View:</label>
            <select class="period-select" data-target-card="${id}">
                <option value="7" selected>Last 7 Days</option>
                <option value="15">Last 15 Days</option>
                <option value="30">Last 30 Days</option>
            </select>
        </div>
    ` : '';

    card.innerHTML = `
        <div class="card-header">
            <div class="card-title">
                <h2><span>${icon}</span>${title}</h2>
            </div>
            ${periodSelectorHtml}
            <button class="dropdown-toggle"><span class="dropdown-icon ${isOpen ? '' : 'collapsed'}">▼</span></button>
        </div>
        <div class="card-content ${isOpen ? '' : 'collapsed'}">
            ${contentHtml}
        </div>
    `;
    return card;
}

document.addEventListener('change', function(e) {
    if (e.target.classList.contains('period-select')) {
        const cardId = e.target.dataset.targetCard;
        const days = parseInt(e.target.value, 10);
        const tableBody = document.querySelector(`#${cardId} tbody`);
        if (!tableBody) return;

        const allRows = Array.from(tableBody.querySelectorAll('tr'));
        allRows.forEach((row, index) => {
            // Show rows from the end of the list
            row.style.display = (index >= allRows.length - days) ? '' : 'none';
        });
    }
});

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

    return tabsHtml + chartContainers;
}

function createAnalysisContent(content) {
    if (!content) {
        return '<div class="unavailable-notice"><strong>⚠️ Analysis Unavailable</strong><p>Could not retrieve rule-based or AI analysis for this security.</p></div>';
    }
    let html = content.trim()
        .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`(.+?)`/g, '<code>$1</code>')
        .replace(/~~(.+?)~~/g, '<del>$1</del>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');

    if (!html.startsWith('<')) html = '<p>' + html + '</p>';

    return `<div class="analysis-content">${html}</div>`;
}

document.addEventListener('click', function(e) {
    // Event delegation for chart tabs
    const chartTab = e.target.closest('.chart-tab');
    if (chartTab && e.target.closest('#visualization-card')) {
        const chartTabsContainer = chartTab.parentElement;
        
        chartTabsContainer.querySelectorAll('.chart-tab').forEach(btn => btn.classList.remove('active'));
        chartTab.classList.add('active');

        const chartId = chartTab.dataset.chart;

        document.querySelectorAll('#visualization-card .chart-container').forEach(container => {
            container.classList.remove('active');
        });
        const activeChartContainer = document.getElementById(`chart-${chartId}`);
        if (activeChartContainer) {
            activeChartContainer.classList.add('active');
        }

        // Resize chart to ensure it renders correctly when shown
        if (STATE.charts[chartId]) {
            STATE.charts[chartId].resize();
        }
    }
});

function createOhlcvTable(data) {
    if (!data?.length) {
        return '<div class="unavailable-notice"><strong>⚠️ Data Unavailable</strong><p>No OHLCV data available.</p></div>';
    }

    return `
        <div class="table-scroll-wrapper">
            <div class="data-table">
                <table>
                    <thead>
                        <tr><th>Date</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th></tr>
                    </thead>
                    <tbody>
                        ${data.map((item, index) => `
                            <tr style="${index < data.length - 7 ? 'display: none;' : ''}">
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
                    <thead><tr><th>Date</th><th>MA5</th><th>MA10</th><th>MA20</th></tr></thead>
                    <tbody>
                        ${maData.map((item, index) => `
                            <tr style="${index < maData.length - 7 ? 'display: none;' : ''}">
                                <td>${item.Date || 'N/A'}</td>
                                <td>${formatPrice(item.MA5)}</td>
                                <td>${formatPrice(item.MA10)}</td>
                                <td>${formatPrice(item.MA20)}</td>
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
                <thead><tr><th>Date</th><th>RSI</th><th>Status</th></tr></thead>
                <tbody>
                    ${rsiData.map((item, index) => {
                        const rsi = item.RSI;
                        const color = getRsiColor(rsi);
                        const background = getRsiBackground(rsi);
                        let status = 'Neutral';
                        if (rsi > 70) status = 'Overbought';
                        if (rsi < 30) status = 'Oversold';

                        return `
                            <tr style="${index < rsiData.length - 7 ? 'display: none;' : ''}">
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
                <thead><tr><th>Date</th><th>MACD</th><th>Signal</th><th>Histogram</th></tr></thead>
                <tbody>
                    ${data.map((item, index) => {
                        const histClass = item.Histogram > 0 ? 'positive-hist' : (item.Histogram < 0 ? 'negative-hist' : '');
                        return `
                            <tr style="${index < data.length - 7 ? 'display: none;' : ''}">
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