from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from dashboard.routes.base_template import render_page

router = APIRouter()

LOGS_CONTENT = """
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
"""

@router.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request):
    return HTMLResponse(render_page(request, LOGS_CONTENT, "BlackSwan Logs"))

@router.get("/api/logs/text", response_class=PlainTextResponse)
def logs_text():
    from dashboard.docker_service import get_swarm_logs
    return get_swarm_logs(200)

@router.post("/api/save_logs", response_class=PlainTextResponse)
def save_logs():
    from dashboard.docker_service import save_logs_to_disk
    msg = save_logs_to_disk()
    return PlainTextResponse(msg)

@router.get("/api/container_status", response_class=PlainTextResponse)
def container_status():
    from dashboard.docker_service import list_containers
    containers = list_containers()
    if not containers:
        return "No containers found."
    statuses = [f"{c.name}: {c.status}" for c in containers]
    return "\n".join(statuses)