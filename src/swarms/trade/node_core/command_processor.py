"""Trade node command processor."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Mapping

from src.swarms.common.protocols import command_is_expired, normalize_command

logger = logging.getLogger("SwarmNode")


async def process_trade_command(node: Any, command: Mapping[str, Any]) -> None:
    """Process one normalized trade command for a node."""
    normalized = normalize_command(command)

    gid = str(normalized.get("gid") or command.get("gid") or "")
    if gid and gid in node._processed_command_gids:
        return

    if command_is_expired(normalized):
        if gid:
            node._processed_command_gids.add(gid)
        return

    if not node._command_applies_to_self(normalized):
        return

    action = node._command_action(normalized)
    if not action:
        return

    if gid:
        node._processed_command_gids.add(gid)

    if action == "PAUSE":
        node._paused = True
        await node._emit_trade_event(
            event_type="command_applied",
            parent_gid=gid or None,
            payload={"action": action, "status": "paused"},
        )
        logger.info("[%s] Trade node paused by command.", node.node_id)
        return

    if action == "RESUME":
        node._paused = False
        await node._emit_trade_event(
            event_type="command_applied",
            parent_gid=gid or None,
            payload={"action": action, "status": "resumed"},
        )
        logger.info("[%s] Trade node resumed by command.", node.node_id)
        return

    if action == "RESTART_NODE":
        await node._emit_trade_event(
            event_type="command_applied",
            parent_gid=gid or None,
            payload={"action": action, "status": "shutdown_requested"},
        )
        logger.critical("[%s] Received RESTART_NODE. Requesting shutdown.", node.node_id)
        node.shutdown_event.set()
        return

    if action == "SET_DRY_RUN":
        value = node._command_value(normalized, "enabled", node._command_value(normalized, "value", True))
        dry_run = bool(value)
        node.trade_config = replace(
            node.trade_config,
            dry_run=dry_run,
            execution_enabled=False if dry_run else node.trade_config.execution_enabled,
        )
        node.ctx.config = node.trade_config
        await node._emit_trade_event(
            event_type="command_applied",
            parent_gid=gid or None,
            payload={
                "action": action,
                "dry_run": node.trade_config.dry_run,
                "execution_enabled": node.trade_config.execution_enabled,
            },
        )
        return

    if action == "SET_EXECUTION_ENABLED":
        value = bool(node._command_value(normalized, "enabled", node._command_value(normalized, "value", False)))

        if value and not node._command_has_explicit_approval(normalized):
            await node._emit_trade_event(
                event_type="command_blocked",
                parent_gid=gid or None,
                payload={
                    "action": action,
                    "reason": "explicit_approval_required",
                    "execution_enabled": node.trade_config.execution_enabled,
                    "dry_run": node.trade_config.dry_run,
                },
            )
            logger.warning("[%s] Blocked SET_EXECUTION_ENABLED without approval.", node.node_id)
            return

        node.trade_config = replace(
            node.trade_config,
            execution_enabled=value,
            dry_run=False if value else True,
        )
        node.ctx.config = node.trade_config
        await node._emit_trade_event(
            event_type="command_applied",
            parent_gid=gid or None,
            payload={
                "action": action,
                "execution_enabled": node.trade_config.execution_enabled,
                "dry_run": node.trade_config.dry_run,
            },
        )
        return

    await node._emit_trade_event(
        event_type="command_unsupported",
        parent_gid=gid or None,
        payload={"action": action},
    )


__all__ = ["process_trade_command"]