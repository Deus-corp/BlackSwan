"""Deterministic Explorer research-goal source planning.

This module turns a research goal into auditable source/evidence candidates.
It does not perform network I/O and does not execute external writes.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Literal, TypedDict, Mapping
from urllib.parse import quote_plus, urlparse

from src.swarms.explorer.meta_agent_core.public_search_templates import (
    build_safe_public_search_template_plan,
    public_search_template_to_candidate,
)


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

    evidence_category: str
    topic_tags: list[str]
    content_expectation: str


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

_GOAL_PROFILE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "agents": (
        "agent",
        "agents",
        "autonomous",
        "multiagent",
        "multi-agent",
        "llm",
        "ai",
    ),
    "memory": (
        "memory",
        "memories",
        "retrieval",
        "rag",
        "vector",
        "embedding",
        "index",
        "knowledge",
    ),
    "orchestration": (
        "orchestration",
        "workflow",
        "runtime",
        "async",
        "asyncio",
        "task",
        "coordination",
        "scheduler",
    ),
    "evaluation": (
        "evaluation",
        "benchmark",
        "quality",
        "test",
        "testing",
        "score",
        "metrics",
    ),
    "code_improvement": (
        "code",
        "coding",
        "improvement",
        "review",
        "repository",
        "github",
        "python",
    ),
}


def goal_profile_tags(terms: list[str]) -> list[str]:
    """Infer broad research profile tags from normalized goal terms."""
    tags: list[str] = []

    term_set = set(terms)
    for tag, keywords in _GOAL_PROFILE_KEYWORDS.items():
        if any(keyword in term_set for keyword in keywords):
            tags.append(tag)

    return tags

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
        "topic_tags": ("agents", "code_improvement", "orchestration"),
        "evidence_category": "python_llm_agents",
        "authority_score": 0.72,
        "freshness_score": 0.50,
        "rationale": "course-level Python LLM agent evidence candidate",
        "content_expectation": "Python LLM agent implementation pattern with typed runtime validation",
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
            "task",
            "event",
            "loop",
        ),
        "topic_tags": ("orchestration", "code_improvement"),
        "evidence_category": "python_async_runtime",
        "authority_score": 0.96,
        "freshness_score": 0.50,
        "rationale": "Python async runtime documentation",
        "content_expectation": "Runtime primitives for concurrent agent/node execution",
    },
    {
        "url": "https://docs.python.org/3/library/asyncio-task.html",
        "keywords": (
            "python",
            "asyncio",
            "task",
            "tasks",
            "coroutine",
            "runtime",
            "orchestration",
            "agent",
        ),
        "topic_tags": ("orchestration", "code_improvement"),
        "evidence_category": "python_async_tasks",
        "authority_score": 0.96,
        "freshness_score": 0.50,
        "rationale": "Python asyncio tasks documentation",
        "content_expectation": "Task lifecycle and scheduling patterns for swarm runtime",
    },
    {
        "url": "https://docs.python.org/3/library/queue.html",
        "keywords": (
            "python",
            "queue",
            "task",
            "coordination",
            "producer",
            "consumer",
            "thread",
            "runtime",
        ),
        "topic_tags": ("orchestration", "memory", "code_improvement"),
        "evidence_category": "python_coordination_primitives",
        "authority_score": 0.96,
        "freshness_score": 0.50,
        "rationale": "Python queue coordination primitives",
        "content_expectation": "Deterministic coordination primitives for pipeline components",
    },
    {
        "url": "https://docs.python.org/3/library/sqlite3.html",
        "keywords": (
            "python",
            "sqlite",
            "sqlite3",
            "database",
            "memory",
            "persistence",
            "storage",
            "index",
        ),
        "topic_tags": ("memory", "code_improvement"),
        "evidence_category": "python_persistence",
        "authority_score": 0.96,
        "freshness_score": 0.50,
        "rationale": "Python sqlite persistence documentation",
        "content_expectation": "Local persistence and indexing patterns for memory swarm",
    },
    {
        "url": "https://docs.python.org/3/library/dataclasses.html",
        "keywords": (
            "python",
            "dataclass",
            "dataclasses",
            "schema",
            "typed",
            "model",
            "data",
        ),
        "topic_tags": ("memory", "code_improvement"),
        "evidence_category": "python_data_models",
        "authority_score": 0.96,
        "freshness_score": 0.50,
        "rationale": "Python dataclasses documentation",
        "content_expectation": "Structured data modeling for evidence and memory records",
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
            "implementation",
        ),
        "topic_tags": ("code_improvement", "agents"),
        "evidence_category": "github_code_search",
        "authority_score": 0.79,
        "freshness_score": 0.50,
        "rationale": "GitHub code search documentation useful for source discovery",
        "content_expectation": "Code search syntax for implementation evidence discovery",
    },
    {
        "url": "https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories",
        "keywords": (
            "github",
            "repository",
            "repositories",
            "search",
            "code",
            "agent",
            "agents",
            "project",
        ),
        "topic_tags": ("code_improvement", "agents"),
        "evidence_category": "github_repository_search",
        "authority_score": 0.79,
        "freshness_score": 0.50,
        "rationale": "GitHub repository search documentation",
        "content_expectation": "Repository discovery syntax for open-source agent/memory systems",
    },
    {
        "url": "https://docs.github.com/en/copilot",
        "keywords": (
            "github",
            "copilot",
            "ai",
            "coding",
            "code",
            "agent",
            "review",
            "improvement",
        ),
        "topic_tags": ("code_improvement", "agents"),
        "evidence_category": "ai_code_assistance",
        "authority_score": 0.79,
        "freshness_score": 0.60,
        "rationale": "GitHub Copilot documentation root for AI coding workflows",
        "content_expectation": "AI-assisted code improvement and review workflow evidence",
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
    evidence_category: str = "",
    topic_tags: Iterable[str] | None = None,
    content_expectation: str = "",
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
        "evidence_category": str(evidence_category or ""),
        "topic_tags": [
            str(tag)
            for tag in list(topic_tags or [])
            if str(tag).strip()
        ],
        "content_expectation": str(content_expectation or ""),
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
    profile_tags = set(goal_profile_tags(terms))

    for item in _CURATED_EVIDENCE_CANDIDATES:
        url = str(item.get("url") or "").strip()
        keywords = [
            str(keyword).lower()
            for keyword in item.get("keywords", ())
            if str(keyword).strip()
        ]
        item_topic_tags = {
            str(tag).lower()
            for tag in item.get("topic_tags", ())
            if str(tag).strip()
        }
        rationale = str(item.get("rationale") or "curated evidence candidate")

        matched_terms = [
            term
            for term in terms
            if term in keywords or term in _url_haystack(url, rationale=rationale)
        ]
        profile_overlap = bool(profile_tags and item_topic_tags & profile_tags)

        # Include direct term matches, plus category/profile matches. This lets
        # goals like "autonomous agents memory systems" pull runtime, persistence,
        # and code-search evidence even when every term is not in the URL.
        if not matched_terms and not profile_overlap:
            continue

        candidate = _candidate(
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
            evidence_category=str(item.get("evidence_category") or ""),
            topic_tags=sorted(item_topic_tags),
            content_expectation=str(item.get("content_expectation") or ""),
        )

        # Profile overlap is useful but weaker than direct URL/keyword matches.
        if profile_overlap and not matched_terms:
            candidate["goal_alignment_score"] = max(
                float(candidate.get("goal_alignment_score", 0.0)),
                0.10,
            )
            candidate["system_relevance_score"] = max(
                float(candidate.get("system_relevance_score", 0.0)),
                0.72,
            )
            candidate["source_score"] = max(
                float(candidate.get("source_score", 0.0)),
                0.72,
            )
            candidate["score"] = candidate["source_score"]

        candidates.append(candidate)

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

        existing_adapter = str(existing.get("source_adapter") or "")
        candidate_adapter = str(candidate.get("source_adapter") or "")

        # Operator seed URLs are protected. They must remain in the plan even
        # when a generated sitemap/docs candidate for the same URL has a higher
        # computed score.
        if existing_adapter == "seed" and candidate_adapter != "seed":
            continue

        if candidate_adapter == "seed" and existing_adapter != "seed":
            deduped[url] = candidate
            continue

        if float(candidate.get("source_score", 0.0)) > float(
            existing.get("source_score", 0.0)
        ):
            deduped[url] = candidate

    def sort_key(item: SourcePlanCandidate) -> tuple[Any, ...]:
        return (
            str(item.get("source_adapter") or "") != "seed",
            not bool(item.get("preferred_evidence_target")),
            -float(item.get("goal_alignment_score", 0.0) or 0.0),
            -float(item.get("seed_score", 0.0) or 0.0),
            -float(item.get("source_score", 0.0) or 0.0),
            str(item.get("source_adapter") or ""),
            str(item.get("url") or ""),
        )

    ranked = sorted(deduped.values(), key=sort_key)

    max_items = max(1, int(limit or 1))
    limited = ranked[:max_items]

    # Preserve broad source coverage under expanded curated evidence. Without
    # this, high-scoring evidence candidates can crowd out source adapters such
    # as public search, which breaks the source-planning contract.
    coverage_adapters = ("seed", "github", "arxiv", "search", "sitemap")

    def adapter_counts(items: list[SourcePlanCandidate]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            adapter = str(item.get("source_adapter") or "")
            if not adapter:
                continue
            counts[adapter] = counts.get(adapter, 0) + 1
        return counts

    def best_adapter_candidate(adapter: str) -> SourcePlanCandidate | None:
        for item in ranked:
            if str(item.get("source_adapter") or "") == adapter:
                return item
        return None

    def replacement_index(
        items: list[SourcePlanCandidate],
    ) -> int:
        counts = adapter_counts(items)

        # First try replacing optional duplicate adapter candidates from the end.
        for index in range(len(items) - 1, -1, -1):
            item = items[index]
            adapter = str(item.get("source_adapter") or "")

            if adapter == "seed":
                continue

            if adapter in coverage_adapters and counts.get(adapter, 0) <= 1:
                continue

            if not bool(item.get("preferred_evidence_target")):
                return index

        # If every removable candidate is preferred evidence, replace the weakest
        # non-seed preferred evidence candidate. Adapter coverage is more useful
        # than keeping every curated evidence URL in a small top-N plan.
        for index in range(len(items) - 1, -1, -1):
            item = items[index]
            adapter = str(item.get("source_adapter") or "")

            if adapter == "seed":
                continue

            if adapter in coverage_adapters and counts.get(adapter, 0) <= 1:
                continue

            return index

        # Last resort: replace the final non-seed item.
        for index in range(len(items) - 1, -1, -1):
            if str(items[index].get("source_adapter") or "") != "seed":
                return index

        return len(items) - 1

    limited_urls = {
        str(item.get("url") or "")
        for item in limited
        if str(item.get("url") or "")
    }

    for adapter in coverage_adapters:
        candidate = best_adapter_candidate(adapter)
        if candidate is None:
            continue

        candidate_url = str(candidate.get("url") or "")
        if not candidate_url or candidate_url in limited_urls:
            continue

        if len(limited) < max_items:
            limited.append(candidate)
            limited_urls.add(candidate_url)
            continue

        index = replacement_index(limited)
        removed_url = str(limited[index].get("url") or "")
        if removed_url in limited_urls:
            limited_urls.remove(removed_url)

        limited[index] = candidate
        limited_urls.add(candidate_url)

    limited = sorted(limited, key=sort_key)

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
    safe_public_search_template_audit: dict[str, Any] = {}

    candidates.extend(
        _seed_url_candidates(
            clean_seed_urls,
            goal=clean_goal,
            plan_id=plan_id,
            terms=terms,
        )
    )

    adapter_set = set(clean_adapters)

    if "search" in adapter_set or "public_search" in adapter_set:
        safe_template_plan = build_safe_public_search_template_plan(
            clean_goal,
            limit=8,
        )
        safe_public_search_template_audit = dict(
            safe_template_plan.get("audit", {}) or {}
        )
        candidates.extend(
            public_search_template_to_candidate(
                template,
                goal=clean_goal,
                existing_score=0.70,
            )
            for template in safe_template_plan.get("templates", [])
            if isinstance(template, Mapping)
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
        "safe_public_search_template_audit": safe_public_search_template_audit,
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