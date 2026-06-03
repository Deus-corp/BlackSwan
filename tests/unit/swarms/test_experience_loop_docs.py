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
    assert "command_template" in text
    assert "<scenario_id>" in text
    assert "<new_directive_id>" in text
    assert "replay_lifecycle_retry_proposal" in text
    assert "do not execute" in text
    assert "pending `replay_lifecycle_retry_proposal`" in text
    assert "non-executing" in text
    assert "replay_lifecycle_retry_proposal" in text
    assert "pending" in text
    assert "standard" in text
    assert "patient" in text
    assert "retry proposal opportunities" in text
    assert "replay_lifecycle_retry_approval" in text
    assert "execution_enabled=false" in text
    assert "approve or reject" in text
    assert "retry approval opportunities" in text
    assert "decision_mode=manual|policy" in text
    assert "Autonomous approval is not valid" in text
    assert "security_validation_retry_approval_decision_modes" in text
    assert "security_retry_approval_decision_modes" in text
    assert "manual and policy" in text
    assert "replay_lifecycle_retry_execution_plan" in text
    assert "status=planned" in text
    assert "execution_enabled=false" in text
    assert "without executing the retry automatically" in text
    assert "Security validation recognizes `replay_lifecycle_retry_execution_plan`" in text
    assert "Only non-executing plans" in text
    assert "retry execution plan opportunities" in text
    assert "src.testing.run_retry_execution_plans" in text
    assert "replay_lifecycle_retry_execution_result" in text
    assert "reason=execution_disabled" in text
    assert "execution_not_supported" in text
    assert "replay_lifecycle_retry_execution_result" in text
    assert "reason=execution_disabled" in text
    assert "executed=false" in text
    assert "retry execution result opportunities" in text
    assert "security_validation_retry_execution_result_statuses" in text
    assert "security_validation_retry_execution_result_reasons" in text
    assert "security_retry_execution_result_statuses" in text
    assert "security_retry_execution_result_reasons" in text
    assert "src.testing.inspect_retry_governance_trail" in text
    assert "read-only helper" in text
    assert "does not publish records" in text
    assert "chain_complete" in text
    assert "missing_stages" in text
    assert "--require-complete" in text
    assert "chain_complete=false" in text
    assert "proposal-to-result trail" in text
    assert "src.testing.seed_retry_governance_trail" in text
    assert "complete synthetic governance" in text
    assert "chain_complete=true" in text
    assert "src.testing.check_retry_governance_observability" in text
    assert "Security validation metrics and Overseer global brief" in text
    assert "execution-disabled reason" in text
    assert "src.testing.retry_governance_smoke" in text
    assert "One-command retry governance smoke" in text
    assert "Security/Overseer observability" in text
    assert "python -m src.testing.retry_governance_smoke" in text
    assert "src.testing.swarm_runtime_smoke" in text
    assert "isolated temporary CRDT database" in text
    assert "safe proposal-to-result governance path" in text
    assert "--require-clean" in text
    assert "existing_retry_governance_records" in text