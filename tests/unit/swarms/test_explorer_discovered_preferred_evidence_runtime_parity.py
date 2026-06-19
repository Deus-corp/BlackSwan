import asyncio
from pathlib import Path

from src.swarms.explorer.meta_agent import ExplorerMetaAgent


class _FakeCRDT:
    def __init__(self) -> None:
        self.records = []
        self.state = {}

    async def add_genome(self, record):
        self.records.append(record)
        gid = record.get("gid") if isinstance(record, dict) else None
        if gid:
            self.state[gid] = record
        return record


def test_runtime_like_github_blog_preferred_evidence_is_useful(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-runtime-preferred-parity-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()
    agent.active_exploration_run_id = "run-runtime-preferred-parity"

    finding = {
        "type": "explorer_finding",
        "source_gid": "source-github-blog",
        "url": (
            "https://github.blog/changelog/2026-06-18-"
            "copilot-code-review-agents-md-support-and-ui-improvements"
        ),
        "domain": "github.blog",
        "content_preview": "",
        "content_hash": "hash-github-blog-changelog",
        "fetch_status": "ok",
        "classification": "unclassified",
        "confidence": 0.0,
        "reason": "network read completed",
        "timestamp": 1.0,
        "gid": "finding-github-blog-changelog",
        "provenance": {
            "exploration_run_id": "run-runtime-preferred-parity",
            "research_goal_id": "run-runtime-preferred-parity",
            "preferred_evidence_target": True,
            "concrete_evidence_page": True,
            "goal_alignment_score": 0.14,
            "goal_terms_matched": ["agent", "agents", "improvement"],
            "source_score": 0.84,
            "quality_score": 0.84,
            "system_relevance_score": 0.75,
            "authority_score": 0.70,
            "freshness_score": 0.90,
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }

    async def run():
        return await agent._fallback_classify_findings(
            [finding],
            batch_gid="batch-runtime-preferred-parity",
            prompt_h="prompt",
            model_name="noop",
            fallback_reason="test",
        )

    classified, _ = asyncio.run(run())

    assert classified[0]["classification"] == "USEFUL"
    assert classified[0]["content_preview"]
    assert classified[0]["confidence"] >= 0.70

    signals = classified[0]["provenance"]["classification_signals"]
    assert signals["preferred_evidence_target"] is True
    assert signals["concrete_evidence_page"] is True
    assert signals["discovered_preferred_evidence_source"] is True
    assert signals["evidence_candidate_source"] is True
    assert signals["has_meaningful_preview"] is True

    memory_records = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict)
        and record.get("type") == "memory_record"
        and record.get("record_kind") == "explorer_useful_evidence"
    ]

    assert len(memory_records) == 1
    assert memory_records[0]["content_preview"]