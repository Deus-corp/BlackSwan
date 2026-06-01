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
        "simulation_replay_scenarios": simulation_replay_scenarios,
        "simulation_replay_pending": simulation_replay_pending,
        "simulation_replay_completed": simulation_replay_completed,
        "simulation_replay_failed": simulation_replay_failed,
        "simulation_replay_executions": simulation_replay_executions,
        "simulation_replay_execution_completed": simulation_replay_execution_completed,
        "simulation_replay_execution_failed": simulation_replay_execution_failed,
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
        simulation_replay_pending=simulation_replay_pending,
        simulation_replay_failed=simulation_replay_failed,
        simulation_replay_execution_completed=simulation_replay_execution_completed,
        simulation_replay_execution_failed=simulation_replay_execution_failed,
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
    severity_counts: dict[str, int] = {}
    record_type_counts: dict[str, int] = {}

    for heartbeat in heartbeats:
        metrics = heartbeat.get("metrics")
        if not isinstance(metrics, Mapping):
            continue

        aggregate["security_validation_records"] += _safe_int(metrics.get("security_validation_records"), 0)
        aggregate["security_validation_valid_records"] += _safe_int(metrics.get("security_validation_valid_records"), 0)
        aggregate["security_validation_invalid_records"] += _safe_int(metrics.get("security_validation_invalid_records"), 0)
        aggregate["security_validation_critical_records"] += _safe_int(metrics.get("security_validation_critical_records"), 0)

        _merge_int_counts(invalid_reasons, metrics.get("security_validation_invalid_reasons"))
        _merge_int_counts(severity_counts, metrics.get("security_validation_severity_counts"))
        _merge_int_counts(record_type_counts, metrics.get("security_validation_record_type_counts"))

    aggregate["security_validation_invalid_reasons"] = invalid_reasons
    aggregate["security_validation_severity_counts"] = severity_counts
    aggregate["security_validation_record_type_counts"] = record_type_counts

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