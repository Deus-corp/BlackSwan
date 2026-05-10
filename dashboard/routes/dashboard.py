from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

# Ваш идентификатор дашборда (можно заменить на любой другой)
DASHBOARD_ID = "adxhpc6"
DASHBOARD_SLUG = "blackswan-swarm"

DASHBOARD_HTML = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>BlackSwan Dashboard</title>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <div class="tabs">
        <a href="/">🏠 Main</a>
        <a href="/trades">📈 Trades</a>
        <a href="/logs">📜 Logs</a>
        <a href="/dashboard" class="active">📊 Dashboard</a>
        <a href="/settings">⚙️ Settings</a>
    </div>
    <iframe class="iframe-container"
            src="http://localhost:3000/d/{DASHBOARD_ID}/{DASHBOARD_SLUG}?orgId=1&refresh=10s&kiosk"
            frameborder="0">
    </iframe>
</body>
</html>"""

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(DASHBOARD_HTML)