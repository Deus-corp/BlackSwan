from __future__ import annotations

from src.swarms.memory.ingestion import (
    build_memory_ingest_candidate,
    is_explorer_useful_evidence_record,
    memory_record_from_ingest_candidate,
    validate_memory_ingest_candidate,
)
from src.swarms.memory.shared_bridge import SharedMemoryBridge


def _explorer_memory_record() -> dict:
    return {
        "type": "memory_record",
        "record_kind": "explorer_useful_evidence",
        "gid": "mem-exp-1",
        "url": "https://github.blog/changelog/2026-06-18-copilot-code-review-agents-md-support-and-ui-improvements",
        "domain": "github.blog",
        "content_preview": (
            "GitHub Blog changelog evidence about Copilot code review agents, "
            "agentic coding workflows, markdown support, and UI improvements."
        ),
        "content_hash": "hash-github-blog-evidence",
        "source_score": 0.84,
        "quality_score": 0.84,
        "system_relevance_score": 0.75,
        "authority_score": 0.70,
        "freshness_score": 0.90,
        "topic_tags": ["agents", "code_improvement"],
        "evidence_category": "github_blog_changelog",
        "provenance": {
            "exploration_run_id": "run-memory-ingestion",
            "research_goal_id": "run-memory-ingestion",
            "preferred_evidence_target": True,
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }


def test_builds_memory_ingest_candidate_from_explorer_evidence() -> None:
    record = _explorer_memory_record()

    candidate = build_memory_ingest_candidate(record)

    assert candidate["type"] == "memory_ingest_candidate"
    assert candidate["candidate_kind"] == "explorer_useful_evidence"
    assert candidate["source_record_gid"] == "mem-exp-1"
    assert candidate["url"] == record["url"]
    assert candidate["domain"] == "github.blog"
    assert candidate["content_preview"] == record["content_preview"]
    assert candidate["source_score"] == 0.84
    assert candidate["system_relevance_score"] == 0.75
    assert candidate["ingestion_status"] == "candidate"
    assert candidate["dedupe_key"]
    assert candidate["provenance"]["source"] == "explorer"
    assert candidate["provenance"]["external_write_performed"] is False
    assert candidate["provenance"]["real_execution_enabled"] is False
    assert validate_memory_ingest_candidate(candidate) == []


def test_memory_ingest_candidate_dedupe_key_is_stable() -> None:
    first = build_memory_ingest_candidate(_explorer_memory_record())
    second = build_memory_ingest_candidate(_explorer_memory_record())

    assert first["dedupe_key"] == second["dedupe_key"]


def test_memory_ingest_candidate_rejects_missing_url() -> None:
    record = _explorer_memory_record()
    record["url"] = ""

    candidate = build_memory_ingest_candidate(record)
    errors = validate_memory_ingest_candidate(candidate)

    assert "url is required" in errors


def test_memory_ingest_candidate_rejects_short_preview() -> None:
    record = _explorer_memory_record()
    record["content_preview"] = "too short"

    candidate = build_memory_ingest_candidate(record)
    errors = validate_memory_ingest_candidate(candidate)

    assert "content_preview is too short" in errors


def test_memory_ingest_candidate_rejects_low_scores() -> None:
    record = _explorer_memory_record()
    record["source_score"] = 0.10
    record["system_relevance_score"] = 0.10

    candidate = build_memory_ingest_candidate(record)
    errors = validate_memory_ingest_candidate(candidate)

    assert "source_score below ingestion threshold" in errors
    assert "system_relevance_score below ingestion threshold" in errors


def test_memory_record_from_ingest_candidate_is_local_memory_compatible() -> None:
    candidate = build_memory_ingest_candidate(_explorer_memory_record())

    memory_record = memory_record_from_ingest_candidate(candidate)

    assert memory_record["kind"] == "evidence"
    assert memory_record["scope"] == "shared"
    assert memory_record["topic"] == "github_blog_changelog"
    assert memory_record["payload"]["candidate_kind"] == "explorer_useful_evidence"
    assert memory_record["payload"]["url"] == candidate["url"]
    assert memory_record["payload"]["source_score"] == 0.84
    assert memory_record["source"]["swarm"] == "explorer"
    assert memory_record["verified"] is True


def test_shared_bridge_converts_explorer_useful_evidence_record() -> None:
    record = _explorer_memory_record()

    converted = SharedMemoryBridge._to_memory_record(
        "crdt-record-1",
        record,
    )

    assert converted is not None
    assert converted["kind"] == "evidence"
    assert converted["payload"]["candidate_kind"] == "explorer_useful_evidence"
    assert converted["payload"]["url"] == record["url"]
    assert converted["payload"]["content_preview"] == record["content_preview"]


def test_shared_bridge_accepts_memory_ingest_candidate_payload() -> None:
    candidate = build_memory_ingest_candidate(_explorer_memory_record())

    converted = SharedMemoryBridge._to_memory_record(
        "candidate-1",
        candidate,
    )

    assert converted is not None
    assert converted["kind"] == "evidence"
    assert converted["payload"]["source_record_gid"] == "mem-exp-1"


def test_non_explorer_memory_record_uses_legacy_bridge_path() -> None:
    payload = {
        "type": "memory_record",
        "id": "legacy-memory-1",
        "kind": "event",
        "scope": "shared",
        "topic": "legacy",
        "payload": {"message": "legacy memory"},
        "source": {"originNodeId": "node-1", "swarm": "memory"},
        "verified": True,
    }

    converted = SharedMemoryBridge._to_memory_record(
        "legacy-memory-1",
        payload,
    )

    assert converted is not None
    assert converted["kind"] == "event"
    assert converted["payload"]["message"] == "legacy memory"
    assert converted["source"]["swarm"] == "memory"


def test_detects_explorer_useful_evidence_record() -> None:
    assert is_explorer_useful_evidence_record(_explorer_memory_record()) is True
    assert is_explorer_useful_evidence_record({"type": "memory_record"}) is False