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


def test_planner_curated_evidence_classifies_and_hands_off_to_memory(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-planner-evidence-parity-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()
    agent.active_exploration_run_id = "run-planner-evidence-parity"

    finding = {
        "type": "explorer_finding",
        "source_gid": "source-planner-evidence",
        "url": "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai",
        "domain": "realpython.com",
        "content_preview": "",
        "content_hash": "hash-planner-evidence",
        "fetch_status": "ok",
        "classification": "unclassified",
        "confidence": 0.0,
        "reason": "network read completed",
        "timestamp": 1.0,
        "gid": "finding-planner-evidence",
        "provenance": {
            "exploration_run_id": "run-planner-evidence-parity",
            "research_goal_id": "run-planner-evidence-parity",
            "source_adapter": "evidence",
            "source_kind": "curated_evidence_url",
            "discovery_method": "research_goal_curated_evidence_candidate",
            "preferred_evidence_target": True,
            "goal_alignment_score": 0.16,
            "goal_terms_matched": ["agents", "memory"],
            "source_score": 0.75,
            "quality_score": 0.75,
            "system_relevance_score": 0.96,
            "authority_score": 0.72,
            "freshness_score": 0.50,
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }

    async def run():
        return await agent._fallback_classify_findings(
            [finding],
            batch_gid="batch-planner-evidence",
            prompt_h="prompt",
            model_name="noop",
            fallback_reason="test",
        )

    classified, _ = asyncio.run(run())

    assert classified[0]["classification"] == "USEFUL"
    assert classified[0]["confidence"] >= 0.70
    assert classified[0]["content_preview"]
    assert classified[0]["provenance"]["classification_signals"][
        "evidence_candidate_source"
    ] is True
    assert classified[0]["provenance"]["classification_preview_repaired"] is True

    memory_records = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict)
        and record.get("type") == "memory_record"
        and record.get("record_kind") == "explorer_useful_evidence"
    ]

    assert len(memory_records) == 1
    assert memory_records[0]["content_preview"]
    assert memory_records[0]["provenance"]["memory_handoff_preview_repaired"] is True


def test_memory_quality_gate_treats_curated_evidence_like_evidence_seed(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-planner-evidence-gate-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )

    finding = {
        "url": "https://docs.python.org/3/library/asyncio.html",
        "domain": "docs.python.org",
        "content_preview": "Asyncio Python runtime evidence candidate.",
        "content_hash": "hash-asyncio",
        "fetch_status": "ok",
        "classification": "USEFUL",
        "confidence": 0.70,
        "provenance": {
            "source_adapter": "evidence",
            "source_kind": "curated_evidence_url",
            "preferred_evidence_target": True,
            "source_score": 0.80,
            "quality_score": 0.80,
            "system_relevance_score": 0.80,
            "fallback_quality_signals": {
                "source_adapter": "evidence",
                "source_kind": "curated_evidence_url",
                "preferred_evidence_target": True,
                "concrete_evidence_page": True,
                "placeholder_domain": False,
                "fetch_status": "ok",
                "content_hash_present": True,
                "source_score": 0.80,
                "quality_score": 0.80,
                "system_relevance_score": 0.80,
            },
        },
    }

    passed, reasons, metrics = agent._memory_handoff_quality_gate(finding)

    assert passed is True
    assert reasons == []
    assert metrics["minimum_preview_chars"] == 30
    assert metrics["evidence_candidate_source"] is True