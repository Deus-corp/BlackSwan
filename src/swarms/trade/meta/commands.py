"""Meta-command handling for the trade swarm node.

This module applies coordination commands emitted by overseer / meta-agents.
It follows the same service-oriented style as heartbeat and risk:
- dependency injection via RuntimeContext;
- no inline node state scanning outside the service;
- one-time application per command gid;
- conservative clamping of all parameter changes.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set

from ..context import RuntimeContext

logger = logging.getLogger("SwarmNode.MetaCommands")


@dataclass(slots=True, frozen=True)
class MetaCommand:
    """Normalized meta-command envelope extracted from CRDT state."""

    gid: str
    timestamp: float
    expires_at: float
    data: Dict[str, Any]
    raw: Dict[str, Any]

    @property
    def action(self) -> str:
        return str(self.data.get("action", ""))


class MetaCommandService:
    """Applies meta-commands from shared state exactly once per gid."""

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx
        self._applied_gids: Set[str] = set()
        self._last_applied_ts: float = 0.0

    async def apply_pending(self) -> bool:
        """Apply the latest unexpired command from CRDT state.

        Returns True when a command was applied during this call.
        """
        command = self._latest_unexpired_command()
        if command is None:
            return False

        if command.gid in self._applied_gids:
            return False

        applied = await self._apply(command)
        if applied:
            self._applied_gids.add(command.gid)
            self._last_applied_ts = command.timestamp
        return applied

    def _latest_unexpired_command(self) -> Optional[MetaCommand]:
        state = getattr(self._ctx.crdt, "state", {})
        now = time.time()
        candidates = []

        for value in state.values():
            if not isinstance(value, dict):
                continue
            if value.get("type") != "meta_command_json":
                continue

            raw_gid = value.get("gid")
            if not raw_gid:
                continue

            try:
                ts = float(value.get("timestamp", 0.0))
            except Exception:
                ts = 0.0

            try:
                expires_at = float(value.get("expires_at", ts))
            except Exception:
                expires_at = ts

            if expires_at <= now:
                continue

            data = value.get("data", {})
            if not isinstance(data, dict):
                continue

            candidates.append(
                MetaCommand(
                    gid=str(raw_gid),
                    timestamp=ts,
                    expires_at=expires_at,
                    data=data,
                    raw=value,
                )
            )

        if not candidates:
            return None

        # Newest timestamp first, then newest expiry.
        candidates.sort(key=lambda c: (c.timestamp, c.expires_at))
        return candidates[-1]

    async def _apply(self, command: MetaCommand) -> bool:
        if command.action != "ADJUST_SWARM":
            logger.debug("Ignoring unsupported meta-command action: %s", command.action)
            return False

        params = command.data.get("params", {})
        if not isinstance(params, dict):
            logger.warning("Malformed meta-command params for gid=%s", command.gid)
            return False

        changed = False

        if "risk_scale" in params:
            changed = self._apply_risk_scale(params) or changed

        if "exploration_multiplier" in params:
            changed = self._apply_exploration_multiplier(params) or changed

        if "survival_bias_adj" in params:
            changed = self._apply_survival_bias(params) or changed

        if "stop_loss_adj" in params:
            changed = self._apply_stop_loss(params) or changed

        if changed:
            logger.info("Applied meta-command gid=%s action=%s", command.gid, command.action)
        return changed

    def _apply_risk_scale(self, params: Dict[str, Any]) -> bool:
        try:
            raw_risk_scale = float(params["risk_scale"])
            alpha = 0.1
            adjustment = alpha * math.tanh(raw_risk_scale - 1.0)

            current_params = getattr(self._ctx, "current_params", None)
            if not isinstance(current_params, dict):
                logger.warning("Current params unavailable for risk_scale meta-command")
                return False

            old_risk = float(current_params.get("max_risk_per_trade", 0.05))
            new_risk = old_risk * (1.0 + adjustment)
            new_risk = max(0.005, min(0.15, new_risk))
            current_params["max_risk_per_trade"] = new_risk

            logger.info("Meta-command: risk %.4f -> %.4f", old_risk, new_risk)
            return True
        except Exception as exc:
            logger.warning("Failed to apply risk_scale meta-command: %s", exc)
            return False

    def _apply_exploration_multiplier(self, params: Dict[str, Any]) -> bool:
        try:
            mult = float(params["exploration_multiplier"])
            engine = getattr(self._ctx, "engine", None)
            if engine is None:
                logger.warning("Engine unavailable for exploration_multiplier meta-command")
                return False

            old_rate = float(getattr(engine, "_mutation_rate", 0.25))
            new_rate = max(0.1, min(0.7, old_rate * mult))

            if hasattr(engine, "set_mutation_rate") and callable(getattr(engine, "set_mutation_rate")):
                engine.set_mutation_rate(new_rate)
            else:
                setattr(engine, "_mutation_rate", new_rate)

            logger.info("Meta-command: exploration rate %.3f -> %.3f", old_rate, new_rate)
            return True
        except Exception as exc:
            logger.warning("Failed to apply exploration_multiplier meta-command: %s", exc)
            return False

    def _apply_survival_bias(self, params: Dict[str, Any]) -> bool:
        try:
            delta = max(-0.05, min(0.05, float(params["survival_bias_adj"])))
            survival_cfg = getattr(self._ctx.survival, "config", None)
            if not isinstance(survival_cfg, dict):
                logger.warning("Survival config unavailable for meta-command application")
                return False

            old_sb = float(survival_cfg.get("lambda", 0.15))
            new_sb = max(0.1, min(0.9, old_sb + delta))
            survival_cfg["lambda"] = new_sb

            logger.info("Meta-command: survival lambda %.3f -> %.3f", old_sb, new_sb)
            return True
        except Exception as exc:
            logger.warning("Failed to apply survival_bias_adj meta-command: %s", exc)
            return False

    def _apply_stop_loss(self, params: Dict[str, Any]) -> bool:
        try:
            factor = float(params["stop_loss_adj"])
            current_params = getattr(self._ctx, "current_params", None)
            if not isinstance(current_params, dict):
                logger.warning("Current params unavailable for meta-command application")
                return False

            old_sl = float(current_params.get("stop_loss_ratio", 0.05))
            new_sl = max(0.001, min(0.2, old_sl * factor))
            current_params["stop_loss_ratio"] = new_sl

            logger.info("Meta-command: stop-loss %.4f -> %.4f", old_sl, new_sl)
            return True
        except Exception as exc:
            logger.warning("Failed to apply stop_loss_adj meta-command: %s", exc)
            return False

    @property
    def last_applied_ts(self) -> float:
        return self._last_applied_ts

    @property
    def applied_count(self) -> int:
        return len(self._applied_gids)

def apply_meta_commands(ctx, commands: list) -> None:
    """Применяет мета-команды к контексту узла."""
    for cmd in commands:
        logging.debug("Applying meta command: %s", cmd.get("action", "unknown"))
