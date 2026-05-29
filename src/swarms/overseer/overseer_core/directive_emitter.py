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
            directives.append(
                build_directive(
                    action="PROMOTE_GOLD_CANDIDATES",
                    source=source,
                    target_type=DirectiveTargetType.SWARM.value,
                    target="memory",
                    payload={
                        "brief_id": normalized.brief_id,
                        "reason_item": dict(item),
                    },
                    reason="Global brief recommends promoting memory gold candidates.",
                    severity=DirectiveSeverity.INFO.value,
                    ttl_ms=120_000,
                )
            )

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

    return directives


__all__ = ["build_directives_from_brief"]