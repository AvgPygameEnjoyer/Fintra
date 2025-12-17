// ==================== CHART RENDERING ====================
import { STATE, CONFIG } from './config.js';

export function renderCharts(data) {
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

    STATE.charts.ohlcv = new Chart(priceCtx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Close Price',
                    data: closes,
                    borderColor: 'rgb(102, 126, 234)',
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
                    display: false
                },
                y: {
                    title: { display: false },
                    position: 'right',
                    ticks: {
                        callback: function(value) {
                            return value.toExponential(0);
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
    const rsiValues = rsiData.map(item => item.RSI); // This now correctly extracts the RSI value from each object

    STATE.charts.rsi = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'RSI (14)',
                    data: rsiValues,
                    borderColor: '#10b981',
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