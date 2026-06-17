from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import quote_plus, urlparse

from .utils import is_probably_valid_url, normalize_url

EXPLORER_EXECUTION_RISK_TIER = "network_read"
EXPLORER_COORDINATION_CHANNEL = "crdt_genomes"

DEFAULT_SOURCE_ADAPTERS = (
    "rss",
    "sitemap",
    "github",
    "arxiv",
    "search",
)


def build_source_adapter_targets(
    *,
    goal: str = "",
    adapters: Iterable[str] | None = None,
    seed_urls: Iterable[str] | None = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Build initial explorer targets from source adapters.

    These are dataflow targets for ExplorerNode. They do not perform external
    writes and do not require credentials.
    """
    clean_goal = " ".join(str(goal or "").split())
    selected = tuple(
        str(item or "").strip().lower()
        for item in (adapters or DEFAULT_SOURCE_ADAPTERS)
        if str(item or "").strip()
    )
    seeds = [
        normalize_url(str(url or ""))
        for url in (seed_urls or [])
        if normalize_url(str(url or ""))
    ]

    targets: list[dict[str, Any]] = []

    for adapter in selected:
        if adapter == "rss":
            targets.extend(_rss_targets(seeds))
        elif adapter == "sitemap":
            targets.extend(_sitemap_targets(seeds))
        elif adapter == "github":
            targets.extend(_github_targets(clean_goal))
        elif adapter == "arxiv":
            targets.extend(_arxiv_targets(clean_goal))
        elif adapter in {"search", "search_source", "web_search"}:
            targets.extend(_search_targets(clean_goal))

    return _dedupe_targets(targets)[: max(0, int(limit or 0))]


def _rss_targets(seed_urls: list[str]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []

    for root in _site_roots(seed_urls):
        for path in ("/feed", "/rss.xml", "/atom.xml", "/feed.xml"):
            targets.append(
                _target(
                    f"{root}{path}",
                    source_adapter="rss",
                    source_kind="rss_or_atom_feed",
                    discovery_method="rss_feed_candidate",
                    score=0.75,
                )
            )

    return targets


def _sitemap_targets(seed_urls: list[str]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []

    for root in _site_roots(seed_urls):
        for path in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
            targets.append(
                _target(
                    f"{root}{path}",
                    source_adapter="sitemap",
                    source_kind="sitemap_xml",
                    discovery_method="sitemap_candidate",
                    score=0.85,
                )
            )

    return targets


def _github_targets(goal: str) -> list[dict[str, Any]]:
    if not goal:
        return []

    q = quote_plus(goal)
    return [
        _target(
            f"https://github.com/search?q={q}&type=repositories",
            source_adapter="github",
            source_kind="github_repository_search",
            discovery_method="github_search",
            score=0.8,
        ),
        _target(
            f"https://github.com/search?q={q}&type=code",
            source_adapter="github",
            source_kind="github_code_search",
            discovery_method="github_search",
            score=0.65,
        ),
    ]


def _arxiv_targets(goal: str) -> list[dict[str, Any]]:
    if not goal:
        return []

    query = quote_plus(f"all:{goal}")
    return [
        _target(
            (
                "https://export.arxiv.org/api/query"
                f"?search_query={query}&start=0&max_results=10"
            ),
            source_adapter="arxiv",
            source_kind="arxiv_api_query",
            discovery_method="arxiv_api_search",
            score=0.9,
        ),
        _target(
            f"https://arxiv.org/search/?query={quote_plus(goal)}&searchtype=all",
            source_adapter="arxiv",
            source_kind="arxiv_web_search",
            discovery_method="arxiv_web_search",
            score=0.7,
        ),
    ]


def _search_targets(goal: str) -> list[dict[str, Any]]:
    if not goal:
        return []

    q = quote_plus(goal)
    return [
        _target(
            f"https://duckduckgo.com/html/?q={q}",
            source_adapter="search",
            source_kind="public_search_html",
            discovery_method="public_search_query",
            score=0.65,
        )
    ]


def _site_roots(seed_urls: list[str]) -> list[str]:
    roots: list[str] = []
    seen: set[str] = set()

    for url in seed_urls:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue

        root = f"{parsed.scheme}://{parsed.netloc}"
        if root in seen:
            continue

        seen.add(root)
        roots.append(root)

    return roots


def _target(
    url: str,
    *,
    source_adapter: str,
    source_kind: str,
    discovery_method: str,
    score: float,
) -> dict[str, Any]:
    normalized = normalize_url(url)
    return {
        "url": normalized,
        "source_adapter": source_adapter,
        "source_kind": source_kind,
        "discovery_method": discovery_method,
        "score": float(score),
        "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
        "coordination_channel": EXPLORER_COORDINATION_CHANNEL,
        "network_read_candidate": True,
        "external_write_performed": False,
        "real_execution_enabled": False,
    }


def _dedupe_targets(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for target in targets:
        url = normalize_url(str(target.get("url") or ""))
        if not url or url in seen:
            continue
        if not is_probably_valid_url(url):
            continue

        seen.add(url)
        out.append({**target, "url": url})

    out.sort(
        key=lambda item: (
            -float(item.get("score", 0.0) or 0.0),
            str(item.get("source_adapter") or ""),
            str(item.get("url") or ""),
        )
    )
    return out