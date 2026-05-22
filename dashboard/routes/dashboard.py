from __future__ import annotations

from typing import Final
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from dashboard.routes.base_template import render_page

router = APIRouter()

# Configuration for the embedded Grafana dashboard
DASHBOARD_URL: Final[str] = "http://localhost:3000/d/adxhpc6/blackswan-swarm?orgId=1&refresh=10s&kiosk"

DASHBOARD_CONTENT: Final[str] = f"""
    <iframe class="iframe-container"
            src="{DASHBOARD_URL}"
            frameborder="0" 
            style="width:100%; height:800px;" 
            title="BlackSwan Dashboard">
    </iframe>
"""

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    """
    Renders the dashboard page containing the embedded Grafana instance.

    Args:
        request: The incoming FastAPI request object.

    Returns:
        HTMLResponse: A rendered HTML page containing the dashboard iframe.
    """
    content = render_page(request, DASHBOARD_CONTENT, "BlackSwan Dashboard")
    return HTMLResponse(content=content)