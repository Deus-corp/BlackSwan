import asyncio
from pathlib import Path

from src.swarms.explorer.meta_agent import ExplorerMetaAgent


class _FakeCRDT:
    def __init__(self) -> None:
        self.state = {}
        self.records = []

    async def add_genome(self, record):
        self.records.append(record)
        gid = record.get("gid") if isinstance(record, dict) else None
        if gid:
            self.state[gid] = record
        return record

    def close(self) -> None:
        return None


def _useful_finding(**overrides):
    base = {
        "type": "explorer_finding",
        "source_gid": "source-quality",
        "url": "https://docs.python.org/3/library/asyncio.html",
        "domain": "docs.python.org",
        "content_preview": (
            "asyncio is a library to write concurrent code using async and await. "
            "It is useful for Python runtime, autonomous agents, orchestration, "
            "network clients, and system improvement work."
        ),
        "content_hash": "hash-asyncio",
        "fetch_status": "ok",
        "classification": "USEFUL",
        "confidence": 0.75,
        "reason": "useful source",
        "timestamp": 1.0,
        "gid": "finding-quality",
        "provenance": {
            "exploration_run_id": "run-quality",
            "research_goal_id": "run-quality",
            "execution_risk_tier": "network_read",
            "network_read_performed": True,
            "external_write_performed": False,
            "real_execution_enabled": False,
            "source_adapter": "sitemap",
            "source_kind": "sitemap_xml",
            "authority_score": 0.96,
            "freshness_score": 0.5,
            "system_relevance_score": 0.90,
            "quality_score": 0.85,
            "source_score": 0.85,
        },
    }
    base.update(overrides)
    return base


def test_memory_handoff_quality_gate_accepts_high_quality_evidence(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-quality-gate-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()
    agent.active_exploration_run_id = "run-quality"

    async def run() -> bool:
        return await agent._publish_memory_evidence_handoff(
            _useful_finding(),
            classification_event_gid="cls-quality",
            parent_gid="batch-quality",
            handoff_reason="test_quality",
        )

    published = asyncio.run(run())

    assert published is True

    memory_records = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict)
        and record.get("type") == "memory_record"
        and record.get("record_kind") == "explorer_useful_evidence"
    ]

    assert len(memory_records) == 1
    record = memory_records[0]
    assert record["handoff_quality_gate_passed"] is True
    assert record["handoff_quality_reasons"] == []
    assert record["memory_evidence_identity"]
    assert record["evidence"]["source_score"] == 0.85


def test_memory_handoff_quality_gate_rejects_placeholder_domain(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-placeholder-gate-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()

    finding = _useful_finding(
        url="https://example.com/",
        domain="example.com",
        content_preview=(
            "This domain is for use in illustrative examples in documents. "
            "It is not a useful system improvement source despite being fetchable."
        ),
    )

    async def run() -> bool:
        return await agent._publish_memory_evidence_handoff(
            finding,
            classification_event_gid="cls-placeholder",
            parent_gid="batch-placeholder",
            handoff_reason="test_placeholder",
        )

    published = asyncio.run(run())

    assert published is False
    assert [
        record
        for record in agent.crdt.records
        if isinstance(record, dict) and record.get("type") == "memory_record"
    ] == []


def test_memory_handoff_dedupes_same_evidence_identity(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-dedupe-handoff-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()

    finding = _useful_finding()

    async def run() -> tuple[bool, bool]:
        first = await agent._publish_memory_evidence_handoff(
            finding,
            classification_event_gid="cls-1",
            parent_gid="batch-1",
            handoff_reason="test_first",
        )
        second = await agent._publish_memory_evidence_handoff(
            finding,
            classification_event_gid="cls-2",
            parent_gid="batch-2",
            handoff_reason="test_second",
        )
        return first, second

    first, second = asyncio.run(run())

    memory_records = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict)
        and record.get("type") == "memory_record"
        and record.get("record_kind") == "explorer_useful_evidence"
    ]

    assert first is True
    assert second is False
    assert len(memory_records) == 1