"""
Adapter for an industrial-grade gossip layer (HMAC, backoff, replay protection).
Replaces the old gossip_loop and peer_score without modifying node_agent.py.
"""
import asyncio
import os
import time
import uuid
import traceback
from typing import Any
import aiohttp
from aiohttp import web

import logging
logger = logging.getLogger(__name__)

from src.core.gossip_layer import (
    GossipConfig,
    GossipNode,
    DeltaPolicy,
    # GossipEnvelope, # No longer needed here as GossipNode handles envelope creation
)
from src.core.crdt_adapter import CRDTAdapter  # Our new CRDT

# Configuration from environment variables
CFG: GossipConfig = GossipConfig(
    node_id=os.environ.get("NODE_ID", str(uuid.uuid4())),
    port=int(os.environ.get("PORT", "8000")),
    peers_csv=os.environ.get("PEERS", ""),
    shared_secret=os.environ.get("GOSSIP_SECRET", "blackswan-dev-secret"),
    gossip_interval_s=float(os.environ.get("GOSSIP_INTERVAL", "1.5")),
)

class SafeGossipAdapter:
    """
    Adapter to integrate the secure GossipNode with existing system components.

    It replaces the previous pubsub, old gossip_loop, and peer_score mechanisms,
    providing a modern, secure, and robust gossip layer. It allows `node_agent.py`
    to interact with the gossip system without direct knowledge of the underlying
    GossipNode implementation.
    """

    __slots__ = ('node', '_running', 'reputation_manager', 'crdt_adapter')

    node: GossipNode
    _running: bool
    reputation_manager: Any | None # Type can be more specific if ReputationManager class is available
    crdt_adapter: CRDTAdapter

    def __init__(self, crdt_adapter: CRDTAdapter) -> None:
        """
        Initializes the SafeGossipAdapter.

        Args:
            crdt_adapter: An instance of CRDTAdapter to manage state synchronization.

        Raises:
            TypeError: If `crdt_adapter` is not an instance of `CRDTAdapter`.
        """
        if not isinstance(crdt_adapter, CRDTAdapter):
            raise TypeError("crdt_adapter must be an instance of CRDTAdapter.")

        self.crdt_adapter = crdt_adapter
        # The GossipNode itself manages peers, state, and its own background sync loop.
        # The DeltaPolicy is configured here, or can be passed from the CRDTAdapter if it has one.
        self.node = GossipNode(CFG, policy=DeltaPolicy(min_fitness=0.0))
        self._running = False
        self.reputation_manager = None
        
    def __repr__(self) -> str:
        """
        Returns a string representation of the SafeGossipAdapter object.
        """
        node_id_prefix = self.node.node_id[:8] if self.node.node_id else "None"
        return f"SafeGossipAdapter(node_id_prefix={node_id_prefix}, running={self._running})"

    def set_reputation_manager(self, rep_man: Any) -> None:
        """
        Sets the reputation manager for the adapter.

        Args:
            rep_man: An object representing the reputation manager.
                     Type is `Any` if a specific class is not available/imported.
        """
        self.reputation_manager = rep_man

    async def broadcast(self, message: dict[str, Any]) -> None:
        """
        Alias for a broadcast mechanism. In this adapter's design, direct, immediate
        "broadcasts" of arbitrary messages are not exposed. Genomes are added to
        the CRDT and then gossiped on the next cycle by the background sync loop.
        This method is kept as a stub to preserve external API compatibility with
        `node_agent.py`, but it currently has no effect for immediate message dissemination.

        Args:
            message: The message to be broadcasted. Currently ignored.

        Raises:
            TypeError: If `message` is not a dictionary.
        """
        if not isinstance(message, dict):
            raise TypeError("Message for broadcast must be a dictionary.")

        logger.warning(
            "SafeGossipAdapter.broadcast() called but direct immediate broadcast "
            "of arbitrary messages is not implemented. Genomes are added to CRDT "
            "and gossiped automatically."
        )
        # If immediate broadcast of specific messages (not genomes) were needed,
        # one would implement logic here to wrap the message in a GossipEnvelope
        # and send it to all peers. However, the current design assumes genomes
        # are managed via CRDT and propagate through the standard gossip cycle.

    # ----- Methods called by node_agent.py -----

    def set_champion(self, genome: dict[str, Any]) -> None:
        """
        Saves a champion genome to the CRDT and prepares it for gossip publication.
        Called by node_agent.py when a new champion emerges.

        Args:
            genome: A dictionary representing the champion genome.

        Raises:
            TypeError: If `genome` is not a dictionary.
        """
        if not isinstance(genome, dict):
            raise TypeError("Genome for champion must be a dictionary.")

        # Save the genome locally (asynchronously, node_agent.py does not wait)
        asyncio.create_task(self.crdt_adapter.add_genome(genome))
        # Publication will happen automatically on the next gossip cycle
        # because the new genome is already in CRDT.

    def pull_genomes(self) -> list[dict[str, Any]]:
        """
        Returns a list of genomes received from peers.
        Called by node_agent.py in its main loop.

        Note: For simplicity, this currently returns an empty list. The actual
        integration logic for genomes is expected to directly retrieve them from
        `crdt_adapter.get_top()` or other CRDT mechanisms by `node_agent.py` itself,
        as the adapter merely ensures state convergence.

        Returns:
            An empty list of genomes, as the calling system is expected to query the CRDT directly.
        """
        # Node_agent.py is expected to retrieve genomes directly from crdt_adapter.get_top().
        # This method serves as a compatibility stub.
        return []

    async def gossip_round(self) -> None:
        """
        Executes a single, on-demand gossip synchronization round with one peer.
        This method is called periodically (e.g., every 50 steps) by node_agent.py.
        It leverages the underlying GossipNode's protocol to select a peer and
        perform a sync, ensuring proper state management (backoff, scoring, etc.).

        Note: The GossipNode also runs its own continuous background sync loop.
        This method provides an additional, explicit trigger for `node_agent.py`.
        """
        if not CFG.peers:
            logger.debug("No peers configured for gossip_round.")
            return

        # Use the underlying GossipProtocol to select a peer and perform a sync.
        # This ensures peer metrics, backoff, and state management are consistent.
        peer_url: str | None = self.node.protocol._choose_peer()

        if peer_url:
            logger.debug(f"Node_agent-triggered gossip_round with peer: {peer_url}")
            # ClientSession should be created per request if not managed globally,
            # especially for single, on-demand calls.
            # Use the same timeout as the main gossip loop.
            timeout = aiohttp.ClientTimeout(total=CFG.request_timeout_s + 1.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                await self.node.protocol.sync_once(session, peer_url)
        else:
            logger.debug("No eligible peer selected for node_agent-triggered gossip_round (all might be in backoff).")

    # ----- HTTP endpoints and lifecycle -----

    async def _handle_health(self, request: web.Request) -> web.Response:
        """
        HTTP request handler for checking the node's health status.

        Args:
            request: The aiohttp web request object.

        Returns:
            A JSON response with status "ok".
        """
        return web.json_response({"status": "ok"})

    async def start(self) -> None:
        """
        Starts the HTTP server and the background gossip loop
        (replaces run_server + gossip_loop).
        The GossipNode's internal background sync loop will handle continuous gossiping.
        """
        app: web.Application = self.node.build_app()
        # Add routes for health and metrics
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/metrics", self._handle_metrics)
        
        runner: web.AppRunner = web.AppRunner(app)
        await runner.setup()
        site: web.TCPSite = web.TCPSite(runner, CFG.bind_host, CFG.port)
        await site.start()
        self._running = True
        logger.info(f"SafeGossipAdapter started HTTP server on {CFG.bind_host}:{CFG.port}")

        # The GossipNode itself manages its continuous background sync loop (self.node.protocol.sync_loop).
        # We removed the redundant _gossip_loop here.

    async def stop(self) -> None:
        """
        Stops the SafeGossipAdapter components.
        For now, this primarily means setting the `_running` flag to False.
        The underlying GossipNode's `on_cleanup` hook handles cancellation of its
        background tasks when the aiohttp app stops.
        """
        self._running = False
        logger.info("SafeGossipAdapter stop requested. The aiohttp app will handle GossipNode cleanup.")
    
    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """
        HTTP request handler for serving metrics in Prometheus format.
        This method dynamically imports the metrics collection module.

        Args:
            request: The aiohttp web request object.

        Returns:
            A text response with metrics data in Prometheus format.
            Returns a 500 error response if metrics collection fails.
        """
        try:
            # Dynamic import to avoid hard dependency if observability is optional
            from src.observability.metrics import collect_metrics, prometheus_format
            metrics: dict[str, Any] = collect_metrics()
            body: str = prometheus_format(metrics)
            return web.Response(text=body, content_type="text/plain", charset="utf-8")
        except ImportError:
            logger.error("Metrics module 'src.observability.metrics' not found. Cannot serve metrics.")
            return web.Response(text="Metrics module not available.", status=501, content_type="text/plain")
        except Exception as e:
            logger.error(f"Metrics endpoint failed: {traceback.format_exc()}")
            return web.Response(text=f"Error collecting metrics: {e}", status=500, content_type="text/plain")