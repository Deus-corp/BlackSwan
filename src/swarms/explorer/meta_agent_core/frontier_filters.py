"""Shared Explorer frontier filtering helpers.

These helpers are deterministic and do not perform network I/O.
They only classify whether a URL is low-value for Explorer research frontier.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse


LOW_VALUE_FRONTIER_DOMAINS = frozenset(
    {
        "githubstatus.com",
        "www.githubstatus.com",
        "au.githubstatus.com",
        "subscriptions.statuspage.io",
        "statuspage.io",
    }
)

LOW_VALUE_FRONTIER_DOMAIN_SUFFIXES = (
    ".statuspage.io",
)

LOW_VALUE_FRONTIER_PATH_MARKERS = frozenset(
    {
        "account",
        "accounts",
        "auth",
        "authorize",
        "callback",
        "contact",
        "cookie",
        "cookies",
        "donate",
        "login",
        "logout",
        "oauth",
        "privacy",
        "request",
        "security",
        "signin",
        "signup",
        "slack_authentication",
        "status",
        "subscribe",
        "subscription",
        "subscriptions",
        "support",
        "terms",
    }
)

LOW_VALUE_FRONTIER_QUERY_KEYS = frozenset(
    {
        "client_id",
        "redirect_uri",
        "scope",
        "state",
        "utm_campaign",
        "utm_content",
        "utm_medium",
        "utm_source",
        "utm_term",
    }
)

LOW_VALUE_FRONTIER_EXACT_PATHS = frozenset(
    {
        "/",
        "/about",
        "/about/",
        "/community",
        "/community/",
        "/contact",
        "/contact/",
        "/privacy",
        "/privacy/",
        "/security",
        "/security/",
        "/support",
        "/support/",
        "/terms",
        "/terms/",
    }
)


def _normalized_domain(url: str) -> str:
    return urlparse(str(url or "")).netloc.lower().split("@")[-1]


def _path_parts(url: str) -> list[str]:
    parsed = urlparse(str(url or ""))
    return [
        part.strip().lower()
        for part in parsed.path.strip("/").split("/")
        if part.strip()
    ]


def is_low_value_frontier_url(url: str) -> bool:
    """Return True when URL is likely low-value for research frontier expansion."""
    raw = str(url or "").strip()
    if not raw:
        return True

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return True

    domain = _normalized_domain(raw)
    path = parsed.path.lower() or "/"
    parts = _path_parts(raw)
    query = parse_qs(parsed.query)

    if domain in LOW_VALUE_FRONTIER_DOMAINS:
        return True

    if any(domain.endswith(suffix) for suffix in LOW_VALUE_FRONTIER_DOMAIN_SUFFIXES):
        return True

    if path in LOW_VALUE_FRONTIER_EXACT_PATHS:
        # Root/about/support/privacy pages can be fetched as frontier anchors,
        # but they should not be recursively expanded as research evidence.
        return True

    if any(part in LOW_VALUE_FRONTIER_PATH_MARKERS for part in parts):
        return True

    if any(key.lower() in LOW_VALUE_FRONTIER_QUERY_KEYS for key in query):
        return True

    # Explicit OAuth/auth endpoints often appear after redirects and should not
    # become research frontier targets.
    haystack = f"{domain} {path} {parsed.query}".lower()
    if any(
        marker in haystack
        for marker in (
            "oauth",
            "slack_authentication",
            "signin",
            "signup",
            "login",
            "privacy-statement",
            "privacy-policies",
            "terms-of-service",
            "statuspage",
        )
    ):
        return True

    return False