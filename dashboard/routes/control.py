from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from dashboard.docker_service import start_swarm, stop_swarm, rebuild_swarm, update_config
from dashboard.routes.main import render_main

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
async def api_rebuild():
    msg = rebuild_swarm()
    return HTMLResponse(render_main(message=msg))