from typing import Dict, Any
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from dashboard.docker_service import (
    start_swarm,
    stop_swarm,
    rebuild_swarm,
    get_container_stats,
    inspect_container,
    pause_container,
    unpause_container,
)
from dashboard.routes.base_template import render_page
from dashboard.routes.main import MAIN_CONTENT

router = APIRouter()

DEFAULT_CONTAINER: str = "lab_swarm_demo-node-1"

async def _render_api_result_page(request: Request, message: str) -> HTMLResponse:
    """
    Render a consistent HTML page displaying an operation result.

    Args:
        request: The FastAPI request object.
        message: The status or error message to display.

    Returns:
        An HTMLResponse containing the formatted result.
    """
    content: str = f'<section><h3>Result</h3><pre>{message}</pre></section>{MAIN_CONTENT}'
    return HTMLResponse(render_page(request, content))

async def _get_form_value(request: Request, key: str, default: str) -> str:
    """
    Extract a specific value from the request form data.
    """
    form: Dict[str, Any] = await request.form()
    return str(form.get(key, default))

@router.post("/api/start")
async def api_start(request: Request) -> HTMLResponse:
    """
    API endpoint to start the Docker swarm with an optional scale parameter.
    """
    scale_str = await _get_form_value(request, "scale", "1")
    try:
        scale = int(scale_str)
        msg = start_swarm(scale)
    except ValueError:
        msg = f"Error: Invalid scale value '{scale_str}'. Please provide an integer."
    return await _render_api_result_page(request, msg)

@router.post("/api/stop")
async def api_stop(request: Request) -> HTMLResponse:
    """
    API endpoint to stop the Docker swarm.
    """
    return await _render_api_result_page(request, stop_swarm())

@router.post("/api/restart")
async def api_restart(request: Request) -> HTMLResponse:
    """
    API endpoint to restart the Docker swarm.
    """
    stop_msg = stop_swarm()
    start_msg = start_swarm()
    return await _render_api_result_page(request, f"Stop swarm: {stop_msg}\nStart swarm: {start_msg}")

@router.post("/api/rebuild")
async def api_rebuild(request: Request) -> HTMLResponse:
    """
    API endpoint to rebuild the Docker swarm with a specific scale.
    """
    scale_str = await _get_form_value(request, "scale", "1")
    try:
        scale = int(scale_str)
        msg = rebuild_swarm(scale)
    except ValueError:
        msg = f"Error: Invalid scale value '{scale_str}'. Please provide an integer."
    return await _render_api_result_page(request, msg)

@router.post("/api/container_stats")
async def api_container_stats(request: Request) -> PlainTextResponse:
    """
    Retrieve resource statistics for a container.
    """
    name = await _get_form_value(request, "container", DEFAULT_CONTAINER)
    return PlainTextResponse(get_container_stats(name))

@router.post("/api/container_inspect")
async def api_container_inspect(request: Request) -> PlainTextResponse:
    """
    Retrieve detailed inspection data for a container.
    """
    name = await _get_form_value(request, "container", DEFAULT_CONTAINER)
    return PlainTextResponse(inspect_container(name))

@router.post("/api/container_pause")
async def api_container_pause(request: Request) -> PlainTextResponse:
    """
    Pause a running container.
    """
    name = await _get_form_value(request, "container", DEFAULT_CONTAINER)
    return PlainTextResponse(pause_container(name))

@router.post("/api/container_unpause")
async def api_container_unpause(request: Request) -> PlainTextResponse:
    """
    Unpause a container.
    """
    name = await _get_form_value(request, "container", DEFAULT_CONTAINER)
    return PlainTextResponse(unpause_container(name))