"""Adapter for the secure gossip layer.

SafeGossipAdapter bridges legacy callers with ``GossipNode`` and ``CRDTAdapter``.
It starts the aiohttp gossip server, exposes health/metrics endpoints, and keeps
compatibility methods used by older node loops.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Final, Optional

import aiohttp
from aiohttp import web

from src.core.crdt_adapter import CRDTAdapter
from src.core.gossip_layer import DeltaPolicy, GossipConfig, GossipNode

logger = logging.getLogger(__name__)

DEFAULT_NODE_ID: Final[str] = str(uuid.uuid4())
DEFAULT_SECRET: Final[str] = "blackswan-dev-secret"


def _build_config_from_env() -> GossipConfig:
    """Build GossipConfig from environment variables."""
    return GossipConfig(
        node_id=os.environ.get("NODE_ID", DEFAULT_NODE_ID),
        port=int(os.environ.get("PORT", os.environ.get("GOSSIP_PORT", "8000"))),
        peers_csv=os.environ.get("PEERS", ""),
        shared_secret=os.environ.get("GOSSIP_SECRET", DEFAULT_SECRET),
        gossip_interval_s=float(os.environ.get("GOSSIP_INTERVAL", "1.5")),
    )


class SafeGossipAdapter:
    """Compatibility adapter around the secure GossipNode implementation."""

    __slots__ = (
        "node",
        "crdt_adapter",
        "reputation_manager",
        "_config",
        "_running",
        "_runner",
        "_site",
        "_background_tasks",
    )

    def __init__(
        self,
        crdt_adapter: CRDTAdapter,
        *,
        config: Optional[GossipConfig] = None,
        policy: Optional[DeltaPolicy] = None,
    ) -> None:
        if not isinstance(crdt_adapter, CRDTAdapter):
            raise TypeError("crdt_adapter must be an instance of CRDTAdapter")

        self.crdt_adapter = crdt_adapter
        self.reputation_manager: Any | None = None
        self._config = config or _build_config_from_env()
        self.node = GossipNode(self._config, policy=policy or DeltaPolicy(min_fitness=0.0))

        self._running = False
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._background_tasks: set[asyncio.Task[Any]] = set()

    def __repr__(self) -> str:
        return (
            f"SafeGossipAdapter(node_id={self._config.node_id!r}, "
            f"port={self._config.port}, peers={len(self._config.peers)}, "
            f"running={self._running})"
        )

    @property
    def running(self) -> bool:
        return self._running

    @property
    def config(self) -> GossipConfig:
        return self._config

    def set_reputation_manager(self, rep_man: Any) -> None:
        """Attach an optional reputation manager used by higher-level callers."""
        self.reputation_manager = rep_man

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Compatibility broadcast hook: add dict payloads to CRDT for gossip."""
        if not isinstance(message, dict):
            raise TypeError("message must be a dictionary")

        await self.crdt_adapter.add_genome(dict(message))

    def set_champion(self, genome: dict[str, Any]) -> None:
        """Compatibility hook used by legacy agents to publish a champion genome."""
        if not isinstance(genome, dict):
            raise TypeError("genome must be a dictionary")

        self._spawn_background_task(
            self.crdt_adapter.add_genome(dict(genome)),
            name="gossip_set_champion",
        )

    def pull_genomes(self) -> list[dict[str, Any]]:
        """Return current top genomes from local CRDT state."""
        state = self.crdt_adapter.state
        genomes = [
            dict(payload)
            for payload in state.values()
            if isinstance(payload, dict) and "params" in payload
        ]
        genomes.sort(key=lambda item: float(item.get("fitness", 0.0) or 0.0), reverse=True)
        return genomes

    async def gossip_round(self) -> None:
        """Run one explicit gossip sync round with an eligible peer."""
        if not self._config.peers:
            logger.debug("No peers configured for gossip_round.")
            return

        peer_url = self.node.protocol._choose_peer()
        if not peer_url:
            logger.debug("No eligible peer selected for gossip_round.")
            return

        timeout = aiohttp.ClientTimeout(total=float(self._config.request_timeout_s) + 1.0)
        logger.debug("Running explicit gossip round with peer=%s", peer_url)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            await self.node.protocol.sync_once(session, peer_url)

    async def start(self) -> None:
        """Start the gossip HTTP server."""
        if self._running:
            logger.debug("SafeGossipAdapter already running.")
            return

        app = self.node.build_app()
        self._add_route_if_missing(app, "GET", "/health", self._handle_health)
        self._add_route_if_missing(app, "GET", "/metrics", self._handle_metrics)

        self._runner = web.AppRunner(app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self._config.bind_host, self._config.port)
        await self._site.start()

        self._running = True
        logger.info(
            "SafeGossipAdapter started on %s:%s node_id=%s peers=%s",
            self._config.bind_host,
            self._config.port,
            self._config.node_id,
            len(self._config.peers),
        )

    async def stop(self) -> None:
        """Stop the gossip HTTP server and cancel adapter-owned tasks."""
        if not self._running and self._runner is None:
            return

        self._running = False

        for task in list(self._background_tasks):
            task.cancel()

        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()

        if self._site is not None:
            await self._site.stop()
            self._site = None

        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

        logger.info("SafeGossipAdapter stopped.")

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "ok" if self._running else "stopped",
                "node_id": self._config.node_id,
                "peers": len(self._config.peers),
            }
        )

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        try:
            from src.observability.metrics import collect_metrics, prometheus_format

            metrics = collect_metrics()
            body = prometheus_format(metrics)
            return web.Response(text=body, content_type="text/plain")
        except ImportError:
            logger.warning("Metrics module is not available.")
            return web.Response(
                text="metrics_unavailable 1\n",
                status=501,
                content_type="text/plain",
            )
        except Exception as exc:
            logger.exception("Metrics endpoint failed: %s", exc)
            return web.Response(
                text=f"metrics_error 1\n# {exc}\n",
                status=500,
                content_type="text/plain",
            )

    def _spawn_background_task(self, coro: Any, *, name: str) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("No running event loop; cannot schedule background task %s.", name)
            return

        task = loop.create_task(coro, name=name)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        def _log_failure(done: asyncio.Task[Any]) -> None:
            if done.cancelled():
                return
            exc = done.exception()
            if exc is not None:
                logger.exception("Background task %s failed: %s", name, exc)

        task.add_done_callback(_log_failure)

    @staticmethod
    def _add_route_if_missing(
        app: web.Application,
        method: str,
        path: str,
        handler: Any,
    ) -> None:
        for route in app.router.routes():
            resource = route.resource
            if getattr(resource, "canonical", None) == path and route.method == method:
                return

        app.router.add_route(method, path, handler)