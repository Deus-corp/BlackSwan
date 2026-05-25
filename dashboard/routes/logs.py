from typing import Any, Dict, List
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from dashboard.docker_service import (
    get_swarm_logs,
    save_logs_to_disk,
    list_containers,
)
from dashboard.routes.base_template import render_page

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
    Renders the logs dashboard page with controls for log management.

    Args:
        request: The incoming FastAPI request instance.

    Returns:
        HTMLResponse: The rendered page template containing log UI elements.
    """
    return HTMLResponse(render_page(request, LOGS_CONTENT, "BlackSwan Logs"))

@router.get("/api/logs/text", response_class=PlainTextResponse)
def logs_text() -> PlainTextResponse:
    """
    Retrieves the last 200 lines of swarm logs as plain text.

    Returns:
        PlainTextResponse: The raw log buffer content.
    """
    return PlainTextResponse(get_swarm_logs(200))

@router.post("/api/save_logs", response_class=PlainTextResponse)
def save_logs() -> PlainTextResponse:
    """
    Triggers a persistence operation to write current swarm logs to disk.

    Returns:
        PlainTextResponse: Status message indicating success or failure of the operation.
    """
    return PlainTextResponse(save_logs_to_disk())

@router.get("/api/container_status", response_class=PlainTextResponse)
def container_status() -> PlainTextResponse:
    """
    Fetches the operational status of all containers within the swarm.

    Returns:
        PlainTextResponse: A newline-separated string of "Name: Status" entries.
    """
    containers: List[Dict[str, Any]] = list_containers()
    if not containers:
        return PlainTextResponse("No containers found.")

    statuses: List[str] = [
        f"{c.get('name', 'unknown')}: {c.get('status', 'unknown')}" 
        for c in containers
    ]
    return PlainTextResponse("\n".join(statuses))