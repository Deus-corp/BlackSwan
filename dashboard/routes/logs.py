from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from dashboard.docker_service import get_swarm_logs, save_logs_to_disk, list_containers
from dashboard.routes.base_template import render_page
from typing import Any, Dict, List

router = APIRouter()

LOGS_CONTENT: str = """
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
def logs_page(request: Request) -> HTMLResponse:
    """
    Renders the logs page, providing an interface to view and manage swarm logs.
    
    Args:
        request (Request): The incoming request object.
    
    Returns:
        HTMLResponse: The rendered logs page.
    """
    return HTMLResponse(render_page(request, LOGS_CONTENT, "BlackSwan Logs"))

@router.get("/api/logs/text", response_class=PlainTextResponse)
def logs_text() -> PlainTextResponse:
    """
    Retrieves the latest Docker swarm logs as plain text.
    Fetches the last 200 lines of logs.
    
    Returns:
        PlainTextResponse: The latest Docker swarm logs as plain text.
    """
    return PlainTextResponse(get_swarm_logs(200))

@router.post("/api/save_logs", response_class=PlainTextResponse)
def save_logs() -> PlainTextResponse:
    """
    Saves the current Docker swarm logs to a file on disk.
    Returns a message indicating the success or failure of the operation.
    
    Returns:
        PlainTextResponse: A message indicating the success or failure of the operation.
    """
    msg: str = save_logs_to_disk()
    return PlainTextResponse(msg)

@router.get("/api/container_status", response_class=PlainTextResponse)
def container_status() -> PlainTextResponse:
    """
    Retrieves the status of all Docker containers in the swarm.
    Returns a plain text string with each container's name and status.
    
    Returns:
        PlainTextResponse: A plain text string with each container's name and status.
    """
    containers: List[Dict[str, Any]] = list_containers()
    if not containers:
        return PlainTextResponse("No containers found.")

    statuses: List[str] = [f"{c['name']}: {c['status']}" for c in containers]
    return PlainTextResponse("\n".join(statuses))