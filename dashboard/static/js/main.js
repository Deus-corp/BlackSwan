// main.js – управление контейнерами на главной странице

const containerOutput = document.getElementById('container-output');

async function fetchContainerStats() {
    const res = await fetch('/api/container_stats', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'container=lab_swarm_demo-node-1'
    });
    containerOutput.textContent = await res.text();
}

async function inspectContainer() {
    const res = await fetch('/api/container_inspect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'container=lab_swarm_demo-node-1'
    });
    containerOutput.textContent = await res.text();
}

async function pauseContainer() {
    const res = await fetch('/api/container_pause', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'container=lab_swarm_demo-node-1'
    });
    containerOutput.textContent = await res.text();
}

async function unpauseContainer() {
    const res = await fetch('/api/container_unpause', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'container=lab_swarm_demo-node-1'
    });
    containerOutput.textContent = await res.text();
}

// Загрузка состояния при открытии страницы (опционально)
fetchContainerStats();

async function fetchContainerStatus() {
    const res = await fetch('/api/container_status_json');
    const data = await res.json();
    let text = '';
    data.forEach(c => {
        text += `${c.name}: ${c.status}\n`;
    });
    document.getElementById('container-status').textContent = text || 'No containers found.';
}
fetchContainerStatus(); // автоматически при загрузке