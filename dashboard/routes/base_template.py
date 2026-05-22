"""
base_template.py — A unified HTML layout service for the BlackSwan dashboard.

Provides standard page wrapping, navigation generation with path-based activation,
and consistent header/footer injection.
"""

from __future__ import annotations

from typing import Final, List, Tuple
from fastapi import Request

# Navigation configuration: (path, display_label, unique_key)
DEFAULT_PAGE_TITLE: Final[str] = "BlackSwan Control Panel"
TABS_CONFIG: Final[List[Tuple[str, str, str]]] = [
    ("/", "🏠 Main", "main"),
    ("/trades", "📈 Trades", "trades"),
    ("/logs", "📜 Logs", "logs"),
    ("/dashboard", "📊 Dashboard", "dashboard"),
    ("/mutations", "🧬 Mutations", "mutations"),
    ("/settings", "⚙️ Settings", "settings"),
]


def render_page(request: Request, content: str, title: str = DEFAULT_PAGE_TITLE) -> str:
    """
    Wraps provided HTML content in the application's base template.

    Args:
        request: FastAPI request object to resolve the current active navigation tab.
        content: HTML string for the main content area.
        title: Page title for the document metadata.

    Returns:
        A complete HTML5 document string.

    Raises:
        ValueError: If `request` or `content` is missing.
    """
    if not request:
        raise ValueError("Request object cannot be None.")
    if not content:
        raise ValueError("Content cannot be None.")

    # Resolve active tab based on request path
    active_tab: str = next(
        (key for href, _, key in TABS_CONFIG if request.url.path == href), ""
    )

    # Generate tab HTML components
    tabs_list: List[str] = [
        f'<a href="{href}" class="{"active" if key == active_tab else ""}">{label}</a>'
        for href, label, key in TABS_CONFIG
    ]
    tabs_html: str = "\n        ".join(tabs_list)

    return f"""<!DOCTYPE html>
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
    <nav class="tabs">
        {tabs_html}
    </nav>
    <main>
        {content}
    </main>
    <script src="/static/js/main.js"></script>
</body>
</html>"""