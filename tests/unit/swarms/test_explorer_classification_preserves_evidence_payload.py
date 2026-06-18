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


def test_fallback_classification_preserves_preview_for_memory_handoff(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-preserve-evidence-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()
    agent.active_exploration_run_id = "run-preserve-evidence"

    finding = {
        "type": "explorer_finding",
        "source_gid": "source-course",
        "url": "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai",
        "domain": "realpython.com",
        "content_preview": (
            "Building Type Safe LLM Agents With Pydantic AI. "
            "Seeded explorer evidence target for autonomous agents memory systems."
        ),
        "content_hash": "hash-preserve-preview",
        "fetch_status": "ok",
        "classification": "unclassified",
        "confidence": 0.0,
        "reason": "network read completed",
        "timestamp": 1.0,
        "gid": "finding-preserve-preview",
        "provenance": {
            "exploration_run_id": "run-preserve-evidence",
            "research_goal_id": "run-preserve-evidence",
            "source_adapter": "evidence_seed",
            "source_kind": "goal_evidence_url",
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
            batch_gid="batch-preserve",
            prompt_h="prompt",
            model_name="noop",
            fallback_reason="test",
        )

    classified, _ = asyncio.run(run())

    assert classified[0]["classification"] == "USEFUL"
    assert classified[0]["content_preview"] == finding["content_preview"]
    assert classified[0]["content_hash"] == finding["content_hash"]
    assert classified[0]["fetch_status"] == "ok"

    memory_records = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict)
        and record.get("type") == "memory_record"
        and record.get("record_kind") == "explorer_useful_evidence"
    ]

    assert len(memory_records) == 1