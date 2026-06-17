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


def _finding(**overrides):
    base = {
        "type": "explorer_finding",
        "source_gid": "source-1",
        "url": "https://docs.python.org/3/library/asyncio.html",
        "domain": "docs.python.org",
        "content_preview": (
            "asyncio is a Python library to write concurrent code using async and "
            "await syntax. It is useful for autonomous agents, runtime orchestration, "
            "network clients, testing, and system improvement architecture."
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
            "exploration_run_id": "run-content-quality",
            "research_goal_id": "run-content-quality",
            "execution_risk_tier": "network_read",
            "network_read_performed": True,
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }
    base.update(overrides)
    return base


def test_content_aware_fallback_classifies_high_value_source_as_useful(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-content-quality-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()
    agent.active_exploration_run_id = "run-content-quality"

    async def run():
        return await agent._fallback_classify_findings(
            [_finding()],
            batch_gid="batch-content-quality",
            prompt_h="prompt-hash",
            model_name="noop-llm",
            fallback_reason="test",
        )

    classified, _batch_gid = asyncio.run(run())

    assert classified
    assert classified[0]["classification"] == "USEFUL"
    assert classified[0]["confidence"] >= 0.50
    assert classified[0]["provenance"]["source_score"] >= 0.65
    assert classified[0]["provenance"]["system_relevance_score"] >= 0.60

    memory_records = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict)
        and record.get("type") == "memory_record"
        and record.get("record_kind") == "explorer_useful_evidence"
    ]

    assert len(memory_records) == 1
    assert memory_records[0]["evidence"]["url"] == (
        "https://docs.python.org/3/library/asyncio.html"
    )


def test_content_aware_fallback_keeps_placeholder_domain_neutral(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-placeholder-content-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()

    placeholder = _finding(
        url="https://example.com/",
        domain="example.com",
        content_preview=(
            "This domain is for illustrative examples in documents. It should not "
            "be treated as system improvement evidence even when fetched successfully."
        ),
        content_hash="hash-example",
    )

    async def run():
        return await agent._fallback_classify_findings(
            [placeholder],
            batch_gid="batch-placeholder",
            prompt_h="prompt-hash",
            model_name="noop-llm",
            fallback_reason="test",
        )

    classified, _batch_gid = asyncio.run(run())

    assert classified
    assert classified[0]["classification"] == "NEUTRAL"

    memory_records = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict) and record.get("type") == "memory_record"
    ]

    assert memory_records == []