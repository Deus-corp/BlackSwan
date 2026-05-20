"""Command executor for overseer decisions."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict

from .interfaces import GenomeSink
from .models import OverseerDecision, SwarmSnapshot

logger = logging.getLogger(__name__)

COMMAND_EXPIRATION_DEFAULT_SECONDS = 300
EXPLORER_COMMAND_EXPIRATION_SECONDS = 600
COMMAND_COOLDOWN_SECONDS = 600

_VOLATILE_KEYS = {"timestamp", "expires_at", "gid"}


class ActionExecutor:
    """Emits commands into CRDT with deduplication and cooldown."""

    def __init__(self, sink: GenomeSink) -> None:
        self._sink = sink
        self._last_emitted_at: Dict[str, float] = {}
        self._last_fingerprint: Dict[str, str] = {}

    async def apply(self, snapshot: SwarmSnapshot, decision: OverseerDecision, now: float) -> None:
        for stale_node_id in snapshot.stale_trade_nodes:
            await self._emit_restart_command("trade", stale_node_id, now)
        for stale_node_id in snapshot.stale_security_nodes:
            await self._emit_restart_command("security", stale_node_id, now)
        for stale_node_id in snapshot.stale_explorer_nodes:
            await self._emit_restart_command("explorer", stale_node_id, now)

        if decision.reduce_risk:
            await self._emit_command(
                "reduce_risk",
                self._meta_command(
                    gid_prefix="overseer_reduce_risk",
                    reason="Overseer policy: reduce risk due to DQ/capital/vulnerability conditions.",
                    params={
                        "exploration_multiplier": 1.0,
                        "risk_scale": 0.7,
                        "survival_bias_adj": 0.05,
                        "stop_loss_adj": 0.8,
                        "confidence": 0.95,
                    },
                    expiration_seconds=COMMAND_EXPIRATION_DEFAULT_SECONDS,
                    action_type="meta_command_json",
                ),
                now,
            )

        if decision.increase_exploration:
            await self._emit_command(
                "increase_exploration",
                self._meta_command(
                    gid_prefix="overseer_increase_exploration",
                    reason="Overseer suggestion: increase exploration.",
                    params={
                        "exploration_multiplier": 1.5,
                        "risk_scale": 1.0,
                        "survival_bias_adj": 0.0,
                        "stop_loss_adj": 1.0,
                        "confidence": 0.8,
                    },
                    expiration_seconds=COMMAND_EXPIRATION_DEFAULT_SECONDS,
                    action_type="meta_command_json",
                ),
                now,
            )

        if decision.unblock_ips:
            await self._emit_command(
                "unblock_ips",
                {
                    "type": "sec_command",
                    "data": {"action": "UNBLOCK_ALL"},
                    "timestamp": time.time(),
                    "expires_at": time.time() + EXPLORER_COMMAND_EXPIRATION_SECONDS,
                    "gid": f"overseer_sec_unblock_{uuid.uuid4().hex}",
                },
                now,
            )

        if decision.spawn_nodes:
            logger.info(
                "Spawn nodes recommended, but external orchestrator integration is not wired yet."
            )

        if decision.continue_explorer is False:
            await self._emit_command(
                "pause_explorer",
                {
                    "type": "explorer_command",
                    "data": {"action": "PAUSE"},
                    "timestamp": time.time(),
                    "expires_at": time.time() + EXPLORER_COMMAND_EXPIRATION_SECONDS,
                    "gid": f"overseer_exp_pause_{uuid.uuid4().hex}",
                },
                now,
            )

    async def _emit_restart_command(self, swarm: str, node_id: str, now: float) -> None:
        command_key = f"restart:{swarm}:{node_id}"
        command = {
            "type": "sec_command",
            "data": {"action": "RESTART_NODE", "node_id": node_id, "swarm": swarm},
            "timestamp": time.time(),
            "expires_at": time.time() + COMMAND_EXPIRATION_DEFAULT_SECONDS,
            "gid": f"overseer_restart_{swarm}_{node_id}_{uuid.uuid4().hex}",
        }
        await self._emit_command(command_key, command, now)
        logger.warning("Detected stale %s node %s. Requesting restart.", swarm, node_id)

    async def _emit_command(self, command_key: str, command: Dict[str, Any], now: float) -> None:
        if not self._should_emit(command_key, command, now):
            logger.debug("Skipping command '%s' due to cooldown or identical payload.", command_key)
            return

        try:
            await self._sink.add_genome(command)
        except Exception as exc:
            logger.error("Failed to emit command '%s': %s", command_key, exc, exc_info=True)
            return

        self._last_emitted_at[command_key] = now
        self._last_fingerprint[command_key] = self._fingerprint(command)

    def _should_emit(self, command_key: str, command: Dict[str, Any], now: float) -> bool:
        last_at = self._last_emitted_at.get(command_key)
        fingerprint = self._fingerprint(command)
        last_fp = self._last_fingerprint.get(command_key)

        if last_at is not None and (now - last_at) < COMMAND_COOLDOWN_SECONDS:
            return False
        if last_fp is not None and last_fp == fingerprint:
            return False
        return True

    @staticmethod
    def _meta_command(
        *,
        gid_prefix: str,
        reason: str,
        params: Dict[str, Any],
        expiration_seconds: int,
        action_type: str,
    ) -> Dict[str, Any]:
        now = time.time()
        return {
            "type": action_type,
            "data": {
                "action": "ADJUST_SWARM",
                "params": params,
                "reason": reason,
            },
            "timestamp": now,
            "expires_at": now + expiration_seconds,
            "gid": f"{gid_prefix}_{uuid.uuid4().hex}",
        }

    @classmethod
    def _fingerprint(cls, command: Dict[str, Any]) -> str:
        stable = cls._strip_volatile(command)
        payload = json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def _strip_volatile(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: cls._strip_volatile(inner)
                for key, inner in value.items()
                if key not in _VOLATILE_KEYS
            }
        if isinstance(value, list):
            return [cls._strip_volatile(item) for item in value]
        if isinstance(value, tuple):
            return tuple(cls._strip_volatile(item) for item in value)
        return value