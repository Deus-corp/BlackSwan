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
    assert "run_replay_evidence_check" in text
    assert "One-command replay evidence check" in text
    assert "replay_evidence_lifecycle_result" in text
    assert "replay_evidence_lifecycle_result" in text
    assert "all checks are passed" in text
    assert "Overseer-ready visibility" in text
    assert "MemorySummary replay evidence counters" in text
    assert "Security validation record-type counts" in text
    assert "trail_counts" in text
    assert "visibility_crdt_trail_complete" in text
    assert "replay_evidence_lifecycle_result" in text
    assert "exits with code `0`" in text
    assert "1` when any check fails" in text
    assert "execution_not_observed_before_timeout" in text
    assert "wait_seconds" in text
    assert "poll_interval" in text
    assert "security_validation_warning_reasons" in text
    assert "execution_not_observed_before_timeout" in text
    assert "replay lifecycle timeout warnings" in text
    assert "execution_not_observed_before_timeout" in text
    assert "retry_replay_lifecycle_check" in text
    assert "longer wait window" in text
    assert "--timeout-profile" in text
    assert "standard" in text
    assert "patient" in text
    assert "retry_replay_lifecycle_check" in text
    assert "timeout_profile=standard" in text
    assert "wait_seconds=15.0" in text
    assert "poll_interval=0.5" in text