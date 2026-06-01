from pathlib import Path


def test_runtime_directive_experience_loop_doc_exists_and_mentions_chain() -> None:
    path = Path("docs/runtime_directive_experience_loop.md")

    assert path.exists()

    text = path.read_text(encoding="utf-8")

    assert "Directive" in text
    assert "DirectiveResult" in text
    assert "EvidenceRecord" in text
    assert "MemoryRecord" in text
    assert "REDUCE_RISK" in text
    assert "src.testing.seed_directive" in text
    assert "src.testing.publish_directive_evidence" in text
    assert "src.testing.evidence_memory_bridge" in text
    assert "runtime-reduce-risk-1" in text
    assert "simulation_replay_scenario" in text
    assert "src.testing.publish_replay_scenarios" in text
    assert "simulation_replay_pending" in text
    assert "OBSERVE target=simulation" in text
    assert "advisory-only" in text
    assert "RUN_REPLAY" in text
    assert "run_replay_execution_not_implemented" in text
    assert "src.testing.seed_directive" in text
    assert "--payload-json" in text
    assert '"dry_run":true' in text or "dry_run=true" in text
    assert "src.testing.seed_replay_scenario" in text
    assert "--scenario-id" in text
    assert "publish_replay_execution_evidence" in text
    assert "simulation_replay_execution_check" in text
    assert "simulation_replay_execution_check" in text
    assert "src.testing.evidence_memory_bridge" in text
    assert "memory_record kind=runtime_evidence" in text
    assert "Replay evidence memory lifecycle" in text
    assert "publish_replay_execution_evidence" in text
    assert "--subject simulation_replay_execution_check" in text
    assert "MemorySummary.replay_execution_evidence_records" in text
    assert "memory_intelligence.aggregate.replay_execution_evidence_records" in text
    assert "global_brief.key_metrics.memory_replay_execution_evidence_records" in text