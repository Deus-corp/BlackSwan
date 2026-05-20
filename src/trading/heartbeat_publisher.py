"""Heartbeat publisher for trade nodes."""
import logging

logger = logging.getLogger(__name__)


class HeartbeatPublisher:
    """Publishes trade node heartbeats to CRDT."""

    def __init__(self, node_id: str, crdt=None):
        self.node_id = node_id
        self.crdt = crdt

    async def publish(self) -> None:
        """Publish a heartbeat. Placeholder implementation."""
        logger.debug("Heartbeat published for %s", self.node_id)
