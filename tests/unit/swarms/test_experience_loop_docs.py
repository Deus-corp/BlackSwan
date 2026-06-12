from pathlib import Path


DOC_PATH = Path("docs/runtime_directive_experience_loop.md")


def test_runtime_directive_experience_loop_docs_include_seven_stage_retry_governance_checklist() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "Seven-stage retry governance safe path" in text
    assert "replay_lifecycle_retry_proposal" in text
    assert "replay_lifecycle_retry_execution_eligibility" in text
    assert "chain_records=7" in text
    assert "seven_stage=true" in text
    assert "eligibilities" in text
    assert "execution_blocked=1" in text
    assert "security_retry_execution_eligibilities=1" in text
    assert "existing_complete=true" in text
    assert "existing_execution_blocked=1" in text
    assert "Controlled execution boundary" in text
    assert "does not execute rendered retry commands" in text


def test_runtime_directive_experience_loop_docs_include_controlled_runner_contract() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "Controlled retry runner contract" in text
    assert "controlled retry runner is not implemented yet" in text
    assert "Controlled retry execution is disabled by default" in text
    assert "readiness_score=100" in text
    assert "--allow-controlled-execution" in text
    assert "python -m src.testing.run_replay_evidence_check" in text
    assert "reject arbitrary shell commands" in text
    assert "shell=True" in text
    assert "replay_lifecycle_retry_controlled_execution_result" in text
    assert "controlled_execution_result_id" in text
    assert "operator_authorized" in text
    assert "allowlist_matched" in text
    assert "must not publish a duplicate controlled" in text
    assert "must not support arbitrary command execution" in text


def test_runtime_directive_experience_loop_docs_include_real_adapter_threat_model() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "Real adapter threat model" in text
    assert "Shell injection through command strings" in text
    assert "Path traversal or unexpected working-directory changes" in text
    assert "Environment-variable leakage" in text
    assert "Unbounded execution time" in text
    assert "Unbounded stdout/stderr capture" in text
    assert "Confusing operator authorization intent" in text
    assert "Allowing mock-readiness to imply real-readiness" in text


def test_runtime_directive_experience_loop_docs_include_real_adapter_preflight_contract() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "Real adapter preflight contract" in text
    assert "`shell=True` is never allowed" in text
    assert "module-only invocations with strict argv parsing" in text
    assert "controlled command allowlist" in text
    assert "working directory must be fixed and validated" in text
    assert "environment must be sanitized through an explicit allowlist" in text
    assert "stdout and stderr capture must have byte caps" in text
    assert "fresh readiness report must pass schema validation" in text
    assert "real_execution_approval_id" in text
    assert "Operator authorization intent alone is not sufficient" in text
    assert "Audit records must be published before and after" in text
    assert "ready_for_real_execution=false" in text
    assert "real_adapter_requires_explicit_pr=true" in text


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
    assert "replay_lifecycle_retry_rendered_command" in text
    assert "Rendering only replaces" in text
    assert "does not run shell commands" in text
    assert "Security validation recognizes `replay_lifecycle_retry_rendered_command`" in text
    assert "avoid shell operators" in text
    assert "retry rendered command opportunities" in text
    assert "security_validation_retry_rendered_command_profiles" in text
    assert "security_validation_retry_rendered_command_decision_modes" in text
    assert "security_retry_rendered_command_profiles" in text
    assert "security_retry_rendered_command_decision_modes" in text
    assert "rendered command stage" in text
    assert "proposal, approval, execution plan, rendered command, and execution result" in text
    assert "src.testing.run_rendered_retry_commands" in text
    assert "replay_lifecycle_retry_rendered_command_result" in text
    assert "without executing the command text" in text
    assert "Security validation recognizes `replay_lifecycle_retry_rendered_command_result`" in text
    assert "Rendered command dry-run results" in text
    assert "replay_lifecycle_retry_rendered_command_result" in text
    assert "rendered command dry-run result statuses" in text
    assert "execution_not_supported" in text
    assert "rendered command dry-run runner" in text
    assert "replay_lifecycle_retry_rendered_command_result visibility" in text
    assert "full six-stage governance trail" in text
    assert "chain_records=6" in text
    assert "six_stage=true" in text
    assert "rendered_results=1" in text
    assert "src.testing.build_retry_execution_eligibility" in text
    assert "replay_lifecycle_retry_execution_eligibility" in text
    assert "execution_supported=false" in text
    assert "status=blocked" in text
    assert "Security validation recognizes `replay_lifecycle_retry_execution_eligibility`" in text
    assert "execution remains blocked" in text
    assert "missing_rendered_command_result" in text
    assert "replay_lifecycle_retry_execution_eligibility" in text
    assert "retry execution eligibility observations" in text
    assert "blocked eligibility status" in text
    assert "retry execution eligibility gate" in text
    assert "replay_lifecycle_retry_execution_eligibility" in text
    assert "safe governance path remains non-executing" in text
    assert "full seven-stage safe governance trail" in text
    assert "chain_records=7" in text
    assert "seven_stage=true" in text
    assert "eligibilities=1" in text
    assert "eligibility builder is idempotent" in text
    assert "skips publishing a duplicate" in text
    assert "existing blocked decision" in text
    assert "rendered retry command dry-run runner is idempotent" in text
    assert "replay_lifecycle_retry_rendered_command_result" in text
    assert "skips publishing a duplicate" in text
    assert "existing skipped dry-run result" in text
    assert "retry governance seed helper is idempotent" in text
    assert "skips publishing a duplicate" in text
    assert "existing governance record" in text
    assert "idempotent when rerun without" in text
    assert "existing_complete=true" in text
    assert "records_seeded=0" in text
    assert "eligibility_results=0" in text
    assert "fails the clean preflight" in text
    assert "existing_complete=true" in text
    assert "existing_rendered_results=1" in text
    assert "existing_execution_blocked=1" in text
    assert "Retry governance seven-stage smoke" in text
    assert "chain_records=7" in text
    assert "execution_blocked=1" in text
    assert "Pre-controlled-runner readiness" in text
    assert "check_retry_controlled_runner_readiness" in text
    assert "readiness_score=100" in text
    assert "controlled_execution_enabled=false" in text
    assert "ready_for_controlled_runner_design" in text
    assert "not a permission to execute commands" in text
    assert "Reject-only controlled runner skeleton" in text
    assert "run_controlled_retry_command" in text
    assert "controlled_execution_not_implemented" in text
    assert "payload.executed=false" in text
    assert "It is idempotent for a rendered command" in text
    assert "Security validates `replay_lifecycle_retry_controlled_execution_result`" in text
    assert "reject-only skeleton phase" in text
    assert "operator_authorized=false" in text
    assert "allowlist_matched=false" in text
    assert "Overseer brief surfaces controlled execution result visibility" in text
    assert "rejected/skipped/executed status counts" in text
    assert "controlled_execution_not_implemented" in text
    assert "optional controlled execution extension" in text
    assert "extended_controlled_execution_observed=true" in text
    assert "does not require a controlled execution result" in text
    assert "Controlled execution observability check" in text
    assert "check_controlled_retry_execution_observability" in text
    assert "controlled_execution_observed=true" in text
    assert "controlled_execution_results=1" in text
    assert "controlled_execution_enabled=false" in text
    assert "payload.executed=true" in text
    assert "operator_authorized=true" in text
    assert "read-only command allowlist parser" in text
    assert "execution_performed=false" in text
    assert "Parser allowlist matches do not enable execution" in text
    assert "Controlled command parse observability" in text
    assert "command_parse_valid=1" in text
    assert "command_parse_allowlisted=1" in text
    assert "command_parse_execution_performed=0" in text
    assert "--allow-controlled-execution" in text
    assert "operator_authorized=true" in text
    assert "Authorized intent remains valid only" in text
    assert "Controlled execution gate observability" in text
    assert "gate_status=blocked" in text
    assert "would_execute=false" in text
    assert "controlled_execution_implementation_not_enabled" in text
    assert "Controlled execution readiness report" in text
    assert "check_controlled_execution_readiness" in text
    assert "ready_for_mock_execution=true" in text
    assert "ready_for_real_execution=false" in text
    assert "real_execution_not_supported_yet" in text
    assert "Controlled mock execution adapter" in text
    assert "payload.executed=false" in text
    assert "subprocess_invoked=false" in text
    assert "mock_executed" in text
    assert "Mock execution visibility" in text
    assert "mock_executed=1" in text
    assert "mock_performed=1" in text
    assert "mock_subprocess_invoked=0" in text
    assert "Real execution remains disabled" in text
    assert "automatically derives the" in text
    assert "replay_lifecycle_retry_mock_execution_summary" in text
    assert "does not duplicate either record" in text
    assert "Controlled retry execution adapter contract" in text
    assert "The only supported adapter is `mock`" in text
    assert "Unsupported adapters such as" in text
    assert "payload.executed=false" in text
    assert "real_execution_enabled=false" in text
    assert "adapter=mock" in text
    assert "mode=mock" in text
    assert "Adapter contract observability" in text
    assert "adapter=mock" in text
    assert "mode=mock" in text
    assert "payload_executed=0" in text
    assert "Adapter contract readiness gates" in text
    assert "adapter_contract_observed=true" in text
    assert "adapter_result_mock_executed=1" in text
    assert "adapter_real_execution_enabled=0" in text
    assert "adapter_payload_executed=0" in text
    assert "Adapter contract violation fixtures" in text
    assert "adapter_subprocess_invoked=true" in text
    assert "adapter_real_execution_enabled=true" in text
    assert "adapter_payload_executed=true" in text
    assert "adapter != mock" in text
    assert "mode != mock" in text
    assert "Controlled execution readiness JSON schema" in text
    assert "schema_version=controlled-execution-readiness/v1" in text
    assert "schema_kind=controlled_execution_readiness" in text
    assert "ready_for_real_execution` must remain `false`" in text
    assert "regression fixtures" in text
    assert "required public fields" in text
    assert "ready_for_real_execution=false" in text
    assert "Real adapter placeholder" in text
    assert "real_execution_supported=false" in text
    assert "real_adapter_supported=false" in text
    assert "real_adapter_runnable=false" in text
    assert "Requesting the `real` adapter fails closed" in text
    assert "Unsupported real adapter observability" in text
    assert "real_adapter_supported=false" in text
    assert "real_adapter_runnable=false" in text
    assert "requires_explicit_pr=true" in text
    assert "fail-closed" in text
    assert "security_real_adapter_supported=0" in text
    assert "security_real_adapter_runnable=0" in text
    assert "security_real_adapter_requires_explicit_pr=1" in text
    assert "Real execution CLI scaffold" in text
    assert "`run_controlled_retry_command --real-execution`" in text
    assert "reason=real_execution_not_supported" in text
    assert "real_execution_requested=true" in text
    assert "real_execution_performed=false" in text
    assert "subprocess_invoked=false" in text
    assert "payload.executed=false" in text
    assert "audit-only" in text
    assert "Real execution request observability" in text
    assert "real_execution_request_observed=true" in text
    assert "real_execution_request_rejected=1" in text
    assert "real_execution_performed=0" in text
    assert "subprocess_invoked_count=0" in text
    assert "rejected as unsupported" in text
    assert "Real execution preflight records" in text
    assert "replay_lifecycle_retry_real_execution_preflight" in text
    assert "status=blocked" in text
    assert "would_execute=false" in text
    assert "execution_performed=false" in text
    assert "subprocess_invoked=false" in text
    assert "real_adapter_requires_explicit_pr=true" in text
    assert "Real preflight observability" in text
    assert "real_preflight_observed=true" in text
    assert "real_preflight_blocked=1" in text
    assert "real_preflight_would_execute=0" in text
    assert "real_preflight_execution_performed=0" in text
    assert "real_preflight_subprocess_invoked=0" in text
    assert "real_preflight_requires_explicit_pr=1" in text
    assert "Real execution preflight remains blocked" in text
    assert "Explicit real execution approval records" in text
    assert "replay_lifecycle_retry_real_execution_approval" in text
    assert "real_execution_enabled=false" in text
    assert "subprocess_enabled=false" in text
    assert "Operator authorization alone is insufficient" in text
    assert "Final real execution gate" in text
    assert "replay_lifecycle_retry_real_execution_final_gate" in text
    assert "ready_for_real_execution=false" in text
    assert "would_execute=false" in text
    assert "explicit execution PR" in text
    assert "Real execution dry-run envelope" in text
    assert "replay_lifecycle_retry_real_execution_dry_run_envelope" in text
    assert "dry_run_only=true" in text
    assert "subprocess_invoked=false" in text
    assert "does not execute commands" in text
    assert "Guarded noop execution harness" in text
    assert "replay_lifecycle_retry_real_execution_noop_result" in text
    assert "noop_only=true" in text
    assert "rendered_command_executed=false" in text
    assert "dry_run_envelope_command_executed=false" in text
    assert "subprocess_invoked=true" in text
    assert "Read-only evidence command promotion" in text
    assert "replay_lifecycle_retry_real_execution_read_only_promotion" in text
    assert "src.testing.run_replay_evidence_check" in text
    assert "subprocess_invoked=false" in text
    assert "does not execute the read-only command" in text
    assert "Read-only execution final gate" in text
    assert "replay_lifecycle_retry_real_execution_read_only_final_gate" in text
    assert "ready_for_read_only_execution=false" in text
    assert "read_only_execution_enabled=false" in text
    assert "requires a separate PR" in text
    assert "Read-only execution approval scaffold" in text
    assert "replay_lifecycle_retry_real_execution_read_only_approval" in text
    assert "read_only_execution_enabled=false" in text
    assert "does not execute the read-only command" in text
    assert "Read-only execution approval transition" in text
    assert "replay_lifecycle_retry_real_execution_read_only_approval_transition" in text
    assert "from_status=pending" in text
    assert "to_status=approved" in text
    assert "read_only_execution_enabled=false" in text
    assert "audit artifact only" in text
    assert "Read-only execution readiness gate" in text
    assert "replay_lifecycle_retry_real_execution_read_only_readiness_gate" in text
    assert "ready_for_guarded_read_only_execution=true" in text
    assert "read_only_execution_enabled=false" in text
    assert "guarded_read_only_execution_requires_separate_pr" in text
    assert "Guarded read-only execution result" in text
    assert "replay_lifecycle_retry_real_execution_read_only_execution_result" in text
    assert "status=failed" in text
    assert "validation_reasons=[]" in text
    assert "real_execution_enabled=false" in text
    assert "does not enable arbitrary real execution" in text