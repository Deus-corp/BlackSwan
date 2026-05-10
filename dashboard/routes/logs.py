from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse
from dashboard.docker_service import get_logs, save_logs_to_disk, list_containers, get_swarm_logs

router = APIRouter()

LOGS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Logs</title>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <h1>🦢 BlackSwan Logs</h1>
    <div class="tabs">
        <a href="/">🏠 Main</a>
        <a href="/trades">📈 Trades</a>
        <a href="/logs" class="active">📜 Logs</a>
        <a href="/dashboard">📊 Dashboard</a>
        <a href="/settings">⚙️ Settings</a>
    </div>
    <section>
        <button class="btn" onclick="fetchLogs()">🔄 Refresh</button>
        <button class="btn" onclick="saveLogs()">💾 Save Logs</button>
        <button class="btn" onclick="containerStatus()">📦 Container Status</button>
        <label style="margin-left:1rem;">
            <input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh()"> Auto-refresh (10s)
        </label>
    </section>
    <pre id="log-content">Loading logs...</pre>
    <script src="/static/js/logs.js"></script>
</body>
</html>
"""

@router.get("/logs", response_class=HTMLResponse)
def logs_page():
    return HTMLResponse(LOGS_HTML)

@router.get("/api/logs/text", response_class=PlainTextResponse)
def logs_text():
    from dashboard.docker_service import get_swarm_logs
    return get_swarm_logs(200)

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