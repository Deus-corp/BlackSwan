"""Command executor for orchestrating swarm overseer decisions.

This executor emits canonical swarm_command records while preserving legacy
compatibility records where current swarm nodes still expect them.

Canonical:
- swarm_command

Legacy compatibility:
- sec_command
- meta_command_json
- explorer_command
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, Final, Mapping, Optional, Set

from src.swarms.overseer.overseer_core.interfaces import GenomeSink
from src.swarms.overseer.overseer_core.models import OverseerDecision, SwarmSnapshot

from src.swarms.common import (
    command_allowed_for_swarm,
    command_requires_explicit_gate,
    is_known_swarm,
    make_swarm_command,
)

logger: logging.Logger = logging.getLogger(__name__)

COMMAND_EXPIRATION_DEFAULT_SECONDS: Final[int] = 300
EXPLORER_COMMAND_EXPIRATION_SECONDS: Final[int] = 600
COMMAND_COOLDOWN_SECONDS: Final[int] = 600

_VOLATILE_KEYS: Final[Set[str]] = {
    "timestamp",
    "expires_at",
    "gid",
    "trace_id",
}


class ActionExecutor:
    """Emits commands into the CRDT sink with deduplication and rate-limiting.

    The executor now writes canonical swarm_command records first, then emits
    legacy-compatible records only where current swarm implementations still
    require them.
    """

    def __init__(self, sink: GenomeSink) -> None:
        self._sink: GenomeSink = sink
        self._last_emitted_at: Dict[str, float] = {}
        self._last_fingerprint: Dict[str, str] = {}

    async def apply(
        self,
        snapshot: SwarmSnapshot,
        decision: OverseerDecision,
        now: float,
    ) -> None:
        """Apply overseer decisions to the swarm based on current health snapshot."""
        for node_id in snapshot.stale_trade_nodes:
            await self._emit_restart_command(
                swarm="trade",
                node_id=node_id,
                now=now,
            )

        for node_id in snapshot.stale_security_nodes:
            await self._emit_restart_command(
                swarm="security",
                node_id=node_id,
                now=now,
            )

        for node_id in snapshot.stale_explorer_nodes:
            await self._emit_restart_command(
                swarm="explorer",
                node_id=node_id,
                now=now,
            )

        if decision.reduce_risk:
            await self._emit_trade_meta_command(
                key="reduce_risk",
                action="ADJUST_SWARM",
                reason="Risk mitigation policy triggered.",
                params={
                    "exploration_multiplier": 1.0,
                    "risk_scale": 0.7,
                    "survival_bias_adj": 0.05,
                    "stop_loss_adj": 0.8,
                    "confidence": 0.95,
                },
                now=now,
            )

        if decision.increase_exploration:
            await self._emit_trade_meta_command(
                key="increase_exploration",
                action="ADJUST_SWARM",
                reason="Exploration boost requested.",
                params={
                    "exploration_multiplier": 1.5,
                    "risk_scale": 1.0,
                    "survival_bias_adj": 0.0,
                    "stop_loss_adj": 1.0,
                    "confidence": 0.8,
                },
                now=now,
            )

        if decision.unblock_ips:
            await self._emit_security_command(
                key="unblock_ips",
                action="UNBLOCK_ALL",
                now=now,
                reason="Overseer requested security unblock.",
                payload={},
            )

        if not decision.continue_explorer:
            await self._emit_explorer_command(
                key="pause_explorer",
                action="PAUSE",
                now=now,
                reason="Explorer paused due to overseer policy.",
                payload={},
            )

        if getattr(decision, "run_improver_once", False):
            await self._note_improver_advisory(
                action="RUN_ONCE",
                now=now,
                reason="run_improver_once advisory is active",
            )

        if getattr(decision, "pause_improver", False):
            await self._note_improver_advisory(
                action="PAUSE",
                now=now,
                reason="pause_improver advisory is active",
            )

    def _canonical_command_allowed(
        self,
        *,
        command_type: str,
        target_swarm: str,
        target_role: str,
        explicit_gate: bool = False,
    ) -> bool:
        """Validate canonical command against shared topology.

        Advisory-only swarms/roles require explicit_gate=True.
        v1 intentionally leaves improver commands disabled because improver is
        advisory-only in topology.
        """
        if not is_known_swarm(target_swarm):
            logger.warning(
                "Refusing command %s: unknown target_swarm=%s",
                command_type,
                target_swarm,
            )
            return False

        if not command_allowed_for_swarm(target_swarm, command_type):
            logger.warning(
                "Refusing command %s: not allowed for target_swarm=%s",
                command_type,
                target_swarm,
            )
            return False

        if command_requires_explicit_gate(target_swarm, target_role, command_type) and not explicit_gate:
            logger.warning(
                "Refusing command %s for %s/%s: explicit safety gate required.",
                command_type,
                target_swarm,
                target_role,
            )
            return False

        return True

    # ------------------------------------------------------------------
    # Canonical + legacy emitters
    # ------------------------------------------------------------------

    async def _emit_restart_command(
        self,
        *,
        swarm: str,
        node_id: str,
        now: float,
    ) -> None:
        key = f"restart:{swarm}:{node_id}"

        canonical = make_swarm_command(
            command_type="RESTART_NODE",
            source_agent="overseer",
            source_swarm="overseer",
            target_swarm=swarm,
            target_node=node_id,
            target_role="node",
            ttl_seconds=COMMAND_EXPIRATION_DEFAULT_SECONDS,
            payload={
                "action": "RESTART_NODE",
                "node_id": node_id,
                "swarm": swarm,
                "reason": f"Node {node_id} in swarm {swarm} is stale.",
            },
            provenance={
                "agent": "overseer",
                "emitter": "ActionExecutor",
            },
        )

        await self._emit_canonical_if_allowed(
            key=key,
            command_type="RESTART_NODE",
            target_swarm=swarm,
            target_role="node",
            command=canonical,
            now=now,
        )

        if swarm == "security":
            legacy = self._legacy_sec_command(
                action="RESTART_NODE",
                now=now,
                payload={
                    "node_id": node_id,
                    "swarm": swarm,
                },
            )
            await self._emit_command(
                key=f"{key}:legacy_sec",
                command=legacy,
                now=now,
            )

        elif swarm == "explorer":
            legacy = self._legacy_explorer_command(
                action="RESTART_NODE",
                now=now,
                payload={
                    "node_id": node_id,
                    "swarm": swarm,
                },
            )
            await self._emit_command(
                key=f"{key}:legacy_explorer",
                command=legacy,
                now=now,
            )

        elif swarm == "trade":
            legacy = self._legacy_meta_command(
                action="RESTART_NODE",
                now=now,
                reason=f"Restart stale trade node {node_id}.",
                params={
                    "node_id": node_id,
                    "swarm": swarm,
                },
            )
            await self._emit_command(
                key=f"{key}:legacy_trade",
                command=legacy,
                now=now,
            )

        logger.warning("Requesting restart for stale %s node %s.", swarm, node_id)

    async def _emit_trade_meta_command(
        self,
        *,
        key: str,
        action: str,
        reason: str,
        params: Dict[str, Any],
        now: float,
    ) -> None:
        canonical = make_swarm_command(
            command_type=action,
            source_agent="overseer",
            source_swarm="overseer",
            target_swarm="trade",
            target_role="meta_agent",
            ttl_seconds=COMMAND_EXPIRATION_DEFAULT_SECONDS,
            payload={
                "action": action,
                "reason": reason,
                "params": params,
            },
            provenance={
                "agent": "overseer",
                "emitter": "ActionExecutor",
            },
        )

        await self._emit_canonical_if_allowed(
            key=key,
            command_type=action,
            target_swarm="trade",
            target_role="meta_agent",
            command=canonical,
            now=now,
        )

        legacy = self._legacy_meta_command(
            action=action,
            now=now,
            reason=reason,
            params=params,
        )

        await self._emit_command(
            key=f"{key}:legacy_meta",
            command=legacy,
            now=now,
        )

    async def _emit_security_command(
        self,
        *,
        key: str,
        action: str,
        now: float,
        reason: str,
        payload: Dict[str, Any],
    ) -> None:
        canonical = make_swarm_command(
            command_type=action,
            source_agent="overseer",
            source_swarm="overseer",
            target_swarm="security",
            target_role="node",
            ttl_seconds=COMMAND_EXPIRATION_DEFAULT_SECONDS,
            payload={
                "action": action,
                "reason": reason,
                **payload,
            },
            provenance={
                "agent": "overseer",
                "emitter": "ActionExecutor",
            },
        )

        await self._emit_canonical_if_allowed(
            key=key,
            command_type=action,
            target_swarm="security",
            target_role="node",
            command=canonical,
            now=now,
        )

        legacy = self._legacy_sec_command(
            action=action,
            now=now,
            payload={
                "reason": reason,
                **payload,
            },
        )

        await self._emit_command(
            key=f"{key}:legacy_sec",
            command=legacy,
            now=now,
        )

    async def _emit_explorer_command(
        self,
        *,
        key: str,
        action: str,
        now: float,
        reason: str,
        payload: Dict[str, Any],
    ) -> None:
        canonical = make_swarm_command(
            command_type=action,
            source_agent="overseer",
            source_swarm="overseer",
            target_swarm="explorer",
            target_role="node",
            ttl_seconds=EXPLORER_COMMAND_EXPIRATION_SECONDS,
            payload={
                "action": action,
                "reason": reason,
                **payload,
            },
            provenance={
                "agent": "overseer",
                "emitter": "ActionExecutor",
            },
        )

        await self._emit_canonical_if_allowed(
            key=key,
            command_type=action,
            target_swarm="explorer",
            target_role="node",
            command=canonical,
            now=now,
        )

        legacy = self._legacy_explorer_command(
            action=action,
            now=now,
            payload={
                "reason": reason,
                **payload,
            },
        )

        await self._emit_command(
            key=f"{key}:legacy_explorer",
            command=legacy,
            now=now,
        )

    async def _note_improver_advisory(
        self,
        *,
        action: str,
        now: float,
        reason: str,
    ) -> None:
        """Log improver advisory without emitting command.

        Improver is advisory-only in topology v1. Commands are intentionally
        not emitted until an explicit safety gate is implemented.
        """
        allowed_without_gate = self._canonical_command_allowed(
            command_type=action,
            target_swarm="improver",
            target_role="maintenance_agent",
            explicit_gate=False,
        )

        if allowed_without_gate:
            logger.warning(
                "Unexpected topology state: improver command %s allowed without explicit gate.",
                action,
            )
            return

        logger.info(
            "Improver advisory noted but not emitted: action=%s reason=%s",
            action,
            reason,
        )

    # ------------------------------------------------------------------
    # Legacy compatibility builders
    # ------------------------------------------------------------------

    @staticmethod
    def _legacy_sec_command(
        *,
        action: str,
        now: float,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "type": "sec_command",
            "event_type": "command_issued",
            "gid": f"overseer_sec_{action.lower()}_{hashlib.sha256(str(now).encode()).hexdigest()[:12]}",
            "source_gid": "overseer",
            "parent_gid": None,
            "timestamp": now,
            "expires_at": now + COMMAND_EXPIRATION_DEFAULT_SECONDS,
            "provenance": {
                "agent": "overseer",
                "legacy": True,
            },
            "data": {
                "action": action,
                **(payload or {}),
            },
        }

    @staticmethod
    def _legacy_explorer_command(
        *,
        action: str,
        now: float,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "type": "explorer_command",
            "gid": f"overseer_exp_{action.lower()}_{hashlib.sha256(str(now).encode()).hexdigest()[:12]}",
            "source_gid": "overseer",
            "parent_gid": None,
            "timestamp": now,
            "expires_at": now + EXPLORER_COMMAND_EXPIRATION_SECONDS,
            "provenance": {
                "agent": "overseer",
                "legacy": True,
            },
            "data": {
                "action": action,
                **(payload or {}),
            },
        }

    @staticmethod
    def _legacy_meta_command(
        *,
        action: str,
        now: float,
        reason: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "type": "meta_command_json",
            "gid": f"overseer_meta_{action.lower()}_{hashlib.sha256(str(now).encode()).hexdigest()[:12]}",
            "source_gid": "overseer",
            "parent_gid": None,
            "timestamp": now,
            "expires_at": now + COMMAND_EXPIRATION_DEFAULT_SECONDS,
            "provenance": {
                "agent": "overseer",
                "legacy": True,
            },
            "data": {
                "action": action,
                "reason": reason,
                "params": params,
            },
        }

    async def _emit_canonical_if_allowed(
        self,
        *,
        key: str,
        command_type: str,
        target_swarm: str,
        target_role: str,
        command: Dict[str, Any],
        now: float,
        explicit_gate: bool = False,
    ) -> bool:
        """Emit canonical command only if topology permits it."""
        if not self._canonical_command_allowed(
            command_type=command_type,
            target_swarm=target_swarm,
            target_role=target_role,
            explicit_gate=explicit_gate,
        ):
            return False

        await self._emit_command(
            key=key,
            command=command,
            now=now,
        )
        return True

    # ------------------------------------------------------------------
    # Emission, rate limiting, fingerprints
    # ------------------------------------------------------------------

    async def _emit_command(
        self,
        *,
        key: str,
        command: Dict[str, Any],
        now: float,
    ) -> None:
        if self._is_rate_limited(key, command, now):
            logger.debug("Command '%s' rate-limited or duplicate.", key)
            return

        try:
            await self._sink.add_genome(command)
            self._last_emitted_at[key] = now
            self._last_fingerprint[key] = self._generate_fingerprint(command)
            logger.info(
                "Emitted command key=%s type=%s action=%s target_swarm=%s target_node=%s",
                key,
                command.get("type"),
                self._extract_action(command),
                command.get("target_swarm") or command.get("data", {}).get("swarm"),
                command.get("target_node") or command.get("data", {}).get("node_id"),
            )
        except Exception as exc:
            logger.error("Failed to emit command '%s': %s", key, exc, exc_info=True)

    def _is_rate_limited(
        self,
        key: str,
        command: Mapping[str, Any],
        now: float,
    ) -> bool:
        last_at = self._last_emitted_at.get(key)
        if last_at is not None and (now - last_at) < COMMAND_COOLDOWN_SECONDS:
            return True

        last_fp = self._last_fingerprint.get(key)
        current_fp = self._generate_fingerprint(command)

        return last_fp == current_fp

    @classmethod
    def _generate_fingerprint(cls, command: Mapping[str, Any]) -> str:
        stable = cls._strip_volatile(command)
        payload = json.dumps(
            stable,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def _strip_volatile(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(k): cls._strip_volatile(v)
                for k, v in value.items()
                if str(k) not in _VOLATILE_KEYS
            }

        if isinstance(value, (list, tuple)):
            return [cls._strip_volatile(item) for item in value]

        return value

    @staticmethod
    def _extract_action(command: Mapping[str, Any]) -> str:
        data = command.get("data") if isinstance(command.get("data"), Mapping) else {}
        payload = command.get("payload") if isinstance(command.get("payload"), Mapping) else {}

        return str(
            command.get("command_type")
            or payload.get("action")
            or data.get("action")
            or ""
        )