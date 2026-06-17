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


class _NoopLLM:
    model_name = "noop-llm"

    def generate(self, *_args, **_kwargs):
        return ""


def test_explorer_meta_agent_publishes_memory_record_for_useful_finding(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-memory-handoff-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()
    agent.llm = _NoopLLM()
    agent.active_exploration_run_id = "run-memory-handoff"

    finding = {
        "type": "explorer_finding",
        "source_gid": "source-1",
        "url": "https://docs.python.org/3/library/asyncio.html",
        "domain": "docs.python.org",
        "content_preview": (
            "asyncio documentation for Python async runtime, autonomous agents, "
            "orchestration, memory systems, network clients, and useful system "
            "improvement evidence with enough meaningful content."
        ),
        "content_hash": "hash-asyncio",
        "fetch_status": "ok",
        "fetch_error": None,
        "classification": "unclassified",
        "confidence": 0.0,
        "reason": "network read completed",
        "timestamp": 1.0,
        "gid": "finding-1",
        "event_type": "finding_published",
        "provenance": {
            "exploration_run_id": "run-memory-handoff",
            "research_goal_id": "run-memory-handoff",
            "execution_risk_tier": "network_read",
            "network_read_performed": True,
            "external_write_performed": False,
            "real_execution_enabled": False,
            "source_adapter": "sitemap",
            "source_kind": "sitemap_xml",
            "authority_score": 0.96,
            "freshness_score": 0.5,
            "system_relevance_score": 0.9,
            "quality_score": 0.85,
            "source_score": 0.85,
        },
    }

    async def run() -> None:
        await agent._fallback_classify_findings(
            [finding],
            batch_gid="batch-1",
            prompt_h="prompt-hash",
            model_name="noop-llm",
            fallback_reason="test",
        )

    asyncio.run(run())

    memory_records = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict)
        and record.get("type") == "memory_record"
        and record.get("record_kind") == "explorer_useful_evidence"
    ]

    assert len(memory_records) == 1

    record = memory_records[0]
    assert record["memory_ingestion_candidate"] is True
    assert record["source_swarm"] == "explorer"
    assert record["exploration_run_id"] == "run-memory-handoff"
    assert record["evidence"]["url"] == "https://docs.python.org/3/library/asyncio.html"
    assert record["evidence"]["classification"] == "USEFUL"
    assert record["evidence"]["confidence"] >= 0.50
    assert record["evidence"]["content_hash"] == "hash-asyncio"
    assert record["evidence"]["source_score"] == 0.85
    assert record["provenance"]["external_write_performed"] is False
    assert record["provenance"]["real_execution_enabled"] is False

    assert agent._last_memory_records_published == 1
    assert agent._memory_records_published_total == 1


def test_explorer_meta_agent_does_not_publish_memory_record_for_neutral_finding(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-memory-neutral-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()

    finding = {
        "type": "explorer_finding",
        "source_gid": "source-neutral",
        "url": "https://example.com/",
        "domain": "example.com",
        "content_preview": "example domain",
        "content_hash": "",
        "fetch_status": "http_404",
        "classification": "NEUTRAL",
        "confidence": 0.35,
        "reason": "not useful",
        "timestamp": 1.0,
        "gid": "finding-neutral",
        "provenance": {
            "exploration_run_id": "run-neutral",
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }

    async def run() -> bool:
        return await agent._publish_memory_evidence_handoff(
            finding,
            classification_event_gid="cls-neutral",
            parent_gid="batch-neutral",
            handoff_reason="test_neutral",
        )

    published = asyncio.run(run())

    assert published is False
    assert [
        record
        for record in agent.crdt.records
        if isinstance(record, dict) and record.get("type") == "memory_record"
    ] == []