"""Deterministic Explorer research-goal source planning.

This module turns a research goal into auditable source/evidence candidates.
It does not perform network I/O and does not execute external writes.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Literal, TypedDict
from urllib.parse import quote_plus, urlparse


EXPLORER_SOURCE_PLANNER_VERSION = "explorer_source_planner_v1"

EXPLORER_EXECUTION_RISK_TIER = "network_read"
EXPLORER_COORDINATION_CHANNEL = "crdt_genomes"


SourceAdapterName = Literal[
    "arxiv",
    "github",
    "search",
    "sitemap",
    "seed",
    "evidence",
]


class SourcePlanCandidate(TypedDict, total=False):
    """One planned Explorer target candidate."""

    url: str
    source_adapter: str
    source_kind: str
    discovery_method: str

    score: float
    seed_score: float
    source_type_score: float
    authority_score: float
    freshness_score: float
    system_relevance_score: float
    quality_score: float
    source_score: float

    preferred_evidence_target: bool
    goal_alignment_score: float
    goal_terms_matched: list[str]

    goal: str
    research_goal: str
    research_goal_text: str

    execution_risk_tier: str
    coordination_channel: str
    network_read_candidate: bool
    external_write_performed: bool
    real_execution_enabled: bool

    plan_id: str
    plan_rank: int
    planner_version: str
    rationale: str


class ResearchSourcePlan(TypedDict):
    """Deterministic source plan emitted by Explorer meta-agent planning code."""

    type: str
    goal: str
    plan_id: str
    adapters: list[str]
    seed_urls: list[str]
    candidate_count: int
    candidates: list[SourcePlanCandidate]
    planner_version: str
    execution_risk_tier: str
    external_write_performed: bool
    real_execution_enabled: bool


_GOAL_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
        "system",
        "systems",
        "research",
        "study",
        "find",
        "about",
    }
)

_DEFAULT_ADAPTERS: tuple[str, ...] = (
    "github",
    "arxiv",
    "search",
    "sitemap",
)

# A small deterministic seed list. These are not fetched here; they are only
# candidates for the read-only Explorer frontier. Keep this list conservative
# and auditable.
_CURATED_EVIDENCE_CANDIDATES: tuple[dict[str, Any], ...] = (
    {
        "url": "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai",
        "keywords": (
            "agent",
            "agents",
            "ai",
            "llm",
            "python",
            "pydantic",
            "type",
            "safe",
            "workflow",
        ),
        "authority_score": 0.72,
        "freshness_score": 0.50,
        "rationale": "course-level Python LLM agent evidence candidate",
    },
    {
        "url": "https://docs.github.com/en/search-github/searching-on-github/searching-code",
        "keywords": (
            "github",
            "code",
            "search",
            "agent",
            "agents",
            "repository",
            "repositories",
        ),
        "authority_score": 0.79,
        "freshness_score": 0.50,
        "rationale": "GitHub code search documentation useful for source discovery",
    },
    {
        "url": "https://docs.python.org/3/library/asyncio.html",
        "keywords": (
            "python",
            "async",
            "asyncio",
            "runtime",
            "agent",
            "agents",
            "orchestration",
        ),
        "authority_score": 0.96,
        "freshness_score": 0.50,
        "rationale": "Python async runtime documentation",
    },
)


def normalize_plan_url(url: str) -> str:
    """Normalize a planner URL without performing network I/O."""
    raw = str(url or "").strip()
    if not raw:
        return ""

    if raw.startswith("//"):
        raw = f"https:{raw}"

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return ""

    normalized = raw.split("#", 1)[0].strip()

    # Keep root slash, remove trailing slash elsewhere for stable dedupe.
    parsed = urlparse(normalized)
    if parsed.path not in {"", "/"} and normalized.endswith("/"):
        normalized = normalized.rstrip("/")

    return normalized


def goal_terms(goal: str) -> list[str]:
    """Extract stable planner terms from a research goal."""
    terms: list[str] = []

    for raw in re.split(r"[^A-Za-z0-9]+", str(goal or "").lower()):
        term = raw.strip()
        if not term:
            continue
        if len(term) < 3:
            continue
        if term in _GOAL_STOPWORDS:
            continue
        if term not in terms:
            terms.append(term)

    return terms


def _plan_id(goal: str, seed_urls: Iterable[str], adapters: Iterable[str]) -> str:
    material = "|".join(
        [
            str(goal or "").strip().lower(),
            ",".join(sorted(str(url) for url in seed_urls if url)),
            ",".join(sorted(str(adapter) for adapter in adapters if adapter)),
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
    return f"exp_source_plan_{digest}"


def _url_haystack(url: str, rationale: str = "") -> str:
    parsed = urlparse(str(url or ""))
    return " ".join(
        [
            parsed.netloc.lower(),
            parsed.path.lower().replace("-", " ").replace("_", " "),
            parsed.query.lower().replace("+", " ").replace("%20", " "),
            str(rationale or "").lower(),
        ]
    )


def _matched_goal_terms(url: str, terms: list[str], *, rationale: str = "") -> list[str]:
    haystack = _url_haystack(url, rationale=rationale)
    return [term for term in terms if term in haystack]


def _goal_alignment_score(matched_terms: list[str], terms: list[str]) -> float:
    if not terms or not matched_terms:
        return 0.0

    ratio = len(matched_terms) / max(1, len(terms))
    if ratio >= 0.75:
        return 0.30
    if ratio >= 0.50:
        return 0.24
    if ratio >= 0.25:
        return 0.16
    return 0.10


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, round(float(value), 4)))


def _candidate(
    *,
    url: str,
    goal: str,
    plan_id: str,
    source_adapter: str,
    source_kind: str,
    discovery_method: str,
    terms: list[str],
    preferred_evidence_target: bool,
    seed_score: float,
    source_type_score: float,
    authority_score: float,
    freshness_score: float,
    rationale: str,
) -> SourcePlanCandidate:
    normalized_url = normalize_plan_url(url)
    matched = _matched_goal_terms(normalized_url, terms, rationale=rationale)
    goal_alignment = _goal_alignment_score(matched, terms)

    system_relevance = _clamp_score(
        0.50
        + min(0.35, len(matched) * 0.08)
        + (0.12 if preferred_evidence_target else 0.0)
        + min(0.08, goal_alignment)
    )
    quality_score = _clamp_score(
        0.35
        + (0.18 if preferred_evidence_target else 0.0)
        + source_type_score * 0.18
        + authority_score * 0.22
        + system_relevance * 0.22
        + freshness_score * 0.10
    )
    source_score = _clamp_score(
        quality_score
        + goal_alignment
        + (0.08 if preferred_evidence_target else 0.0)
    )

    return {
        "url": normalized_url,
        "source_adapter": source_adapter,
        "source_kind": source_kind,
        "discovery_method": discovery_method,
        "score": source_score,
        "seed_score": _clamp_score(seed_score),
        "source_type_score": _clamp_score(source_type_score),
        "authority_score": _clamp_score(authority_score),
        "freshness_score": _clamp_score(freshness_score),
        "system_relevance_score": system_relevance,
        "quality_score": quality_score,
        "source_score": source_score,
        "preferred_evidence_target": bool(preferred_evidence_target),
        "goal_alignment_score": goal_alignment,
        "goal_terms_matched": matched,
        "goal": goal,
        "research_goal": goal,
        "research_goal_text": goal,
        "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
        "coordination_channel": EXPLORER_COORDINATION_CHANNEL,
        "network_read_candidate": True,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "plan_id": plan_id,
        "plan_rank": 0,
        "planner_version": EXPLORER_SOURCE_PLANNER_VERSION,
        "rationale": rationale,
    }


def _github_candidates(goal: str, plan_id: str, terms: list[str]) -> list[SourcePlanCandidate]:
    query = quote_plus(goal)
    return [
        _candidate(
            url=f"https://github.com/search?q={query}&type=repositories",
            goal=goal,
            plan_id=plan_id,
            source_adapter="github",
            source_kind="github_repository_search",
            discovery_method="research_goal_github_repository_search",
            terms=terms,
            preferred_evidence_target=False,
            seed_score=0.80,
            source_type_score=0.86,
            authority_score=0.84,
            freshness_score=0.50,
            rationale="GitHub repository search for goal-aligned projects",
        ),
        _candidate(
            url=f"https://github.com/search?q={query}&type=code",
            goal=goal,
            plan_id=plan_id,
            source_adapter="github",
            source_kind="github_code_search",
            discovery_method="research_goal_github_code_search",
            terms=terms,
            preferred_evidence_target=False,
            seed_score=0.78,
            source_type_score=0.82,
            authority_score=0.84,
            freshness_score=0.50,
            rationale="GitHub code search for implementation evidence",
        ),
    ]


def _arxiv_candidates(goal: str, plan_id: str, terms: list[str]) -> list[SourcePlanCandidate]:
    query_plus = quote_plus(goal)
    query_arxiv = quote_plus(f"all:{goal}")
    return [
        _candidate(
            url=(
                "https://export.arxiv.org/api/query?"
                f"search_query={query_arxiv}&start=0&max_results=10"
            ),
            goal=goal,
            plan_id=plan_id,
            source_adapter="arxiv",
            source_kind="arxiv_api_query",
            discovery_method="research_goal_arxiv_api_search",
            terms=terms,
            preferred_evidence_target=False,
            seed_score=0.78,
            source_type_score=0.88,
            authority_score=0.86,
            freshness_score=0.55,
            rationale="arXiv API search for research papers",
        ),
        _candidate(
            url=f"https://arxiv.org/search?query={query_plus}&searchtype=all",
            goal=goal,
            plan_id=plan_id,
            source_adapter="arxiv",
            source_kind="arxiv_public_search",
            discovery_method="research_goal_arxiv_public_search",
            terms=terms,
            preferred_evidence_target=False,
            seed_score=0.72,
            source_type_score=0.78,
            authority_score=0.86,
            freshness_score=0.55,
            rationale="arXiv public search fallback",
        ),
    ]


def _search_candidates(goal: str, plan_id: str, terms: list[str]) -> list[SourcePlanCandidate]:
    query = quote_plus(goal)
    return [
        _candidate(
            url=f"https://duckduckgo.com/html?q={query}",
            goal=goal,
            plan_id=plan_id,
            source_adapter="search",
            source_kind="public_search_html",
            discovery_method="research_goal_public_search",
            terms=terms,
            preferred_evidence_target=False,
            seed_score=0.58,
            source_type_score=0.54,
            authority_score=0.55,
            freshness_score=0.50,
            rationale="public search source discovery",
        )
    ]


def _sitemap_candidates(goal: str, plan_id: str, terms: list[str]) -> list[SourcePlanCandidate]:
    return [
        _candidate(
            url="https://docs.python.org/sitemap-index.xml",
            goal=goal,
            plan_id=plan_id,
            source_adapter="sitemap",
            source_kind="sitemap_xml",
            discovery_method="research_goal_sitemap_seed",
            terms=terms,
            preferred_evidence_target=False,
            seed_score=0.60,
            source_type_score=0.72,
            authority_score=0.96,
            freshness_score=0.50,
            rationale="Python documentation sitemap seed",
        ),
        _candidate(
            url="https://docs.python.org/3/",
            goal=goal,
            plan_id=plan_id,
            source_adapter="sitemap",
            source_kind="documentation_root",
            discovery_method="research_goal_documentation_root",
            terms=terms,
            preferred_evidence_target=False,
            seed_score=0.64,
            source_type_score=0.70,
            authority_score=0.96,
            freshness_score=0.50,
            rationale="Python documentation root seed",
        ),
        _candidate(
            url="https://docs.github.com/",
            goal=goal,
            plan_id=plan_id,
            source_adapter="sitemap",
            source_kind="documentation_root",
            discovery_method="research_goal_documentation_root",
            terms=terms,
            preferred_evidence_target=False,
            seed_score=0.60,
            source_type_score=0.68,
            authority_score=0.79,
            freshness_score=0.50,
            rationale="GitHub documentation root seed",
        ),
    ]


def _curated_evidence_candidates(
    goal: str,
    plan_id: str,
    terms: list[str],
) -> list[SourcePlanCandidate]:
    candidates: list[SourcePlanCandidate] = []

    for item in _CURATED_EVIDENCE_CANDIDATES:
        url = str(item.get("url") or "").strip()
        keywords = [
            str(keyword).lower()
            for keyword in item.get("keywords", ())
            if str(keyword).strip()
        ]
        rationale = str(item.get("rationale") or "curated evidence candidate")

        matched_terms = [
            term
            for term in terms
            if term in keywords or term in _url_haystack(url, rationale=rationale)
        ]

        # Keep curated candidates conservative: include if they match at least one
        # goal term, or if the goal is sparse and the URL/rationale is clearly
        # agent/AI related.
        if not matched_terms:
            continue

        candidates.append(
            _candidate(
                url=url,
                goal=goal,
                plan_id=plan_id,
                source_adapter="evidence",
                source_kind="curated_evidence_url",
                discovery_method="research_goal_curated_evidence_candidate",
                terms=terms,
                preferred_evidence_target=True,
                seed_score=0.92,
                source_type_score=0.90,
                authority_score=float(item.get("authority_score", 0.70)),
                freshness_score=float(item.get("freshness_score", 0.50)),
                rationale=rationale,
            )
        )

    return candidates


def _seed_url_candidates(
    seed_urls: Iterable[str],
    *,
    goal: str,
    plan_id: str,
    terms: list[str],
) -> list[SourcePlanCandidate]:
    candidates: list[SourcePlanCandidate] = []

    for raw_url in seed_urls:
        url = normalize_plan_url(str(raw_url or ""))
        if not url:
            continue

        matched = _matched_goal_terms(url, terms)
        preferred = bool(matched)

        candidates.append(
            _candidate(
                url=url,
                goal=goal,
                plan_id=plan_id,
                source_adapter="seed",
                source_kind="operator_seed_url",
                discovery_method="research_goal_seed_url",
                terms=terms,
                preferred_evidence_target=preferred,
                seed_score=1.00,
                source_type_score=0.80 if preferred else 0.60,
                authority_score=0.70,
                freshness_score=0.50,
                rationale="operator-provided seed URL",
            )
        )

    return candidates


def _rank_and_dedupe(
    candidates: list[SourcePlanCandidate],
    *,
    limit: int,
) -> list[SourcePlanCandidate]:
    deduped: dict[str, SourcePlanCandidate] = {}

    for candidate in candidates:
        url = normalize_plan_url(str(candidate.get("url") or ""))
        if not url:
            continue

        candidate["url"] = url
        existing = deduped.get(url)
        if existing is None:
            deduped[url] = candidate
            continue

        if float(candidate.get("source_score", 0.0)) > float(
            existing.get("source_score", 0.0)
        ):
            deduped[url] = candidate

    ranked = sorted(
        deduped.values(),
        key=lambda item: (
            not bool(item.get("preferred_evidence_target")),
            -float(item.get("goal_alignment_score", 0.0) or 0.0),
            -float(item.get("source_score", 0.0) or 0.0),
            str(item.get("source_adapter") or ""),
            str(item.get("url") or ""),
        ),
    )

    limited = ranked[: max(1, int(limit or 1))]

    for index, candidate in enumerate(limited, start=1):
        candidate["plan_rank"] = index

    return limited


def build_research_source_plan(
    *,
    goal: str,
    seed_urls: Iterable[str] | None = None,
    adapters: Iterable[str] | None = None,
    limit: int = 20,
) -> ResearchSourcePlan:
    """Build a deterministic source plan for an Explorer research goal."""
    clean_goal = str(goal or "").strip()
    clean_seed_urls = [
        url
        for url in (
            normalize_plan_url(str(raw_url or ""))
            for raw_url in list(seed_urls or [])
        )
        if url
    ]

    clean_adapters = [
        str(adapter or "").strip().lower()
        for adapter in list(adapters or _DEFAULT_ADAPTERS)
        if str(adapter or "").strip()
    ]

    if not clean_adapters:
        clean_adapters = list(_DEFAULT_ADAPTERS)

    terms = goal_terms(clean_goal)
    plan_id = _plan_id(clean_goal, clean_seed_urls, clean_adapters)

    candidates: list[SourcePlanCandidate] = []

    candidates.extend(
        _seed_url_candidates(
            clean_seed_urls,
            goal=clean_goal,
            plan_id=plan_id,
            terms=terms,
        )
    )

    # Evidence candidates are planner-internal and may be emitted regardless of
    # adapter selection because they are read-only and ranked by goal alignment.
    candidates.extend(_curated_evidence_candidates(clean_goal, plan_id, terms))

    adapter_set = set(clean_adapters)
    if "github" in adapter_set:
        candidates.extend(_github_candidates(clean_goal, plan_id, terms))
    if "arxiv" in adapter_set:
        candidates.extend(_arxiv_candidates(clean_goal, plan_id, terms))
    if "search" in adapter_set:
        candidates.extend(_search_candidates(clean_goal, plan_id, terms))
    if "sitemap" in adapter_set:
        candidates.extend(_sitemap_candidates(clean_goal, plan_id, terms))

    ranked = _rank_and_dedupe(candidates, limit=limit)

    return {
        "type": "explorer_research_source_plan",
        "goal": clean_goal,
        "plan_id": plan_id,
        "adapters": clean_adapters,
        "seed_urls": clean_seed_urls,
        "candidate_count": len(ranked),
        "candidates": ranked,
        "planner_version": EXPLORER_SOURCE_PLANNER_VERSION,
        "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
        "external_write_performed": False,
        "real_execution_enabled": False,
    }


def build_research_source_plan_targets(
    *,
    goal: str,
    seed_urls: Iterable[str] | None = None,
    adapters: Iterable[str] | None = None,
    limit: int = 20,
) -> list[SourcePlanCandidate]:
    """Return only ranked target candidates from a research source plan."""
    plan = build_research_source_plan(
        goal=goal,
        seed_urls=seed_urls,
        adapters=adapters,
        limit=limit,
    )
    return list(plan["candidates"])