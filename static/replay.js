import { CONFIG } from './config.js';
import { showNotification } from './notifications.js';

// ==================== REPLAY MODULE ====================
let socket = null;
let replayChart = null;
let allCandles = [];       // All candles received so far
let totalCandles = 0;
let currentIndex = 0;
let isPlaying = false;
let playbackSpeed = 1.0;
let playbackTimer = null;
let selectedDate = null;

// ── Public entry point ──
export function openReplayModal() {
    const modal = document.getElementById('replay-modal');
    if (!modal) return;
    modal.showModal();

    // Pre-fill symbol from backtest context
    const symbol = window.currentBacktestData?.symbol || '';
    const label = document.getElementById('replay-symbol-label');
    if (label) {
        label.textContent = symbol
            ? `Replaying ${symbol} – select a time window`
            : 'Select a time window to replay';
    }

    showSetup();
    populateDateGrid();
    populateTimeDropdowns();
    bindSetupEvents();
    bindPlayerEvents();
}
window.openReplayModal = openReplayModal;

// ── Setup Panel ──
function showSetup() {
    const setup = document.getElementById('replay-setup');
    const player = document.getElementById('replay-player');
    if (setup) setup.style.display = '';
    if (player) player.style.display = 'none';
    resetPlayerState();
}

function showPlayer() {
    const setup = document.getElementById('replay-setup');
    const player = document.getElementById('replay-player');
    if (setup) setup.style.display = 'none';
    if (player) player.style.display = '';
}

function populateDateGrid() {
    const grid = document.getElementById('replay-date-grid');
    if (!grid) return;
    grid.innerHTML = '';

    // Show last 30 eligible trading days (31–60 days ago for SEBI lag)
    const today = new Date();
    const dates = [];
    for (let i = 31; i <= 90; i++) {
        const d = new Date(today);
        d.setDate(d.getDate() - i);
        const dow = d.getDay();
        if (dow === 0 || dow === 6) continue; // skip weekends
        dates.push(d);
        if (dates.length >= 30) break;
    }

    dates.forEach(d => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'replay-date-btn';
        const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        const dayNames = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
        btn.innerHTML = `<span class="rdb-day">${dayNames[d.getDay()]}</span><span class="rdb-num">${d.getDate()}</span><span class="rdb-month">${monthNames[d.getMonth()]}</span>`;
        btn.dataset.date = d.toISOString().split('T')[0];
        btn.addEventListener('click', () => {
            grid.querySelectorAll('.replay-date-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            selectedDate = btn.dataset.date;
            updateDuration();
        });
        grid.appendChild(btn);
    });
}

function populateTimeDropdowns() {
    const hourStart = document.getElementById('replay-hour-start');
    const hourEnd = document.getElementById('replay-hour-end');
    const minStart = document.getElementById('replay-min-start');
    const minEnd = document.getElementById('replay-min-end');

    // IST market hours: 9:15 AM to 3:30 PM
    [hourStart, hourEnd].forEach(sel => {
        if (!sel) return;
        sel.innerHTML = '';
        for (let h = 9; h <= 15; h++) {
            const opt = document.createElement('option');
            opt.value = h;
            opt.textContent = h.toString().padStart(2, '0');
            sel.appendChild(opt);
        }
    });

    [minStart, minEnd].forEach(sel => {
        if (!sel) return;
        sel.innerHTML = '';
        for (let m = 0; m < 60; m += 1) {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m.toString().padStart(2, '0');
            sel.appendChild(opt);
        }
    });

    // Defaults: 10:00 → 10:30
    if (hourStart) hourStart.value = '10';
    if (minStart) minStart.value = '0';
    if (hourEnd) hourEnd.value = '10';
    if (minEnd) minEnd.value = '30';

    // Listen for changes
    [hourStart, hourEnd, minStart, minEnd].forEach(el => {
        if (el) el.addEventListener('change', updateDuration);
    });
}

function getSelectedTimes() {
    const hs = parseInt(document.getElementById('replay-hour-start')?.value || '10');
    const ms = parseInt(document.getElementById('replay-min-start')?.value || '0');
    const he = parseInt(document.getElementById('replay-hour-end')?.value || '10');
    const me = parseInt(document.getElementById('replay-min-end')?.value || '30');
    return { hs, ms, he, me };
}

function updateDuration() {
    const badge = document.getElementById('replay-duration-badge');
    const launchBtn = document.getElementById('replay-launch-btn');
    const { hs, ms, he, me } = getSelectedTimes();

    const startMin = hs * 60 + ms;
    const endMin = he * 60 + me;
    const diff = endMin - startMin;

    if (diff <= 0) {
        if (badge) badge.textContent = 'Duration: Invalid (end must be after start)';
        if (badge) badge.classList.add('invalid');
        if (launchBtn) launchBtn.disabled = true;
        return;
    }
    if (diff > 60) {
        if (badge) badge.textContent = `Duration: ${diff} min (max 60 min)`;
        if (badge) badge.classList.add('invalid');
        if (launchBtn) launchBtn.disabled = true;
        return;
    }

    if (badge) {
        badge.textContent = `Duration: ${diff} min → ${diff} candles`;
        badge.classList.remove('invalid');
    }
    if (launchBtn) launchBtn.disabled = !selectedDate;
}

function bindSetupEvents() {
    const launchBtn = document.getElementById('replay-launch-btn');
    const closeBtn = document.getElementById('replay-close-btn');

    if (launchBtn) {
        // Remove old listeners by cloning
        const newBtn = launchBtn.cloneNode(true);
        launchBtn.parentNode.replaceChild(newBtn, launchBtn);
        newBtn.addEventListener('click', handleLaunch);
    }

    if (closeBtn) {
        const newClose = closeBtn.cloneNode(true);
        closeBtn.parentNode.replaceChild(newClose, closeBtn);
        newClose.addEventListener('click', () => {
            cleanup();
            document.getElementById('replay-modal')?.close();
        });
    }
}

function handleLaunch() {
    const symbol = window.currentBacktestData?.symbol;
    if (!symbol) {
        showNotification('Run a backtest first to select a symbol.', 'error');
        return;
    }
    if (!selectedDate) {
        showNotification('Please select a date.', 'error');
        return;
    }

    const { hs, ms, he, me } = getSelectedTimes();
    const startISO = `${selectedDate}T${String(hs).padStart(2,'0')}:${String(ms).padStart(2,'0')}:00`;
    const endISO = `${selectedDate}T${String(he).padStart(2,'0')}:${String(me).padStart(2,'0')}:00`;

    setStatus('Connecting...');
    connectAndStream(symbol, startISO, endISO);
}

// ── WebSocket Connection ──
function connectAndStream(symbol, startISO, endISO) {
    if (socket) socket.disconnect();

    // Build the WS URL from the API base
    const wsBase = CONFIG.API_BASE_URL.replace(/^http/, 'ws');
    socket = io(wsBase, {
        path: '/socket.io',
        transports: ['websocket', 'polling'],
    });

    socket.on('connect', () => {
        setStatus('Connected. Loading candles...');
        socket.emit('init', { symbol, start: startISO, end: endISO, mode: 'slideshow' });
    });

    socket.on('ready', (data) => {
        totalCandles = data.total;
        allCandles = [];
        currentIndex = 0;
        setStatus(`Ready – ${totalCandles} candles loaded`);
        showPlayer();
        initChart(symbol);
        document.getElementById('replay-candle-counter').textContent = `0 / ${totalCandles}`;
        setStatus(`Loading ${totalCandles} candles...`);
        // Request all candles — server sends them in a batch
        socket.emit('start');
    });

    socket.on('candle', (candle) => {
        allCandles.push(candle);
        // Update loading progress
        const pct = totalCandles > 0 ? Math.round((allCandles.length / totalCandles) * 100) : 0;
        setStatus(`Loading candles... ${pct}%`);
    });

    socket.on('end', () => {
        // All candles buffered — show the first one and wait for user to play
        if (allCandles.length > 0) {
            renderUpTo(1);
        }
        setStatus(`Ready — ${allCandles.length} candles loaded. Press ▶ to play.`);
    });

    socket.on('error', (err) => {
        setStatus('');
        showNotification(err.msg || 'Replay connection error', 'error');
    });

    socket.on('disconnect', () => {
        // Only show if we haven't loaded yet
        if (allCandles.length === 0) {
            setStatus('Disconnected.');
        }
    });
}

// ── Chart ──
function initChart(symbol) {
    const canvas = document.getElementById('replay-chart');
    if (!canvas) return;

    if (replayChart) {
        replayChart.destroy();
        replayChart = null;
    }

    const ctx = canvas.getContext('2d');
    replayChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: `${symbol} Close`,
                    data: [],
                    borderColor: '#00D4C8',
                    backgroundColor: 'rgba(0, 212, 200, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHoverBackgroundColor: '#00D4C8',
                },
                {
                    label: 'High',
                    data: [],
                    borderColor: 'rgba(74, 222, 128, 0.5)',
                    borderWidth: 1,
                    borderDash: [3, 3],
                    fill: false,
                    tension: 0.2,
                    pointRadius: 0,
                },
                {
                    label: 'Low',
                    data: [],
                    borderColor: 'rgba(248, 113, 113, 0.5)',
                    borderWidth: 1,
                    borderDash: [3, 3],
                    fill: false,
                    tension: 0.2,
                    pointRadius: 0,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 150 },
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        title: (items) => items[0]?.label || '',
                        label: (ctx) => {
                            const ds = ctx.dataset.label;
                            return `${ds}: ₹${ctx.parsed.y?.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    ticks: { color: 'rgba(255,255,255,0.6)', maxTicksLimit: 10, font: { size: 11 } },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
                y: {
                    display: true,
                    position: 'right',
                    ticks: {
                        color: 'rgba(255,255,255,0.6)',
                        font: { size: 11 },
                        callback: v => '₹' + v.toFixed(0)
                    },
                    grid: { color: 'rgba(255,255,255,0.08)' },
                }
            },
            interaction: { mode: 'nearest', axis: 'x', intersect: false }
        }
    });
}

function renderUpTo(idx) {
    if (!replayChart || idx < 1) return;
    const showCandles = allCandles.slice(0, idx);

    replayChart.data.labels = showCandles.map(c => formatTime(c));
    replayChart.data.datasets[0].data = showCandles.map(c => c.Close ?? c.close);
    replayChart.data.datasets[1].data = showCandles.map(c => c.High ?? c.high);
    replayChart.data.datasets[2].data = showCandles.map(c => c.Low ?? c.low);
    replayChart.update('none');

    currentIndex = idx;

    // Update info bar
    const last = showCandles[showCandles.length - 1];
    document.getElementById('rc-open').textContent = '₹' + ((last.Open ?? last.open) || 0).toFixed(2);
    document.getElementById('rc-high').textContent = '₹' + ((last.High ?? last.high) || 0).toFixed(2);
    document.getElementById('rc-low').textContent = '₹' + ((last.Low ?? last.low) || 0).toFixed(2);
    document.getElementById('rc-close').textContent = '₹' + ((last.Close ?? last.close) || 0).toFixed(2);
    document.getElementById('rc-vol').textContent = ((last.Volume ?? last.volume) || 0).toLocaleString();
    document.getElementById('rc-time').textContent = formatTime(last);

    // Progress
    document.getElementById('replay-candle-counter').textContent = `${idx} / ${totalCandles}`;
    const pct = totalCandles > 0 ? (idx / totalCandles) * 100 : 0;
    const fill = document.getElementById('replay-progress-fill');
    const thumb = document.getElementById('replay-progress-thumb');
    if (fill) fill.style.width = pct + '%';
    if (thumb) thumb.style.left = pct + '%';

    // Time label
    if (showCandles.length > 0) {
        const first = showCandles[0];
        document.getElementById('replay-time-label').textContent =
            `${formatTime(first)} → ${formatTime(last)}`;
    }
}

function formatTime(candle) {
    // Try different property names
    const ts = candle.timestamp || candle.Datetime || candle.datetime || candle.Date || candle.date || '';
    if (!ts) return '--:--';
    const d = new Date(ts);
    if (isNaN(d.getTime())) return String(ts).slice(11, 16) || '--:--';
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
}

// ── Transport Controls ──
function bindPlayerEvents() {
    const playBtn = document.getElementById('replay-btn-play');
    const backBtn = document.getElementById('replay-btn-back');
    const fwdBtn = document.getElementById('replay-btn-forward');
    const resetBtn = document.getElementById('replay-btn-reset');
    const progressBar = document.getElementById('replay-progress-bar');

    if (playBtn) {
        playBtn.onclick = () => {
            if (isPlaying) pausePlayback();
            else startPlayback();
        };
    }

    if (backBtn) {
        backBtn.onclick = () => {
            pausePlayback();
            if (currentIndex > 1) renderUpTo(currentIndex - 1);
        };
    }

    if (fwdBtn) {
        fwdBtn.onclick = () => {
            pausePlayback();
            if (currentIndex < allCandles.length) renderUpTo(currentIndex + 1);
        };
    }

    if (resetBtn) {
        resetBtn.onclick = () => {
            cleanup();
            showSetup();
        };
    }

    // Speed pills
    document.querySelectorAll('.speed-pill').forEach(pill => {
        pill.onclick = () => {
            document.querySelectorAll('.speed-pill').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            playbackSpeed = parseFloat(pill.dataset.speed);
            // If playing, restart timer with new speed
            if (isPlaying) {
                clearInterval(playbackTimer);
                playbackTimer = setInterval(playTick, 1000 / playbackSpeed);
            }
        };
    });

    // Click on progress bar to seek
    if (progressBar) {
        progressBar.onclick = (e) => {
            const rect = progressBar.getBoundingClientRect();
            const pct = (e.clientX - rect.left) / rect.width;
            const targetIdx = Math.max(1, Math.min(allCandles.length, Math.round(pct * totalCandles)));
            pausePlayback();
            renderUpTo(targetIdx);
        };
    }
}

function startPlayback() {
    if (currentIndex >= allCandles.length && allCandles.length >= totalCandles) {
        // Reset to beginning if at end
        currentIndex = 0;
    }
    isPlaying = true;
    const playBtn = document.getElementById('replay-btn-play');
    if (playBtn) playBtn.textContent = '⏸';
    playbackTimer = setInterval(playTick, 1000 / playbackSpeed);
    setStatus('Playing...');
}

function pausePlayback() {
    isPlaying = false;
    const playBtn = document.getElementById('replay-btn-play');
    if (playBtn) playBtn.textContent = '▶';
    if (playbackTimer) {
        clearInterval(playbackTimer);
        playbackTimer = null;
    }
    setStatus('Paused');
}

function playTick() {
    if (currentIndex < allCandles.length) {
        renderUpTo(currentIndex + 1);
    } else {
        // Reached the end
        pausePlayback();
        setStatus('Replay complete');
    }
}

// ── Utils ──
function resetPlayerState() {
    allCandles = [];
    totalCandles = 0;
    currentIndex = 0;
    isPlaying = false;
    playbackSpeed = 1.0;
    if (playbackTimer) {
        clearInterval(playbackTimer);
        playbackTimer = null;
    }
    if (replayChart) {
        replayChart.destroy();
        replayChart = null;
    }
    // Reset speed pills
    document.querySelectorAll('.speed-pill').forEach(p => p.classList.remove('active'));
    const onePill = document.querySelector('.speed-pill[data-speed="1"]');
    if (onePill) onePill.classList.add('active');

    setStatus('');
}

function cleanup() {
    pausePlayback();
    resetPlayerState();
    if (socket) {
        socket.disconnect();
        socket = null;
    }
}

function setStatus(msg) {
    const el = document.getElementById('replay-status');
    if (el) el.textContent = msg;
}
