#!/usr/bin/env python3
"""Simulation swarm node.

The simulation swarm is responsible for offline worlds, policy evaluation,
stress tests, and counterfactual experiments. This initial node is intentionally
minimal: it publishes canonical swarm heartbeats so Overseer and dashboard
layers can treat simulation as a first-class swarm.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import uuid
from typing import Optional, Mapping

from src.core.crdt_adapter import CRDTAdapter
from src.swarms.simulation.heartbeat import build_simulation_heartbeat
from src.memory.publisher import publish_memory_record
from src.swarms.simulation.replay_metrics import build_simulation_replay_heartbeat_metrics
from src.swarms.simulation.directive_consumer import apply_simulation_directive
from swarm_config import config

logger = logging.getLogger(__name__)

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30.0


class SimulationSwarmNode:
    """Minimal simulation swarm node with CRDT heartbeat publishing."""

    def __init__(
        self,
        node_id: Optional[str] = None,
        heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    ) -> None:
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")

        self.node_id = node_id or os.environ.get("SIMULATION_NODE_ID") or f"simulation-{uuid.uuid4().hex[:8]}"
        self.heartbeat_interval_seconds = float(heartbeat_interval_seconds)
        self._stop_event = asyncio.Event()

        self.crdt = CRDTAdapter(
            node_id=self.node_id,
            db_path=config.crdt_db_path,
        )

        self.heartbeats_published = 0
        self.scenarios_run = 0
        self.memory_records_published = 0
        self.last_error = ""

        self._processed_directive_ids: set[str] = set()
        self.shutdown_event = asyncio.Event()

        logger.info(
            "SimulationSwarmNode initialized node_id=%s heartbeat_interval=%.1fs",
            self.node_id,
            self.heartbeat_interval_seconds,
        )

    async def publish_heartbeat(self) -> None:
        """Publish canonical simulation swarm heartbeat."""
        try:
            state = getattr(self.crdt, "state", {}) or {}
            replay_metrics = build_simulation_replay_heartbeat_metrics(
                list(state.values()) if isinstance(state, dict) else []
            )
            replay_metrics["simulation_replay_metrics_enabled"] = True
        except Exception as exc:
            replay_metrics = {
                "simulation_replay_metrics_enabled": False,
                "simulation_replay_metrics_error": str(exc),
                "simulation_replay_scenarios": 0,
                "simulation_replay_pending": 0,
                "simulation_replay_completed": 0,
                "simulation_replay_failed": 0,
            }

        metrics = {
            "heartbeats_published": self.heartbeats_published,
            "scenarios_run": self.scenarios_run,
            "policy_evaluations": 0,
            "stress_tests": 0,
            "memory_records_published": self.memory_records_published,
        }
        metrics.update(replay_metrics)

        payload = build_simulation_heartbeat(
            self.node_id,
            metrics=metrics,
            details={
                "last_error": self.last_error,
                "crdt_db_path": str(config.crdt_db_path),
            },
            status="running" if not self.last_error else "degraded",
        )

        await self.crdt.add_genome(payload)
        self.heartbeats_published += 1
        logger.info(
            "[%s] Published simulation swarm heartbeat count=%d memory_records_published=%d",
            self.node_id,
            self.heartbeats_published,
            self.memory_records_published,
        )

    async def start(self) -> None:
        """Run heartbeat loop until stopped."""
        logger.info("SimulationSwarmNode %s starting.", self.node_id)

        self._install_signal_handlers()
        await self._command_loop()
        await self.publish_memory_event("simulation swarm node started", topic="lifecycle")
        await self.publish_heartbeat()

        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.heartbeat_interval_seconds,
                )
            except asyncio.TimeoutError:
                await self.publish_heartbeat()
            except Exception as exc:
                self.last_error = str(exc)
                logger.exception("SimulationSwarmNode heartbeat loop error: %s", exc)

            try:
                await self.publish_memory_event("simulation swarm node stopped", topic="lifecycle")
            except Exception as exc:
                logger.warning(
                    "[%s] Failed to publish shutdown memory event: %s",
                    self.node_id,
                    exc,
                )

            logger.info("SimulationSwarmNode %s stopped.", self.node_id)

    async def stop(self) -> None:
        """Request graceful shutdown."""
        self._stop_event.set()

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._stop_event.set)
            except NotImplementedError:
                pass

    async def publish_memory_event(
        self,
        message: str,
        *,
        topic: str = "simulation_lifecycle",
        payload: dict[str, object] | None = None,
    ) -> str:
        """Publish simulation event into shared memory via CRDT."""
        record_payload = {
            "message": message,
            "tags": ["simulation", topic],
        }
        if payload:
            record_payload.update(payload)

        record_id = await publish_memory_record(
            self.crdt,
            kind="event",
            scope="shared",
            topic=topic,
            payload=record_payload,
            source_node_id=self.node_id,
            swarm="simulation",
            confidence=1.0,
            verified=True,
        )
        self.memory_records_published += 1
        logger.info(
            "[%s] Published simulation memory record id=%s topic=%s count=%d",
            self.node_id,
            record_id,
            topic,
            self.memory_records_published,
        )
        return record_id
    
    async def _command_loop_once(self) -> int:
        """Consume one batch of simulation directives from CRDT."""
        processed = 0

        try:
            refresh = getattr(self.crdt, "refresh_from_storage", None)
            if callable(refresh):
                refresh()

            state = getattr(self.crdt, "state", {}) or {}
            values = list(state.values()) if isinstance(state, dict) else []

            for value in values:
                if not isinstance(value, Mapping):
                    continue
                if str(value.get("type") or "") != "swarm_directive":
                    continue

                directive_id = str(value.get("directive_id") or "").strip()
                if directive_id and directive_id in self._processed_directive_ids:
                    continue

                result = await apply_simulation_directive(self, value)

                if directive_id:
                    self._processed_directive_ids.add(directive_id)

                await self.crdt.add_genome(result)
                processed += 1

                logger.info(
                    "[%s] Published simulation directive result: directive_id=%s status=%s reason=%s",
                    self.node_id,
                    result.get("directive_id"),
                    result.get("status"),
                    result.get("payload", {}).get("reason"),
                )

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[%s] simulation command loop batch failed", self.node_id)

        return processed
    
    async def _command_loop(self) -> None:
        """Continuously consume simulation directives."""
        while not self.shutdown_event.is_set():
            await self._command_loop_once()
            await asyncio.sleep(1.0)


async def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
    )

    interval = float(os.environ.get("SIMULATION_HEARTBEAT_INTERVAL_SECONDS", DEFAULT_HEARTBEAT_INTERVAL_SECONDS))
    node = SimulationSwarmNode(heartbeat_interval_seconds=interval)
    await node.start()


if __name__ == "__main__":
    asyncio.run(main())