"""Build LLM-friendly global briefs from Overseer runtime state."""

from __future__ import annotations

from typing import Any, Mapping

from src.swarms.common.protocols.briefs import (
    BriefScope,
    BriefSeverity,
    BriefStatus,
    SwarmBrief,
    build_brief_item,
    build_swarm_brief,
)


def build_global_swarm_brief(
    *,
    snapshot: Any,
    topology_health: Mapping[str, Any] | None = None,
    memory_intelligence: Mapping[str, Any] | None = None,
    security_validation: Mapping[str, Any] | None = None,
    simulation_replay: Mapping[str, Any] | None = None,
    evidence_ids: list[str] | None = None,
) -> SwarmBrief:
    """Build a compact global brief from Overseer snapshot and health data."""
    topology_health = dict(topology_health or {})
    memory_intelligence = dict(memory_intelligence or {})
    security_validation = dict(
        security_validation
        if security_validation is not None
        else _extract_security_validation(snapshot)
    )
    simulation_replay = dict(
        simulation_replay
        if simulation_replay is not None
        else _extract_simulation_replay(snapshot)
    )

    if isinstance(snapshot, Mapping):
        swarm_counts = _safe_dict(
            snapshot.get("swarm_counts")
            or snapshot.get("active_swarm_counts")
            or {}
        )
        trade_nodes = _safe_int(snapshot.get("trade_nodes", 0), 0)
        security_nodes = _safe_int(snapshot.get("security_nodes", 0), 0)
        explorer_nodes = _safe_int(snapshot.get("explorer_nodes", 0), 0)
        improver_nodes = _safe_int(snapshot.get("improver_nodes", 0), 0)
        trade_capital = _safe_float(snapshot.get("trade_capital", 0.0), 0.0)
        trade_fitness = _safe_float(snapshot.get("trade_fitness", 0.0), 0.0)
    else:
        swarm_counts = _safe_dict(getattr(snapshot, "swarm_counts", {}))
        trade_nodes = _safe_int(getattr(snapshot, "trade_nodes", 0), 0)
        security_nodes = _safe_int(getattr(snapshot, "security_nodes", 0), 0)
        explorer_nodes = _safe_int(getattr(snapshot, "explorer_nodes", 0), 0)
        improver_nodes = _safe_int(getattr(snapshot, "improver_nodes", 0), 0)
        trade_capital = _safe_float(getattr(snapshot, "trade_capital", 0.0), 0.0)
        trade_fitness = _safe_float(getattr(snapshot, "trade_fitness", 0.0), 0.0)

    aggregate = _safe_dict(memory_intelligence.get("aggregate", {}))

    risks: list[dict[str, Any]] = []
    opportunities: list[dict[str, Any]] = []
    recommended_actions: list[dict[str, Any]] = []

    degraded_swarms = _degraded_swarms(topology_health)
    if degraded_swarms:
        risks.append(
            build_brief_item(
                title="degraded swarms detected",
                severity=BriefSeverity.WARNING.value,
                detail=", ".join(degraded_swarms),
                payload={"swarms": degraded_swarms},
            )
        )
        recommended_actions.append(
            build_brief_item(
                title="inspect degraded swarms",
                severity=BriefSeverity.WARNING.value,
                detail="Review topology health and recent heartbeats for degraded swarms.",
                payload={"swarms": degraded_swarms},
            )
        )

    memory_status = str(aggregate.get("status") or "unknown")
    gold_candidates = _safe_int(aggregate.get("gold_candidates"), 0)
    review_candidates = _safe_int(aggregate.get("review_candidates"), 0)
    alert_candidates = _safe_int(aggregate.get("alert_candidates"), 0)
    dedupe_candidates = _safe_int(aggregate.get("dedupe_candidates"), 0)
    runtime_evidence_records = _safe_int(aggregate.get("runtime_evidence_records"), 0)
    runtime_evidence_gold_candidates = _safe_int(aggregate.get("runtime_evidence_gold_candidates"), 0)
    runtime_evidence_review_candidates = _safe_int(aggregate.get("runtime_evidence_review_candidates"), 0)
    runtime_evidence_alert_candidates = _safe_int(aggregate.get("runtime_evidence_alert_candidates"), 0)
    security_validation_records = _safe_int(security_validation.get("security_validation_records"), 0)
    security_validation_invalid_records = _safe_int(security_validation.get("security_validation_invalid_records"), 0)
    security_validation_critical_records = _safe_int(security_validation.get("security_validation_critical_records"), 0)
    security_validation_record_type_counts = _safe_dict(
        security_validation.get("security_validation_record_type_counts")
    )
    security_replay_lifecycle_results = _safe_int(
        security_validation_record_type_counts.get("replay_evidence_lifecycle_result"),
        0,
    )
    security_retry_proposals = _safe_int(
        security_validation_record_type_counts.get("replay_lifecycle_retry_proposal"),
        0,
    )
    security_retry_approvals = _safe_int(
        security_validation_record_type_counts.get("replay_lifecycle_retry_approval"),
        0,
    )
    security_validation_warning_reasons = _safe_dict(
        security_validation.get("security_validation_warning_reasons")
    )
    security_replay_lifecycle_timeouts = _safe_int(
        security_validation_warning_reasons.get("execution_not_observed_before_timeout"),
        0,
    )
    security_retry_approval_decision_modes = _safe_dict(
        security_validation.get("security_validation_retry_approval_decision_modes")
    )
    security_retry_manual_approvals = _safe_int(
        security_retry_approval_decision_modes.get("manual"),
        0,
    )
    security_retry_policy_approvals = _safe_int(
        security_retry_approval_decision_modes.get("policy"),
        0,
    )
    security_retry_execution_plans = _safe_int(
        security_validation_record_type_counts.get("replay_lifecycle_retry_execution_plan"),
        0,
    )
    security_retry_execution_results = _safe_int(
        security_validation_record_type_counts.get("replay_lifecycle_retry_execution_result"),
        0,
    )
    security_retry_rendered_commands = _safe_int(
        security_validation_record_type_counts.get("replay_lifecycle_retry_rendered_command"),
        0,
    )
    security_retry_rendered_command_results = _safe_int(
        security_validation_record_type_counts.get(
            "replay_lifecycle_retry_rendered_command_result"
        ),
        0,
    )
    security_retry_execution_result_statuses = _safe_dict(
        security_validation.get("security_validation_retry_execution_result_statuses")
    )
    security_retry_execution_result_reasons = _safe_dict(
        security_validation.get("security_validation_retry_execution_result_reasons")
    )

    security_retry_execution_skipped = _safe_int(
        security_retry_execution_result_statuses.get("skipped"),
        0,
    )
    security_retry_execution_rejected = _safe_int(
        security_retry_execution_result_statuses.get("rejected"),
        0,
    )
    security_retry_rendered_command_profiles = _safe_dict(
        security_validation.get("security_validation_retry_rendered_command_profiles")
    )
    security_retry_rendered_command_decision_modes = _safe_dict(
        security_validation.get("security_validation_retry_rendered_command_decision_modes")
    )
    security_retry_rendered_standard_commands = _safe_int(
        security_retry_rendered_command_profiles.get("standard"),
        0,
    )
    security_retry_rendered_patient_commands = _safe_int(
        security_retry_rendered_command_profiles.get("patient"),
        0,
    )
    security_retry_execution_eligibility_statuses = _safe_dict(
       security_validation.get("security_validation_retry_execution_eligibility_statuses")
    )
    security_retry_execution_eligibility_reasons = _safe_dict(
        security_validation.get("security_validation_retry_execution_eligibility_reasons")
    )
    security_retry_execution_blocked = _safe_int(
        security_retry_execution_eligibility_statuses.get("blocked"),
        0,
    )
    security_retry_execution_eligibilities = _safe_int(
        security_validation_record_type_counts.get(
            "replay_lifecycle_retry_execution_eligibility"
        ),
        0,
    )
    security_controlled_command_parse_valid = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_command_parse_valid"
            )
        ).get("true"),
        0,
    )
    security_controlled_command_parse_allowlisted = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_command_parse_allowlist_matched"
            )
        ).get("true"),
        0,
    )
    security_controlled_command_parse_execution_performed = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_command_parse_execution_performed"
            )
        ).get("true"),
        0,
    )
    security_controlled_execution_operator_authorized = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_operator_authorized"
            )
        ).get("true"),
        0,
    )
    security_controlled_execution_gate_statuses = _safe_dict(
        security_validation.get("security_validation_controlled_execution_gate_statuses")
    )
    security_controlled_execution_gate_reasons = _safe_dict(
        security_validation.get("security_validation_controlled_execution_gate_reasons")
    )
    security_controlled_execution_gate_would_execute = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_gate_would_execute"
            )
        ).get("true"),
        0,
    )
    security_controlled_execution_gate_would_execute_if_enabled = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_gate_would_execute_if_enabled"
            )
        ).get("true"),
        0,
    )
    security_controlled_execution_gate_execution_performed = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_gate_execution_performed"
            )
        ).get("true"),
        0,
    )
    security_controlled_execution_gate_blocked = _safe_int(
        security_controlled_execution_gate_statuses.get("blocked"),
        0,
    )
    security_controlled_execution_gate_not_enabled = _safe_int(
        security_controlled_execution_gate_reasons.get(
            "controlled_execution_not_enabled"
        ),
        0,
    )
    security_controlled_execution_gate_implementation_not_enabled = _safe_int(
        security_controlled_execution_gate_reasons.get(
            "controlled_execution_implementation_not_enabled"
        ),
        0,
    )
    simulation_replay_scenarios = _safe_int(simulation_replay.get("simulation_replay_scenarios"), 0)
    simulation_replay_pending = _safe_int(simulation_replay.get("simulation_replay_pending"), 0)
    simulation_replay_completed = _safe_int(simulation_replay.get("simulation_replay_completed"), 0)
    simulation_replay_failed = _safe_int(simulation_replay.get("simulation_replay_failed"), 0)
    simulation_replay_executions = _safe_int(
        simulation_replay.get("simulation_replay_executions"),
        0,
    )
    simulation_replay_execution_completed = _safe_int(
        simulation_replay.get("simulation_replay_execution_completed"),
        0,
    )
    simulation_replay_execution_failed = _safe_int(
        simulation_replay.get("simulation_replay_execution_failed"),
        0,
    )
    memory_replay_execution_evidence_records = _safe_int(
        aggregate.get("replay_execution_evidence_records"),
        0,
    )
    memory_replay_execution_evidence_passed = _safe_int(
        aggregate.get("replay_execution_evidence_passed"),
        0,
    )
    memory_replay_execution_evidence_failed = _safe_int(
        aggregate.get("replay_execution_evidence_failed"),
        0,
    )
    security_retry_rendered_command_result_statuses = _safe_dict(
        security_validation.get("security_validation_retry_rendered_command_result_statuses")
    )
    security_retry_rendered_command_result_reasons = _safe_dict(
        security_validation.get("security_validation_retry_rendered_command_result_reasons")
    )

    security_retry_rendered_command_skipped = _safe_int(
        security_retry_rendered_command_result_statuses.get("skipped"),
        0,
    )
    security_retry_rendered_command_rejected = _safe_int(
        security_retry_rendered_command_result_statuses.get("rejected"),
        0,
    )
    security_controlled_execution_results = _safe_int(
        security_validation_record_type_counts.get(
            "replay_lifecycle_retry_controlled_execution_result"
        ),
        0,
    )
    security_controlled_execution_result_statuses = _safe_dict(
        security_validation.get(
            "security_validation_controlled_execution_result_statuses"
        )
    )
    security_controlled_execution_result_reasons = _safe_dict(
        security_validation.get(
            "security_validation_controlled_execution_result_reasons"
        )
    )
    security_controlled_execution_rejected = _safe_int(
        security_controlled_execution_result_statuses.get("rejected"),
        0,
    )
    security_controlled_execution_skipped = _safe_int(
        security_controlled_execution_result_statuses.get("skipped"),
        0,
    )
    security_controlled_execution_executed = _safe_int(
        security_controlled_execution_result_statuses.get("executed"),
        0,
    )
    security_controlled_execution_not_implemented = _safe_int(
        security_controlled_execution_result_reasons.get(
            "controlled_execution_not_implemented"
        ),
        0,
    )
    security_controlled_mock_statuses = _safe_dict(
        security_validation.get(
            "security_validation_controlled_execution_mock_statuses"
        )
    )
    security_controlled_mock_performed_mapping = _safe_dict(
        security_validation.get(
            "security_validation_controlled_execution_mock_performed"
        )
    )
    security_controlled_mock_subprocess_mapping = _safe_dict(
        security_validation.get(
            "security_validation_controlled_execution_mock_subprocess_invoked"
        )
    )

    security_controlled_mock_executed = _safe_int(
        security_controlled_mock_statuses.get("mock_executed"),
        0,
    )
    security_controlled_mock_performed = _safe_int(
        security_controlled_mock_performed_mapping.get("true"),
        0,
    )
    security_controlled_mock_subprocess_invoked = _safe_int(
        security_controlled_mock_subprocess_mapping.get("true"),
        0,
    )
    security_mock_summary_statuses = _safe_dict(
        security_validation.get("security_validation_mock_summary_statuses")
    )
    security_mock_summary_performed_mapping = _safe_dict(
        security_validation.get("security_validation_mock_summary_performed")
    )
    security_mock_summary_subprocess_mapping = _safe_dict(
        security_validation.get(
            "security_validation_mock_summary_subprocess_invoked"
        )
    )

    security_mock_summary_executed = _safe_int(
        security_mock_summary_statuses.get("mock_executed"),
        0,
    )
    security_mock_summary_performed = _safe_int(
        security_mock_summary_performed_mapping.get("true"),
        0,
    )
    security_mock_summary_subprocess_invoked = _safe_int(
        security_mock_summary_subprocess_mapping.get("true"),
        0,
    )
    security_mock_adapter = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_mock_adapter"
            )
        ).get("mock"),
        0,
    )
    security_mock_adapter_mode = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_mock_adapter_mode"
            )
        ).get("mock"),
        0,
    )
    security_mock_adapter_result_status = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_mock_adapter_result_statuses"
            )
        ).get("mock_executed"),
        0,
    )
    security_mock_adapter_subprocess_invoked = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_mock_adapter_subprocess_invoked"
            )
        ).get("true"),
        0,
    )
    security_mock_adapter_real_execution_enabled = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_mock_adapter_real_execution_enabled"
            )
        ).get("true"),
        0,
    )
    security_mock_adapter_payload_executed = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_mock_adapter_payload_executed"
            )
        ).get("true"),
        0,
    )
    security_controlled_real_execution_requested = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_real_requested"
            )
        ).get("true"),
        0,
    )
    security_controlled_real_execution_performed = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_real_performed"
            )
        ).get("true"),
        0,
    )
    security_controlled_real_execution_supported = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_real_supported"
            )
        ).get("true"),
        0,
    )
    security_controlled_subprocess_invoked = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_controlled_execution_subprocess_invoked"
            )
        ).get("true"),
        0,
    )
    security_real_preflight_blocked = _safe_int(
        _safe_dict(
            security_validation.get("security_validation_real_preflight_statuses")
        ).get("blocked"),
        0,
    )
    security_real_preflight_would_execute = _safe_int(
        _safe_dict(
            security_validation.get("security_validation_real_preflight_would_execute")
        ).get("true"),
        0,
    )
    security_real_preflight_execution_performed = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_real_preflight_execution_performed"
            )
        ).get("true"),
        0,
    )
    security_real_preflight_subprocess_invoked = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_real_preflight_subprocess_invoked"
            )
        ).get("true"),
        0,
    )
    security_real_preflight_requires_explicit_pr = _safe_int(
        _safe_dict(
            security_validation.get(
                "security_validation_real_preflight_requires_explicit_pr"
            )
        ).get("true"),
        0,
    )
    security_real_approval_records = sum(
        _safe_int(value, 0)
        for value in _safe_dict(
            security_validation.get("security_validation_real_approval_statuses")
        ).values()
    )
    security_real_approval_enabled = _safe_int(
        _safe_dict(
            security_validation.get("security_validation_real_approval_enabled")
        ).get("true"),
        0,
    )
    security_real_approval_subprocess_enabled = _safe_int(
        _safe_dict(
            security_validation.get("security_validation_real_approval_subprocess_enabled")
        ).get("true"),
        0,
    )
    security_real_approval_execution_performed = _safe_int(
        _safe_dict(
            security_validation.get("security_validation_real_approval_execution_performed")
        ).get("true"),
        0,
    )
    security_real_approval_subprocess_invoked = _safe_int(
        _safe_dict(
            security_validation.get("security_validation_real_approval_subprocess_invoked")
        ).get("true"),
        0,
    )
    security_read_only_feedback_records = _safe_int(
        security_validation_record_type_counts.get(
            "replay_lifecycle_retry_real_execution_read_only_feedback"
        ),
        0,
    )
    if security_read_only_feedback_records == 0:
        security_read_only_feedback_records = _safe_int(
            security_validation.get(
                "replay_lifecycle_retry_real_execution_read_only_feedback"
            ),
            0,
        )
    if security_read_only_feedback_records == 0:
        security_read_only_feedback_records = _safe_int(
            _safe_dict(security_validation.get("by_type")).get(
                "replay_lifecycle_retry_real_execution_read_only_feedback"
            ),
            0,
        )

    def _security_mapping(*keys: str) -> dict[str, Any]:
        for key in keys:
            mapping = _safe_dict(security_validation.get(key))
            if mapping:
                return mapping
        return {}

    security_read_only_feedback_actionable = _safe_int(
        _security_mapping(
            "security_validation_real_read_only_feedback_statuses",
            "security_validation_read_only_feedback_statuses",
            "security_validation_real_execution_read_only_feedback_statuses",
            "real_read_only_feedback_statuses",
            "read_only_feedback_statuses",
        ).get("actionable"),
        0,
    )
    security_read_only_feedback_source_failed = _safe_int(
        _security_mapping(
            "security_validation_real_read_only_feedback_source_statuses",
            "security_validation_read_only_feedback_source_statuses",
            "security_validation_real_execution_read_only_feedback_source_statuses",
            "real_read_only_feedback_source_statuses",
            "read_only_feedback_source_statuses",
        ).get("failed"),
        0,
    )
    security_read_only_feedback_exit_code_1 = _safe_int(
        _security_mapping(
            "security_validation_real_read_only_feedback_source_exit_codes",
            "security_validation_read_only_feedback_source_exit_codes",
            "security_validation_real_execution_read_only_feedback_source_exit_codes",
            "real_read_only_feedback_source_exit_codes",
            "read_only_feedback_source_exit_codes",
        ).get("1"),
        0,
    )
    security_read_only_feedback_next_action_investigate = _safe_int(
        _security_mapping(
            "security_validation_real_read_only_feedback_next_actions",
            "security_validation_read_only_feedback_next_actions",
            "security_validation_real_execution_read_only_feedback_next_actions",
            "real_read_only_feedback_next_actions",
            "read_only_feedback_next_actions",
        ).get("investigate_failed_read_only_evidence_check"),
        0,
    )
    security_read_only_feedback_real_execution_enabled = _safe_int(
        _security_mapping(
            "security_validation_real_read_only_feedback_real_execution_enabled",
            "security_validation_read_only_feedback_real_execution_enabled",
            "security_validation_real_execution_read_only_feedback_real_execution_enabled",
            "real_read_only_feedback_real_execution_enabled",
            "read_only_feedback_real_execution_enabled",
        ).get("true"),
        0,
    )
    security_read_only_feedback_execution_performed = _safe_int(
        _security_mapping(
            "security_validation_real_read_only_feedback_execution_performed",
            "security_validation_read_only_feedback_execution_performed",
            "security_validation_real_execution_read_only_feedback_execution_performed",
            "real_read_only_feedback_execution_performed",
            "read_only_feedback_execution_performed",
        ).get("true"),
        0,
    )
    security_read_only_feedback_subprocess_invoked = _safe_int(
        _security_mapping(
            "security_validation_real_read_only_feedback_subprocess_invoked",
            "security_validation_read_only_feedback_subprocess_invoked",
            "security_validation_real_execution_read_only_feedback_subprocess_invoked",
            "real_read_only_feedback_subprocess_invoked",
            "read_only_feedback_subprocess_invoked",
        ).get("true"),
        0,
    )
    security_read_only_feedback_feedback_execution_performed = _safe_int(
        _security_mapping(
            "security_validation_real_read_only_feedback_feedback_execution_performed",
            "security_validation_read_only_feedback_feedback_execution_performed",
            "security_validation_real_execution_read_only_feedback_feedback_execution_performed",
            "real_read_only_feedback_feedback_execution_performed",
            "read_only_feedback_feedback_execution_performed",
        ).get("true"),
        0,
    )
    security_read_only_feedback_feedback_subprocess_invoked = _safe_int(
        _security_mapping(
            "security_validation_real_read_only_feedback_feedback_subprocess_invoked",
            "security_validation_read_only_feedback_feedback_subprocess_invoked",
            "security_validation_real_execution_read_only_feedback_feedback_subprocess_invoked",
            "real_read_only_feedback_feedback_subprocess_invoked",
            "read_only_feedback_feedback_subprocess_invoked",
        ).get("true"),
        0,
    )
    security_real_adapter_supported = bool(
        security_validation.get("security_real_adapter_supported", False)
    )
    security_real_adapter_runnable = bool(
        security_validation.get("security_real_adapter_runnable", False)
    )
    security_real_adapter_requires_explicit_pr = bool(
        security_validation.get("security_real_adapter_requires_explicit_pr", True)
    )
    security_real_adapter_subprocess_supported = bool(
        security_validation.get("security_real_adapter_subprocess_supported", False)
    )

    if gold_candidates > 0:
        opportunities.append(
            build_brief_item(
                title="memory gold candidates available",
                severity=BriefSeverity.INFO.value,
                detail=f"Memory reports {gold_candidates} gold candidate(s).",
                payload={"gold_candidates": gold_candidates},
            )
        )
        recommended_actions.append(
            build_brief_item(
                title="promote memory gold candidates",
                severity=BriefSeverity.INFO.value,
                detail="Consider exporting or replaying high-value memory samples.",
                payload={
                    "directive": "PROMOTE_GOLD_CANDIDATES",
                    "target_swarm": "memory",
                    "gold_candidates": gold_candidates,
                },
            )
        )

    if runtime_evidence_gold_candidates > 0:
        opportunities.append(
            build_brief_item(
                title="Runtime evidence available",
                detail=(
                    f"Memory reports {runtime_evidence_gold_candidates} verified "
                    "runtime evidence gold candidate(s)."
                ),
                severity=BriefSeverity.INFO.value,
                payload={
                    "runtime_evidence_records": runtime_evidence_records,
                    "runtime_evidence_gold_candidates": runtime_evidence_gold_candidates,
                    "directive": "PROMOTE_GOLD_CANDIDATES",
                },
            )
        )
        recommended_actions.append(
            build_brief_item(
                title="Promote runtime evidence",
                detail="Promote or replay verified runtime evidence from memory.",
                severity=BriefSeverity.INFO.value,
                payload={
                    "directive": "PROMOTE_GOLD_CANDIDATES",
                    "target_swarm": "memory",
                    "runtime_evidence_gold_candidates": runtime_evidence_gold_candidates,
                },
            )
        )

    if security_retry_approvals > 0:
        opportunities.append(
            build_brief_item(
                title="Replay lifecycle retry approvals observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    f"Security validated {security_retry_approvals} replay lifecycle "
                    "retry approval record(s)."
                ),
                payload={
                    "security_retry_approvals": security_retry_approvals,
                    "recommendation": "review_replay_retry_approvals",
                },
            )
        )

    if alert_candidates > 0:
        risks.append(
            build_brief_item(
                title="memory alert candidates detected",
                severity=BriefSeverity.WARNING.value,
                detail=f"Memory reports {alert_candidates} alert candidate(s).",
                payload={"alert_candidates": alert_candidates},
            )
        )

    if runtime_evidence_alert_candidates > 0:
        risks.append(
            build_brief_item(
                title="Runtime evidence alerts detected",
                detail=(
                    f"Memory reports {runtime_evidence_alert_candidates} runtime "
                    "evidence alert candidate(s)."
                ),
                severity=BriefSeverity.WARNING.value,
                payload={
                    "runtime_evidence_alert_candidates": runtime_evidence_alert_candidates,
                    "recommendation": "review_runtime_evidence_alerts",
                },
            )
        )
        recommended_actions.append(
            build_brief_item(
                title="Review runtime evidence alerts",
                detail="Review failed runtime evidence before further promotion or replay.",
                severity=BriefSeverity.WARNING.value,
                payload={
                    "recommendation": "review_runtime_evidence_alerts",
                    "target_swarm": "memory",
                    "runtime_evidence_alert_candidates": runtime_evidence_alert_candidates,
                },
            )
        )

    if security_validation_critical_records > 0:
        risks.append(
            build_brief_item(
                title="Critical security validation failures",
                severity=BriefSeverity.CRITICAL.value,
                detail=(
                    f"Security reports {security_validation_critical_records} critical "
                    "runtime validation failure(s)."
                ),
                payload={
                    "security_validation_records": security_validation_records,
                    "security_validation_critical_records": security_validation_critical_records,
                    "security_validation_invalid_records": security_validation_invalid_records,
                    "recommendation": "review_security_validation_failures",
                },
            )
        )
        recommended_actions.append(
            build_brief_item(
                title="Review security validation failures",
                severity=BriefSeverity.CRITICAL.value,
                detail="Review invalid directive/evidence/memory runtime records before further automation.",
                payload={
                    "recommendation": "review_security_validation_failures",
                    "target_swarm": "security",
                    "security_validation_critical_records": security_validation_critical_records,
                    "security_validation_invalid_records": security_validation_invalid_records,
                },
            )
        )
    elif security_validation_invalid_records > 0:
        risks.append(
            build_brief_item(
                title="Security validation warnings",
                severity=BriefSeverity.WARNING.value,
                detail=(
                    f"Security reports {security_validation_invalid_records} invalid "
                    "runtime validation record(s)."
                ),
                payload={
                    "security_validation_records": security_validation_records,
                    "security_validation_invalid_records": security_validation_invalid_records,
                    "recommendation": "review_security_validation_warnings",
                },
            )
        )

    if security_replay_lifecycle_results > 0:
        opportunities.append(
            build_brief_item(
                title="Replay evidence lifecycle validation observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    f"Security validated {security_replay_lifecycle_results} "
                    "replay evidence lifecycle result record(s)."
                ),
                payload={
                    "security_replay_lifecycle_results": security_replay_lifecycle_results,
                    "recommendation": "review_replay_lifecycle_validation",
                },
            )
        )

    if security_retry_proposals > 0:
        opportunities.append(
            build_brief_item(
                title="Pending replay lifecycle retry proposals observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    f"Security validated {security_retry_proposals} pending "
                    "replay lifecycle retry proposal record(s)."
                ),
                payload={
                    "security_retry_proposals": security_retry_proposals,
                    "recommendation": "review_replay_retry_proposals",
                },
            )
        )

    if security_replay_lifecycle_timeouts > 0:
        risks.append(
            build_brief_item(
                title="Replay lifecycle timeout warnings observed",
                severity=BriefSeverity.WARNING.value,
                detail=(
                    f"Security observed {security_replay_lifecycle_timeouts} "
                    "replay lifecycle timeout warning(s)."
                ),
                payload={
                    "security_replay_lifecycle_timeouts": security_replay_lifecycle_timeouts,
                    "recommendation": "review_replay_lifecycle_timeouts",
                },
            )
        )
        recommended_actions.append(
            build_brief_item(
                title="Retry replay lifecycle check",
                severity=BriefSeverity.INFO.value,
                detail=(
                    "Retry the replay lifecycle check with timeout_profile=standard before "
                    "investigating simulation responsiveness."
                ),
                payload={
                    "recommendation": "retry_replay_lifecycle_check",
                    "timeout_profile": "standard",
                    "suggested_wait_seconds": 15.0,
                    "suggested_poll_interval": 0.5,
                    "reason": "execution_not_observed_before_timeout",
                    "security_replay_lifecycle_timeouts": security_replay_lifecycle_timeouts,
                    "command_template": (
                        "python -m src.testing.run_replay_evidence_check "
                        "--scenario-id <scenario_id> "
                        "--action REDUCE_RISK "
                        "--directive-id <new_directive_id> "
                        "--timeout-profile standard "
                        "--db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db"
                    ),
                },
            )
        )

    if security_retry_manual_approvals > 0 or security_retry_policy_approvals > 0:
        opportunities.append(
            build_brief_item(
                title="Replay retry approval decision modes observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    "Security observed replay retry approval decision modes: "
                    f"manual={security_retry_manual_approvals}, "
                    f"policy={security_retry_policy_approvals}."
                ),
                payload={
                    "security_retry_approval_decision_modes": security_retry_approval_decision_modes,
                    "security_retry_manual_approvals": security_retry_manual_approvals,
                    "security_retry_policy_approvals": security_retry_policy_approvals,
                    "recommendation": "review_replay_retry_approval_decision_modes",
                },
            )
        )

    if security_retry_execution_plans > 0:
        opportunities.append(
            build_brief_item(
                title="Replay lifecycle retry execution plans observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    f"Security validated {security_retry_execution_plans} "
                    "replay lifecycle retry execution plan record(s)."
                ),
                payload={
                    "security_retry_execution_plans": security_retry_execution_plans,
                    "recommendation": "review_replay_retry_execution_plans",
                },
            )
        )

    if security_retry_execution_results > 0:
        opportunities.append(
            build_brief_item(
                title="Replay lifecycle retry execution results observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    f"Security validated {security_retry_execution_results} "
                    "replay lifecycle retry execution result record(s)."
                ),
                payload={
                    "security_retry_execution_results": security_retry_execution_results,
                    "recommendation": "review_replay_retry_execution_results",
                },
            )
        )

    if security_retry_rendered_commands > 0:
        opportunities.append(
            build_brief_item(
                title="Replay lifecycle retry rendered commands observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    f"Security validated {security_retry_rendered_commands} "
                    "replay lifecycle retry rendered command record(s)."
                ),
                payload={
                    "security_retry_rendered_commands": security_retry_rendered_commands,
                    "recommendation": "review_replay_retry_rendered_commands",
                },
            )
        )

    if security_retry_rendered_command_results > 0:
        opportunities.append(
            build_brief_item(
                title="Replay lifecycle retry rendered command results observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    f"Security validated {security_retry_rendered_command_results} "
                    "replay lifecycle retry rendered command result record(s)."
                ),
                payload={
                    "security_retry_rendered_command_results": security_retry_rendered_command_results,
                    "security_retry_rendered_command_skipped": security_retry_rendered_command_skipped,
                    "security_retry_rendered_command_rejected": security_retry_rendered_command_rejected,
                    "security_retry_rendered_command_result_statuses": (
                        security_retry_rendered_command_result_statuses
                    ),
                    "security_retry_rendered_command_result_reasons": (
                        security_retry_rendered_command_result_reasons
                    ),
                    "recommendation": "review_replay_retry_rendered_command_results",
                },
            )
        )

    if security_retry_execution_eligibilities > 0:
        opportunities.append(
            build_brief_item(
                title="Replay retry execution eligibility observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    f"Security validated {security_retry_execution_eligibilities} "
                    "retry execution eligibility record(s)."
                ),
                payload={
                    "security_retry_execution_eligibilities": security_retry_execution_eligibilities,
                    "security_retry_execution_blocked": security_retry_execution_blocked,
                    "security_retry_execution_eligibility_statuses": (
                        security_retry_execution_eligibility_statuses
                    ),
                    "security_retry_execution_eligibility_reasons": (
                        security_retry_execution_eligibility_reasons
                    ),
                    "recommendation": "review_replay_retry_execution_eligibility",
                },
            )
        )

    if security_controlled_execution_results > 0:
        opportunities.append(
            build_brief_item(
                title="Controlled retry execution results observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    f"Security validated {security_controlled_execution_results} "
                    "controlled retry execution result record(s)."
                ),
                payload={
                    "security_controlled_execution_results": (
                        security_controlled_execution_results
                    ),
                    "security_controlled_execution_rejected": (
                        security_controlled_execution_rejected
                    ),
                    "security_controlled_execution_skipped": (
                        security_controlled_execution_skipped
                    ),
                    "security_controlled_execution_executed": (
                        security_controlled_execution_executed
                    ),
                    "security_controlled_execution_not_implemented": (
                        security_controlled_execution_not_implemented
                    ),
                    "security_controlled_execution_result_statuses": (
                        security_controlled_execution_result_statuses
                    ),
                    "security_controlled_execution_result_reasons": (
                        security_controlled_execution_result_reasons
                    ),
                    "recommendation": "review_controlled_retry_execution_results",
                    "security_controlled_execution_operator_authorized": (
                        security_controlled_execution_operator_authorized
                    ),
                },
            )
        )

    if security_controlled_command_parse_valid > 0:
        opportunities.append(
            build_brief_item(
                title="Controlled retry command parser observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    "Controlled retry command parser recognized "
                    f"{security_controlled_command_parse_allowlisted} "
                    "allowlisted command(s) without execution."
                ),
                payload={
                    "security_controlled_command_parse_valid": (
                        security_controlled_command_parse_valid
                    ),
                    "security_controlled_command_parse_allowlisted": (
                        security_controlled_command_parse_allowlisted
                    ),
                    "security_controlled_command_parse_execution_performed": (
                        security_controlled_command_parse_execution_performed
                    ),
                    "recommendation": "keep_controlled_execution_disabled_until_authorized",
                },
            )
        )

    if security_controlled_execution_gate_blocked > 0:
        opportunities.append(
            build_brief_item(
                title="Controlled retry execution gate evaluated",
                severity=BriefSeverity.INFO.value,
                detail=(
                    "Controlled retry execution gate is blocked: "
                    f"controlled_execution_not_enabled="
                    f"{security_controlled_execution_gate_not_enabled}, "
                    "controlled_execution_implementation_not_enabled="
                    f"{security_controlled_execution_gate_implementation_not_enabled}."
                ),
                payload={
                    "security_controlled_execution_gate_blocked": (
                        security_controlled_execution_gate_blocked
                    ),
                    "security_controlled_execution_gate_would_execute": (
                        security_controlled_execution_gate_would_execute
                    ),
                    "security_controlled_execution_gate_would_execute_if_enabled": (
                        security_controlled_execution_gate_would_execute_if_enabled
                    ),
                    "security_controlled_execution_gate_execution_performed": (
                        security_controlled_execution_gate_execution_performed
                    ),
                    "security_controlled_execution_gate_reasons": (
                        security_controlled_execution_gate_reasons
                    ),
                    "recommendation": "keep_controlled_execution_gate_closed",
                },
            )
        )

    if security_controlled_mock_executed > 0 or security_controlled_mock_performed > 0:
        opportunities.append(
            build_brief_item(
                title="Controlled mock execution observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    "Controlled mock execution observed: "
                    f"mock_executed={security_controlled_mock_executed}, "
                    f"mock_performed={security_controlled_mock_performed}, "
                    "subprocess_invoked="
                    f"{security_controlled_mock_subprocess_invoked}. "
                    "Real execution remains disabled."
                ),
                payload={
                    "security_controlled_mock_executed": (
                        security_controlled_mock_executed
                    ),
                    "security_controlled_mock_performed": (
                        security_controlled_mock_performed
                    ),
                    "security_controlled_mock_subprocess_invoked": (
                        security_controlled_mock_subprocess_invoked
                    ),
                    "recommendation": "keep_real_execution_disabled_until_real_adapter_pr",
                },
            )
        )

    if security_mock_summary_executed > 0 or security_mock_summary_performed > 0:
        opportunities.append(
            build_brief_item(
                title="Controlled mock execution summary observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    "Controlled mock execution summary observed: "
                    f"mock_executed={security_mock_summary_executed}, "
                    f"mock_performed={security_mock_summary_performed}, "
                    "subprocess_invoked="
                    f"{security_mock_summary_subprocess_invoked}."
                ),
                payload={
                    "security_mock_summary_executed": security_mock_summary_executed,
                    "security_mock_summary_performed": security_mock_summary_performed,
                    "security_mock_summary_subprocess_invoked": (
                        security_mock_summary_subprocess_invoked
                    ),
                    "recommendation": "keep_mock_summary_derived_and_real_execution_disabled",
                },
            )
        )

    if security_mock_adapter > 0 or security_mock_adapter_result_status > 0:
        opportunities.append(
            build_brief_item(
                title="Controlled mock adapter contract observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    "Controlled mock adapter contract observed: "
                    f"adapter=mock:{security_mock_adapter}, "
                    f"mode=mock:{security_mock_adapter_mode}, "
                    f"mock_executed={security_mock_adapter_result_status}, "
                    f"subprocess_invoked={security_mock_adapter_subprocess_invoked}, "
                    "real_execution_enabled="
                    f"{security_mock_adapter_real_execution_enabled}, "
                    f"payload_executed={security_mock_adapter_payload_executed}."
                ),
                payload={
                    "security_mock_adapter": security_mock_adapter,
                    "security_mock_adapter_mode": security_mock_adapter_mode,
                    "security_mock_adapter_result_status": (
                        security_mock_adapter_result_status
                    ),
                    "security_mock_adapter_subprocess_invoked": (
                        security_mock_adapter_subprocess_invoked
                    ),
                    "security_mock_adapter_real_execution_enabled": (
                        security_mock_adapter_real_execution_enabled
                    ),
                    "security_mock_adapter_payload_executed": (
                        security_mock_adapter_payload_executed
                    ),
                    "recommendation": "keep_real_adapter_disabled_until_explicit_pr",
                },
            )
        )

    if (
        "security_real_adapter_supported" in security_validation
        or "security_real_adapter_runnable" in security_validation
        or "security_real_adapter_requires_explicit_pr" in security_validation
    ):
        opportunities.append(
            build_brief_item(
                title="Real controlled retry adapter is unsupported",
                severity=BriefSeverity.INFO.value,
                detail=(
                    "Real controlled retry adapter is unsupported/non-runnable: "
                    f"real_adapter_supported={str(security_real_adapter_supported).lower()}, "
                    f"real_adapter_runnable={str(security_real_adapter_runnable).lower()}, "
                    "subprocess_supported="
                    f"{str(security_real_adapter_subprocess_supported).lower()}, "
                    "requires_explicit_pr="
                    f"{str(security_real_adapter_requires_explicit_pr).lower()}."
                ),
                payload={
                    "security_real_adapter_supported": security_real_adapter_supported,
                    "security_real_adapter_runnable": security_real_adapter_runnable,
                    "security_real_adapter_subprocess_supported": (
                        security_real_adapter_subprocess_supported
                    ),
                    "security_real_adapter_requires_explicit_pr": (
                        security_real_adapter_requires_explicit_pr
                    ),
                    "recommendation": "keep_real_adapter_unsupported_until_explicit_pr",
                },
            )
        )

    if security_controlled_real_execution_requested > 0:
        opportunities.append(
            build_brief_item(
                title="Real controlled retry execution request rejected",
                severity=BriefSeverity.INFO.value,
                detail=(
                    "Real controlled retry execution request observed and rejected: "
                    f"requested={security_controlled_real_execution_requested}, "
                    f"performed={security_controlled_real_execution_performed}, "
                    f"supported={security_controlled_real_execution_supported}, "
                    f"subprocess_invoked={security_controlled_subprocess_invoked}."
                ),
                payload={
                    "security_controlled_real_execution_requested": (
                        security_controlled_real_execution_requested
                    ),
                    "security_controlled_real_execution_performed": (
                        security_controlled_real_execution_performed
                    ),
                    "security_controlled_real_execution_supported": (
                        security_controlled_real_execution_supported
                    ),
                    "security_controlled_subprocess_invoked": (
                        security_controlled_subprocess_invoked
                    ),
                    "recommendation": "keep_real_execution_requests_audit_only_until_preflight_pr",
                },
            )
        )

    if security_real_preflight_blocked > 0:
        opportunities.append(
            build_brief_item(
                title="Real execution preflight remains blocked",
                severity=BriefSeverity.INFO.value,
                detail=(
                    "Real execution preflight remains blocked: "
                    f"blocked={security_real_preflight_blocked}, "
                    f"would_execute={security_real_preflight_would_execute}, "
                    "execution_performed="
                    f"{security_real_preflight_execution_performed}, "
                    f"subprocess_invoked={security_real_preflight_subprocess_invoked}, "
                    "requires_explicit_pr="
                    f"{security_real_preflight_requires_explicit_pr}."
                ),
                payload={
                    "security_real_preflight_blocked": (
                        security_real_preflight_blocked
                    ),
                    "security_real_preflight_would_execute": (
                        security_real_preflight_would_execute
                    ),
                    "security_real_preflight_execution_performed": (
                        security_real_preflight_execution_performed
                    ),
                    "security_real_preflight_subprocess_invoked": (
                        security_real_preflight_subprocess_invoked
                    ),
                    "security_real_preflight_requires_explicit_pr": (
                        security_real_preflight_requires_explicit_pr
                    ),
                    "recommendation": "keep_real_execution_preflight_blocked_until_explicit_approval_schema",
                },
            )
        )

    if security_real_approval_records > 0:
        opportunities.append(
            build_brief_item(
                title="Explicit real execution approval observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    "Explicit real execution approval observed: "
                    f"records={security_real_approval_records}, "
                    f"real_execution_enabled={security_real_approval_enabled}, "
                    f"subprocess_enabled={security_real_approval_subprocess_enabled}, "
                    f"execution_performed={security_real_approval_execution_performed}, "
                    f"subprocess_invoked={security_real_approval_subprocess_invoked}."
                ),
                payload={
                    "security_real_approval_records": security_real_approval_records,
                    "security_real_approval_enabled": security_real_approval_enabled,
                    "security_real_approval_subprocess_enabled": (
                        security_real_approval_subprocess_enabled
                    ),
                    "security_real_approval_execution_performed": (
                        security_real_approval_execution_performed
                    ),
                    "security_real_approval_subprocess_invoked": (
                        security_real_approval_subprocess_invoked
                    ),
                    "recommendation": "keep_real_execution_disabled_until_explicit_real_adapter_pr",
                },
            )
        )

    if security_read_only_feedback_records > 0:
        opportunities.append(
            build_brief_item(
                title="Read-only execution feedback observed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    "Read-only execution feedback observed: "
                    f"records={security_read_only_feedback_records}, "
                    f"actionable={security_read_only_feedback_actionable}, "
                    f"source_failed={security_read_only_feedback_source_failed}, "
                    f"exit_code_1={security_read_only_feedback_exit_code_1}, "
                    "next_action=investigate_failed_read_only_evidence_check, "
                    f"next_action_count={security_read_only_feedback_next_action_investigate}, "
                    f"real_execution_enabled={security_read_only_feedback_real_execution_enabled}, "
                    f"execution_performed={security_read_only_feedback_execution_performed}, "
                    f"subprocess_invoked={security_read_only_feedback_subprocess_invoked}, "
                    f"feedback_execution_performed={security_read_only_feedback_feedback_execution_performed}, "
                    f"feedback_subprocess_invoked={security_read_only_feedback_feedback_subprocess_invoked}."
                ),
                payload={
                    "security_read_only_feedback_records": (
                        security_read_only_feedback_records
                    ),
                    "security_read_only_feedback_actionable": (
                        security_read_only_feedback_actionable
                    ),
                    "security_read_only_feedback_source_failed": (
                        security_read_only_feedback_source_failed
                    ),
                    "security_read_only_feedback_exit_code_1": (
                        security_read_only_feedback_exit_code_1
                    ),
                    "security_read_only_feedback_next_action_investigate": (
                        security_read_only_feedback_next_action_investigate
                    ),
                    "security_read_only_feedback_real_execution_enabled": (
                        security_read_only_feedback_real_execution_enabled
                    ),
                    "security_read_only_feedback_execution_performed": (
                        security_read_only_feedback_execution_performed
                    ),
                    "security_read_only_feedback_subprocess_invoked": (
                        security_read_only_feedback_subprocess_invoked
                    ),
                    "security_read_only_feedback_feedback_execution_performed": (
                        security_read_only_feedback_feedback_execution_performed
                    ),
                    "security_read_only_feedback_feedback_subprocess_invoked": (
                        security_read_only_feedback_feedback_subprocess_invoked
                    ),
                    "recommendation": "investigate_failed_read_only_evidence_check",
                },
            )
        )
        recommended_actions.append(
            build_brief_item(
                title="Investigate failed read-only evidence check",
                severity=BriefSeverity.INFO.value,
                detail=(
                    "Use read-only execution feedback to investigate the failed "
                    "replay evidence check before expanding execution capability."
                ),
                payload={
                    "recommendation": "investigate_failed_read_only_evidence_check",
                    "target_swarm": "overseer",
                    "security_read_only_feedback_records": (
                        security_read_only_feedback_records
                    ),
                    "security_read_only_feedback_actionable": (
                        security_read_only_feedback_actionable
                    ),
                    "security_read_only_feedback_source_failed": (
                        security_read_only_feedback_source_failed
                    ),
                    "security_read_only_feedback_exit_code_1": (
                        security_read_only_feedback_exit_code_1
                    ),
                    "execution_enabled": False,
                    "subprocess_enabled": False,
                },
            )
        )

    if simulation_replay_pending > 0:
        opportunities.append(
            build_brief_item(
                title="Simulation replay scenarios pending",
                severity=BriefSeverity.INFO.value,
                detail=(
                    f"Simulation reports {simulation_replay_pending} pending "
                    "replay scenario(s)."
                ),
                payload={
                    "simulation_replay_scenarios": simulation_replay_scenarios,
                    "simulation_replay_pending": simulation_replay_pending,
                    "recommendation": "observe_simulation_replay",
                },
            )
        )
        recommended_actions.append(
            build_brief_item(
                title="Observe simulation replay queue",
                severity=BriefSeverity.INFO.value,
                detail="Observe pending simulation replay scenarios before enabling replay execution.",
                payload={
                    "recommendation": "observe_simulation_replay",
                    "target_swarm": "simulation",
                    "simulation_replay_pending": simulation_replay_pending,
                },
            )
        )

    if simulation_replay_failed > 0:
        risks.append(
            build_brief_item(
                title="Simulation replay failures detected",
                severity=BriefSeverity.WARNING.value,
                detail=(
                    f"Simulation reports {simulation_replay_failed} failed "
                    "replay scenario(s)."
                ),
                payload={
                    "simulation_replay_failed": simulation_replay_failed,
                    "recommendation": "review_simulation_replay_failures",
                },
            )
        )

    if review_candidates > 0 or dedupe_candidates > 0:
        recommended_actions.append(
            build_brief_item(
                title="review memory candidates",
                severity=BriefSeverity.INFO.value,
                detail="Memory has records requiring review or deduplication.",
                payload={
                    "review_candidates": review_candidates,
                    "dedupe_candidates": dedupe_candidates,
                },
            )
        )

    if memory_replay_execution_evidence_passed > 0:
        opportunities.append(
            build_brief_item(
                title="Replay execution evidence captured in memory",
                severity=BriefSeverity.INFO.value,
                detail=(
                    f"Memory contains {memory_replay_execution_evidence_passed} "
                    "passed replay execution evidence record(s)."
                ),
                payload={
                    "replay_execution_evidence_passed": memory_replay_execution_evidence_passed,
                    "recommendation": "review_replay_execution_memory",
                },
            )
        )

    if memory_replay_execution_evidence_failed > 0:
        risks.append(
            build_brief_item(
                title="Replay execution evidence failures in memory",
                severity=BriefSeverity.WARNING.value,
                detail=(
                    f"Memory contains {memory_replay_execution_evidence_failed} "
                    "failed replay execution evidence record(s)."
                ),
                payload={
                    "replay_execution_evidence_failed": memory_replay_execution_evidence_failed,
                    "recommendation": "review_failed_replay_execution_memory",
                },
            )
        )
    
    if simulation_replay_execution_completed > 0:
        opportunities.append(
            build_brief_item(
                title="Simulation replay dry-runs completed",
                severity=BriefSeverity.INFO.value,
                detail=(
                    f"Simulation reports {simulation_replay_execution_completed} "
                    "completed replay dry-run execution(s)."
                ),
                payload={
                    "simulation_replay_executions": simulation_replay_executions,
                    "simulation_replay_execution_completed": simulation_replay_execution_completed,
                    "recommendation": "review_simulation_replay_executions",
                },
            )
        )

    if simulation_replay_execution_failed > 0:
        risks.append(
            build_brief_item(
                title="Simulation replay dry-run failures detected",
                severity=BriefSeverity.WARNING.value,
                detail=(
                    f"Simulation reports {simulation_replay_execution_failed} "
                    "failed replay dry-run execution(s)."
                ),
                payload={
                    "simulation_replay_executions": simulation_replay_executions,
                    "simulation_replay_execution_failed": simulation_replay_execution_failed,
                    "recommendation": "review_simulation_replay_failures",
                },
            )
        )

    status = _global_status(
        degraded_swarms=degraded_swarms,
        alert_candidates=alert_candidates,
        runtime_evidence_alert_candidates=runtime_evidence_alert_candidates,
        security_validation_critical_records=security_validation_critical_records,
        memory_status=memory_status,
    )

    key_metrics = {
        "swarm_counts": swarm_counts,
        "trade_nodes": trade_nodes,
        "security_nodes": security_nodes,
        "explorer_nodes": explorer_nodes,
        "improver_nodes": improver_nodes,
        "trade_capital": trade_capital,
        "trade_fitness": trade_fitness,
        "memory_status": memory_status,
        "memory_gold_candidates": gold_candidates,
        "memory_review_candidates": review_candidates,
        "memory_alert_candidates": alert_candidates,
        "memory_dedupe_candidates": dedupe_candidates,
        "memory_runtime_evidence_records": runtime_evidence_records,
        "memory_runtime_evidence_gold_candidates": runtime_evidence_gold_candidates,
        "memory_runtime_evidence_review_candidates": runtime_evidence_review_candidates,
        "memory_runtime_evidence_alert_candidates": runtime_evidence_alert_candidates,
        "security_validation_records": security_validation_records,
        "security_validation_invalid_records": security_validation_invalid_records,
        "security_validation_critical_records": security_validation_critical_records,
        "security_replay_lifecycle_results": security_replay_lifecycle_results,
        "simulation_replay_scenarios": simulation_replay_scenarios,
        "simulation_replay_pending": simulation_replay_pending,
        "simulation_replay_completed": simulation_replay_completed,
        "simulation_replay_failed": simulation_replay_failed,
        "simulation_replay_executions": simulation_replay_executions,
        "simulation_replay_execution_completed": simulation_replay_execution_completed,
        "simulation_replay_execution_failed": simulation_replay_execution_failed,
        "memory_replay_execution_evidence_records": memory_replay_execution_evidence_records,
        "memory_replay_execution_evidence_passed": memory_replay_execution_evidence_passed,
        "memory_replay_execution_evidence_failed": memory_replay_execution_evidence_failed,
        "security_replay_lifecycle_timeouts": security_replay_lifecycle_timeouts,
        "security_retry_proposals": security_retry_proposals,
        "security_retry_approvals": security_retry_approvals,
        "security_retry_approval_decision_modes": security_retry_approval_decision_modes,
        "security_retry_manual_approvals": security_retry_manual_approvals,
        "security_retry_policy_approvals": security_retry_policy_approvals,
        "security_retry_execution_plans": security_retry_execution_plans,
        "security_retry_execution_results": security_retry_execution_results,
        "security_retry_execution_result_statuses": security_retry_execution_result_statuses,
        "security_retry_execution_result_reasons": security_retry_execution_result_reasons,
        "security_retry_execution_skipped": security_retry_execution_skipped,
        "security_retry_execution_rejected": security_retry_execution_rejected,
        "security_retry_rendered_commands": security_retry_rendered_commands,
        "security_retry_rendered_command_profiles": security_retry_rendered_command_profiles,
        "security_retry_rendered_command_decision_modes": security_retry_rendered_command_decision_modes,
        "security_retry_rendered_standard_commands": security_retry_rendered_standard_commands,
        "security_retry_rendered_patient_commands": security_retry_rendered_patient_commands,
        "security_retry_rendered_command_results": security_retry_rendered_command_results,
        "security_retry_rendered_command_result_statuses": security_retry_rendered_command_result_statuses,
        "security_retry_rendered_command_result_reasons": security_retry_rendered_command_result_reasons,
        "security_retry_rendered_command_skipped": security_retry_rendered_command_skipped,
        "security_retry_rendered_command_rejected": security_retry_rendered_command_rejected,
        "security_retry_execution_eligibilities": security_retry_execution_eligibilities,
        "security_retry_execution_eligibility_statuses": security_retry_execution_eligibility_statuses,
        "security_retry_execution_eligibility_reasons": security_retry_execution_eligibility_reasons,
        "security_retry_execution_blocked": security_retry_execution_blocked,
        "security_controlled_execution_results": security_controlled_execution_results,
        "security_controlled_execution_result_statuses": (
            security_controlled_execution_result_statuses
        ),
        "security_controlled_execution_result_reasons": (
            security_controlled_execution_result_reasons
        ),
        "security_controlled_execution_rejected": security_controlled_execution_rejected,
        "security_controlled_execution_skipped": security_controlled_execution_skipped,
        "security_controlled_execution_executed": security_controlled_execution_executed,
        "security_controlled_execution_not_implemented": (
            security_controlled_execution_not_implemented
        ),
        "security_controlled_command_parse_valid": (
            security_controlled_command_parse_valid
        ),
        "security_controlled_command_parse_allowlisted": (
            security_controlled_command_parse_allowlisted
        ),
        "security_controlled_command_parse_execution_performed": (
            security_controlled_command_parse_execution_performed
        ),
        "security_controlled_execution_operator_authorized": (
            security_controlled_execution_operator_authorized
        ),
        "security_controlled_execution_gate_blocked": (
            security_controlled_execution_gate_blocked
        ),
        "security_controlled_execution_gate_would_execute": (
            security_controlled_execution_gate_would_execute
        ),
        "security_controlled_execution_gate_would_execute_if_enabled": (
            security_controlled_execution_gate_would_execute_if_enabled
        ),
        "security_controlled_execution_gate_execution_performed": (
            security_controlled_execution_gate_execution_performed
        ),
        "security_controlled_execution_gate_not_enabled": (
            security_controlled_execution_gate_not_enabled
        ),
        "security_controlled_execution_gate_implementation_not_enabled": (
            security_controlled_execution_gate_implementation_not_enabled
        ),
        "security_controlled_mock_executed": security_controlled_mock_executed,
        "security_controlled_mock_performed": security_controlled_mock_performed,
        "security_controlled_mock_subprocess_invoked": (
            security_controlled_mock_subprocess_invoked
        ),
        "security_mock_summary_executed": security_mock_summary_executed,
        "security_mock_summary_performed": security_mock_summary_performed,
        "security_mock_summary_subprocess_invoked": (
            security_mock_summary_subprocess_invoked
        ),
        "security_mock_adapter": security_mock_adapter,
        "security_mock_adapter_mode": security_mock_adapter_mode,
        "security_mock_adapter_result_status": security_mock_adapter_result_status,
        "security_mock_adapter_subprocess_invoked": (
            security_mock_adapter_subprocess_invoked
        ),
        "security_mock_adapter_real_execution_enabled": (
            security_mock_adapter_real_execution_enabled
        ),
        "security_mock_adapter_payload_executed": (
            security_mock_adapter_payload_executed
        ),
        "security_real_adapter_supported": int(security_real_adapter_supported),
        "security_real_adapter_runnable": int(security_real_adapter_runnable),
        "security_real_adapter_subprocess_supported": int(
            security_real_adapter_subprocess_supported
        ),
        "security_real_adapter_requires_explicit_pr": int(
            security_real_adapter_requires_explicit_pr
        ),
        "security_controlled_real_execution_requested": (
            security_controlled_real_execution_requested
        ),
        "security_controlled_real_execution_performed": (
            security_controlled_real_execution_performed
        ),
        "security_controlled_real_execution_supported": (
            security_controlled_real_execution_supported
        ),
        "security_controlled_subprocess_invoked": (
            security_controlled_subprocess_invoked
        ),
        "security_real_preflight_blocked": security_real_preflight_blocked,
        "security_real_preflight_would_execute": (
            security_real_preflight_would_execute
        ),
        "security_real_preflight_execution_performed": (
            security_real_preflight_execution_performed
        ),
        "security_real_preflight_subprocess_invoked": (
            security_real_preflight_subprocess_invoked
        ),
        "security_real_preflight_requires_explicit_pr": (
            security_real_preflight_requires_explicit_pr
        ),
        "security_real_approval_records": security_real_approval_records,
        "security_real_approval_enabled": security_real_approval_enabled,
        "security_real_approval_subprocess_enabled": security_real_approval_subprocess_enabled,
        "security_real_approval_execution_performed": security_real_approval_execution_performed,
        "security_real_approval_subprocess_invoked": security_real_approval_subprocess_invoked,
        "security_read_only_feedback_records": security_read_only_feedback_records,
        "security_read_only_feedback_actionable": security_read_only_feedback_actionable,
        "security_read_only_feedback_source_failed": (
            security_read_only_feedback_source_failed
        ),
        "security_read_only_feedback_exit_code_1": (
            security_read_only_feedback_exit_code_1
        ),
        "security_read_only_feedback_next_action_investigate": (
            security_read_only_feedback_next_action_investigate
        ),
        "security_read_only_feedback_real_execution_enabled": (
            security_read_only_feedback_real_execution_enabled
        ),
        "security_read_only_feedback_execution_performed": (
            security_read_only_feedback_execution_performed
        ),
        "security_read_only_feedback_subprocess_invoked": (
            security_read_only_feedback_subprocess_invoked
        ),
        "security_read_only_feedback_feedback_execution_performed": (
            security_read_only_feedback_feedback_execution_performed
        ),
        "security_read_only_feedback_feedback_subprocess_invoked": (
            security_read_only_feedback_feedback_subprocess_invoked
        ),
    }

    summary = _build_summary(
        status=status,
        swarm_counts=swarm_counts,
        degraded_swarms=degraded_swarms,
        gold_candidates=gold_candidates,
        alert_candidates=alert_candidates,
        runtime_evidence_gold_candidates=runtime_evidence_gold_candidates,
        runtime_evidence_alert_candidates=runtime_evidence_alert_candidates,
        security_validation_critical_records=security_validation_critical_records,
        security_validation_invalid_records=security_validation_invalid_records,
        security_replay_lifecycle_results=security_replay_lifecycle_results,
        simulation_replay_pending=simulation_replay_pending,
        simulation_replay_failed=simulation_replay_failed,
        simulation_replay_execution_completed=simulation_replay_execution_completed,
        simulation_replay_execution_failed=simulation_replay_execution_failed,
        memory_replay_execution_evidence_passed=memory_replay_execution_evidence_passed,
        memory_replay_execution_evidence_failed=memory_replay_execution_evidence_failed,
        security_replay_lifecycle_timeouts=security_replay_lifecycle_timeouts,
        security_retry_proposals=security_retry_proposals,
        security_retry_approvals=security_retry_approvals,
        security_retry_manual_approvals=security_retry_manual_approvals,
        security_retry_policy_approvals=security_retry_policy_approvals,
        security_retry_execution_plans=security_retry_execution_plans,
        security_retry_execution_results=security_retry_execution_results,
        security_retry_execution_skipped=security_retry_execution_skipped,
        security_retry_execution_rejected=security_retry_execution_rejected,
        security_retry_rendered_commands=security_retry_rendered_commands,
        security_retry_rendered_standard_commands=security_retry_rendered_standard_commands,
        security_retry_rendered_patient_commands=security_retry_rendered_patient_commands,
        security_retry_rendered_command_results=security_retry_rendered_command_results,
        security_retry_rendered_command_skipped=security_retry_rendered_command_skipped,
        security_retry_rendered_command_rejected=security_retry_rendered_command_rejected,
        security_retry_execution_eligibilities=security_retry_execution_eligibilities,
        security_retry_execution_blocked=security_retry_execution_blocked,
        security_retry_execution_eligibility_reasons=security_retry_execution_eligibility_reasons,
        security_controlled_execution_results=security_controlled_execution_results,
        security_controlled_execution_rejected=security_controlled_execution_rejected,
        security_controlled_execution_skipped=security_controlled_execution_skipped,
        security_controlled_execution_executed=security_controlled_execution_executed,
        security_controlled_execution_not_implemented=(
            security_controlled_execution_not_implemented
        ),
        security_controlled_command_parse_valid=security_controlled_command_parse_valid,
        security_controlled_command_parse_allowlisted=(
            security_controlled_command_parse_allowlisted
        ),
        security_controlled_command_parse_execution_performed=(
            security_controlled_command_parse_execution_performed
        ),
        security_controlled_execution_operator_authorized=(
            security_controlled_execution_operator_authorized
        ),
        security_controlled_execution_gate_blocked=(
            security_controlled_execution_gate_blocked
        ),
        security_controlled_execution_gate_would_execute=(
            security_controlled_execution_gate_would_execute
        ),
        security_controlled_execution_gate_would_execute_if_enabled=(
            security_controlled_execution_gate_would_execute_if_enabled
        ),
        security_controlled_execution_gate_execution_performed=(
            security_controlled_execution_gate_execution_performed
        ),
        security_controlled_execution_gate_not_enabled=(
            security_controlled_execution_gate_not_enabled
        ),
        security_controlled_execution_gate_implementation_not_enabled=(
            security_controlled_execution_gate_implementation_not_enabled
        ),
        security_controlled_mock_executed=security_controlled_mock_executed,
        security_controlled_mock_performed=security_controlled_mock_performed,
        security_controlled_mock_subprocess_invoked=(
            security_controlled_mock_subprocess_invoked
        ),
        security_mock_summary_executed=security_mock_summary_executed,
        security_mock_summary_performed=security_mock_summary_performed,
        security_mock_summary_subprocess_invoked=(
            security_mock_summary_subprocess_invoked
        ),
        security_mock_adapter=security_mock_adapter,
        security_mock_adapter_mode=security_mock_adapter_mode,
        security_mock_adapter_result_status=security_mock_adapter_result_status,
        security_mock_adapter_subprocess_invoked=(
            security_mock_adapter_subprocess_invoked
        ),
        security_mock_adapter_real_execution_enabled=(
            security_mock_adapter_real_execution_enabled
        ),
        security_mock_adapter_payload_executed=security_mock_adapter_payload_executed,
        security_real_adapter_supported=security_real_adapter_supported,
        security_real_adapter_runnable=security_real_adapter_runnable,
        security_real_adapter_subprocess_supported=(
            security_real_adapter_subprocess_supported
        ),
        security_real_adapter_requires_explicit_pr=(
            security_real_adapter_requires_explicit_pr
        ),
        security_controlled_real_execution_requested=(
            security_controlled_real_execution_requested
        ),
        security_controlled_real_execution_performed=(
            security_controlled_real_execution_performed
        ),
        security_controlled_real_execution_supported=(
            security_controlled_real_execution_supported
        ),
        security_controlled_subprocess_invoked=(
            security_controlled_subprocess_invoked
        ),
        security_real_preflight_blocked=security_real_preflight_blocked,
        security_real_preflight_would_execute=(
            security_real_preflight_would_execute
        ),
        security_real_preflight_execution_performed=(
            security_real_preflight_execution_performed
        ),
        security_real_preflight_subprocess_invoked=(
            security_real_preflight_subprocess_invoked
        ),
        security_real_preflight_requires_explicit_pr=(
            security_real_preflight_requires_explicit_pr
        ),
        security_real_approval_records=security_real_approval_records,
        security_real_approval_enabled=security_real_approval_enabled,
        security_real_approval_subprocess_enabled=(
            security_real_approval_subprocess_enabled
        ),
        security_real_approval_execution_performed=(
            security_real_approval_execution_performed
        ),
        security_real_approval_subprocess_invoked=(
            security_real_approval_subprocess_invoked
        ),
        security_read_only_feedback_records=security_read_only_feedback_records,
        security_read_only_feedback_actionable=(
            security_read_only_feedback_actionable
        ),
        security_read_only_feedback_source_failed=(
            security_read_only_feedback_source_failed
        ),
        security_read_only_feedback_exit_code_1=(
            security_read_only_feedback_exit_code_1
        ),
        security_read_only_feedback_next_action_investigate=(
            security_read_only_feedback_next_action_investigate
        ),
        security_read_only_feedback_real_execution_enabled=(
            security_read_only_feedback_real_execution_enabled
        ),
        security_read_only_feedback_execution_performed=(
            security_read_only_feedback_execution_performed
        ),
        security_read_only_feedback_subprocess_invoked=(
            security_read_only_feedback_subprocess_invoked
        ),
        security_read_only_feedback_feedback_execution_performed=(
            security_read_only_feedback_feedback_execution_performed
        ),
        security_read_only_feedback_feedback_subprocess_invoked=(
            security_read_only_feedback_feedback_subprocess_invoked
        ),
    )

    return build_swarm_brief(
        scope=BriefScope.GLOBAL.value,
        status=status,
        summary=summary,
        swarm="overseer",
        key_metrics=key_metrics,
        risks=risks,
        opportunities=opportunities,
        recommended_actions=recommended_actions,
        evidence_ids=evidence_ids or [],
    )


def _global_status(
    *,
    degraded_swarms: list[str],
    alert_candidates: int,
    runtime_evidence_alert_candidates: int,
    security_validation_critical_records: int,
    memory_status: str,
) -> str:
    if security_validation_critical_records > 0:
        return BriefStatus.CRITICAL.value

    if degraded_swarms or alert_candidates > 0 or runtime_evidence_alert_candidates > 0:
        return BriefStatus.DEGRADED.value

    return BriefStatus.HEALTHY.value


def _build_summary(
    *,
    status: str,
    swarm_counts: Mapping[str, Any],
    degraded_swarms: list[str],
    gold_candidates: int,
    alert_candidates: int,
    runtime_evidence_gold_candidates: int,
    runtime_evidence_alert_candidates: int,
    security_validation_critical_records: int,
    security_validation_invalid_records: int,
    simulation_replay_pending: int,
    simulation_replay_failed: int,
    simulation_replay_execution_completed: int,
    simulation_replay_execution_failed: int,
    memory_replay_execution_evidence_passed: int,
    memory_replay_execution_evidence_failed: int,
    security_replay_lifecycle_results: int,
    security_replay_lifecycle_timeouts: int,
    security_retry_proposals: int,
    security_retry_approvals: int,
    security_retry_manual_approvals: int,
    security_retry_policy_approvals: int,
    security_retry_execution_plans: int,
    security_retry_execution_results: int,
    security_retry_execution_skipped: int,
    security_retry_execution_rejected: int,
    security_retry_rendered_commands: int,
    security_retry_rendered_standard_commands: int,
    security_retry_rendered_patient_commands: int,
    security_retry_rendered_command_results: int,
    security_retry_rendered_command_skipped: int,
    security_retry_rendered_command_rejected: int,
    security_retry_execution_eligibilities: int,
    security_retry_execution_blocked: int,
    security_retry_execution_eligibility_reasons: Mapping[str, Any],
    security_controlled_execution_results: int,
    security_controlled_execution_rejected: int,
    security_controlled_execution_skipped: int,
    security_controlled_execution_executed: int,
    security_controlled_execution_not_implemented: int,
    security_controlled_command_parse_valid: int,
    security_controlled_command_parse_allowlisted: int,
    security_controlled_command_parse_execution_performed: int,
    security_controlled_execution_operator_authorized: int,
    security_controlled_execution_gate_blocked: int,
    security_controlled_execution_gate_would_execute: int,
    security_controlled_execution_gate_would_execute_if_enabled: int,
    security_controlled_execution_gate_execution_performed: int,
    security_controlled_execution_gate_not_enabled: int,
    security_controlled_execution_gate_implementation_not_enabled: int,
    security_controlled_mock_executed: int,
    security_controlled_mock_performed: int,
    security_controlled_mock_subprocess_invoked: int,
    security_mock_summary_executed: int,
    security_mock_summary_performed: int,
    security_mock_summary_subprocess_invoked: int,
    security_mock_adapter: int,
    security_mock_adapter_mode: int,
    security_mock_adapter_result_status: int,
    security_mock_adapter_subprocess_invoked: int,
    security_mock_adapter_real_execution_enabled: int,
    security_mock_adapter_payload_executed: int,
    security_real_adapter_supported: bool,
    security_real_adapter_runnable: bool,
    security_real_adapter_subprocess_supported: bool,
    security_real_adapter_requires_explicit_pr: bool,
    security_controlled_real_execution_requested: int,
    security_controlled_real_execution_performed: int,
    security_controlled_real_execution_supported: int,
    security_controlled_subprocess_invoked: int,
    security_real_preflight_blocked: int,
    security_real_preflight_would_execute: int,
    security_real_preflight_execution_performed: int,
    security_real_preflight_subprocess_invoked: int,
    security_real_preflight_requires_explicit_pr: int,
    security_real_approval_records: int,
    security_real_approval_enabled: int,
    security_real_approval_subprocess_enabled: int,
    security_real_approval_execution_performed: int,
    security_real_approval_subprocess_invoked: int,
    security_read_only_feedback_records: int,
    security_read_only_feedback_actionable: int,
    security_read_only_feedback_source_failed: int,
    security_read_only_feedback_exit_code_1: int,
    security_read_only_feedback_next_action_investigate: int,
    security_read_only_feedback_real_execution_enabled: int,
    security_read_only_feedback_execution_performed: int,
    security_read_only_feedback_subprocess_invoked: int,
    security_read_only_feedback_feedback_execution_performed: int,
    security_read_only_feedback_feedback_subprocess_invoked: int,
) -> str:
    active = ", ".join(f"{name}={count}" for name, count in sorted(swarm_counts.items())) or "none"

    parts = [
        f"Global swarm status is {status}.",
        f"Active swarm counts: {active}.",
    ]

    if degraded_swarms:
        parts.append(f"Degraded swarms: {', '.join(degraded_swarms)}.")

    if gold_candidates > 0:
        parts.append(f"Memory has {gold_candidates} gold candidate(s).")

    if alert_candidates > 0:
        parts.append(f"Memory has {alert_candidates} alert candidate(s).")

    if runtime_evidence_gold_candidates > 0:
        parts.append(
            f"Memory has {runtime_evidence_gold_candidates} verified runtime evidence candidate(s)."
        )

    if runtime_evidence_alert_candidates > 0:
        parts.append(
            f"Memory has {runtime_evidence_alert_candidates} runtime evidence alert candidate(s)."
        )

    if security_validation_critical_records > 0:
        parts.append(
            f"Security has {security_validation_critical_records} critical validation failure(s)."
        )
    elif security_validation_invalid_records > 0:
        parts.append(
            f"Security has {security_validation_invalid_records} validation warning(s)."
        )

    if security_replay_lifecycle_results > 0:
        parts.append(
            f"Security validated {security_replay_lifecycle_results} replay evidence lifecycle result record(s)."
        )

    if security_replay_lifecycle_timeouts > 0:
        parts.append(
            f"Security observed {security_replay_lifecycle_timeouts} replay lifecycle timeout warning(s)."
        )

    if security_retry_proposals > 0:
        parts.append(
            f"Security validated {security_retry_proposals} pending replay lifecycle retry proposal record(s)."
        )

    if security_retry_approvals > 0:
        parts.append(
            f"Security validated {security_retry_approvals} replay lifecycle retry approval record(s)."
        )

    if security_retry_manual_approvals > 0 or security_retry_policy_approvals > 0:
        parts.append(
            "Security observed replay retry approval decision modes: "
            f"manual={security_retry_manual_approvals}, "
            f"policy={security_retry_policy_approvals}."
        )

    if security_retry_execution_plans > 0:
        parts.append(
            f"Security validated {security_retry_execution_plans} replay lifecycle retry execution plan record(s)."
        )

    if security_retry_execution_results > 0:
        parts.append(
           f"Security validated {security_retry_execution_results} replay lifecycle retry execution result record(s)."
        )

    if security_retry_execution_skipped > 0 or security_retry_execution_rejected > 0:
        parts.append(
            "Security observed replay retry execution result statuses: "
            f"skipped={security_retry_execution_skipped}, "
            f"rejected={security_retry_execution_rejected}."
        )

    if security_retry_rendered_commands > 0:
        parts.append(
            f"Security validated {security_retry_rendered_commands} replay lifecycle retry rendered command record(s)."
        )

    if security_retry_rendered_standard_commands > 0 or security_retry_rendered_patient_commands > 0:
        parts.append(
            "Security observed replay retry rendered command profiles: "
           f"standard={security_retry_rendered_standard_commands}, "
           f"patient={security_retry_rendered_patient_commands}."
        )

    if security_retry_rendered_command_results > 0:
        parts.append(
            f"Security validated {security_retry_rendered_command_results} "
            "replay lifecycle retry rendered command result record(s)."
        )

    if security_retry_rendered_command_skipped > 0 or security_retry_rendered_command_rejected > 0:
        parts.append(
           "Security observed replay retry rendered command result statuses: "
            f"skipped={security_retry_rendered_command_skipped}, "
            f"rejected={security_retry_rendered_command_rejected}."
        )

    if security_retry_execution_eligibilities > 0:
        parts.append(
            f"Security validated {security_retry_execution_eligibilities} "
            "retry execution eligibility record(s)."
        )

    if security_retry_execution_blocked > 0:
        parts.append(
            "Security observed retry execution eligibility statuses: "
            f"blocked={security_retry_execution_blocked}."
        )

    if security_controlled_command_parse_valid > 0:
        parts.append(
            "Controlled retry command parser recognized "
            f"{security_controlled_command_parse_allowlisted} allowlisted command(s). "
            "No controlled command execution was performed."
        )

    if security_controlled_command_parse_execution_performed > 0:
        parts.append(
            "Controlled retry command parser reported execution_performed="
            f"{security_controlled_command_parse_execution_performed}."
        )

    if security_controlled_execution_operator_authorized > 0:
        parts.append(
            "Controlled retry execution operator authorization intent observed: "
            f"operator_authorized={security_controlled_execution_operator_authorized}. "
            "No controlled command execution was performed."
        )

    if security_controlled_execution_gate_blocked > 0:
        parts.append(
            "Controlled retry execution gate is blocked: "
            f"controlled_execution_not_enabled="
            f"{security_controlled_execution_gate_not_enabled}, "
            "controlled_execution_implementation_not_enabled="
            f"{security_controlled_execution_gate_implementation_not_enabled}."
        )

    if (
        security_controlled_execution_gate_would_execute > 0
        or security_controlled_execution_gate_execution_performed > 0
    ):
        parts.append(
            "Controlled execution gate reported: "
            f"would_execute={security_controlled_execution_gate_would_execute}, "
            f"execution_performed="
            f"{security_controlled_execution_gate_execution_performed}."
        )

    if security_controlled_mock_executed > 0 or security_controlled_mock_performed > 0:
        parts.append(
            "Controlled mock execution observed: "
            f"mock_executed={security_controlled_mock_executed}, "
            f"mock_performed={security_controlled_mock_performed}, "
            f"subprocess_invoked={security_controlled_mock_subprocess_invoked}. "
            "Real execution remains disabled."
        )
    
    if security_mock_summary_executed > 0 or security_mock_summary_performed > 0:
        parts.append(
            "Controlled mock execution summary observed: "
            f"mock_executed={security_mock_summary_executed}, "
            f"mock_performed={security_mock_summary_performed}, "
            f"subprocess_invoked={security_mock_summary_subprocess_invoked}."
        )

    if security_mock_adapter > 0 or security_mock_adapter_result_status > 0:
        parts.append(
            "Controlled mock adapter contract observed: "
            f"adapter=mock:{security_mock_adapter}, "
            f"mode=mock:{security_mock_adapter_mode}, "
            f"mock_executed={security_mock_adapter_result_status}, "
            f"subprocess_invoked={security_mock_adapter_subprocess_invoked}, "
            f"real_execution_enabled={security_mock_adapter_real_execution_enabled}, "
            f"payload_executed={security_mock_adapter_payload_executed}."
        )

    if security_real_adapter_requires_explicit_pr or (
        not security_real_adapter_supported and not security_real_adapter_runnable
    ):
        parts.append(
            "Real controlled retry adapter is unsupported/non-runnable: "
            f"real_adapter_supported={str(security_real_adapter_supported).lower()}, "
            f"real_adapter_runnable={str(security_real_adapter_runnable).lower()}, "
            "subprocess_supported="
            f"{str(security_real_adapter_subprocess_supported).lower()}, "
            "requires_explicit_pr="
            f"{str(security_real_adapter_requires_explicit_pr).lower()}."
        )
    
    if security_controlled_real_execution_requested > 0:
        parts.append(
            "Real controlled retry execution request observed and rejected: "
            f"requested={security_controlled_real_execution_requested}, "
            f"performed={security_controlled_real_execution_performed}, "
            f"supported={security_controlled_real_execution_supported}, "
            f"subprocess_invoked={security_controlled_subprocess_invoked}."
        )
    
    if security_real_preflight_blocked > 0:
        parts.append(
            "Real execution preflight remains blocked: "
            f"blocked={security_real_preflight_blocked}, "
            f"would_execute={security_real_preflight_would_execute}, "
            f"execution_performed={security_real_preflight_execution_performed}, "
            f"subprocess_invoked={security_real_preflight_subprocess_invoked}, "
            f"requires_explicit_pr={security_real_preflight_requires_explicit_pr}."
        )
    
    if security_real_approval_records > 0:
        parts.append(
            "Explicit real execution approval observed: "
            f"records={security_real_approval_records}, "
            f"real_execution_enabled={security_real_approval_enabled}, "
            f"subprocess_enabled={security_real_approval_subprocess_enabled}, "
            f"execution_performed={security_real_approval_execution_performed}, "
            f"subprocess_invoked={security_real_approval_subprocess_invoked}."
        )

    if security_read_only_feedback_records > 0:
        parts.append(
            "Read-only execution feedback observed: "
            f"records={security_read_only_feedback_records}, "
            f"actionable={security_read_only_feedback_actionable}, "
            f"source_failed={security_read_only_feedback_source_failed}, "
            f"exit_code_1={security_read_only_feedback_exit_code_1}, "
            "next_action=investigate_failed_read_only_evidence_check, "
            f"next_action_count={security_read_only_feedback_next_action_investigate}, "
            f"real_execution_enabled={security_read_only_feedback_real_execution_enabled}, "
            f"execution_performed={security_read_only_feedback_execution_performed}, "
            f"subprocess_invoked={security_read_only_feedback_subprocess_invoked}, "
            f"feedback_execution_performed={security_read_only_feedback_feedback_execution_performed}, "
            f"feedback_subprocess_invoked={security_read_only_feedback_feedback_subprocess_invoked}."
        )

    blocked_execution_disabled = _safe_int(
        security_retry_execution_eligibility_reasons.get("execution_disabled"),
        0,
    )
    blocked_execution_not_supported = _safe_int(
        security_retry_execution_eligibility_reasons.get("execution_not_supported"),
        0,
    )
    blocked_missing_result = _safe_int(
        security_retry_execution_eligibility_reasons.get("missing_rendered_command_result"),
        0,
    )
    blocked_missing_command = _safe_int(
        security_retry_execution_eligibility_reasons.get("missing_rendered_command"),
        0,
    )

    if (
        blocked_execution_disabled > 0
        or blocked_execution_not_supported > 0
        or blocked_missing_result > 0
        or blocked_missing_command > 0
    ):
        parts.append(
            "Execution remains blocked: "
            f"execution_disabled={blocked_execution_disabled}, "
            f"execution_not_supported={blocked_execution_not_supported}, "
            f"missing_rendered_command_result={blocked_missing_result}, "
            f"missing_rendered_command={blocked_missing_command}."
        )

    if security_controlled_execution_results > 0:
        parts.append(
            f"Security validated {security_controlled_execution_results} "
            "controlled retry execution result record(s)."
        )

    if (
        security_controlled_execution_rejected > 0
        or security_controlled_execution_skipped > 0
        or security_controlled_execution_executed > 0
    ):
        parts.append(
            "Controlled retry execution results: "
            f"rejected={security_controlled_execution_rejected}, "
            f"skipped={security_controlled_execution_skipped}, "
            f"executed={security_controlled_execution_executed}."
        )

    if security_controlled_execution_not_implemented > 0:
        parts.append(
            "Controlled retry execution remains disabled/not implemented: "
            f"controlled_execution_not_implemented="
            f"{security_controlled_execution_not_implemented}."
        )

    if simulation_replay_pending > 0:
        parts.append(
            f"Simulation has {simulation_replay_pending} pending replay scenario(s)."
        )

    if simulation_replay_failed > 0:
        parts.append(
            f"Simulation has {simulation_replay_failed} failed replay scenario(s)."
        )

    if simulation_replay_execution_completed > 0:
        parts.append(
            f"Simulation completed {simulation_replay_execution_completed} replay dry-run execution(s)."
        )

    if simulation_replay_execution_failed > 0:
        parts.append(
            f"Simulation has {simulation_replay_execution_failed} failed replay dry-run execution(s)."
        )

    if memory_replay_execution_evidence_passed > 0:
        parts.append(
            f"Memory captured {memory_replay_execution_evidence_passed} passed replay execution evidence record(s)."
        )

    if memory_replay_execution_evidence_failed > 0:
        parts.append(
            f"Memory has {memory_replay_execution_evidence_failed} failed replay execution evidence record(s)."
        )

    return " ".join(parts)


def _degraded_swarms(topology_health: Mapping[str, Any]) -> list[str]:
    degraded: list[str] = []

    for swarm_name, value in topology_health.items():
        status = ""
        if isinstance(value, Mapping):
            status = str(value.get("status") or value.get("health") or "").lower()
        else:
            status = str(value or "").lower()

        if status in {"degraded", "critical", "failed", "unknown"}:
            degraded.append(str(swarm_name))

    return sorted(degraded)


def _snapshot_mapping_value(snapshot: Any, key: str) -> Mapping[str, Any]:
    if isinstance(snapshot, Mapping):
        value = snapshot.get(key)
    else:
        value = getattr(snapshot, key, None)
    return value if isinstance(value, Mapping) else {}


def _extract_security_validation(snapshot: Any) -> dict[str, Any]:
    explicit = _snapshot_mapping_value(snapshot, "security_validation")
    if explicit:
        return dict(explicit)

    heartbeats = _security_heartbeats_from_snapshot(snapshot)
    if not heartbeats:
        return {}

    return _aggregate_security_validation_from_heartbeats(heartbeats)


def _extract_simulation_replay(snapshot: Any) -> dict[str, Any]:
    explicit = _snapshot_mapping_value(snapshot, "simulation_replay")
    if explicit:
        return dict(explicit)

    heartbeats = _simulation_heartbeats_from_snapshot(snapshot)
    if not heartbeats:
        return {}

    return _aggregate_simulation_replay_from_heartbeats(heartbeats)


def _simulation_heartbeats_from_snapshot(snapshot: Any) -> list[Mapping[str, Any]]:
    groups: list[Any] = []

    recent = _snapshot_mapping_value(snapshot, "recent_heartbeats_by_swarm")
    latest = _snapshot_mapping_value(snapshot, "latest_swarm_heartbeats")

    groups.append(recent.get("simulation", []))
    groups.append(latest.get("simulation", []))
    groups.extend(recent.values())
    groups.extend(latest.values())

    heartbeats: list[Mapping[str, Any]] = []
    seen: set[int] = set()

    for group in groups:
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, Mapping):
                continue
            if id(item) in seen:
                continue
            seen.add(id(item))

            swarm = str(item.get("swarm") or "")
            item_type = str(item.get("type") or "")
            if swarm == "simulation" or item_type in {"simulation_heartbeat", "swarm_heartbeat"}:
                metrics = item.get("metrics")
                if isinstance(metrics, Mapping) and any(
                    str(key).startswith("simulation_replay") for key in metrics
                ):
                    heartbeats.append(item)

    return heartbeats


def _aggregate_simulation_replay_from_heartbeats(
    heartbeats: list[Mapping[str, Any]],
) -> dict[str, Any]:
    aggregate = {
        "simulation_replay_scenarios": 0,
        "simulation_replay_pending": 0,
        "simulation_replay_completed": 0,
        "simulation_replay_failed": 0,
        "simulation_replay_executions": 0,
        "simulation_replay_execution_completed": 0,
        "simulation_replay_execution_failed": 0,
    }

    status_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    execution_status_counts: dict[str, int] = {}

    for heartbeat in heartbeats:
        metrics = heartbeat.get("metrics")
        if not isinstance(metrics, Mapping):
            continue

        aggregate["simulation_replay_scenarios"] += _safe_int(metrics.get("simulation_replay_scenarios"), 0)
        aggregate["simulation_replay_pending"] += _safe_int(metrics.get("simulation_replay_pending"), 0)
        aggregate["simulation_replay_completed"] += _safe_int(metrics.get("simulation_replay_completed"), 0)
        aggregate["simulation_replay_failed"] += _safe_int(metrics.get("simulation_replay_failed"), 0)
        aggregate["simulation_replay_executions"] += _safe_int(
            metrics.get("simulation_replay_executions"),
            0,
        )
        aggregate["simulation_replay_execution_completed"] += _safe_int(
            metrics.get("simulation_replay_execution_completed"),
            0,
        )
        aggregate["simulation_replay_execution_failed"] += _safe_int(
            metrics.get("simulation_replay_execution_failed"),
            0,
        )

        _merge_int_counts(status_counts, metrics.get("simulation_replay_status_counts"))
        _merge_int_counts(kind_counts, metrics.get("simulation_replay_kind_counts"))
        _merge_int_counts(action_counts, metrics.get("simulation_replay_action_counts"))
        _merge_int_counts(
            execution_status_counts,
            metrics.get("simulation_replay_execution_status_counts"),
        )

    aggregate["simulation_replay_status_counts"] = status_counts
    aggregate["simulation_replay_kind_counts"] = kind_counts
    aggregate["simulation_replay_action_counts"] = action_counts
    aggregate["simulation_replay_execution_status_counts"] = execution_status_counts

    return aggregate


def _security_heartbeats_from_snapshot(snapshot: Any) -> list[Mapping[str, Any]]:
    groups: list[Any] = []

    recent = _snapshot_mapping_value(snapshot, "recent_heartbeats_by_swarm")
    latest = _snapshot_mapping_value(snapshot, "latest_swarm_heartbeats")

    groups.append(recent.get("security", []))
    groups.append(latest.get("security", []))

    # Some legacy records may use the direct security_heartbeat type and may be
    # grouped under non-security keys.
    groups.extend(recent.values())
    groups.extend(latest.values())

    heartbeats: list[Mapping[str, Any]] = []
    seen: set[int] = set()

    for group in groups:
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, Mapping):
                continue
            if id(item) in seen:
                continue
            seen.add(id(item))

            item_type = str(item.get("type") or "")
            swarm = str(item.get("swarm") or "")
            if swarm == "security" or item_type in {"security_heartbeat", "swarm_heartbeat"}:
                metrics = item.get("metrics")
                if isinstance(metrics, Mapping) and any(
                    str(key).startswith("security_validation") for key in metrics
                ):
                    heartbeats.append(item)

    return heartbeats


def _aggregate_security_validation_from_heartbeats(
    heartbeats: list[Mapping[str, Any]],
) -> dict[str, Any]:
    aggregate = {
        "security_validation_records": 0,
        "security_validation_valid_records": 0,
        "security_validation_invalid_records": 0,
        "security_validation_critical_records": 0,
    }

    invalid_reasons: dict[str, int] = {}
    warning_reasons: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    record_type_counts: dict[str, int] = {}
    retry_approval_decision_modes: dict[str, int] = {}
    retry_execution_result_statuses: dict[str, int] = {}
    retry_execution_result_reasons: dict[str, int] = {}
    retry_rendered_command_profiles: dict[str, int] = {}
    retry_rendered_command_decision_modes: dict[str, int] = {}
    retry_rendered_command_result_statuses: dict[str, int] = {}
    retry_rendered_command_result_reasons: dict[str, int] = {}
    retry_execution_eligibility_statuses: dict[str, int] = {}
    retry_execution_eligibility_reasons: dict[str, int] = {}
    controlled_execution_result_statuses: dict[str, int] = {}
    controlled_execution_result_reasons: dict[str, int] = {}
    controlled_execution_operator_authorized: dict[str, int] = {}
    controlled_execution_allowlist_matched: dict[str, int] = {}
    controlled_execution_command_parse_valid: dict[str, int] = {}
    controlled_execution_command_parse_allowlist_matched: dict[str, int] = {}
    controlled_execution_command_parse_execution_performed: dict[str, int] = {}
    controlled_execution_gate_statuses: dict[str, int] = {}
    controlled_execution_gate_would_execute: dict[str, int] = {}
    controlled_execution_gate_would_execute_if_enabled: dict[str, int] = {}
    controlled_execution_gate_execution_performed: dict[str, int] = {}
    controlled_execution_gate_reasons: dict[str, int] = {}
    controlled_execution_mock_statuses: dict[str, int] = {}
    controlled_execution_mock_performed: dict[str, int] = {}
    controlled_execution_mock_subprocess_invoked: dict[str, int] = {}
    mock_summary_statuses: dict[str, int] = {}
    mock_summary_performed: dict[str, int] = {}
    mock_summary_subprocess_invoked: dict[str, int] = {}
    controlled_execution_mock_adapter: dict[str, int] = {}
    controlled_execution_mock_adapter_mode: dict[str, int] = {}
    controlled_execution_mock_adapter_result_statuses: dict[str, int] = {}
    controlled_execution_mock_adapter_subprocess_invoked: dict[str, int] = {}
    controlled_execution_mock_adapter_real_execution_enabled: dict[str, int] = {}
    controlled_execution_mock_adapter_payload_executed: dict[str, int] = {}
    controlled_execution_real_requested: dict[str, int] = {}
    controlled_execution_real_performed: dict[str, int] = {}
    controlled_execution_real_supported: dict[str, int] = {}
    controlled_execution_subprocess_invoked: dict[str, int] = {}
    real_preflight_statuses: dict[str, int] = {}
    real_preflight_would_execute: dict[str, int] = {}
    real_preflight_execution_performed: dict[str, int] = {}
    real_preflight_subprocess_invoked: dict[str, int] = {}
    real_preflight_requires_explicit_pr: dict[str, int] = {}

    for heartbeat in heartbeats:
        metrics = heartbeat.get("metrics")
        if not isinstance(metrics, Mapping):
            continue

        aggregate["security_validation_records"] += _safe_int(metrics.get("security_validation_records"), 0)
        aggregate["security_validation_valid_records"] += _safe_int(metrics.get("security_validation_valid_records"), 0)
        aggregate["security_validation_invalid_records"] += _safe_int(metrics.get("security_validation_invalid_records"), 0)
        aggregate["security_validation_critical_records"] += _safe_int(metrics.get("security_validation_critical_records"), 0)

        _merge_int_counts(invalid_reasons, metrics.get("security_validation_invalid_reasons"))
        _merge_int_counts(warning_reasons, metrics.get("security_validation_warning_reasons"))
        _merge_int_counts(severity_counts, metrics.get("security_validation_severity_counts"))
        _merge_int_counts(record_type_counts, metrics.get("security_validation_record_type_counts"))
        _merge_int_counts(
            retry_approval_decision_modes,
            metrics.get("security_validation_retry_approval_decision_modes"),
        )
        _merge_int_counts(
            retry_execution_result_statuses,
            metrics.get("security_validation_retry_execution_result_statuses"),
        )
        _merge_int_counts(
            retry_execution_result_reasons,
            metrics.get("security_validation_retry_execution_result_reasons"),
        )
        _merge_int_counts(
            retry_rendered_command_profiles,
            metrics.get("security_validation_retry_rendered_command_profiles"),
        )
        _merge_int_counts(
            retry_rendered_command_decision_modes,
            metrics.get("security_validation_retry_rendered_command_decision_modes"),
        )
        _merge_int_counts(
            retry_rendered_command_result_statuses,
            metrics.get("security_validation_retry_rendered_command_result_statuses"),
        )
        _merge_int_counts(
            retry_rendered_command_result_reasons,
            metrics.get("security_validation_retry_rendered_command_result_reasons"),
        )
        _merge_int_counts(
            retry_execution_eligibility_statuses,
            metrics.get("security_validation_retry_execution_eligibility_statuses"),
        )
        _merge_int_counts(
            retry_execution_eligibility_reasons,
            metrics.get("security_validation_retry_execution_eligibility_reasons"),
        )
        _merge_int_counts(
            controlled_execution_result_statuses,
            metrics.get("security_validation_controlled_execution_result_statuses"),
        )
        _merge_int_counts(
            controlled_execution_result_reasons,
            metrics.get("security_validation_controlled_execution_result_reasons"),
        )
        _merge_int_counts(
            controlled_execution_operator_authorized,
            metrics.get("security_validation_controlled_execution_operator_authorized"),
        )
        _merge_int_counts(
            controlled_execution_allowlist_matched,
            metrics.get("security_validation_controlled_execution_allowlist_matched"),
        )
        _merge_int_counts(
            controlled_execution_command_parse_valid,
            metrics.get("security_validation_controlled_execution_command_parse_valid"),
        )
        _merge_int_counts(
            controlled_execution_command_parse_allowlist_matched,
            metrics.get(
                "security_validation_controlled_execution_command_parse_allowlist_matched"
            ),
        )
        _merge_int_counts(
            controlled_execution_command_parse_execution_performed,
            metrics.get(
                "security_validation_controlled_execution_command_parse_execution_performed"
            ),
        )
        _merge_int_counts(
            controlled_execution_gate_statuses,
            metrics.get("security_validation_controlled_execution_gate_statuses"),
        )
        _merge_int_counts(
            controlled_execution_gate_would_execute,
            metrics.get("security_validation_controlled_execution_gate_would_execute"),
        )
        _merge_int_counts(
            controlled_execution_gate_would_execute_if_enabled,
            metrics.get(
                "security_validation_controlled_execution_gate_would_execute_if_enabled"
            ),
        )
        _merge_int_counts(
            controlled_execution_gate_execution_performed,
            metrics.get(
                "security_validation_controlled_execution_gate_execution_performed"
            ),
        )
        _merge_int_counts(
            controlled_execution_gate_reasons,
            metrics.get("security_validation_controlled_execution_gate_reasons"),
        )
        _merge_int_counts(
            controlled_execution_mock_statuses,
            metrics.get("security_validation_controlled_execution_mock_statuses"),
        )
        _merge_int_counts(
            controlled_execution_mock_performed,
            metrics.get("security_validation_controlled_execution_mock_performed"),
        )
        _merge_int_counts(
            controlled_execution_mock_subprocess_invoked,
            metrics.get(
                "security_validation_controlled_execution_mock_subprocess_invoked"
            ),
        )
        _merge_int_counts(
            mock_summary_statuses,
            metrics.get("security_validation_mock_summary_statuses"),
        )
        _merge_int_counts(
            mock_summary_performed,
            metrics.get("security_validation_mock_summary_performed"),
        )
        _merge_int_counts(
            mock_summary_subprocess_invoked,
            metrics.get("security_validation_mock_summary_subprocess_invoked"),
        )
        _merge_int_counts(
            controlled_execution_mock_adapter,
            metrics.get("security_validation_controlled_execution_mock_adapter"),
        )
        _merge_int_counts(
            controlled_execution_mock_adapter_mode,
            metrics.get("security_validation_controlled_execution_mock_adapter_mode"),
        )
        _merge_int_counts(
            controlled_execution_mock_adapter_result_statuses,
            metrics.get(
                "security_validation_controlled_execution_mock_adapter_result_statuses"
            ),
        )
        _merge_int_counts(
            controlled_execution_mock_adapter_subprocess_invoked,
            metrics.get(
                "security_validation_controlled_execution_mock_adapter_subprocess_invoked"
            ),
        )
        _merge_int_counts(
            controlled_execution_mock_adapter_real_execution_enabled,
            metrics.get(
                "security_validation_controlled_execution_mock_adapter_real_execution_enabled"
            ),
        )
        _merge_int_counts(
            controlled_execution_mock_adapter_payload_executed,
            metrics.get(
                "security_validation_controlled_execution_mock_adapter_payload_executed"
            ),
        )
        _merge_int_counts(
            controlled_execution_real_requested,
            metrics.get("security_validation_controlled_execution_real_requested"),
        )
        _merge_int_counts(
            controlled_execution_real_performed,
            metrics.get("security_validation_controlled_execution_real_performed"),
        )
        _merge_int_counts(
            controlled_execution_real_supported,
            metrics.get("security_validation_controlled_execution_real_supported"),
        )
        _merge_int_counts(
            controlled_execution_subprocess_invoked,
            metrics.get("security_validation_controlled_execution_subprocess_invoked"),
        )
        _merge_int_counts(
            real_preflight_statuses,
            metrics.get("security_validation_real_preflight_statuses"),
        )
        _merge_int_counts(
            real_preflight_would_execute,
            metrics.get("security_validation_real_preflight_would_execute"),
        )
        _merge_int_counts(
            real_preflight_execution_performed,
            metrics.get("security_validation_real_preflight_execution_performed"),
        )
        _merge_int_counts(
            real_preflight_subprocess_invoked,
            metrics.get("security_validation_real_preflight_subprocess_invoked"),
        )
        _merge_int_counts(
            real_preflight_requires_explicit_pr,
            metrics.get("security_validation_real_preflight_requires_explicit_pr"),
        )

    aggregate["security_validation_invalid_reasons"] = invalid_reasons
    aggregate["security_validation_warning_reasons"] = warning_reasons
    aggregate["security_validation_severity_counts"] = severity_counts
    aggregate["security_validation_record_type_counts"] = record_type_counts
    aggregate["security_validation_retry_approval_decision_modes"] = retry_approval_decision_modes
    aggregate["security_validation_retry_execution_result_statuses"] = retry_execution_result_statuses
    aggregate["security_validation_retry_execution_result_reasons"] = retry_execution_result_reasons
    aggregate["security_validation_retry_rendered_command_profiles"] = retry_rendered_command_profiles
    aggregate["security_validation_retry_rendered_command_decision_modes"] = retry_rendered_command_decision_modes
    aggregate["security_validation_retry_rendered_command_result_statuses"] = (
        retry_rendered_command_result_statuses
    )
    aggregate["security_validation_retry_rendered_command_result_reasons"] = (
        retry_rendered_command_result_reasons
    )
    aggregate["security_validation_retry_execution_eligibility_statuses"] = (
        retry_execution_eligibility_statuses
    )
    aggregate["security_validation_retry_execution_eligibility_reasons"] = (
        retry_execution_eligibility_reasons
    )
    aggregate["security_validation_controlled_execution_result_statuses"] = (
        controlled_execution_result_statuses
    )
    aggregate["security_validation_controlled_execution_result_reasons"] = (
        controlled_execution_result_reasons
    )
    aggregate["security_validation_controlled_execution_operator_authorized"] = (
        controlled_execution_operator_authorized
    )
    aggregate["security_validation_controlled_execution_allowlist_matched"] = (
        controlled_execution_allowlist_matched
    )
    aggregate["security_validation_controlled_execution_command_parse_valid"] = (
        controlled_execution_command_parse_valid
    )
    aggregate[
        "security_validation_controlled_execution_command_parse_allowlist_matched"
    ] = controlled_execution_command_parse_allowlist_matched
    aggregate[
        "security_validation_controlled_execution_command_parse_execution_performed"
    ] = controlled_execution_command_parse_execution_performed
    aggregate["security_validation_controlled_execution_gate_statuses"] = (
        controlled_execution_gate_statuses
    )
    aggregate["security_validation_controlled_execution_gate_would_execute"] = (
        controlled_execution_gate_would_execute
    )
    aggregate[
        "security_validation_controlled_execution_gate_would_execute_if_enabled"
    ] = controlled_execution_gate_would_execute_if_enabled
    aggregate["security_validation_controlled_execution_gate_execution_performed"] = (
        controlled_execution_gate_execution_performed
    )
    aggregate["security_validation_controlled_execution_gate_reasons"] = (
        controlled_execution_gate_reasons
    )
    aggregate["security_validation_controlled_execution_mock_statuses"] = (
        controlled_execution_mock_statuses
    )
    aggregate["security_validation_controlled_execution_mock_performed"] = (
        controlled_execution_mock_performed
    )
    aggregate["security_validation_controlled_execution_mock_subprocess_invoked"] = (
        controlled_execution_mock_subprocess_invoked
    )
    aggregate["security_validation_mock_summary_statuses"] = mock_summary_statuses
    aggregate["security_validation_mock_summary_performed"] = mock_summary_performed
    aggregate["security_validation_mock_summary_subprocess_invoked"] = (
        mock_summary_subprocess_invoked
    )
    aggregate["security_validation_controlled_execution_mock_adapter"] = (
        controlled_execution_mock_adapter
    )
    aggregate["security_validation_controlled_execution_mock_adapter_mode"] = (
        controlled_execution_mock_adapter_mode
    )
    aggregate[
        "security_validation_controlled_execution_mock_adapter_result_statuses"
    ] = controlled_execution_mock_adapter_result_statuses
    aggregate[
        "security_validation_controlled_execution_mock_adapter_subprocess_invoked"
    ] = controlled_execution_mock_adapter_subprocess_invoked
    aggregate[
        "security_validation_controlled_execution_mock_adapter_real_execution_enabled"
    ] = controlled_execution_mock_adapter_real_execution_enabled
    aggregate[
        "security_validation_controlled_execution_mock_adapter_payload_executed"
    ] = controlled_execution_mock_adapter_payload_executed
    aggregate["security_validation_controlled_execution_real_requested"] = (
        controlled_execution_real_requested
    )
    aggregate["security_validation_controlled_execution_real_performed"] = (
        controlled_execution_real_performed
    )
    aggregate["security_validation_controlled_execution_real_supported"] = (
        controlled_execution_real_supported
    )
    aggregate["security_validation_controlled_execution_subprocess_invoked"] = (
        controlled_execution_subprocess_invoked
    )
    aggregate["security_validation_real_preflight_statuses"] = (
        real_preflight_statuses
    )
    aggregate["security_validation_real_preflight_would_execute"] = (
        real_preflight_would_execute
    )
    aggregate["security_validation_real_preflight_execution_performed"] = (
        real_preflight_execution_performed
    )
    aggregate["security_validation_real_preflight_subprocess_invoked"] = (
        real_preflight_subprocess_invoked
    )
    aggregate["security_validation_real_preflight_requires_explicit_pr"] = (
        real_preflight_requires_explicit_pr
    )

    return aggregate


def _merge_int_counts(target: dict[str, int], value: Any) -> None:
    if not isinstance(value, Mapping):
        return

    for key, count in value.items():
        clean_key = str(key or "").strip()
        if not clean_key:
            continue
        target[clean_key] = target.get(clean_key, 0) + _safe_int(count, 0)


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = ["build_global_swarm_brief"]