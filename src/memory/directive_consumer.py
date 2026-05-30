"""Memory directive consumer.

This module handles safe cross-swarm directives for the memory subsystem.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.swarms.common.protocols.directives import (
    DirectiveStatus,
    build_directive_result,
    directive_is_expired,
    directive_targets_node,
    normalize_directive,
)


SAFE_MEMORY_DIRECTIVES = {
    "OBSERVE",
    "PROMOTE_GOLD_CANDIDATES",
}


async def apply_memory_directive(node: Any, directive_data: Mapping[str, Any]) -> dict[str, Any]:
    """Apply one safe memory directive and return directive result as dict."""
    directive = normalize_directive(directive_data)

    if directive.directive_id in getattr(node, "_processed_directive_ids", set()):
        return build_directive_result(
            directive_id=directive.directive_id,
            status=DirectiveStatus.ACKNOWLEDGED.value,
            source=node.node_id,
            swarm="memory",
            node_id=node.node_id,
            message="Directive already processed.",
        ).to_dict()

    if directive_is_expired(directive):
        _mark_processed(node, directive.directive_id)
        return build_directive_result(
            directive_id=directive.directive_id,
            status=DirectiveStatus.EXPIRED.value,
            source=node.node_id,
            swarm="memory",
            node_id=node.node_id,
            message="Directive expired before processing.",
        ).to_dict()

    if not directive_targets_node(
        directive,
        swarm="memory",
        node_id=node.node_id,
        capabilities=getattr(node, "capabilities", []),
    ):
        return build_directive_result(
            directive_id=directive.directive_id,
            status=DirectiveStatus.REJECTED.value,
            source=node.node_id,
            swarm="memory",
            node_id=node.node_id,
            message="Directive does not target this memory node.",
        ).to_dict()

    if directive.action not in SAFE_MEMORY_DIRECTIVES:
        _mark_processed(node, directive.directive_id)
        return build_directive_result(
            directive_id=directive.directive_id,
            status=DirectiveStatus.REJECTED.value,
            source=node.node_id,
            swarm="memory",
            node_id=node.node_id,
            message=f"Unsupported or unsafe memory directive: {directive.action}",
            payload={"action": directive.action},
        ).to_dict()

    if directive.action == "OBSERVE":
        _mark_processed(node, directive.directive_id)
        return build_directive_result(
            directive_id=directive.directive_id,
            status=DirectiveStatus.ACKNOWLEDGED.value,
            source=node.node_id,
            swarm="memory",
            node_id=node.node_id,
            message="Observe directive acknowledged.",
            payload={"action": directive.action},
        ).to_dict()

    if directive.action == "PROMOTE_GOLD_CANDIDATES":
        summary = getattr(node, "last_memory_summary", {}) or {}
        if hasattr(summary, "to_dict"):
            summary = summary.to_dict()
        if not isinstance(summary, dict):
            summary = {}

        gold_candidates = int(summary.get("gold_candidates", 0) or 0)

        _mark_processed(node, directive.directive_id)
        return build_directive_result(
            directive_id=directive.directive_id,
            status=DirectiveStatus.APPLIED.value,
            source=node.node_id,
            swarm="memory",
            node_id=node.node_id,
            message="Memory gold candidate promotion acknowledged.",
            payload={
                "action": directive.action,
                "gold_candidates": gold_candidates,
                "next_step": "export_or_replay_gold_candidates",
            },
        ).to_dict()

    _mark_processed(node, directive.directive_id)
    return build_directive_result(
        directive_id=directive.directive_id,
        status=DirectiveStatus.REJECTED.value,
        source=node.node_id,
        swarm="memory",
        node_id=node.node_id,
        message=f"Unhandled memory directive: {directive.action}",
    ).to_dict()


def _mark_processed(node: Any, directive_id: str) -> None:
    if not hasattr(node, "_processed_directive_ids"):
        node._processed_directive_ids = set()
    node._processed_directive_ids.add(directive_id)


__all__ = ["SAFE_MEMORY_DIRECTIVES", "apply_memory_directive"]