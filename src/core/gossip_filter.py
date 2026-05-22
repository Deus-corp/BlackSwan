"""
Gossip message filter: replay protection, monotonic sequence numbers, timestamp validation.

This module provides a robust `GossipFilter` class used to validate incoming gossip
messages by checking for replayed nonces, non-monotonic sequence numbers, and 
expired or clock-skewed timestamps.
"""
import time
import logging
from collections import deque
from typing import Dict, Deque, Set, Optional, Final

logger: Final = logging.getLogger(__name__)

class GossipFilter:
    """
    Validates incoming gossip messages to prevent replay and out-of-order delivery.

    Attributes:
        max_clock_skew_ms: Maximum allowed deviation from system clock in milliseconds.
        max_nonce_cache: Maximum number of nonces tracked per sender.
        _seen_nonces: Internal map of sender ID to a set of recent nonces.
        _last_seq: Internal map of sender ID to the last accepted sequence number.
    """

    __slots__ = ("max_clock_skew_ms", "max_nonce_cache", "_seen_nonces", "_last_seq")

    def __init__(self, max_clock_skew_ms: int = 10_000, max_nonce_cache: int = 10_000) -> None:
        self.max_clock_skew_ms: int = max_clock_skew_ms
        self.max_nonce_cache: int = max_nonce_cache
        self._seen_nonces: Dict[str, Set[str]] = {}
        self._last_seq: Dict[str, int] = {}

    def check(
        self, 
        sender_node_id: str, 
        nonce: Optional[str], 
        seq_no: Optional[int],
        timestamp_ms: Optional[int], 
        ttl_ms: Optional[int] = None
    ) -> bool:
        """
        Validates message metadata for security and ordering.

        Args:
            sender_node_id: Unique identifier for the sending node.
            nonce: Unique message identifier used for replay protection.
            seq_no: Monotonic sequence number for ordering.
            timestamp_ms: Epoch time of message creation.
            ttl_ms: Duration for which the message is considered valid.

        Returns:
            True if the message passes all security/ordering checks, False otherwise.
        """
        now_ms: int = int(time.time() * 1000)

        # 1. Temporal Validation
        if timestamp_ms is not None:
            # Check for messages from the future or too far in the past
            skew = abs(now_ms - timestamp_ms)
            if skew > self.max_clock_skew_ms:
                logger.debug("Gossip rejection: skew %d ms exceeds limit for %s", skew, sender_node_id)
                return False

            # Expiration check via TTL
            if ttl_ms is not None and now_ms > (timestamp_ms + ttl_ms):
                logger.debug("Gossip rejection: expired message from %s", sender_node_id)
                return False

        # 2. Replay Protection (Nonce)
        if nonce is not None:
            seen = self._seen_nonces.setdefault(sender_node_id, set())
            if nonce in seen:
                logger.debug("Gossip rejection: replay detected from %s (nonce: %s)", sender_node_id, nonce)
                return False
            
            if len(seen) >= self.max_nonce_cache:
                seen.clear()
            seen.add(nonce)

        # 3. Ordering Protection (Monotonic Sequence)
        if seq_no is not None:
            last_seq = self._last_seq.get(sender_node_id, -1)
            if seq_no <= last_seq:
                logger.debug("Gossip rejection: seq_no %d not monotonic for %s", seq_no, sender_node_id)
                return False
            self._last_seq[sender_node_id] = seq_no

        return True

    def reset(self, sender_node_id: str) -> None:
        """
        Clears the state for a specific sender to handle node restarts or state desync.
        """
        self._seen_nonces.pop(sender_node_id, None)
        self._last_seq.pop(sender_node_id, None)
        logger.info("GossipFilter state reset for sender: %s", sender_node_id)