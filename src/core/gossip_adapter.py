"""
Adapter for an industrial-grade gossip layer (HMAC, backoff, replay protection).
Replaces the old gossip_loop and peer_score without modifying node_agent.py.
"""
import asyncio
import os
import time
import uuid
import traceback
from typing import Dict, Optional, Any, List
import aiohttp
from aiohttp import web

import logging
logger = logging.getLogger(__name__)

from src.core.gossip_layer import (
    GossipConfig,
    GossipNode,
    DeltaPolicy,
    GossipEnvelope,
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
    Replaces:
      - pubsub + r.publish(...) for genomes
      - old gossip_loop + peer_score
    with a secure GossipNode.
    """

    node: GossipNode
    _known_versions: Dict[str, Dict[str, int]]
    _running: bool
    reputation_manager: Optional[Any] # Type can be more specific if ReputationManager class is available

    def __init__(self, crdt_adapter: CRDTAdapter) -> None:
        """
        Initializes the SafeGossipAdapter.

        Args:
            crdt_adapter: An instance of CRDTAdapter to manage state synchronization.
        """
        self.crdt_adapter = crdt_adapter
        self.node = GossipNode(CFG, policy=DeltaPolicy(min_fitness=0.0))
        self._known_versions = {}
        self._running = False
        self.reputation_manager = None
        
    def set_reputation_manager(self, rep_man: Any) -> None:
        """
        Sets the reputation manager for the adapter.

        Args:
            rep_man: An object representing the reputation manager.
                     Type is `Any` if a specific class is not available/imported.
        """
        self.reputation_manager = rep_man

    # ----- Methods called by node_agent.py -----

    def set_champion(self, genome: Dict[str, Any]) -> None:
        """
        Saves a champion genome to the CRDT and prepares it for gossip publication.
        Called by node_agent.py when a new champion emerges.

        Args:
            genome: A dictionary representing the champion genome.
        """
        # Save the genome locally (asynchronously, node_agent.py does not wait)
        asyncio.create_task(self.crdt_adapter.add_genome(genome))
        # Publication will happen automatically on the next gossip cycle
        # because the new genome is already in CRDT.

    def pull_genomes(self) -> List[Dict[str, Any]]:
        """
        Returns a list of genomes received from peers.
        Called by node_agent.py in its main loop.

        Note: For simplicity, this currently returns an empty list, as the
        integration logic for genomes will directly retrieve them from
        `crdt_adapter.get_top()`.

        Returns:
            An empty list of genomes.
        """
        # Retrieve fresh genomes from CRDT (all except those already present?)
        # For simplicity: return an empty list, as integrate will
        # retrieve genomes directly from crdt_adapter.get_top().
        return []

    async def gossip_round(self) -> None:
        """
        Executes a single round of gossip: selects a peer and exchanges genomes.
        Called periodically (e.g., every 50 steps) by node_agent.py.
        """
        if not CFG.peers:
            return

        # Create a session and perform sync_once with one peer
        async with aiohttp.ClientSession() as session:
            # Select the first peer (could be improved to be random)
            peer: str = CFG.peers[0]
            try:
                # Form an envelope with our delta
                our_versions: Dict[str, int] = await self.crdt_adapter.get_versions()
                our_delta: Dict[str, Any] = await self.crdt_adapter.get_delta(
                    self._known_versions.get(peer, {})
                )
                envelope: GossipEnvelope = GossipEnvelope(
                    sender=CFG.node_id,
                    ts=time.time(),
                    nonce=uuid.uuid4().hex,
                    versions=our_versions,
                    delta=our_delta,
                )
                envelope.sign(CFG.secret_bytes)

                async with session.post(
                    f"http://{peer}/gossip",
                    json=envelope.to_dict(),
                    timeout=CFG.request_timeout_s
                ) as resp:
                    if resp.status == 200:
                        data: Dict[str, Any] = await resp.json()
                        remote_delta: Dict[str, Any] = data.get("delta", {})
                        if remote_delta:
                            await self.crdt_adapter.merge(remote_delta)
                        # Update the peer's known versions
                        self._known_versions[peer] = data.get("versions", {})
            except Exception as e:
                # Log specific error for better debugging
                logger.warning(f"Gossip round with peer {peer} failed: {e}")
                pass  # Peer unavailable – continue

    # ----- Health endpoint -----
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

        # Start the background gossip loop
        asyncio.create_task(self._gossip_loop())

    async def _gossip_loop(self) -> None:
        """
        Background loop for periodically performing gossip rounds.
        Continues as long as the adapter is running (`_running` is True).
        """
        while self._running:
            await self.gossip_round()
            await asyncio.sleep(CFG.gossip_interval_s)

    async def stop(self) -> None:
        """
        Stops the background gossip loop by setting the `_running` flag to False.
        """
        self._running = False
    
    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """
        HTTP request handler for serving metrics in Prometheus format.

        Args:
            request: The aiohttp web request object.

        Returns:
            A text response with metrics data in Prometheus format.
            Returns a 500 error response if metrics collection fails.
        """
        try:
            from src.observability.metrics import collect_metrics, prometheus_format
            metrics: Dict[str, Any] = collect_metrics()
            body: str = prometheus_format(metrics)
            return web.Response(text=body, content_type="text/plain", charset="utf-8")
        except Exception as e:
            logger.error(f"Metrics endpoint failed: {traceback.format_exc()}")
            return web.Response(text=f"Error: {e}", status=500, content_type="text/plain")
