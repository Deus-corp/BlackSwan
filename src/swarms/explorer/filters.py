"""Shared URL and domain filtering utilities for Explorer."""

from __future__ import annotations

from urllib.parse import urlparse

from src.swarms.explorer.meta_agent_core.frontier_filters import (
    is_low_value_frontier_url,
)


# Domains that should never be targeted for exploration.
LOW_VALUE_TARGET_DOMAINS = frozenset(
    {
        "www.googletagmanager.com",
        "googletagmanager.com",
        "www.google-analytics.com",
        "google-analytics.com",
        "stats.g.doubleclick.net",
        "doubleclick.net",
        "iana.org",
        "www.iana.org",
        "donate.python.org",
        "github.githubassets.com",
        "analytics.githubassets.com",
        "githubassets.com",
        "gmpg.org",
        "www.w3.org",
        "w3.org",
        "fosstodon.org",
        "githubuniverse.com",
        "www.pythonjobshq.com",
        "pythonjobshq.com",
        "brochure.getpython.info",
        "support.github.com",
        "skills.github.com",
        "translations.python.org",
        "support.realpython.com",
        "helpscout.com",
        "www.helpscout.com",
        "pycon.blogspot.com",
        "pyfound.blogspot.com",
        "realpython.workable.com",
        "apply.workable.com",
        "workable.com",
        "www.workable.com",
        "workablehr.s3.amazonaws.com",
        "workable-application-form.s3.amazonaws.com",
        "youtube.com",
        "www.youtube.com",
        "youtu.be",
        "developers.google.com",
        "planetpython.org",
        "www.planetpython.org",
        "facebook.com",
        "www.facebook.com",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "www.linkedin.com",
    }
)

LOW_VALUE_TARGET_PATH_PARTS = (
    "/account/",
    "/accounts/",
    "/login",
    "/logout",
    "/signin",
    "/signup",
    "/sign-up",
    "/register",
    "/password",
    "/onboarding",
    "/donate",
    "/donation",
    "/privacy",
    "/terms",
    "/cookies",
    "/cookie",
    "/cdn-cgi/",
    "/help/example-domains",
    "/domains/example",
    "/_static",
    "/assets/",
    "/static/",
    "/fonts/",
    "/font/",
    "/1999/xlink",
    "/xfn/",
    "/@",
    "/continue",
    "/discussion",
    "/category/",
    "/docs-refer",
    "/events",
    "/event",
    "/calendar",
    "/jobs",
    "/job",
    "/careers",
    "/career",
    "/apply",
    "/application",
    "/llms.txt",
    "/youtube",
    "/channel/",
    "/watch",
    "/playlist",
)

LOW_VALUE_TARGET_QUERY_PARTS = (
    "utm_",
    "fbclid=",
    "gclid=",
    "gtag/js",
    "google/login",
    "next=",
    "intent=learning_plan",
)

SKIPPED_URL_EXTENSIONS = (
    ".7z",
    ".avi",
    ".bin",
    ".bmp",
    ".css",
    ".dmg",
    ".doc",
    ".docx",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".iso",
    ".jpeg",
    ".jpg",
    ".js",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".svg",
    ".tar",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
    ".xml",
)


def is_low_value_target_url(url: str) -> bool:
    """Return True if the URL belongs to a low-value domain/path/query.

    This function is used by both ExplorerNode and ExplorerMetaAgent
    to skip targets that are unlikely to be useful evidence or discovery.
    """
    normalized = url.strip()
    if not normalized:
        return True

    # Delegate to the shared frontier filter first.
    if is_low_value_frontier_url(normalized):
        return True

    parsed = urlparse(normalized)
    domain = parsed.netloc.lower().split("@")[-1].split(":")[0]
    path = parsed.path.lower()
    query = parsed.query.lower()
    full = f"{path}?{query}" if query else path

    # ---- Special domain-specific rules ----
    if domain == "wiki.python.org" and ("event" in path or "calendar" in path):
        return True

    if domain == "realpython.com" and path in {
        "/security",
        "/security/",
        "/books",
        "/books/",
    }:
        return True

    if domain == "github.com" and ("is%3aprivate" in query or "is:private" in query):
        return True

    if domain == "realpython.com" and path.startswith("/courses/"):
        if path.endswith("/continue") or path.endswith("/discussion"):
            return True
        if "/continue/" in path or "/discussion/" in path:
            return True

    if domain == "realpython.com" and path.startswith("/tutorials/"):
        return True

    if domain == "realpython.com" and path.startswith("/learning-paths/"):
        return True

    if domain == "github.com" and path.startswith(
        (
            "/customer-stories",
            "/features",
            "/pricing",
            "/enterprise",
        )
    ):
        return True

    # ---- Generic filters ----
    if not domain:
        return True

    if domain in LOW_VALUE_TARGET_DOMAINS:
        return True

    if any(part in path for part in LOW_VALUE_TARGET_PATH_PARTS):
        return True

    if any(part in query for part in LOW_VALUE_TARGET_QUERY_PARTS):
        return True

    if full.endswith(SKIPPED_URL_EXTENSIONS):
        return True

    return False


def is_target_blacklisted(url: str) -> bool:
    """Return True if the URL scheme/netloc are invalid for exploration."""
    parsed = urlparse(url)
    return parsed.scheme not in {"http", "https"} or not parsed.netloc