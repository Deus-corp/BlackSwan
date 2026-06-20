from __future__ import annotations

from src.swarms.memory.catalog import (
    build_memory_evidence_catalog,
    query_memory_evidence_catalog,
)
from src.swarms.memory.ingestion import build_memory_ingest_candidate


def _explorer_memory_record(
    *,
    gid: str,
    url: str,
    domain: str,
    category: str,
    tags: list[str],
    preview: str,
    source_score: float = 0.84,
    relevance_score: float = 0.75,
    authority_score: float = 0.80,
    freshness_score: float = 0.70,
) -> dict:
    return {
        "type": "memory_record",
        "record_kind": "explorer_useful_evidence",
        "gid": gid,
        "url": url,
        "domain": domain,
        "content_preview": preview,
        "content_hash": f"hash-{gid}",
        "source_score": source_score,
        "quality_score": source_score,
        "system_relevance_score": relevance_score,
        "authority_score": authority_score,
        "freshness_score": freshness_score,
        "topic_tags": tags,
        "evidence_category": category,
        "provenance": {
            "exploration_run_id": "run-memory-query",
            "research_goal_id": "run-memory-query",
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }


def _candidate(**kwargs) -> dict:
    return build_memory_ingest_candidate(_explorer_memory_record(**kwargs))


def _catalog() -> dict:
    candidates = [
        _candidate(
            gid="github-blog",
            url="https://github.blog/changelog/agent-update",
            domain="github.blog",
            category="github_blog_changelog",
            tags=["agents", "code_improvement"],
            preview=(
                "GitHub Blog changelog evidence about Copilot code review agents, "
                "agentic coding workflows, markdown support, and UI improvements."
            ),
            source_score=0.90,
            relevance_score=0.86,
            authority_score=0.84,
            freshness_score=0.90,
        ),
        _candidate(
            gid="python-asyncio",
            url="https://docs.python.org/3/library/asyncio.html",
            domain="docs.python.org",
            category="python_docs",
            tags=["asyncio", "agents"],
            preview=(
                "Python asyncio documentation evidence about event loops, tasks, "
                "concurrency, orchestration, and autonomous agent runtime systems."
            ),
            source_score=0.86,
            relevance_score=0.80,
            authority_score=0.90,
            freshness_score=0.60,
        ),
        _candidate(
            gid="sqlite-memory",
            url="https://docs.python.org/3/library/sqlite3.html",
            domain="docs.python.org",
            category="python_docs",
            tags=["sqlite", "memory"],
            preview=(
                "Python sqlite3 documentation evidence about local persistence, "
                "memory storage, transactions, and durable agent state."
            ),
            source_score=0.78,
            relevance_score=0.74,
            authority_score=0.90,
            freshness_score=0.55,
        ),
    ]

    return build_memory_evidence_catalog(candidates)


def test_query_memory_catalog_by_domain() -> None:
    result = query_memory_evidence_catalog(
        _catalog(),
        domain="docs.python.org",
    )

    assert result["type"] == "memory_evidence_query_result"
    assert result["result_count"] == 2
    assert all(item["domain"] == "docs.python.org" for item in result["results"])


def test_query_memory_catalog_by_category() -> None:
    result = query_memory_evidence_catalog(
        _catalog(),
        evidence_category="github_blog_changelog",
    )

    assert result["result_count"] == 1
    assert result["results"][0]["domain"] == "github.blog"


def test_query_memory_catalog_by_topic_tags_requires_all_tags() -> None:
    result = query_memory_evidence_catalog(
        _catalog(),
        topic_tags=["agents", "code_improvement"],
    )

    assert result["result_count"] == 1
    assert result["results"][0]["url"] == "https://github.blog/changelog/agent-update"


def test_query_memory_catalog_by_text_query() -> None:
    result = query_memory_evidence_catalog(
        _catalog(),
        text_query="event loops orchestration",
    )

    assert result["result_count"] == 1
    assert "asyncio" in result["results"][0]["url"]


def test_query_memory_catalog_min_ranking_score_filters_weak_items() -> None:
    result = query_memory_evidence_catalog(
        _catalog(),
        min_ranking_score=0.84,
    )

    assert result["result_count"] >= 1
    assert all(item["ranking_score"] >= 0.84 for item in result["results"])


def test_query_memory_catalog_results_sorted_by_ranking_score_descending() -> None:
    result = query_memory_evidence_catalog(_catalog())

    scores = [item["ranking_score"] for item in result["results"]]

    assert scores == sorted(scores, reverse=True)


def test_query_memory_catalog_limit_applies() -> None:
    result = query_memory_evidence_catalog(
        _catalog(),
        limit=2,
    )

    assert result["result_count"] == 2
    assert len(result["results"]) == 2


def test_query_memory_catalog_empty_result_is_valid() -> None:
    result = query_memory_evidence_catalog(
        _catalog(),
        domain="missing.example",
    )

    assert result["result_count"] == 0
    assert result["matched_count"] == 0
    assert result["results"] == []


def test_query_memory_catalog_safety_flags_are_false() -> None:
    result = query_memory_evidence_catalog(
        _catalog(),
        text_query="agents",
    )

    assert result["external_write_performed"] is False
    assert result["real_execution_enabled"] is False
    assert result["production_paths_mutated"] is False
    assert result["production_secrets_accessed"] is False


def test_query_memory_catalog_query_metadata_is_normalized() -> None:
    result = query_memory_evidence_catalog(
        _catalog(),
        domain="  DOCS.PYTHON.ORG  ",
        evidence_category=" python_docs ",
        topic_tags=[" agents ", "asyncio"],
        text_query=" Event   Loops ",
        min_ranking_score=0.7,
        limit=3,
    )

    assert result["query"]["domain"] == "DOCS.PYTHON.ORG"
    assert result["query"]["evidence_category"] == "python_docs"
    assert result["query"]["topic_tags"] == ["agents", "asyncio"]
    assert result["query"]["text_query"] == "Event Loops"
    assert result["query"]["min_ranking_score"] == 0.7
    assert result["query"]["limit"] == 3