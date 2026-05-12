"""
base_template.py — единый HTML-шаблон с header/footer и активной вкладкой.
"""
from fastapi import Request

def render_page(request: Request, content: str, title: str = "BlackSwan Control Panel") -> str:
    """Возвращает полную HTML-страницу с общим header/footer."""
    # Определяем активную вкладку по URL
    active_tab = {
        "/": "main",
        "/trades": "trades",
        "/logs": "logs",
        "/dashboard": "dashboard",
        "/mutations": "mutations",
        "/settings": "settings",
    }.get(request.url.path, "")

    tabs = [
        ("/", "🏠 Main", "main"),
        ("/trades", "📈 Trades", "trades"),
        ("/logs", "📜 Logs", "logs"),
        ("/dashboard", "📊 Dashboard", "dashboard"),
        ("/mutations", "🧬 Mutations", "mutations"),
        ("/settings", "⚙️ Settings", "settings"),
    ]

    tabs_html = ""
    for href, label, key in tabs:
        cls = 'class="active"' if key == active_tab else ""
        tabs_html += f'<a href="{href}" {cls}>{label}</a>\n'

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🦢</text></svg>">
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <div id="global-status" style="display:none; background:#21262d; border:1px solid #30363d; border-radius:8px; padding:0.75rem 1.5rem; margin-bottom:1rem; color:#c9d1d9;">
        <span id="status-icon"></span>
        <span id="status-message"></span>
    </div>
    <h1>🦢 BlackSwan Control Panel</h1>
    <div class="tabs">
        {tabs_html}
    </div>
    {content}
    <script src="/static/js/main.js"></script>
</body>
</html>"""
    return html