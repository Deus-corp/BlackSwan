"""
This module defines the main routes for the dashboard, including the home page
and an API endpoint for container status.
"""

from typing import Any, List, Dict
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from dashboard.routes.base_template import render_page
from dashboard.docker_service import get_container_statuses

router: APIRouter = APIRouter()

MAIN_CONTENT: str = """
    <section>
        <h2>Swarm Actions</h2>
        <form action="/api/start" method="post" style="display:inline">
            <input type="number" name="scale" value="1" min="1" max="10" style="width:60px">
            <button class="btn btn-success" type="submit">🚀 Start</button>
        </form>
        <form action="/api/stop" method="post" style="display:inline">
            <button class="btn btn-danger" type="submit">⏹️ Stop</button>
        </form>
        <form action="/api/restart" method="post" style="display:inline">
            <button class="btn" type="submit">🔄 Restart</button>
        </form>
        <form action="/api/rebuild" method="post" style="display:inline">
            <input type="number" name="scale" value="1" min="1" max="10" style="width:60px">
            <button class="btn" type="submit">🔄 Rebuild & Start</button>
        </form>
    </section>
    <section>
        <h2>Container Management</h2>
        <button class="btn" onclick="fetchContainerStats()">📊 Stats</button>
        <button class="btn" onclick="inspectContainer()">🔍 Inspect</button>
        <button class="btn" onclick="pauseContainer()">⏸️ Pause</button>
        <button class="btn" onclick="unpauseContainer()">▶️ Unpause</button>
        <pre id="container-output" style="margin-top:1rem;">Click a button...</pre>
    </section>
    <section>
        <h2>Container Status</h2>
        <pre id="container-status">Loading...</pre>
        <button class="btn" onclick="fetchContainerStatus()">🔄 Refresh</button>
    </section>
"""

@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """
    Renders the main dashboard page using the base template.

    Args:
        request: The FastAPI Request object.

    Returns:
        HTMLResponse: The rendered page content.
    """
    html_content: str = render_page(request, MAIN_CONTENT)
    return HTMLResponse(content=html_content)

@router.get("/api/container_status_json", response_model=List[Dict[str, Any]])
async def container_status_json() -> List[Dict[str, Any]]:
    """
    Retrieves the current status of all Docker containers as a JSON list.

    Returns:
        List[Dict[str, Any]]: A list containing the current status for each container.
    """
    return get_container_statuses()