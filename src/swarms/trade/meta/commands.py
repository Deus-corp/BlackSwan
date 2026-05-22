"""Meta-command handling for the trade swarm node.

This module applies coordination commands emitted by overseer / meta-agents.
It follows a service-oriented architecture with dependency injection and
conservative parameter clamping to ensure system stability.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set, List

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
    """Applies meta-commands from shared state exactly once per GID."""

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx
        self._applied_gids: Set[str] = set()
        self._last_applied_ts: float = 0.0

    async def apply_pending(self) -> bool:
        """Finds and applies the latest unexpired command."""
        command = self._get_latest_unexpired_command()
        if not command or command.gid in self._applied_gids:
            return False

        if await self._apply(command):
            self._applied_gids.add(command.gid)
            self._last_applied_ts = command.timestamp
            return True
        return False

    def _get_latest_unexpired_command(self) -> Optional[MetaCommand]:
        state = getattr(self._ctx.crdt, "state", {})
        now = time.time()
        candidates: List[MetaCommand] = []

        for value in state.values():
            if not isinstance(value, dict) or value.get("type") != "meta_command_json":
                continue

            gid = str(value.get("gid", ""))
            if not gid: continue

            ts = float(value.get("timestamp", 0.0))
            expires_at = float(value.get("expires_at", ts))
            
            if expires_at <= now:
                continue

            data = value.get("data")
            if isinstance(data, dict):
                candidates.append(MetaCommand(gid, ts, expires_at, data, value))

        if not candidates:
            return None

        return max(candidates, key=lambda c: (c.timestamp, c.expires_at))

    async def _apply(self, command: MetaCommand) -> bool:
        if command.action != "ADJUST_SWARM":
            return False

        params = command.data.get("params", {})
        if not isinstance(params, dict):
            logger.warning(f"Malformed params for GID {command.gid}")
            return False

        changes = [
            self._apply_risk_scale(params),
            self._apply_exploration_multiplier(params),
            self._apply_survival_bias(params),
            self._apply_stop_loss(params)
        ]
        
        applied = any(changes)
        if applied:
            logger.info(f"Applied meta-command GID={command.gid}")
        return applied

    def _apply_risk_scale(self, params: Dict[str, Any]) -> bool:
        if "risk_scale" not in params:
            return False
        try:
            curr = getattr(self._ctx, "current_params", {})
            old = float(curr.get("max_risk_per_trade", 0.05))
            adj = 0.1 * math.tanh(float(params["risk_scale"]) - 1.0)
            new = max(0.005, min(0.15, old * (1.0 + adj)))
            curr["max_risk_per_trade"] = new
            return True
        except (ValueError, TypeError, AttributeError): return False

    def _apply_exploration_multiplier(self, params: Dict[str, Any]) -> bool:
        if "exploration_multiplier" not in params:
            return False
        try:
            engine = getattr(self._ctx, "engine", None)
            if not engine: return False
            old = float(getattr(engine, "_mutation_rate", 0.25))
            new = max(0.1, min(0.7, old * float(params["exploration_multiplier"])))
            if callable(getattr(engine, "set_mutation_rate", None)):
                engine.set_mutation_rate(new)
            else:
                setattr(engine, "_mutation_rate", new)
            return True
        except (ValueError, TypeError, AttributeError): return False

    def _apply_survival_bias(self, params: Dict[str, Any]) -> bool:
        if "survival_bias_adj" not in params:
            return False
        try:
            cfg = getattr(self._ctx.survival, "config", {})
            old = float(cfg.get("lambda", 0.15))
            delta = max(-0.05, min(0.05, float(params["survival_bias_adj"])))
            cfg["lambda"] = max(0.1, min(0.9, old + delta))
            return True
        except (ValueError, TypeError, AttributeError): return False

    def _apply_stop_loss(self, params: Dict[str, Any]) -> bool:
        if "stop_loss_adj" not in params:
            return False
        try:
            curr = getattr(self._ctx, "current_params", {})
            old = float(curr.get("stop_loss_ratio", 0.05))
            new = max(0.001, min(0.2, old * float(params["stop_loss_adj"])))
            curr["stop_loss_ratio"] = new
            return True
        except (ValueError, TypeError, AttributeError): return False

    @property
    def last_applied_ts(self) -> float:
        return self._last_applied_ts

    @property
    def applied_count(self) -> int:
        return len(self._applied_gids)