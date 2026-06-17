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


def test_explorer_meta_agent_fallback_classifies_and_publishes_targets(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-fallback-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()
    agent.llm = _NoopLLM()

    finding = {
        "type": "explorer_finding",
        "source_gid": "source-1",
        "url": "https://example.com/path/page.html",
        "domain": "example.com",
        "content_preview": "Useful explorer evidence",
        "content_hash": "hash-1",
        "fetch_status": "ok",
        "fetch_error": None,
        "classification": "unclassified",
        "confidence": 0.0,
        "reason": "network read completed",
        "timestamp": 1.0,
        "gid": "finding-1",
        "event_type": "finding_published",
        "provenance": {
            "execution_risk_tier": "network_read",
            "network_read_performed": True,
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }

    async def run() -> int:
        classified, batch_gid = await agent._classify_findings([finding])
        return await agent._publish_new_targets(classified, batch_gid)

    targets_published = asyncio.run(run())

    classified = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict)
        and record.get("type") == "explorer_finding"
        and record.get("event_type") == "finding_classified"
    ]
    targets = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict) and record.get("type") == "explorer_targets"
    ]

    assert classified
    assert classified[0]["classification"] == "USEFUL"
    assert classified[0]["provenance"]["execution_risk_tier"] == "network_read"
    assert classified[0]["provenance"]["external_write_performed"] is False
    assert classified[0]["provenance"]["real_execution_enabled"] is False

    assert targets_published >= 1
    assert targets
    assert targets[0]["data"]["urls"]
    assert targets[0]["provenance"]["target_generation_mode"] == (
        "deterministic_fallback"
    )
    assert targets[0]["provenance"]["execution_risk_tier"] == "network_read"
    assert targets[0]["provenance"]["external_write_performed"] is False
    assert targets[0]["provenance"]["real_execution_enabled"] is False