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


def test_meta_fallback_uses_evidence_seed_provenance_for_useful_memory(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-evidence-seed-provenance-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()
    agent.active_exploration_run_id = "run-evidence-seed-provenance"

    finding = {
        "type": "explorer_finding",
        "source_gid": "source-course",
        "url": "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai",
        "domain": "realpython.com",
        "content_preview": (
            "Building type-safe LLM agents with Pydantic AI explains Python "
            "agent workflows, runtime orchestration, structured outputs, "
            "memory-aware systems, validation, and autonomous AI application "
            "architecture."
        ),
        "content_hash": "hash-course-pydantic-ai",
        "fetch_status": "ok",
        "classification": "unclassified",
        "confidence": 0.0,
        "reason": "network read completed",
        "timestamp": 1.0,
        "gid": "finding-course",
        "provenance": {
            "exploration_run_id": "run-evidence-seed-provenance",
            "research_goal_id": "run-evidence-seed-provenance",
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
            "discovered_target_count": 12,
        },
    }

    async def run():
        return await agent._fallback_classify_findings(
            [finding],
            batch_gid="batch-evidence-seed",
            prompt_h="prompt",
            model_name="noop",
            fallback_reason="test",
        )

    classified, _ = asyncio.run(run())

    assert classified[0]["classification"] == "USEFUL"
    assert classified[0]["provenance"]["fallback_quality_signals"][
        "preferred_evidence_target"
    ] is True

    memory_records = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict)
        and record.get("type") == "memory_record"
        and record.get("record_kind") == "explorer_useful_evidence"
    ]

    assert len(memory_records) == 1