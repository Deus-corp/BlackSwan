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


def test_evidence_seed_can_be_useful_with_short_but_specific_preview(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-evidence-seed-override-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()
    agent.active_exploration_run_id = "run-evidence-seed-override"

    finding = {
        "type": "explorer_finding",
        "source_gid": "source-course",
        "url": "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai",
        "domain": "realpython.com",
        "content_preview": "Building Type-Safe LLM Agents With Pydantic AI course.",
        "content_hash": "hash-short-course-preview",
        "fetch_status": "ok",
        "classification": "unclassified",
        "confidence": 0.0,
        "reason": "network read completed",
        "timestamp": 1.0,
        "gid": "finding-course-short",
        "provenance": {
            "exploration_run_id": "run-evidence-seed-override",
            "research_goal_id": "run-evidence-seed-override",
            "source_adapter": "evidence_seed",
            "source_kind": "goal_evidence_url",
            "discovery_method": "operator_seeded_evidence_url",
            "preferred_evidence_target": True,
            "goal_alignment_score": 0.28,
            "goal_terms_matched": ["agents"],
            "source_score": 0.95,
            "quality_score": 0.95,
            "system_relevance_score": 0.92,
            "authority_score": 0.80,
            "freshness_score": 0.50,
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }

    async def run():
        return await agent._fallback_classify_findings(
            [finding],
            batch_gid="batch-evidence-seed-override",
            prompt_h="prompt",
            model_name="noop",
            fallback_reason="test",
        )

    classified, _ = asyncio.run(run())

    assert classified[0]["classification"] == "USEFUL"
    assert classified[0]["confidence"] >= 0.70
    signals = classified[0]["provenance"]["classification_signals"]
    assert signals["preferred_evidence_target"] is True
    assert signals["evidence_seed_source"] is True
    assert signals["has_meaningful_preview"] is True

    memory_records = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict)
        and record.get("type") == "memory_record"
        and record.get("record_kind") == "explorer_useful_evidence"
    ]
    assert len(memory_records) == 1