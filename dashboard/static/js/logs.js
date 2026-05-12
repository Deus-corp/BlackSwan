// logs.js – загрузка и автообновление логов

let logsAutoRefresh = null;

async function fetchLogs() {
    try {
        const res = await fetch('/api/logs/text');
        const text = await res.text();
        document.getElementById('log-content').textContent = text || 'No logs available.';
    } catch (e) {
        console.error('Error fetching logs:', e);
    }
}

async function saveLogs() {
    try {
        const res = await fetch('/api/save_logs', { method: 'POST' });
        const text = await res.text();
        alert(text);
    } catch (e) {
        console.error('Error saving logs:', e);
    }
}

async function containerStatus() {
    try {
        const res = await fetch('/api/container_status');
        const text = await res.text();
        document.getElementById('log-content').textContent = text;
    } catch (e) {
        console.error('Error fetching container status:', e);
    }
}

function toggleAutoRefresh() {
    const checked = document.getElementById('autoRefresh').checked;
    if (checked) {
        logsAutoRefresh = setInterval(fetchLogs, 10000);
    } else {
        clearInterval(logsAutoRefresh);
    }
}

// Первая загрузка
fetchLogs();