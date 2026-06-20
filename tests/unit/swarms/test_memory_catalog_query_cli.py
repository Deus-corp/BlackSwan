from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from src.swarms.memory.ingestion import (
    build_memory_ingest_candidate,
    memory_record_from_ingest_candidate,
)
from src.testing.query_memory_evidence_catalog import (
    _async_main,
    build_parser,
    run_memory_evidence_catalog_query,
)


class _FakeMemory:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records
        self.last_limit = 0

    async def recent(self, limit: int = 1000) -> list[dict[str, Any]]:
        self.last_limit = limit
        return list(self.records[:limit])


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
) -> dict[str, Any]:
    raw = {
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
        "authority_score": 0.80,
        "freshness_score": 0.70,
        "topic_tags": tags,
        "evidence_category": category,
        "provenance": {
            "exploration_run_id": "run-memory-query-cli",
            "research_goal_id": "run-memory-query-cli",
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }

    candidate = build_memory_ingest_candidate(raw)
    return memory_record_from_ingest_candidate(candidate)


def _records() -> list[dict[str, Any]]:
    return [
        _explorer_memory_record(
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
        ),
        _explorer_memory_record(
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
        ),
        {
            "id": "event-1",
            "kind": "event",
            "scope": "own",
            "topic": "lifecycle",
            "payload": {"message": "not catalog evidence"},
            "source": {"swarm": "memory"},
            "verified": True,
        },
    ]


def test_memory_catalog_query_cli_parser_accepts_filters() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--node-id",
            "memory-test",
            "--recent-limit",
            "50",
            "--domain",
            "docs.python.org",
            "--category",
            "python_docs",
            "--tag",
            "agents",
            "--tag",
            "asyncio",
            "--text-query",
            "event loops",
            "--min-ranking-score",
            "0.7",
            "--limit",
            "3",
            "--json",
        ]
    )

    assert args.node_id == "memory-test"
    assert args.recent_limit == 50
    assert args.domain == "docs.python.org"
    assert args.evidence_category == "python_docs"
    assert args.topic_tags == ["agents", "asyncio"]
    assert args.text_query == "event loops"
    assert args.min_ranking_score == 0.7
    assert args.limit == 3
    assert args.json is True


def test_run_memory_catalog_query_filters_by_domain_and_tag() -> None:
    memory = _FakeMemory(_records())
    args = argparse.Namespace(
        node_id="memory-test",
        recent_limit=100,
        top_items_limit=100,
        domain="docs.python.org",
        evidence_category="",
        topic_tags=["agents"],
        text_query="event loops",
        min_ranking_score=0.0,
        limit=10,
    )

    result = asyncio.run(
        run_memory_evidence_catalog_query(
            args,
            memory_backend=memory,
        )
    )

    assert memory.last_limit == 100
    assert result["type"] == "memory_evidence_query_result"
    assert result["catalog"]["item_count"] == 2
    assert result["result_count"] == 1
    assert result["results"][0]["domain"] == "docs.python.org"
    assert "asyncio" in result["results"][0]["url"]


def test_run_memory_catalog_query_json_result_has_safety_flags() -> None:
    memory = _FakeMemory(_records())
    args = argparse.Namespace(
        node_id="memory-test",
        recent_limit=100,
        top_items_limit=100,
        domain="",
        evidence_category="",
        topic_tags=[],
        text_query="agents",
        min_ranking_score=0.0,
        limit=10,
    )

    result = asyncio.run(
        run_memory_evidence_catalog_query(
            args,
            memory_backend=memory,
        )
    )

    assert result["external_write_performed"] is False
    assert result["real_execution_enabled"] is False
    assert result["production_paths_mutated"] is False
    assert result["production_secrets_accessed"] is False
    assert result["testing_only"] is True


def test_run_memory_catalog_query_limit_applies() -> None:
    memory = _FakeMemory(_records())
    args = argparse.Namespace(
        node_id="memory-test",
        recent_limit=100,
        top_items_limit=100,
        domain="",
        evidence_category="",
        topic_tags=[],
        text_query="",
        min_ranking_score=0.0,
        limit=1,
    )

    result = asyncio.run(
        run_memory_evidence_catalog_query(
            args,
            memory_backend=memory,
        )
    )

    assert result["result_count"] == 1
    assert len(result["results"]) == 1


def test_async_main_writes_json_output(tmp_path: Path) -> None:
    output_path = tmp_path / "memory_query.json"

    exit_code = asyncio.run(
        _async_main(
            [
                "--node-id",
                "memory-query-empty-test",
                "--json",
                "--json-output",
                str(output_path),
            ]
        )
    )

    assert exit_code == 0
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["type"] == "memory_evidence_query_result"
    assert data["external_write_performed"] is False
    assert data["real_execution_enabled"] is False