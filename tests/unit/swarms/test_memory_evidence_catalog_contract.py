from __future__ import annotations

from copy import deepcopy

from src.swarms.memory.catalog import (
    build_memory_evidence_catalog,
    build_memory_evidence_catalog_item,
    validate_memory_evidence_catalog_item,
)
from src.swarms.memory.ingestion import build_memory_ingest_candidate


def _explorer_memory_record(
    *,
    gid: str = "mem-exp-1",
    url: str = "https://github.blog/changelog/2026-06-18-copilot-code-review-agents-md-support-and-ui-improvements",
    domain: str = "github.blog",
    category: str = "github_blog_changelog",
    source_score: float = 0.84,
    relevance_score: float = 0.75,
    authority_score: float = 0.70,
    freshness_score: float = 0.90,
    tags: list[str] | None = None,
) -> dict:
    return {
        "type": "memory_record",
        "record_kind": "explorer_useful_evidence",
        "gid": gid,
        "url": url,
        "domain": domain,
        "content_preview": (
            "GitHub Blog changelog evidence about Copilot code review agents, "
            "agentic coding workflows, markdown support, and UI improvements."
        ),
        "content_hash": f"hash-{gid}",
        "source_score": source_score,
        "quality_score": source_score,
        "system_relevance_score": relevance_score,
        "authority_score": authority_score,
        "freshness_score": freshness_score,
        "topic_tags": tags or ["agents", "code_improvement"],
        "evidence_category": category,
        "provenance": {
            "exploration_run_id": "run-memory-catalog",
            "research_goal_id": "run-memory-catalog",
            "preferred_evidence_target": True,
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }


def _candidate(**kwargs) -> dict:
    return build_memory_ingest_candidate(_explorer_memory_record(**kwargs))


def test_builds_catalog_item_from_memory_ingest_candidate() -> None:
    candidate = _candidate()

    item = build_memory_evidence_catalog_item(candidate)

    assert item["type"] == "memory_evidence_catalog_item"
    assert item["catalog_item_kind"] == "explorer_useful_evidence"
    assert item["source_candidate_dedupe_key"] == candidate["dedupe_key"]
    assert item["url"] == candidate["url"]
    assert item["domain"] == "github.blog"
    assert item["content_preview"] == candidate["content_preview"]
    assert item["summary"]
    assert len(item["summary"]) <= 240
    assert item["topic_tags"] == ["agents", "code_improvement"]
    assert item["evidence_category"] == "github_blog_changelog"
    assert item["ranking_score"] > 0.0
    assert item["catalog_status"] == "indexed"
    assert item["provenance"]["source"] == "memory_ingestion"
    assert item["provenance"]["external_write_performed"] is False
    assert item["provenance"]["real_execution_enabled"] is False
    assert validate_memory_evidence_catalog_item(item) == []


def test_catalog_item_validation_rejects_missing_required_fields() -> None:
    item = build_memory_evidence_catalog_item(_candidate())
    item["url"] = ""
    item["dedupe_key"] = ""
    item["content_preview"] = "too short"

    errors = validate_memory_evidence_catalog_item(item)

    assert "url is required" in errors
    assert "dedupe_key is required" in errors
    assert "content_preview is too short" in errors


def test_catalog_item_validation_rejects_unsafe_flags() -> None:
    item = build_memory_evidence_catalog_item(_candidate())
    item["provenance"]["external_write_performed"] = True

    errors = validate_memory_evidence_catalog_item(item)

    assert "external_write_performed must be false" in errors


def test_catalog_ranking_prefers_stronger_scores() -> None:
    weak = build_memory_evidence_catalog_item(
        _candidate(
            gid="weak",
            source_score=0.70,
            relevance_score=0.70,
            authority_score=0.50,
            freshness_score=0.50,
        )
    )
    strong = build_memory_evidence_catalog_item(
        _candidate(
            gid="strong",
            source_score=0.95,
            relevance_score=0.95,
            authority_score=0.90,
            freshness_score=0.90,
        )
    )

    assert strong["ranking_score"] > weak["ranking_score"]


def test_catalog_aggregate_groups_by_domain_category_and_topic_tags() -> None:
    candidates = [
        _candidate(gid="one", domain="github.blog", category="github_blog_changelog"),
        _candidate(
            gid="two",
            url="https://docs.python.org/3/library/asyncio.html",
            domain="docs.python.org",
            category="python_docs",
            tags=["asyncio", "agents"],
        ),
        _candidate(
            gid="three",
            url="https://docs.python.org/3/library/sqlite3.html",
            domain="docs.python.org",
            category="python_docs",
            tags=["sqlite", "memory"],
        ),
    ]

    catalog = build_memory_evidence_catalog(candidates)

    assert catalog["type"] == "memory_evidence_catalog"
    assert catalog["catalog_status"] == "indexed"
    assert catalog["item_count"] == 3
    assert catalog["by_domain"]["github.blog"] == 1
    assert catalog["by_domain"]["docs.python.org"] == 2
    assert catalog["by_category"]["github_blog_changelog"] == 1
    assert catalog["by_category"]["python_docs"] == 2
    assert catalog["by_topic_tag"]["agents"] == 2
    assert catalog["by_topic_tag"]["memory"] == 1
    assert catalog["external_write_performed"] is False
    assert catalog["real_execution_enabled"] is False


def test_catalog_aggregate_dedupes_by_catalog_dedupe_key() -> None:
    candidate = _candidate(gid="same")
    first = build_memory_evidence_catalog_item(candidate)
    second = deepcopy(first)
    second["ranking_score"] = first["ranking_score"] - 0.1

    catalog = build_memory_evidence_catalog([first, second])

    assert catalog["input_count"] == 2
    assert catalog["item_count"] == 1
    assert catalog["deduped_count"] == 1
    assert catalog["top_items"][0]["ranking_score"] == first["ranking_score"]


def test_catalog_keeps_highest_ranked_duplicate() -> None:
    candidate = _candidate(gid="same")
    first = build_memory_evidence_catalog_item(candidate)
    second = deepcopy(first)
    second["ranking_score"] = first["ranking_score"] + 0.05
    second["summary"] = "better duplicate"

    catalog = build_memory_evidence_catalog([first, second])

    assert catalog["item_count"] == 1
    assert catalog["top_items"][0]["summary"] == "better duplicate"


def test_catalog_top_items_sorted_by_ranking_score_descending() -> None:
    candidates = [
        _candidate(gid="low", source_score=0.70, relevance_score=0.70),
        _candidate(gid="high", source_score=0.95, relevance_score=0.95),
        _candidate(gid="mid", source_score=0.80, relevance_score=0.80),
    ]

    catalog = build_memory_evidence_catalog(candidates)

    scores = [item["ranking_score"] for item in catalog["top_items"]]

    assert scores == sorted(scores, reverse=True)


def test_catalog_rejects_invalid_items_but_builds_valid_index() -> None:
    valid = _candidate(gid="valid")
    invalid = {"type": "not_a_candidate"}

    catalog = build_memory_evidence_catalog([valid, invalid])

    assert catalog["input_count"] == 2
    assert catalog["item_count"] == 1
    assert catalog["rejected_count"] == 1