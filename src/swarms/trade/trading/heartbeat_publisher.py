import time
import logging
from typing import Dict, Any

from src.trading.context import RuntimeContext
from src.trading.mutation_metrics import get_llm_stats

logger = logging.getLogger("HeartbeatPublisher")


class HeartbeatPublisher:

    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx

    async def publish(self) -> None:
        try:
            current_fitness: float = 0.0

            if self.ctx.engine and self.ctx.engine.champion:
                current_fitness = float(self.ctx.engine.champion[1])

            current_diversity: float = self._population_diversity()
            current_crdt_size: int = len(self.ctx.crdt.state)
            current_niche_counts: Dict[str, int] = self._population_niche_counts()
            llm_mutations_count: int = get_llm_stats()[0]

            self.ctx.telemetry.heartbeat(
                step=self.ctx.step_count,
                capital=self.ctx.capital,
                dq=self.ctx.survival.dq,
                fitness=current_fitness,
                diversity=current_diversity,
                crdt_size=current_crdt_size,
                llm_mutations=llm_mutations_count,
                niche_counts=current_niche_counts,
                trace_id=self.ctx.trace_id,
            )

            heartbeat_payload: Dict[str, Any] = {
                "type": "heartbeat",
                "capital": self.ctx.capital,
                "dq": self.ctx.survival.dq,
                "fitness": current_fitness,
                "diversity": current_diversity,
                "crdt_size": current_crdt_size,
                "llm_mutations": llm_mutations_count,
                "niche_counts": current_niche_counts,
                "node_id": self.ctx.node_id,
                "timestamp": time.time(),
                "trace_id": self.ctx.trace_id,
                "origin_pubkey_hex": self.ctx.crypto.public_bytes_hex,
            }

            await self.ctx.crdt.add_genome(heartbeat_payload)

        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}", exc_info=True)

    def _population_diversity(self) -> float:
        try:
            pop = getattr(self.ctx.engine, "population", [])
            if not pop:
                return 0.0
            sigs = set()
            for g in pop:
                if hasattr(g, "params"):
                    sigs.add(frozenset(g.params.items()))
                elif isinstance(g, dict) and isinstance(g.get("params"), dict):
                    sigs.add(frozenset(g["params"].items()))
            return len(sigs) / len(pop) if pop else 0.0
        except Exception:
            return 0.0

    def _population_niche_counts(self) -> Dict[str, int]:
        try:
            counts = {"survival": 0, "capital": 0, "exploration": 0}
            pop = getattr(self.ctx.engine, "population", [])
            for item in pop:
                niche = None
                if hasattr(item, "niche"):
                    niche = item.niche
                elif isinstance(item, dict):
                    niche = item.get("niche", "exploration")
                if niche in counts:
                    counts[niche] += 1
            return counts
        except Exception:
            return {"survival": 0, "capital": 0, "exploration": 0}