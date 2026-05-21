"""Top-level overseer composition root."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Optional, Final, Dict, Any

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
    """Orchestrates collection, policy, LLM strategy, and execution for the swarm.

    Attributes:
        node_id: Unique identifier for this overseer node.
        coordination_interval_seconds: Interval between coordination cycles in seconds.
        llm: LLM client for generating strategic suggestions.
        crdt: CRDT adapter for state synchronization.
        collector: Collects state snapshots from the swarm.
        policy: Evaluates hard rules and merges decisions.
        strategist: Generates LLM-based strategic suggestions.
        executor: Applies decisions to the swarm.
        _next_coordination_at: Monotonic time for the next coordination cycle.
        _coordinate_lock: Lock to prevent concurrent coordination cycles.
        _failure_backoff_seconds: Current backoff duration after failures.
    """
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
        """Initialize the OverseerNode.

        Args:
            node_id: Unique identifier for this node. If None, a random ID is generated.
            coordination_interval_seconds: Interval between coordination cycles in seconds.
                If None, uses the default or environment variable.

        Raises:
            ValueError: If `coordination_interval_seconds` is not positive.
        """
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
        """Run the overseer node's main coordination loop.

        Raises:
            asyncio.CancelledError: If the loop is cancelled by the user.
            Exception: For unexpected fatal errors in the run loop.
        """
        logger.info(
            "🧭 Overseer %s started (interval=%ss)",
            self.node_id,
            self.coordination_interval_seconds,
        )

        try:
            while True:
                now = time.monotonic()

                if now >= self._next_coordination_at:
                    ok = await self.coordinate()
                    if ok:
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
            logger.info("Overseer %s run cancelled.", self.node_id)
            raise
        except Exception:
            logger.critical(
                "Overseer %s encountered a fatal error in run loop.",
                self.node_id,
                exc_info=True,
            )
            raise

    async def coordinate(self) -> bool:
        """Execute a single coordination cycle.

        Returns:
            bool: True if the cycle completed successfully, False otherwise.
        """
        if self._coordinate_lock.locked():
            logger.warning("Overseer coordination already in progress; skipping this cycle.")
            return False

        async with self._coordinate_lock:
            started_at = time.time()
            try:
                snapshot = self.collector.collect()
                hard_rules = self.policy.evaluate_hard_rules(snapshot)
                llm_suggestions = await self.strategist.suggest(snapshot)
                if not isinstance(llm_suggestions, dict):
                    raise ValueError("llm_suggestions must be a dictionary")
                decision = self.policy.merge(hard_rules, llm_suggestions)

                self._log_cycle(snapshot, hard_rules, decision, llm_suggestions)

                await self.executor.apply(snapshot, decision, started_at)
                logger.info(
                    "Overseer cycle completed successfully (source=%s, confidence=%.2f)",
                    decision.source,
                    decision.confidence,
                )
                return True

            except Exception as exc:
                logger.error("Overseer coordination failed: %s", exc, exc_info=True)
                return False

    def _log_cycle(
        self,
        snapshot: SwarmSnapshot,
        hard_rules: OverseerDecision,
        decision: OverseerDecision,
        llm_suggestions: Dict[str, bool],
    ) -> None:
        """Log details of a coordination cycle for observability.

        Args:
            snapshot: The swarm state snapshot used in the cycle.
            hard_rules: The decision based on hard rules.
            decision: The final merged decision.
            llm_suggestions: The LLM-generated strategic suggestions.
        """
        logger.info(
            "Snapshot: trade_nodes=%s trade_capital=%.2f trade_dq=%.4f trade_fitness=%.4f "
            "security_nodes=%s blocked_ips=%s explorer_nodes=%s findings=%s vuln_alerts=%s",
            snapshot.trade_nodes,
            snapshot.trade_capital,
            snapshot.trade_dq,
            snapshot.trade_fitness,
            snapshot.security_nodes,
            snapshot.blocked_ips,
            snapshot.explorer_nodes,
            snapshot.recent_findings,
            snapshot.recent_vulnerability_alerts,
        )
        logger.info(
            "Hard rules: reduce_risk=%s increase_exploration=%s unblock_ips=%s spawn_nodes=%s continue_explorer=%s reason=%s",
            hard_rules.reduce_risk,
            hard_rules.increase_exploration,
            hard_rules.unblock_ips,
            hard_rules.spawn_nodes,
            hard_rules.continue_explorer,
            hard_rules.reason,
        )
        logger.info(
            "LLM suggestions: %s",
            llm_suggestions if llm_suggestions else {},
        )
        logger.info(
            "Merged decision: reduce_risk=%s increase_exploration=%s unblock_ips=%s spawn_nodes=%s continue_explorer=%s source=%s confidence=%.2f reason=%s",
            decision.reduce_risk,
            decision.increase_exploration,
            decision.unblock_ips,
            decision.spawn_nodes,
            decision.continue_explorer,
            decision.source,
            decision.confidence,
            decision.reason,
        )


def main() -> None:
    """Entry point for the overseer node.

    Configures logging and starts the overseer node.
    """
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        )
    node = OverseerNode()
    asyncio.run(node.run())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Overseer stopped by user (KeyboardInterrupt).")
    except Exception:
        logger.critical("Overseer encountered a fatal error.", exc_info=True)