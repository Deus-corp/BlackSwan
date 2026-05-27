"""Typed trade heartbeat payloads and publisher.

Trade heartbeat remains backward-compatible with the existing runtime:
- type == "trade_heartbeat"

It also exposes generic swarm heartbeat fields:
- generic_type == "swarm_heartbeat"
- swarm == "trade"
- capabilities
- metrics
- details

This lets Overseer and future dashboard code treat trade as one equal swarm
among trade/security/explorer/improver/overseer/memory/simulation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional, cast

from src.swarms.common.contracts import SwarmHeartbeat

from .context import RuntimeContext
from .market.snapshot import MarketSnapshot

logger = logging.getLogger("SwarmNode.Heartbeat")


@dataclass(slots=True, frozen=True)
class TradeHeartbeat:
    """Versioned heartbeat emitted by the trade node."""

    schema_version: int
    type: str
    generic_type: str
    swarm: str
    node_id: str
    role: str
    status: str
    timestamp: float

    capabilities: list[str]
    metrics: dict[str, Any]
    details: dict[str, Any]

    capital: float
    dq: float
    fitness: float
    diversity: float
    crdt_size: int
    llm_mutations: int
    niche_counts: dict[str, int]
    trace_id: str
    origin_pubkey_hex: str
    best_symbol: str
    best_price: float
    market_mode: str
    execution_enabled: bool
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert heartbeat to serializable dictionary."""
        data = asdict(self)

        # Backward-compatible aliases for older readers.
        data.setdefault("node", self.node_id)
        data.setdefault("swarm_type", self.swarm)

        return data


class HeartbeatPublisher:
    """Publishes heartbeat events into the shared CRDT state."""

    TRADE_CAPABILITIES = [
        "market_observation",
        "strategy_evolution",
        "capital_management",
        "risk_assessment",
        "dry_run_execution",
        "crdt_genome_sync",
        "heartbeat_publish",
    ]

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx

    async def publish(self, snapshot: Optional[MarketSnapshot] = None) -> None:
        """Construct and push heartbeat data to the CRDT."""
        heartbeat = self.build_heartbeat(snapshot)
        payload = heartbeat.to_dict()

        logger.info(
            "[%s] Publishing trade heartbeat payload: type=%s generic_type=%s swarm=%s role=%s "
            "capital=%.4f dry_run=%s execution_enabled=%s",
            heartbeat.node_id,
            payload.get("type"),
            payload.get("generic_type"),
            payload.get("swarm"),
            payload.get("role"),
            heartbeat.capital,
            heartbeat.dry_run,
            heartbeat.execution_enabled,
        )

        await self._ctx.crdt.add_genome(payload)
        logger.info("[%s] Published trade heartbeat.", heartbeat.node_id)

    def build_heartbeat(self, snapshot: Optional[MarketSnapshot] = None) -> TradeHeartbeat:
        """Build a backward-compatible trade heartbeat with generic swarm fields."""
        node_id = str(getattr(self._ctx.config, "node_id", "unknown"))
        timestamp = time.time()

        capital = float(getattr(self._ctx, "capital", 0.0))
        dq = float(getattr(self._ctx.survival, "dq", 0.0))
        liveness = float(getattr(self._ctx.survival, "liveness", 1.0))
        fitness = self._get_current_fitness()
        diversity = self._get_population_diversity()
        crdt_size = len(getattr(self._ctx.crdt, "state", {}))
        llm_mutations = self._get_llm_mutations()
        niche_counts = self._get_niche_counts()
        best_symbol = self._get_best_symbol(snapshot)
        best_price = self._get_best_price(snapshot)
        market_mode = str(getattr(self._ctx.config, "market_mode", ""))
        execution_enabled = bool(getattr(self._ctx.config, "execution_enabled", False))
        dry_run = bool(getattr(self._ctx.config, "dry_run", True))

        status = self._derive_status(
            capital=capital,
            liveness=liveness,
            execution_enabled=execution_enabled,
            dry_run=dry_run,
        )

        metrics = {
            "capital": capital,
            "dq": dq,
            "liveness": liveness,
            "fitness": fitness,
            "diversity": diversity,
            "crdt_size": crdt_size,
            "llm_mutations": llm_mutations,
            "best_price": best_price,
            "niche_counts": dict(niche_counts),
        }

        details = {
            "trace_id": str(getattr(self._ctx, "trace_id", "")),
            "origin_pubkey_hex": str(getattr(self._ctx.crypto, "public_bytes_hex", "")),
            "best_symbol": best_symbol,
            "market_mode": market_mode,
            "execution_enabled": execution_enabled,
            "dry_run": dry_run,
            "primary_symbol": str(getattr(self._ctx, "primary_symbol", "")),
        }

        generic = SwarmHeartbeat(
            swarm="trade",
            node_id=node_id,
            role="node",
            status=status,
            capabilities=list(self.TRADE_CAPABILITIES),
            metrics=metrics,
            details=details,
            timestamp=timestamp,
        ).to_dict()

        return TradeHeartbeat(
            schema_version=2,
            type="trade_heartbeat",
            generic_type=str(generic.get("type", "swarm_heartbeat")),
            swarm="trade",
            node_id=node_id,
            role="node",
            status=status,
            timestamp=timestamp,
            capabilities=list(self.TRADE_CAPABILITIES),
            metrics=metrics,
            details=details,
            capital=capital,
            dq=dq,
            fitness=fitness,
            diversity=diversity,
            crdt_size=crdt_size,
            llm_mutations=llm_mutations,
            niche_counts=niche_counts,
            trace_id=str(details["trace_id"]),
            origin_pubkey_hex=str(details["origin_pubkey_hex"]),
            best_symbol=best_symbol,
            best_price=best_price,
            market_mode=market_mode,
            execution_enabled=execution_enabled,
            dry_run=dry_run,
        )

    def _fallback_snapshot(self) -> MarketSnapshot:
        symbol = str(getattr(self._ctx, "primary_symbol", "BTC/USDT"))
        last_market = getattr(self._ctx, "last_market", None)
        market = dict(last_market) if isinstance(last_market, dict) else {"price": 0.0, "symbol": symbol}

        if "symbol" not in market:
            market["symbol"] = symbol

        return MarketSnapshot(
            best_symbol=symbol,
            best_market=market,
            markets={symbol: market},
            timestamp=time.time(),
        )

    def _get_best_symbol(self, snapshot: Optional[MarketSnapshot]) -> str:
        snap = snapshot or self._fallback_snapshot()
        return str(getattr(snap, "best_symbol", "BTC/USDT"))

    def _get_best_price(self, snapshot: Optional[MarketSnapshot]) -> float:
        snap = snapshot or self._fallback_snapshot()
        try:
            return float(snap.price_for(snap.best_symbol))
        except (AttributeError, ValueError, TypeError):
            return 0.0

    def _get_current_fitness(self) -> float:
        try:
            engine = getattr(self._ctx, "engine", None)
            champ = getattr(engine, "champion", None)
            if champ is None:
                return 0.0
            if isinstance(champ, (list, tuple)) and len(champ) > 1:
                return float(champ[1])
            return float(getattr(champ, "fitness", 0.0))
        except Exception:
            return 0.0

    def _get_population_diversity(self) -> float:
        try:
            engine = getattr(self._ctx, "engine", None)
            if hasattr(engine, "diversity"):
                return float(engine.diversity())
            return 0.0
        except Exception:
            return 0.0

    def _get_llm_mutations(self) -> int:
        try:
            engine = getattr(self._ctx, "engine", None)
            return int(getattr(engine, "llm_mutations", 0))
        except Exception:
            return 0

    def _get_niche_counts(self) -> dict[str, int]:
        default = {"survival": 0, "capital": 0, "exploration": 0}

        try:
            engine = getattr(self._ctx, "engine", None)
            if not engine or not hasattr(engine, "population"):
                return default

            counts = default.copy()
            for item in engine.population:
                niche = getattr(item, "niche", None)
                if niche is None and isinstance(item, dict):
                    niche = cast(dict[str, Any], item).get("niche", "exploration")

                if niche in counts:
                    counts[str(niche)] += 1

            return counts
        except Exception:
            return default

    @staticmethod
    def _derive_status(
        *,
        capital: float,
        liveness: float,
        execution_enabled: bool,
        dry_run: bool,
    ) -> str:
        if capital <= 0.0:
            return "failed"

        if liveness < 0.5:
            return "degraded"

        if execution_enabled and dry_run:
            return "degraded"

        return "running"