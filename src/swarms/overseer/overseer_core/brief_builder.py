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
    evidence_ids: list[str] | None = None,
) -> SwarmBrief:
    """Build a compact global brief from Overseer snapshot and health data."""
    topology_health = dict(topology_health or {})
    memory_intelligence = dict(memory_intelligence or {})

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
                payload={"directive": "PROMOTE_GOLD_CANDIDATES"},
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

    status = _global_status(
        degraded_swarms=degraded_swarms,
        alert_candidates=alert_candidates,
        runtime_evidence_alert_candidates=runtime_evidence_alert_candidates,
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
    }

    summary = _build_summary(
        status=status,
        swarm_counts=swarm_counts,
        degraded_swarms=degraded_swarms,
        gold_candidates=gold_candidates,
        alert_candidates=alert_candidates,
        runtime_evidence_gold_candidates=runtime_evidence_gold_candidates,
        runtime_evidence_alert_candidates=runtime_evidence_alert_candidates,
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
    memory_status: str,
) -> str:
    if degraded_swarms or alert_candidates > 0 or runtime_evidence_alert_candidates > 0:
        return BriefStatus.DEGRADED.value

    if memory_status in {"critical", "failed"}:
        return BriefStatus.CRITICAL.value

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