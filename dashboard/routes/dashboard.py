from __future__ import annotations

from typing import Final
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from dashboard.routes.base_template import render_page

router = APIRouter()

DASHBOARD_CONTENT: Final[str] = """
    <iframe class="iframe-container"
            src="http://localhost:3000/d/adxhpc6/blackswan-swarm?orgId=1&refresh=10s&kiosk"
            frameborder="0" style="width:100%; height:800px;">
    </iframe>
"""

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    """
    Renders the dashboard page, typically displaying an embedded Grafana dashboard.

    Args:
        request: The FastAPI request object.

    Returns:
        HTMLResponse: The rendered HTML response.
    """
    return HTMLResponse(render_page(request, DASHBOARD_CONTENT, "BlackSwan Dashboard"))