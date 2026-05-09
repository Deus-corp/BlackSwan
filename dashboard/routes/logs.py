from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse
from dashboard.docker_service import get_logs, save_logs_to_disk, list_containers

router = APIRouter()

LOGS_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Logs</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🦢</text></svg>">
    <style>
        body { font-family: sans-serif; background: #1a1a2e; color: #e0e0e0; margin: 20px; }
        h1 { color: #f0c000; }
        section { background: #16213e; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
        button { background: #e94560; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 8px; cursor: pointer; font-size: 1rem; margin-right: 0.5rem; }
        button:hover { background: #c23152; }
        pre { background: #0d1117; padding: 1rem; border-radius: 8px; overflow-x: auto; max-height: 800px; white-space: pre-wrap; word-wrap: break-word; }
        .tabs { display: flex; gap: 1rem; margin-bottom: 1rem; }
        .tabs a { color: #f0c000; text-decoration: none; padding: 0.5rem 1rem; border-radius: 8px; background: #16213e; }
        .tabs a.active { background: #e94560; color: white; }
    </style>
</head>
<body>
    <h1>🦢 BlackSwan Logs</h1>
    <div class="tabs">
        <a href="/">🏠 Main</a>
        <a href="/logs" class="active">📜 Logs</a>
        <a href="/dashboard">📊 Dashboard</a>
        <a href="/settings">⚙️ Settings</a>
    </div>
    <section>
        <button onclick="fetchLogs()">🔄 Refresh Logs</button>
        <button onclick="saveLogs()">💾 Save Logs</button>
        <button onclick="containerStatus()">📦 Container Status</button>
    </section>
    <pre id="log-content">Loading logs...</pre>
    <script>
        const logEl = document.getElementById('log-content');

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

        fetchLogs();
    </script>
</body>
</html>"""

@router.get("/logs", response_class=HTMLResponse)
def logs_page():
    return HTMLResponse(LOGS_HTML)

@router.get("/api/logs/text", response_class=PlainTextResponse)
def logs_text():
    return get_logs(200)

@router.post("/api/save_logs", response_class=PlainTextResponse)
def save_logs():
    msg = save_logs_to_disk()
    return PlainTextResponse(msg)

@router.get("/api/container_status", response_class=PlainTextResponse)
def container_status():
    containers = list_containers()
    if not containers:
        return "No containers found."
    statuses = []
    for c in containers:
        statuses.append(f"{c.name}: {c.status}")
    return "\n".join(statuses)