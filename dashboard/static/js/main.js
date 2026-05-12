// main.js – безопасная версия для всех страниц

// Все обращения к DOM выполняем только если элементы существуют
function getElementSafe(id) {
    return document.getElementById(id);
}

// ---------- Глобальный индикатор состояния ----------
function showGlobalStatus(message, isError = false) {
    const box = getElementSafe('global-status');
    if (!box) return;
    const icon = getElementSafe('status-icon');
    const msg = getElementSafe('status-message');
    if (message) {
        if (icon) icon.innerHTML = isError ? '❌' : '<span class="spinning">⏳</span>';
        if (msg) msg.textContent = message;
        box.style.display = 'block';
    } else {
        box.style.display = 'none';
    }
}

// Универсальная обёртка для длительных операций
async function performAction(url, method, body, btn) {
    if (btn) {
        btn.disabled = true;
        btn.classList.add('loading');
    }
    showGlobalStatus('Operation in progress, please wait...');
    const containerOutput = getElementSafe('container-output');
    try {
        const response = await fetch(url, { method, headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body });
        if (!response.ok) {
            const text = await response.text();
            throw new Error(text || response.statusText);
        }
        const text = await response.text();
        if (containerOutput) {
            containerOutput.textContent = text;
        }
        showGlobalStatus('', false);
    } catch (err) {
        showGlobalStatus('Error: ' + err.message, true);
        if (containerOutput) {
            containerOutput.textContent = 'Error: ' + err.message;
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.classList.remove('loading');
        }
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
        await performAction(url, method, params.toString(), btn);
        if (url.includes('/api/start') || url.includes('/api/stop') || url.includes('/api/restart') || url.includes('/api/rebuild')) {
            location.reload();
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

// ---------- Статус контейнеров (только если элемент существует) ----------
async function fetchContainerStatus() {
    const el = getElementSafe('container-status');
    if (!el) return;
    try {
        const res = await fetch('/api/container_status_json');
        const data = await res.json();
        let text = '';
        data.forEach(c => { text += `${c.name}: ${c.status}\n`; });
        el.textContent = text || 'No containers found.';
    } catch (e) {
        console.error(e);
    }
}
if (getElementSafe('container-status')) {
    fetchContainerStatus();
    setInterval(fetchContainerStatus, 30000);
}