"""
base_template.py — единый HTML-шаблон с header/footer и активной вкладкой.
"""
from typing import List, Tuple
from fastapi import Request

# Constants for default page title and navigation tabs configuration
DEFAULT_PAGE_TITLE: str = "BlackSwan Control Panel"
TABS_CONFIG: List[Tuple[str, str, str]] = [
    ("/", "🏠 Main", "main"),
    ("/trades", "📈 Trades", "trades"),
    ("/logs", "📜 Logs", "logs"),
    ("/dashboard", "📊 Dashboard", "dashboard"),
    ("/mutations", "🧬 Mutations", "mutations"),
    ("/settings", "⚙️ Settings", "settings"),
]

def render_page(request: Request, content: str, title: str = DEFAULT_PAGE_TITLE) -> str:
    """
    Возвращает полную HTML-страницу с общим header/footer и динамически выделенной активной вкладкой.

    Определяет активную вкладку на основе URL-пути запроса.
    Генерирует HTML для навигационных вкладок, выделяя активную.
    Вставляет предоставленное содержимое в основную часть страницы.

    Args:
        request: Объект запроса FastAPI, используемый для определения текущего URL и активной вкладки.
        content: HTML-содержимое, которое будет вставлено в `<main>` раздел страницы.
        title: Заголовок HTML-страницы, отображаемый в теге `<title>`. По умолчанию используется
               `DEFAULT_PAGE_TITLE`.

    Returns:
        Полная HTML-страница в виде строки.
    """
    # Create a mapping from URL path to tab key for efficient lookup
    path_to_tab_key_map: dict[str, str] = {href: key for href, _, key in TABS_CONFIG}
    active_tab: str = path_to_tab_key_map.get(request.url.path, "")

    # Generate HTML for the navigation tabs
    tabs_html_parts: List[str] = []
    for href, label, key in TABS_CONFIG:
        cls: str = 'class="active"' if key == active_tab else ""
        tabs_html_parts.append(f'<a href="{href}" {cls}>{label}</a>')
    # Join with newline and indentation for better readability in the rendered HTML source
    tabs_html: str = "\n        ".join(tabs_html_parts)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
    <main>
        {content}
    </main>
    <script src="/static/js/main.js"></script>
</body>
</html>"""
    return html