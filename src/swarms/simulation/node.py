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
from typing import Optional

from src.core.crdt_adapter import CRDTAdapter
from src.swarms.simulation.heartbeat import build_simulation_heartbeat
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
        self.last_error = ""

        logger.info(
            "SimulationSwarmNode initialized node_id=%s heartbeat_interval=%.1fs",
            self.node_id,
            self.heartbeat_interval_seconds,
        )

    async def publish_heartbeat(self) -> None:
        """Publish canonical simulation swarm heartbeat."""
        payload = build_simulation_heartbeat(
            self.node_id,
            metrics={
                "heartbeats_published": self.heartbeats_published,
                "scenarios_run": self.scenarios_run,
                "policy_evaluations": 0,
                "stress_tests": 0,
            },
            details={
                "last_error": self.last_error,
                "crdt_db_path": str(config.crdt_db_path),
            },
            status="running" if not self.last_error else "degraded",
        )

        await self.crdt.add_genome(payload)
        self.heartbeats_published += 1
        logger.info(
            "[%s] Published simulation swarm heartbeat count=%d",
            self.node_id,
            self.heartbeats_published,
        )

    async def start(self) -> None:
        """Run heartbeat loop until stopped."""
        logger.info("SimulationSwarmNode %s starting.", self.node_id)

        self._install_signal_handlers()

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