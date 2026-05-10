// main.js – управление контейнерами и действиями на главной странице

const containerOutput = document.getElementById('container-output');

// ---------- Глобальный индикатор состояния ----------
function showGlobalStatus(message, isError = false) {
    const box = document.getElementById('global-status');
    const icon = document.getElementById('status-icon');
    const msg = document.getElementById('status-message');
    if (message) {
        icon.innerHTML = isError ? '❌' : '<span class="spinning">⏳</span>';
        msg.textContent = message;
        box.style.display = 'block';
    } else {
        box.style.display = 'none';
    }
}

// Универсальная обёртка для длительных операций
async function performAction(url, method = 'POST', body = null, originalBtn = null) {
    if (originalBtn) {
        originalBtn.disabled = true;
        const originalText = originalBtn.innerHTML;
        originalBtn.innerHTML = '⏳ Processing...';
        try {
            showGlobalStatus('Operation in progress, please wait...');
            const res = await fetch(url, {
                method,
                headers: body ? { 'Content-Type': 'application/x-www-form-urlencoded' } : {},
                body
            });
            const text = await res.text();
            containerOutput.textContent = text;
            showGlobalStatus('', false);
        } catch (err) {
            showGlobalStatus('Error: ' + err.message, true);
        } finally {
            if (originalBtn) {
                originalBtn.innerHTML = originalText;
                originalBtn.disabled = false;
            }
            setTimeout(() => showGlobalStatus('', false), 10000);
        }
    } else {
        return fetch(url, { method, headers: body ? { 'Content-Type': 'application/x-www-form-urlencoded' } : {}, body });
    }
}

// ---------- Перехват всех форм (Start, Stop, Restart, Rebuild) ----------
document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = form.querySelector('button[type="submit"]');
        const url = form.getAttribute('action');
        const method = form.getAttribute('method') || 'post';
        const formData = new FormData(form);
        const params = new URLSearchParams(formData);
        // Для действий с роем – просто отправляем и перезагружаем страницу
        if (url.includes('/api/start') || url.includes('/api/stop') || url.includes('/api/restart') || url.includes('/api/rebuild')) {
            try {
                showGlobalStatus('Operation in progress, please wait...');
                await fetch(url, { method, headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: params.toString() });
                showGlobalStatus('', false);
                location.reload();
            } catch (err) {
                showGlobalStatus('Error: ' + err.message, true);
            }
        } else {
            await performAction(url, method, params.toString(), btn);
        }
    });
});

// ---------- Кнопки управления контейнерами ----------
async function fetchContainerStats() {
    const btn = document.querySelector('button[onclick="fetchContainerStats()"]');
    await performAction('/api/container_stats', 'POST', 'container=lab_swarm_demo-node-1', btn);
}

async function inspectContainer() {
    const btn = document.querySelector('button[onclick="inspectContainer()"]');
    await performAction('/api/container_inspect', 'POST', 'container=lab_swarm_demo-node-1', btn);
}

async function pauseContainer() {
    const btn = document.querySelector('button[onclick="pauseContainer()"]');
    await performAction('/api/container_pause', 'POST', 'container=lab_swarm_demo-node-1', btn);
}

async function unpauseContainer() {
    const btn = document.querySelector('button[onclick="unpauseContainer()"]');
    await performAction('/api/container_unpause', 'POST', 'container=lab_swarm_demo-node-1', btn);
}

// ---------- Статус контейнеров (автообновление) ----------
async function fetchContainerStatus() {
    const res = await fetch('/api/container_status_json');
    const data = await res.json();
    let text = '';
    data.forEach(c => {
        text += `${c.name}: ${c.status}\n`;
    });
    document.getElementById('container-status').textContent = text || 'No containers found.';
}
fetchContainerStatus();
setInterval(fetchContainerStatus, 30000);