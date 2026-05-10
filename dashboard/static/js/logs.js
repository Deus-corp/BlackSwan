const logEl = document.getElementById('log-content');
let autoRefreshInterval = null;

async function fetchLogs() {
    const res = await fetch('/api/logs/text');
    logEl.textContent = await res.text();
}

async function saveLogs() {
    const res = await fetch('/api/save_logs', { method: 'POST' });
    const msg = await res.text();
    alert(msg);
}

async function containerStatus() {
    const res = await fetch('/api/container_status');
    const text = await res.text();
    logEl.textContent = text;
}

function toggleAutoRefresh() {
    const checkbox = document.getElementById('autoRefresh');
    if (checkbox.checked) {
        fetchLogs();
        autoRefreshInterval = setInterval(fetchLogs, 10000);
    } else if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

fetchLogs();