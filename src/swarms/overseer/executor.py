"""Command executor for orchestrating swarm overseer decisions."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, Final, Optional, Set

from src.swarms.overseer.interfaces import GenomeSink
from src.swarms.overseer.models import OverseerDecision, SwarmSnapshot

logger: logging.Logger = logging.getLogger(__name__)

COMMAND_EXPIRATION_DEFAULT_SECONDS: Final[int] = 300
EXPLORER_COMMAND_EXPIRATION_SECONDS: Final[int] = 600
COMMAND_COOLDOWN_SECONDS: Final[int] = 600

_VOLATILE_KEYS: Final[Set[str]] = {"timestamp", "expires_at", "gid"}


class ActionExecutor:
    """Emits commands into the CRDT sink with deduplication and rate-limiting."""

    def __init__(self, sink: GenomeSink) -> None:
        self._sink: GenomeSink = sink
        self._last_emitted_at: Dict[str, float] = {}
        self._last_fingerprint: Dict[str, str] = {}

    async def apply(self, snapshot: SwarmSnapshot, decision: OverseerDecision, now: float) -> None:
        """Apply overseer decisions to the swarm based on current health snapshot."""
        for node_id in snapshot.stale_trade_nodes:
            await self._emit_restart_command("trade", node_id, now)
        for node_id in snapshot.stale_security_nodes:
            await self._emit_restart_command("security", node_id, now)
        for node_id in snapshot.stale_explorer_nodes:
            await self._emit_restart_command("explorer", node_id, now)

        if decision.reduce_risk:
            await self._emit_command(
                "reduce_risk",
                self._create_meta_command(
                    gid_prefix="overseer_reduce_risk",
                    reason="Risk mitigation policy triggered.",
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
                self._create_meta_command(
                    gid_prefix="overseer_increase_exploration",
                    reason="Exploration boost requested.",
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
                self._wrap_command("sec_command", "UNBLOCK_ALL", "sec_unblock"),
                now,
            )

        if not decision.continue_explorer:
            await self._emit_command(
                "pause_explorer",
                self._wrap_command("explorer_command", "PAUSE", "exp_pause"),
                now,
            )

    async def _emit_restart_command(self, swarm: str, node_id: str, now: float) -> None:
        command_key = f"restart:{swarm}:{node_id}"
        command = {
            "type": "sec_command",
            "data": {"action": "RESTART_NODE", "node_id": node_id, "swarm": swarm},
            "timestamp": now,
            "expires_at": now + COMMAND_EXPIRATION_DEFAULT_SECONDS,
            "gid": f"overseer_restart_{swarm}_{node_id}_{uuid.uuid4().hex}",
        }
        await self._emit_command(command_key, command, now)
        logger.warning("Requesting restart for stale %s node %s.", swarm, node_id)

    async def _emit_command(self, key: str, command: Dict[str, Any], now: float) -> None:
        if not self._is_rate_limited(key, command, now):
            try:
                await self._sink.add_genome(command)
                self._last_emitted_at[key] = now
                self._last_fingerprint[key] = self._generate_fingerprint(command)
            except Exception as e:
                logger.error("Failed to emit command '%s': %s", key, e, exc_info=True)

    def _is_rate_limited(self, key: str, command: Dict[str, Any], now: float) -> bool:
        last_at = self._last_emitted_at.get(key)
        if last_at is not None and (now - last_at) < COMMAND_COOLDOWN_SECONDS:
            return True
        
        last_fp = self._last_fingerprint.get(key)
        current_fp = self._generate_fingerprint(command)
        return last_fp == current_fp

    @staticmethod
    def _wrap_command(cmd_type: str, action: str, gid_slug: str) -> Dict[str, Any]:
        now = time.time()
        return {
            "type": cmd_type,
            "data": {"action": action},
            "timestamp": now,
            "expires_at": now + EXPLORER_COMMAND_EXPIRATION_SECONDS,
            "gid": f"overseer_{gid_slug}_{uuid.uuid4().hex}",
        }

    @staticmethod
    def _create_meta_command(
        gid_prefix: str, reason: str, params: Dict[str, Any], expiration_seconds: int, action_type: str
    ) -> Dict[str, Any]:
        now = time.time()
        return {
            "type": action_type,
            "data": {"action": "ADJUST_SWARM", "params": params, "reason": reason},
            "timestamp": now,
            "expires_at": now + expiration_seconds,
            "gid": f"{gid_prefix}_{uuid.uuid4().hex}",
        }

    @classmethod
    def _generate_fingerprint(cls, command: Dict[str, Any]) -> str:
        stable = cls._strip_volatile(command)
        payload = json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def _strip_volatile(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: cls._strip_volatile(v) for k, v in value.items() if k not in _VOLATILE_KEYS}
        if isinstance(value, (list, tuple)):
            return [cls._strip_volatile(i) for i in value]
        return value