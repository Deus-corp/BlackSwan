"""Top-level overseer composition root."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Optional

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

from .collector import StateCollector
from .executor import ActionExecutor
from .policy import PolicyEngine
from .strategist import LLMStrategist
from .models import OverseerDecision, SwarmSnapshot

logger = logging.getLogger(__name__)

DEFAULT_COORDINATION_INTERVAL_SECONDS = 150
MIN_FAILURE_BACKOFF_SECONDS = 5
MAX_FAILURE_BACKOFF_SECONDS = 60


class OverseerNode:
    """Orchestrates collection, policy, LLM strategy, and execution."""

    def __init__(
        self,
        node_id: Optional[str] = None,
        coordination_interval_seconds: Optional[int] = None,
    ) -> None:
        self.node_id = node_id or f"overseer-{uuid.uuid4().hex[:8]}"
        self.coordination_interval_seconds = coordination_interval_seconds or int(
            os.environ.get("OVERSEER_COORDINATION_INTERVAL_SECONDS", DEFAULT_COORDINATION_INTERVAL_SECONDS)
        )

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
        if self._coordinate_lock.locked():
            logger.warning("Overseer coordination already in progress; skipping this cycle.")
            return False

        async with self._coordinate_lock:
            started_at = time.time()
            try:
                snapshot = self.collector.collect()
                hard_rules = self.policy.evaluate_hard_rules(snapshot)
                llm_suggestions = await self.strategist.suggest(snapshot)
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
        llm_suggestions: dict[str, bool],
    ) -> None:
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