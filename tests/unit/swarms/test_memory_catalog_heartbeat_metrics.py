from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from src.swarms.memory.catalog import (
    build_memory_evidence_catalog_from_memory_records,
)
from src.swarms.memory.ingestion import (
    build_memory_ingest_candidate,
    memory_record_from_ingest_candidate,
)
from src.swarms.memory.node import MemorySwarmNode


class _FakeStats:
    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": "fake",
            "total_records": 3,
            "by_scope": {"shared": 2, "own": 1},
            "by_kind": {"evidence": 2, "event": 1},
            "verified_records": 2,
            "expired_records": 0,
            "details": {
                "episodic_count": 0,
                "semantic_count": 0,
                "policy_count": 0,
                "snapshot_count": 0,
            },
        }


class _FakeMemory:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    async def stats(self) -> _FakeStats:
        return _FakeStats()

    async def recent(self, limit: int = 200) -> list[dict[str, Any]]:
        return list(self._records[:limit])


class _FakeCRDT:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def add_genome(self, record: dict[str, Any]) -> dict[str, Any]:
        self.records.append(record)
        return record


def _explorer_memory_record(
    *,
    gid: str,
    url: str,
    domain: str,
    category: str,
    tags: list[str],
    source_score: float = 0.84,
    relevance_score: float = 0.75,
) -> dict[str, Any]:
    record = {
        "type": "memory_record",
        "record_kind": "explorer_useful_evidence",
        "gid": gid,
        "url": url,
        "domain": domain,
        "content_preview": (
            "Explorer useful evidence about autonomous agents, memory systems, "
            "retrieval, orchestration, evaluation, and code improvement workflows."
        ),
        "content_hash": f"hash-{gid}",
        "source_score": source_score,
        "quality_score": source_score,
        "system_relevance_score": relevance_score,
        "authority_score": 0.80,
        "freshness_score": 0.70,
        "topic_tags": tags,
        "evidence_category": category,
        "provenance": {
            "exploration_run_id": "run-memory-catalog-heartbeat",
            "research_goal_id": "run-memory-catalog-heartbeat",
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }
    candidate = build_memory_ingest_candidate(record)
    return memory_record_from_ingest_candidate(candidate)


def test_builds_catalog_from_local_memory_evidence_records() -> None:
    records = [
        _explorer_memory_record(
            gid="one",
            url="https://github.blog/changelog/agent-update",
            domain="github.blog",
            category="github_blog_changelog",
            tags=["agents", "code_improvement"],
        ),
        _explorer_memory_record(
            gid="two",
            url="https://docs.python.org/3/library/asyncio.html",
            domain="docs.python.org",
            category="python_docs",
            tags=["asyncio", "agents"],
        ),
        {
            "id": "event-1",
            "kind": "event",
            "scope": "own",
            "topic": "lifecycle",
            "payload": {"message": "not evidence"},
            "source": {"swarm": "memory"},
            "verified": True,
        },
    ]

    catalog = build_memory_evidence_catalog_from_memory_records(records)

    assert catalog["type"] == "memory_evidence_catalog"
    assert catalog["item_count"] == 2
    assert catalog["by_domain"]["github.blog"] == 1
    assert catalog["by_domain"]["docs.python.org"] == 1
    assert catalog["by_category"]["github_blog_changelog"] == 1
    assert catalog["by_category"]["python_docs"] == 1
    assert catalog["by_topic_tag"]["agents"] == 2
    assert catalog["rejected_count"] == 0
    assert catalog["external_write_performed"] is False
    assert catalog["real_execution_enabled"] is False


def test_catalog_from_local_memory_ignores_non_evidence_records() -> None:
    records = [
        {
            "id": "event-1",
            "kind": "event",
            "scope": "own",
            "topic": "lifecycle",
            "payload": {"message": "not evidence"},
            "source": {"swarm": "memory"},
            "verified": True,
        }
    ]

    catalog = build_memory_evidence_catalog_from_memory_records(records)

    assert catalog["item_count"] == 0
    assert catalog["top_items"] == []


def test_memory_heartbeat_includes_evidence_catalog_metrics(
    tmp_path: Path,
) -> None:
    records = [
        _explorer_memory_record(
            gid="one",
            url="https://github.blog/changelog/agent-update",
            domain="github.blog",
            category="github_blog_changelog",
            tags=["agents", "code_improvement"],
        ),
        _explorer_memory_record(
            gid="two",
            url="https://docs.python.org/3/library/asyncio.html",
            domain="docs.python.org",
            category="python_docs",
            tags=["asyncio", "agents"],
        ),
    ]

    node = MemorySwarmNode(
        node_id="memory-catalog-heartbeat-test",
        heartbeat_interval_seconds=1.0,
    )
    node.memory = _FakeMemory(records)
    node.crdt = _FakeCRDT()

    asyncio.run(node.publish_heartbeat())

    assert node.crdt.records
    heartbeat = node.crdt.records[0]
    metrics = heartbeat["metrics"]
    details = heartbeat["details"]

    assert metrics["evidence_catalog_items"] == 2
    assert metrics["evidence_catalog_rejected_items"] == 0
    assert metrics["evidence_catalog_domains"]["github.blog"] == 1
    assert metrics["evidence_catalog_domains"]["docs.python.org"] == 1
    assert metrics["evidence_catalog_categories"]["github_blog_changelog"] == 1
    assert metrics["evidence_catalog_categories"]["python_docs"] == 1
    assert metrics["evidence_catalog_topic_tags"]["agents"] == 2
    assert len(metrics["evidence_catalog_top_items"]) == 2

    assert details["evidence_catalog_status"] == "indexed"
    assert details["evidence_catalog_input_count"] == 2
    assert details["evidence_catalog_deduped_count"] == 0

    assert heartbeat["swarm"] == "memory"
    assert heartbeat["status"] == "running"


def test_memory_heartbeat_catalog_metrics_are_dataflow_safe(
    tmp_path: Path,
) -> None:
    records = [
        _explorer_memory_record(
            gid="safe",
            url="https://github.blog/changelog/safe-agent-update",
            domain="github.blog",
            category="github_blog_changelog",
            tags=["agents"],
        ),
    ]

    node = MemorySwarmNode(
        node_id="memory-catalog-safe-heartbeat-test",
        heartbeat_interval_seconds=1.0,
    )
    node.memory = _FakeMemory(records)
    node.crdt = _FakeCRDT()

    asyncio.run(node.publish_heartbeat())

    heartbeat = node.crdt.records[0]
    metrics = heartbeat["metrics"]

    assert metrics["evidence_catalog_items"] == 1

    top_item = metrics["evidence_catalog_top_items"][0]
    assert top_item["provenance"]["external_write_performed"] is False
    assert top_item["provenance"]["real_execution_enabled"] is False
    assert top_item["provenance"]["production_paths_mutated"] is False
    assert top_item["provenance"]["production_secrets_accessed"] is False