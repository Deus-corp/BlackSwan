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


def test_memory_handoff_repairs_missing_preview_for_evidence_seed(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-preview-repair-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()

    finding = {
        "type": "explorer_finding",
        "event_type": "finding_classified",
        "gid": "classified-preview-repair",
        "source_gid": "source-preview-repair",
        "url": "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai",
        "domain": "realpython.com",
        "content_preview": "",
        "content_hash": "hash-preview-repair",
        "fetch_status": "ok",
        "classification": "USEFUL",
        "confidence": 0.70,
        "reason": "classified useful evidence seed",
        "timestamp": 1.0,
        "provenance": {
            "exploration_run_id": "run-preview-repair",
            "research_goal_id": "run-preview-repair",
            "source_adapter": "evidence_seed",
            "source_kind": "goal_evidence_url",
            "preferred_evidence_target": True,
            "goal_alignment_score": 0.28,
            "source_score": 0.80,
            "quality_score": 0.80,
            "system_relevance_score": 0.96,
            "authority_score": 0.72,
            "freshness_score": 0.50,
            "fallback_quality_signals": {
                "url": "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai",
                "domain": "realpython.com",
                "fetch_status": "ok",
                "content_hash_present": True,
                "content_preview_chars": 0,
                "concrete_evidence_page": True,
                "preferred_evidence_target": True,
                "source_adapter": "evidence_seed",
                "source_kind": "goal_evidence_url",
                "source_score": 0.80,
                "quality_score": 0.80,
                "system_relevance_score": 0.96,
                "authority_score": 0.72,
                "freshness_score": 0.50,
                "placeholder_domain": False,
                "keyword_matches": [
                    "agent",
                    "agents",
                    "ai",
                    "llm",
                    "python",
                    "pydantic",
                    "type-safe",
                    "course",
                ],
            },
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }

    async def run() -> bool:
        return await agent._publish_memory_evidence_handoff(
            finding,
            classification_event_gid="cls-preview-repair",
            parent_gid="batch-preview-repair",
            handoff_reason="test_preview_repair",
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
    assert memory_records[0]["content_preview"]
    assert "Building Type Safe Llm Agents With Pydantic Ai" in memory_records[0][
        "content_preview"
    ]
    assert memory_records[0]["provenance"]["memory_handoff_preview_repaired"] is True