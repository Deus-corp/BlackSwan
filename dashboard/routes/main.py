from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

HTML_HEADER = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>BlackSwan Control Panel</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🦢</text></svg>">
    <style>
        body { font-family: sans-serif; max-width: 1200px; margin: 2rem auto; padding: 0 1rem; background: #1a1a2e; color: #e0e0e0; }
        h1 { color: #f0c000; }
        section { background: #16213e; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
        button, input[type=submit] { background: #e94560; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 8px; cursor: pointer; font-size: 1rem; margin-right: 0.5rem; }
        button:hover { background: #c23152; }
        input[type=text], input[type=password], select { padding: 0.5rem; border-radius: 8px; border: 1px solid #30363d; background: #0d1117; color: white; margin-right: 0.5rem; }
        pre { background: #0d1117; padding: 1rem; border-radius: 8px; overflow-x: auto; max-height: 600px; white-space: pre-wrap; word-wrap: break-word; }
        .row { display: flex; align-items: center; margin-bottom: 0.5rem; }
        .row label { width: 300px; }
        .tabs { display: flex; gap: 1rem; margin-bottom: 1rem; }
        .tabs a { color: #f0c000; text-decoration: none; padding: 0.5rem 1rem; border-radius: 8px; background: #16213e; }
        .tabs a.active { background: #e94560; color: white; }
    </style>
</head>
<body>
    <h1>🦢 BlackSwan Control Panel</h1>
    <div class="tabs">
        <a href="/" class="active">🏠 Main</a>
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
            <button type="submit">🚀 Start</button>
        </form>
        <form action="/api/stop" method="post" style="display:inline">
            <button type="submit">⏹️ Stop</button>
        </form>
        <form action="/api/restart" method="post" style="display:inline">
            <button type="submit">🔄 Restart</button>
        </form>
        <form action="/api/rebuild" method="post" style="display:inline">
            <button type="submit">🔄 Rebuild & Start</button>
        </form>
    </section>
    <section>
        <h2>Monitoring</h2>
        <button onclick="fetchLogs()">📜 Refresh Logs</button>
        <button onclick="saveLogs()">💾 Save Logs</button>
        <label style="color: #f0c000; margin-left: 1rem;">
            <input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh()"> Auto-refresh (10s)
        </label>
        <pre id="log-box" style="margin-top:1rem;">{logs_text}</pre>
    </section>
    {msg_section}
    <script>
        const logBox = document.getElementById('log-box');

        async function fetchLogs() {{
            try {{
                const res = await fetch('/api/logs/text');
                const text = await res.text();
                logBox.textContent = text;
            }} catch (e) {{
                logBox.textContent = 'Failed to load logs.';
            }}
        }}

        async function saveLogs() {{
            const res = await fetch('/api/save_logs', {{ method: 'POST' }});
            const data = await res.text();
            alert(data);
        }}

        let autoRefreshInterval = null;
        function toggleAutoRefresh() {{
            const checkbox = document.getElementById('autoRefresh');
            if (checkbox.checked) {{
                fetchLogs();
                autoRefreshInterval = setInterval(fetchLogs, 10000);
            }} else if (autoRefreshInterval) {{
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
            }}
        }}

        fetchLogs();

        document.querySelectorAll('form').forEach(form => {{
            form.addEventListener('submit', async (e) => {{
                e.preventDefault();
                const formData = new FormData(form);
                const url = form.getAttribute('action');
                const method = form.getAttribute('method') || 'post';
                const params = new URLSearchParams(formData);
                try {{
                    const res = await fetch(url, {{
                        method: method,
                        body: params,
                        headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }}
                    }});
                    const resultHtml = await res.text();
                    location.reload();
                }} catch (err) {{
                    alert('Error: ' + err.message);
                }}
            }});
        }});
    </script>
    {HTML_FOOTER}"""

@router.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(render_main())