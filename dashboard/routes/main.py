from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

HTML_HEADER = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>BlackSwan Control Panel</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🦢</text></svg>">
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <h1>🦢 BlackSwan Control Panel</h1>
    <div class="tabs">
        <a href="/" class="active">🏠 Main</a>
        <a href="/trades">📈 Trades</a>
        <a href="/logs">📜 Logs</a>
        <a href="/dashboard">📊 Dashboard</a>
        <a href="/settings">⚙️ Settings</a>
    </div>
"""

HTML_FOOTER = """</body>
</html>"""

def render_main(message: str = "", logs_text: str = "Logs will appear here...") -> str:
    msg_section = f"<section><h3>Result</h3><pre>{message}</pre></section>" if message else ""
    return f"""{HTML_HEADER}
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
    {msg_section}
<script src="/static/js/main.js"></script>
    {HTML_FOOTER}"""

@router.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(render_main())

@router.get("/api/container_status_json")
def container_status_json():
    from dashboard.docker_service import get_container_statuses
    return get_container_statuses()