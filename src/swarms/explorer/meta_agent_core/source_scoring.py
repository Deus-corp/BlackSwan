from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote_plus, urlparse

from .utils import normalize_url


HIGH_AUTHORITY_DOMAINS: Mapping[str, float] = {
    "docs.python.org": 0.96,
    "www.python.org": 0.94,
    "python.org": 0.94,
    "peps.python.org": 0.95,
    "github.com": 0.84,
    "arxiv.org": 0.92,
    "export.arxiv.org": 0.92,
    "pypi.org": 0.82,
    "readthedocs.io": 0.78,
    "realpython.com": 0.72,
}

SOURCE_ADAPTER_BASE_SCORE: Mapping[str, float] = {
    "arxiv": 0.92,
    "sitemap": 0.82,
    "github": 0.78,
    "rss": 0.74,
    "search": 0.60,
    "": 0.50,
}

SOURCE_KIND_BASE_SCORE: Mapping[str, float] = {
    "arxiv_api_query": 0.94,
    "arxiv_web_search": 0.82,
    "sitemap_xml": 0.82,
    "github_repository_search": 0.80,
    "github_code_search": 0.70,
    "rss_or_atom_feed": 0.76,
    "public_search_html": 0.60,
    "html_link": 0.55,
    "": 0.50,
}

SYSTEM_IMPROVEMENT_KEYWORDS: tuple[str, ...] = (
    "agent",
    "agents",
    "autonomous",
    "ai",
    "llm",
    "memory",
    "retrieval",
    "rag",
    "swarm",
    "multi-agent",
    "orchestration",
    "planning",
    "evaluation",
    "eval",
    "observability",
    "runtime",
    "sandbox",
    "security",
    "safety",
    "python",
    "async",
    "crdt",
    "database",
    "testing",
    "pytest",
    "classification",
    "dedupe",
    "freshness",
    "ranking",
    "finance",
    "trading",
    "blockchain",
    "ethereum",
    "sepolia",
)

YEAR_PATTERN = re.compile(r"(?:^|[^0-9])((?:19|20)[0-9]{2})(?:[^0-9]|$)")


def score_source_target(
    url: str,
    *,
    source_adapter: str = "",
    source_kind: str = "",
    discovery_method: str = "",
    goal: str = "",
    existing_score: Any = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """Return deterministic quality/freshness scores for an explorer target.

    The score is intentionally heuristic and local. It does not perform network
    access. It only ranks already discovered network_read targets.
    """
    normalized = normalize_url(str(url or ""))
    meta = metadata if isinstance(metadata, Mapping) else {}

    adapter = str(source_adapter or meta.get("source_adapter") or "").strip().lower()
    kind = str(source_kind or meta.get("source_kind") or "").strip().lower()
    method = str(
        discovery_method or meta.get("discovery_method") or ""
    ).strip().lower()

    seed_score = _safe_float(
        existing_score if existing_score is not None else meta.get("score"),
        default=0.50,
    )

    authority_score = _authority_score(normalized)
    freshness_score = _freshness_score(normalized, meta)
    adapter_score = SOURCE_ADAPTER_BASE_SCORE.get(adapter, 0.50)
    kind_score = SOURCE_KIND_BASE_SCORE.get(kind, 0.50)
    relevance_score = _system_relevance_score(
        normalized,
        goal=str(goal or meta.get("goal") or ""),
        source_kind=kind,
        discovery_method=method,
    )

    source_type_score = max(adapter_score, kind_score)

    source_score = _clamp01(
        0.20 * seed_score
        + 0.20 * source_type_score
        + 0.22 * authority_score
        + 0.18 * freshness_score
        + 0.20 * relevance_score
    )

    return {
        "seed_score": round(_clamp01(seed_score), 4),
        "source_type_score": round(_clamp01(source_type_score), 4),
        "authority_score": round(_clamp01(authority_score), 4),
        "freshness_score": round(_clamp01(freshness_score), 4),
        "system_relevance_score": round(_clamp01(relevance_score), 4),
        "quality_score": round(source_score, 4),
        "source_score": round(source_score, 4),
    }


def _authority_score(url: str) -> float:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().split("@")[-1].split(":")[0]

    if not host:
        return 0.35

    if host in HIGH_AUTHORITY_DOMAINS:
        return HIGH_AUTHORITY_DOMAINS[host]

    for domain, score in HIGH_AUTHORITY_DOMAINS.items():
        if host.endswith(f".{domain}"):
            return max(0.50, score - 0.05)

    if host.endswith(".edu"):
        return 0.82
    if host.endswith(".gov"):
        return 0.86
    if host.endswith(".org"):
        return 0.66
    if host.endswith(".io"):
        return 0.58

    return 0.50


def _freshness_score(url: str, metadata: Mapping[str, Any]) -> float:
    explicit = (
        metadata.get("freshness_score")
        or metadata.get("source_freshness_score")
        or metadata.get("recency_score")
    )
    if explicit is not None:
        return _safe_float(explicit, default=0.50)

    year = _extract_year(url)
    if year is None:
        return 0.50

    now_year = datetime.now(timezone.utc).year

    if year >= now_year:
        return 0.90
    if year == now_year - 1:
        return 0.82
    if year == now_year - 2:
        return 0.72
    if year >= now_year - 5:
        return 0.60
    if year >= now_year - 10:
        return 0.45

    return 0.30


def _system_relevance_score(
    url: str,
    *,
    goal: str,
    source_kind: str,
    discovery_method: str,
) -> float:
    parsed = urlparse(url)

    query_text = " ".join(
        " ".join(values)
        for values in parse_qs(parsed.query, keep_blank_values=True).values()
    )

    source_text = " ".join(
        [
            unquote_plus(parsed.netloc or ""),
            unquote_plus(parsed.path or ""),
            unquote_plus(parsed.query or ""),
            unquote_plus(query_text or ""),
            source_kind,
            discovery_method,
        ]
    ).lower()
    goal_text = str(goal or "").lower()

    source_matches = sum(
        1 for keyword in SYSTEM_IMPROVEMENT_KEYWORDS if keyword in source_text
    )
    goal_matches = sum(
        1 for keyword in SYSTEM_IMPROVEMENT_KEYWORDS if keyword in goal_text
    )

    # Goal relevance should provide intent context, but it must not make every
    # target maximally relevant. The source URL/kind/method should carry most of
    # the relevance signal.
    score = 0.35
    score += min(0.45, source_matches * 0.12)
    score += min(0.20, goal_matches * 0.04)

    if source_kind in {
        "arxiv_api_query",
        "github_repository_search",
        "sitemap_xml",
        "rss_or_atom_feed",
    }:
        score += 0.05

    if discovery_method in {
        "arxiv_api_search",
        "github_search",
        "sitemap_candidate",
        "rss_feed_candidate",
    }:
        score += 0.03

    return _clamp01(score)


def _extract_year(text: str) -> int | None:
    years: list[int] = []

    for match in YEAR_PATTERN.finditer(str(text or "")):
        try:
            years.append(int(match.group(1)))
        except (TypeError, ValueError):
            continue

    if not years:
        return None

    return max(years)


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))