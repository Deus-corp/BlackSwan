"""Trade directive consumer."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from src.swarms.common.protocols.directives import (
    DirectiveStatus,
    build_directive_result,
    directive_is_expired,
    directive_targets_node,
    normalize_directive,
)


SAFE_TRADE_DIRECTIVES = {
    "OBSERVE",
    "REDUCE_RISK",
    "SET_DRY_RUN",
}


async def apply_trade_directive(node: Any, directive_data: Mapping[str, Any]) -> dict[str, Any]:
    """Apply one safe trade directive and return directive result as dict."""
    directive = normalize_directive(directive_data)

    if directive.directive_id in getattr(node, "_processed_directive_ids", set()):
        return build_directive_result(
            directive_id=directive.directive_id,
            status=DirectiveStatus.ACKNOWLEDGED.value,
            source=node.node_id,
            swarm="trade",
            node_id=node.node_id,
            message="Directive already processed.",
        ).to_dict()

    if directive_is_expired(directive):
        result = build_directive_result(
            directive_id=directive.directive_id,
            status=DirectiveStatus.EXPIRED.value,
            source=node.node_id,
            swarm="trade",
            node_id=node.node_id,
            message="Directive expired before processing.",
        )
        _mark_processed(node, directive.directive_id)
        return result.to_dict()

    if not directive_targets_node(
        directive,
        swarm="trade",
        node_id=node.node_id,
        capabilities=getattr(node, "capabilities", []),
    ):
        return build_directive_result(
            directive_id=directive.directive_id,
            status=DirectiveStatus.REJECTED.value,
            source=node.node_id,
            swarm="trade",
            node_id=node.node_id,
            message="Directive does not target this trade node.",
        ).to_dict()

    if directive.action not in SAFE_TRADE_DIRECTIVES:
        result = build_directive_result(
            directive_id=directive.directive_id,
            status=DirectiveStatus.REJECTED.value,
            source=node.node_id,
            swarm="trade",
            node_id=node.node_id,
            message=f"Unsupported or unsafe trade directive: {directive.action}",
            payload={"action": directive.action},
        )
        _mark_processed(node, directive.directive_id)
        return result.to_dict()

    if directive.action == "OBSERVE":
        result = build_directive_result(
            directive_id=directive.directive_id,
            status=DirectiveStatus.ACKNOWLEDGED.value,
            source=node.node_id,
            swarm="trade",
            node_id=node.node_id,
            message="Observe directive acknowledged.",
            payload={"action": directive.action},
        )
        _mark_processed(node, directive.directive_id)
        return result.to_dict()

    if directive.action in {"REDUCE_RISK", "SET_DRY_RUN"}:
        node.trade_config = replace(
            node.trade_config,
            dry_run=True,
            execution_enabled=False,
        )
        node.ctx.config = node.trade_config

        if hasattr(node, "_emit_trade_event"):
            await node._emit_trade_event(
                event_type="directive_applied",
                parent_gid=directive.directive_id,
                payload={
                    "action": directive.action,
                    "dry_run": node.trade_config.dry_run,
                    "execution_enabled": node.trade_config.execution_enabled,
                },
            )

        result = build_directive_result(
            directive_id=directive.directive_id,
            status=DirectiveStatus.APPLIED.value,
            source=node.node_id,
            swarm="trade",
            node_id=node.node_id,
            message="Trade risk reduced: dry_run=True, execution_enabled=False.",
            payload={
                "action": directive.action,
                "dry_run": node.trade_config.dry_run,
                "execution_enabled": node.trade_config.execution_enabled,
            },
        )
        _mark_processed(node, directive.directive_id)
        return result.to_dict()

    result = build_directive_result(
        directive_id=directive.directive_id,
        status=DirectiveStatus.REJECTED.value,
        source=node.node_id,
        swarm="trade",
        node_id=node.node_id,
        message=f"Unhandled trade directive: {directive.action}",
    )
    _mark_processed(node, directive.directive_id)
    return result.to_dict()


def _mark_processed(node: Any, directive_id: str) -> None:
    if not hasattr(node, "_processed_directive_ids"):
        node._processed_directive_ids = set()
    node._processed_directive_ids.add(directive_id)


__all__ = ["SAFE_TRADE_DIRECTIVES", "apply_trade_directive"]