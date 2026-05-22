"""Top-level overseer composition root for orchestrating swarm state and strategy."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Final, Dict, Any, Optional

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

from src.swarms.overseer.collector import StateCollector
from src.swarms.overseer.models import OverseerDecision, SwarmSnapshot
from src.swarms.overseer.executor import ActionExecutor
from src.swarms.overseer.policy import PolicyEngine
from src.swarms.overseer.strategist import LLMStrategist

logger: Final = logging.getLogger(__name__)

DEFAULT_COORDINATION_INTERVAL_SECONDS: Final[int] = 150
MIN_FAILURE_BACKOFF_SECONDS: Final[int] = 5
MAX_FAILURE_BACKOFF_SECONDS: Final[int] = 60


class OverseerNode:
    """Orchestrates collection, policy, LLM strategy, and execution for the swarm."""

    __slots__ = (
        "node_id", "coordination_interval_seconds", "llm", "crdt", 
        "collector", "policy", "strategist", "executor", 
        "_next_coordination_at", "_coordinate_lock", "_failure_backoff_seconds"
    )

    def __init__(
        self,
        node_id: Optional[str] = None,
        coordination_interval_seconds: Optional[int] = None,
    ) -> None:
        self.node_id = node_id or f"overseer-{uuid.uuid4().hex[:8]}"
        
        interval = coordination_interval_seconds or int(
            os.environ.get("OVERSEER_COORDINATION_INTERVAL_SECONDS", DEFAULT_COORDINATION_INTERVAL_SECONDS)
        )
        if interval <= 0:
            raise ValueError("coordination_interval_seconds must be positive")
        
        self.coordination_interval_seconds = interval

        self.llm = LLMClient(n_ctx=8192)
        self.crdt = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)

        self.collector = StateCollector(self.crdt)
        self.policy = PolicyEngine()
        self.strategist = LLMStrategist(self.llm)
        self.executor = ActionExecutor(self.crdt)

        self._next_coordination_at = time.monotonic()
        self._coordinate_lock = asyncio.Lock()
        self._failure_backoff_seconds = MIN_FAILURE_BACKOFF_SECONDS

    async def run(self) -> None:
        """Executes the main coordination loop with exponential backoff on failure."""
        logger.info("🧭 Overseer %s started (interval=%ss)", self.node_id, self.coordination_interval_seconds)

        try:
            while True:
                now = time.monotonic()
                if now >= self._next_coordination_at:
                    if await self.coordinate():
                        self._failure_backoff_seconds = MIN_FAILURE_BACKOFF_SECONDS
                        self._next_coordination_at = now + self.coordination_interval_seconds
                    else:
                        self._next_coordination_at = now + self._failure_backoff_seconds
                        self._failure_backoff_seconds = min(
                            self._failure_backoff_seconds * 2,
                            MAX_FAILURE_BACKOFF_SECONDS,
                        )
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info("Overseer %s shutting down.", self.node_id)
            raise
        except Exception:
            logger.critical("Overseer %s fatal loop error.", self.node_id, exc_info=True)
            raise

    async def coordinate(self) -> bool:
        """Performs a single cycle of snapshot collection, strategy generation, and execution."""
        if self._coordinate_lock.locked():
            return False

        async with self._coordinate_lock:
            try:
                started_at = time.time()
                snapshot = self.collector.collect()
                hard_rules = self.policy.evaluate_hard_rules(snapshot)
                llm_suggestions = await self.strategist.suggest(snapshot)
                
                if not isinstance(llm_suggestions, dict):
                    raise TypeError("Expected dict from LLMStrategist")

                decision = self.policy.merge(hard_rules, llm_suggestions)
                self._log_cycle(snapshot, hard_rules, decision, llm_suggestions)
                
                await self.executor.apply(snapshot, decision, started_at)
                return True
            except Exception as e:
                logger.error("Coordination cycle failed: %s", e)
                return False

    def _log_cycle(
        self, snapshot: SwarmSnapshot, hard_rules: OverseerDecision, 
        decision: OverseerDecision, llm_suggestions: Dict[str, Any]
    ) -> None:
        """Observability helper for logging state transitions."""
        logger.info("Snapshot: nodes_t=%d, cap=%.2f, fitness=%.4f", 
                    len(snapshot.trade_nodes), snapshot.trade_capital, snapshot.trade_fitness)
        logger.info("Decision: source=%s, confidence=%.2f, reason=%s", 
                    decision.source, decision.confidence, decision.reason)


def main() -> None:
    """CLI entry point for initializing the overseer."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    asyncio.run(OverseerNode().run())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.critical("Fatal startup error: %s", e, exc_info=True)