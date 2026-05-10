from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from dashboard.docker_service import start_swarm, stop_swarm, rebuild_swarm, update_config
from dashboard.routes.main import render_main
import subprocess
from dashboard.docker_service import get_container_stats, inspect_container, pause_container, unpause_container
from fastapi.responses import PlainTextResponse

router = APIRouter()

@router.post("/api/start")
async def api_start(request: Request):
    form = await request.form()
    scale = int(form.get("scale", 1))
    msg = start_swarm(scale)
    return HTMLResponse(render_main(message=msg))

@router.post("/api/stop")
async def api_stop():
    msg = stop_swarm()
    return HTMLResponse(render_main(message=msg))

@router.post("/api/restart")
async def api_restart():
    stop_swarm()
    msg = start_swarm()
    return HTMLResponse(render_main(message=msg))

@router.post("/api/rebuild")
async def api_rebuild(request: Request):
    form = await request.form()
    scale = int(form.get("scale", 1))
    msg = rebuild_swarm(scale)
    return HTMLResponse(render_main(message=msg))

@router.post("/api/container_stats")
async def api_container_stats(request: Request):
    form = await request.form()
    name = form.get("container", "lab_swarm_demo-node-1")
    msg = get_container_stats(name)
    return PlainTextResponse(msg)

@router.post("/api/container_inspect")
async def api_container_inspect(request: Request):
    form = await request.form()
    name = form.get("container", "lab_swarm_demo-node-1")
    msg = inspect_container(name)
    return PlainTextResponse(msg)

@router.post("/api/container_pause")
async def api_container_pause(request: Request):
    form = await request.form()
    name = form.get("container", "lab_swarm_demo-node-1")
    msg = pause_container(name)
    return PlainTextResponse(msg)

@router.post("/api/container_unpause")
async def api_container_unpause(request: Request):
    form = await request.form()
    name = form.get("container", "lab_swarm_demo-node-1")
    msg = unpause_container(name)
    return PlainTextResponse(msg)