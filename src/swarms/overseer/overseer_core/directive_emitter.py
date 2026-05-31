"""Build safe Overseer directives from global swarm briefs."""

from __future__ import annotations

from typing import Any, Mapping

from src.swarms.common.protocols.briefs import SwarmBrief, normalize_swarm_brief
from src.swarms.common.protocols.directives import (
    Directive,
    DirectiveSeverity,
    DirectiveTargetType,
    build_directive,
)


def build_directives_from_brief(
    brief: SwarmBrief | Mapping[str, Any],
    *,
    source: str = "overseer",
) -> list[Directive]:
    """Build safe directives from a global brief.

    This function is intentionally conservative: it only emits low-risk
    directives that cannot enable live execution.
    """
    normalized = normalize_swarm_brief(brief)
    directives: list[Directive] = []

    for item in normalized.recommended_actions:
        payload = item.get("payload", {})
        if not isinstance(payload, Mapping):
            continue

        directive_name = str(payload.get("directive") or "").strip().upper()

        if directive_name == "PROMOTE_GOLD_CANDIDATES":
            runtime_evidence_gold_candidates = _safe_int(
                payload.get("runtime_evidence_gold_candidates"),
                0,
            )
            gold_candidates = _safe_int(payload.get("gold_candidates"), 0)

            directive_payload = {
                "brief_id": normalized.brief_id,
                "reason": (
                    "runtime_evidence_gold_candidates_detected"
                    if runtime_evidence_gold_candidates > 0
                    else "memory_gold_candidates_detected"
                ),
                "gold_candidates": gold_candidates,
                "reason_item": dict(item),
            }

            if runtime_evidence_gold_candidates > 0:
                directive_payload["runtime_evidence_gold_candidates"] = runtime_evidence_gold_candidates

            directives.append(
                build_directive(
                    action="PROMOTE_GOLD_CANDIDATES",
                    target=payload.get("target_swarm") or "memory",
                    target_type=DirectiveTargetType.SWARM.value,
                    source=source,
                    payload=directive_payload,
                    reason="Global brief recommends promoting memory candidates.",
                    severity=DirectiveSeverity.INFO.value,
                    ttl_ms=120_000,
                )
            )
            continue

        if directive_name == "REDUCE_RISK":
            directives.append(
                build_directive(
                    action="REDUCE_RISK",
                    source=source,
                    target_type=DirectiveTargetType.SWARM.value,
                    target="trade",
                    payload={
                        "brief_id": normalized.brief_id,
                        "dry_run": True,
                        "execution_enabled": False,
                        "reason_item": dict(item),
                    },
                    reason="Global brief recommends risk reduction.",
                    severity=DirectiveSeverity.WARNING.value,
                    ttl_ms=120_000,
                )
            )
            continue

        recommendation = str(payload.get("recommendation") or "").strip()

        if recommendation == "review_runtime_evidence_alerts":
            runtime_evidence_alert_candidates = _safe_int(
                payload.get("runtime_evidence_alert_candidates"),
                0,
            )
            if runtime_evidence_alert_candidates <= 0:
                continue

            directives.append(
                build_directive(
                    action="OBSERVE",
                    target=payload.get("target_swarm") or "memory",
                    target_type=DirectiveTargetType.SWARM.value,
                    source=source,
                    payload={
                        "brief_id": normalized.brief_id,
                        "reason": "runtime_evidence_alert_candidates_detected",
                        "runtime_evidence_alert_candidates": runtime_evidence_alert_candidates,
                        "reason_item": dict(item),
                    },
                    reason="Global brief recommends observing runtime evidence alerts.",
                    severity=DirectiveSeverity.INFO.value,
                    ttl_ms=120_000,
                )
            )
            continue

        if recommendation == "review_security_validation_failures":
            security_validation_critical_records = _safe_int(
                payload.get("security_validation_critical_records"),
                0,
            )
            security_validation_invalid_records = _safe_int(
                payload.get("security_validation_invalid_records"),
                0,
            )
            if security_validation_critical_records <= 0 and security_validation_invalid_records <= 0:
                continue

            directives.append(
                build_directive(
                    action="OBSERVE",
                    target=payload.get("target_swarm") or "security",
                    target_type=DirectiveTargetType.SWARM.value,
                    source=source,
                    payload={
                        "brief_id": normalized.brief_id,
                        "reason": "security_validation_failures_detected",
                        "security_validation_critical_records": security_validation_critical_records,
                        "security_validation_invalid_records": security_validation_invalid_records,
                        "reason_item": dict(item),
                    },
                    reason="Global brief recommends observing security validation failures.",
                    severity=DirectiveSeverity.WARNING.value,
                    ttl_ms=120_000,
                )
            )
            continue

    return directives

def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


__all__ = ["build_directives_from_brief"]