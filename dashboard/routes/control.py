from fastapi import APIRouter, Request, Form
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

async def _render_api_result_page(request: Request, message: str) -> HTMLResponse:
    """
    Helper function to render a consistent API result page with a message
    and the main content.
    """
    content = f'<section><h3>Result</h3><pre>{message}</pre></section>' + MAIN_CONTENT
    return HTMLResponse(render_page(request, content))

@router.post("/api/start")
async def api_start(request: Request) -> HTMLResponse:
    """
    API endpoint to start the Docker swarm.
    Retrieves the desired scale from the request form (defaulting to 1)
    and initiates the swarm.
    """
    form = await request.form()
    scale_str: str = form.get("scale", "1")
    try:
        scale: int = int(scale_str)
    except ValueError:
        return await _render_api_result_page(request, f"Error: Invalid scale value '{scale_str}'. Please provide an integer.")
    
    msg: str = start_swarm(scale)
    return await _render_api_result_page(request, msg)

@router.post("/api/stop")
async def api_stop(request: Request) -> HTMLResponse:
    """
    API endpoint to stop the Docker swarm.
    """
    msg: str = stop_swarm()
    return await _render_api_result_page(request, msg)

@router.post("/api/restart")
async def api_restart(request: Request) -> HTMLResponse:
    """
    API endpoint to restart the Docker swarm.
    Stops the existing swarm and then starts a new one.
    """
    stop_swarm_msg: str = stop_swarm()
    start_swarm_msg: str = start_swarm() # Assumes default scale if not provided.
    msg: str = f"Stop swarm: {stop_swarm_msg}\nStart swarm: {start_swarm_msg}"
    return await _render_api_result_page(request, msg)

@router.post("/api/rebuild")
async def api_rebuild(request: Request) -> HTMLResponse:
    """
    API endpoint to rebuild the Docker swarm.
    Retrieves the desired scale from the request form (defaulting to 1)
    and rebuilds the swarm.
    """
    form = await request.form()
    scale_str: str = form.get("scale", "1")
    try:
        scale: int = int(scale_str)
    except ValueError:
        return await _render_api_result_page(request, f"Error: Invalid scale value '{scale_str}'. Please provide an integer.")

    msg: str = rebuild_swarm(scale)
    return await _render_api_result_page(request, msg)

@router.post("/api/container_stats")
async def api_container_stats(request: Request) -> PlainTextResponse:
    """
    API endpoint to get statistics for a specific container.
    Defaults to 'lab_swarm_demo-node-1' if no container name is provided.
    """
    form = await request.form()
    name: str = form.get("container", "lab_swarm_demo-node-1")
    msg: str = get_container_stats(name)
    return PlainTextResponse(msg)

@router.post("/api/container_inspect")
async def api_container_inspect(request: Request) -> PlainTextResponse:
    """
    API endpoint to inspect a specific container for detailed information.
    Defaults to 'lab_swarm_demo-node-1' if no container name is provided.
    """
    form = await request.form()
    name: str = form.get("container", "lab_swarm_demo-node-1")
    msg: str = inspect_container(name)
    return PlainTextResponse(msg)

@router.post("/api/container_pause")
async def api_container_pause(request: Request) -> PlainTextResponse:
    """
    API endpoint to pause a specific container.
    Defaults to 'lab_swarm_demo-node-1' if no container name is provided.
    """
    form = await request.form()
    name: str = form.get("container", "lab_swarm_demo-node-1")
    msg: str = pause_container(name)
    return PlainTextResponse(msg)

@router.post("/api/container_unpause")
async def api_container_unpause(request: Request) -> PlainTextResponse:
    """
    API endpoint to unpause a specific container.
    Defaults to 'lab_swarm_demo-node-1' if no container name is provided.
    """
    form = await request.form()
    name: str = form.get("container", "lab_swarm_demo-node-1")
    msg: str = unpause_container(name)
    return PlainTextResponse(msg)