"""Typed trade heartbeat payloads and publisher."""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, cast

from .context import RuntimeContext
from .market.snapshot import MarketSnapshot

logger = logging.getLogger("SwarmNode.Heartbeat")

@dataclass(slots=True, frozen=True)
class TradeHeartbeat:
    """Versioned heartbeat emitted by the trade node."""

    schema_version: int
    type: str
    swarm: str
    node_id: str
    role: str
    status: str
    timestamp: float
    capital: float
    dq: float
    fitness: float
    diversity: float
    crdt_size: int
    llm_mutations: int
    niche_counts: Dict[str, int]
    trace_id: str
    origin_pubkey_hex: str
    best_symbol: str
    best_price: float
    market_mode: str
    execution_enabled: bool
    dry_run: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert heartbeat to serializable dictionary."""
        return asdict(self)


class HeartbeatPublisher:
    """Publishes heartbeat events into the shared CRDT state."""

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx

    async def publish(self, snapshot: Optional[MarketSnapshot] = None) -> None:
        """Construct and push heartbeat data to the CRDT."""
        heartbeat = TradeHeartbeat(
            schema_version=1,
            type="trade_heartbeat",
            swarm="trade",
            node_id=str(getattr(self._ctx.config, "node_id", "unknown")),
            role="node",
            status="ok",
            timestamp=time.time(),
            capital=float(getattr(self._ctx, "capital", 0.0)),
            dq=float(getattr(self._ctx.survival, "dq", 0.0)),
            fitness=self._get_current_fitness(),
            diversity=self._get_population_diversity(),
            crdt_size=len(getattr(self._ctx.crdt, "state", {})),
            llm_mutations=self._get_llm_mutations(),
            niche_counts=self._get_niche_counts(),
            trace_id=str(getattr(self._ctx, "trace_id", "")),
            origin_pubkey_hex=str(getattr(self._ctx.crypto, "public_bytes_hex", "")),
            best_symbol=self._get_best_symbol(snapshot),
            best_price=self._get_best_price(snapshot),
            market_mode=str(getattr(self._ctx.config, "market_mode", "")),
            execution_enabled=bool(getattr(self._ctx.config, "execution_enabled", False)),
            dry_run=bool(getattr(self._ctx.config, "dry_run", True)),
        )

        payload = heartbeat.to_dict()
        logger.info(
            "[%s] Publishing trade heartbeat payload: type=%s swarm=%s role=%s capital=%.4f dry_run=%s execution_enabled=%s",
            heartbeat.node_id,
            payload.get("type"),
            payload.get("swarm"),
            payload.get("role"),
            heartbeat.capital,
            heartbeat.dry_run,
            heartbeat.execution_enabled,
        )
        await self._ctx.crdt.add_genome(payload)
        logger.info("[%s] Published trade heartbeat.", heartbeat.node_id)

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
        return getattr(snap, "best_symbol", "BTC/USDT")

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

    def _get_niche_counts(self) -> Dict[str, int]:
        default = {"survival": 0, "capital": 0, "exploration": 0}
        try:
            engine = getattr(self._ctx, "engine", None)
            if not engine or not hasattr(engine, "population"):
                return default

            counts = default.copy()
            for item in engine.population:
                niche = getattr(item, "niche", None)
                if niche is None and isinstance(item, dict):
                    niche = cast(dict, item).get("niche", "exploration")
                if niche in counts:
                    counts[str(niche)] += 1
            return counts
        except Exception:
            return default