"""Typed trade heartbeat payloads and publisher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .context import RuntimeContext
from .market_snapshot import MarketSnapshot


@dataclass(slots=True, frozen=True)
class TradeHeartbeat:
    """Versioned heartbeat emitted by the trade node."""

    schema_version: int
    node_id: str
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "trade_heartbeat",
            "schema_version": self.schema_version,
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "capital": self.capital,
            "dq": self.dq,
            "fitness": self.fitness,
            "diversity": self.diversity,
            "crdt_size": self.crdt_size,
            "llm_mutations": self.llm_mutations,
            "niche_counts": dict(self.niche_counts),
            "trace_id": self.trace_id,
            "origin_pubkey_hex": self.origin_pubkey_hex,
            "best_symbol": self.best_symbol,
            "best_price": self.best_price,
            "market_mode": self.market_mode,
        }


class HeartbeatPublisher:
    """Publishes heartbeat events into the shared CRDT state."""

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx

    async def publish(self, snapshot: MarketSnapshot) -> None:
        heartbeat = TradeHeartbeat(
            schema_version=1,
            node_id=self._ctx.config.node_id,
            timestamp=__import__("time").time(),
            capital=float(self._ctx.capital),
            dq=float(getattr(self._ctx.survival, "dq", 0.0)),
            fitness=float(self._current_fitness()),
            diversity=float(self._population_diversity()),
            crdt_size=len(getattr(self._ctx.crdt, "state", {})),
            llm_mutations=int(self._llm_mutations()),
            niche_counts=self._niche_counts(),
            trace_id=self._ctx.trace_id,
            origin_pubkey_hex=getattr(self._ctx.crypto, "public_bytes_hex", ""),
            best_symbol=snapshot.best_symbol,
            best_price=snapshot.price_for(snapshot.best_symbol),
            market_mode=self._ctx.config.market_mode,
        )
        await self._ctx.crdt.add_genome(heartbeat.to_dict())

    def _current_fitness(self) -> float:
        try:
            engine = self._ctx.engine
            champ = getattr(engine, "champion", None)
            if not champ:
                return 0.0
            if isinstance(champ, (list, tuple)) and len(champ) > 1:
                return float(champ[1])
            if hasattr(champ, "fitness"):
                return float(champ.fitness)
            return 0.0
        except Exception:
            return 0.0

    def _population_diversity(self) -> float:
        try:
            engine = self._ctx.engine
            if engine and hasattr(engine, "diversity"):
                return float(engine.diversity())
            return 0.0
        except Exception:
            return 0.0

    def _llm_mutations(self) -> int:
        try:
            engine = self._ctx.engine
            if engine and hasattr(engine, "llm_mutations"):
                return int(engine.llm_mutations)
            return 0
        except Exception:
            return 0

    def _niche_counts(self) -> Dict[str, int]:
        try:
            engine = self._ctx.engine
            if not engine or not hasattr(engine, "population"):
                return {"survival": 0, "capital": 0, "exploration": 0}

            counts = {"survival": 0, "capital": 0, "exploration": 0}
            for item in engine.population:
                niche = getattr(item, "niche", None)
                if niche is None and isinstance(item, dict):
                    niche = item.get("niche", "exploration")
                if niche in counts:
                    counts[niche] += 1
            return counts
        except Exception:
            return {"survival": 0, "capital": 0, "exploration": 0}
