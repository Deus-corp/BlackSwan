"""
Gossip message filter: replay protection, monotonic sequence numbers, timestamp validation.

This module provides a standalone `GossipFilter` class that can be used to check
the validity of incoming gossip messages based on nonce, sequence number, and timestamp.
It helps prevent message replays and ensures message order for a given sender.
"""
import time
import logging
from typing import Dict, Optional, Set, Tuple

logger = logging.getLogger(__name__)

class GossipFilter:
    """
    Checks each incoming gossip message (regardless of type).
    Stores a 'seen' cache for nonces and the last sequence number for each sender.

    Attributes:
        max_clock_skew_ms: The maximum allowed clock skew in milliseconds.
        _seen_nonces: A dictionary mapping sender_node_id to a set of seen nonces.
        _last_seq: A dictionary mapping sender_node_id to its last received sequence number.
    """

    _seen_nonces: Dict[str, Set[str]]
    _last_seq: Dict[str, int]

    def __init__(self, max_clock_skew_ms: int = 10_000) -> None:
        """
        Initializes the GossipFilter.

        Args:
            max_clock_skew_ms: The maximum allowed clock skew in milliseconds
                               between sender and receiver timestamps. Defaults to 10 seconds.
        """
        self.max_clock_skew_ms = max_clock_skew_ms
        self._seen_nonces = {}   # sender_node_id -> set of nonces
        self._last_seq = {}            # sender_node_id -> last seq_no

    def check(self, sender_node_id: str, nonce: Optional[str], seq_no: Optional[int],
              timestamp_ms: Optional[int], ttl_ms: Optional[int] = None) -> bool:
        """
        Checks a message based on cryptographic nonce for replay protection,
        monotonic sequence numbers, and temporal timestamps.
        Returns True if the message can be accepted based on these criteria.

        Args:
            sender_node_id: The ID of the message sender node.
            nonce: A single-use number (nonce) for replay protection. Can be None.
            seq_no: A sequential number to ensure monotonicity. Can be None.
            timestamp_ms: The message's timestamp in milliseconds (Unix epoch). Can be None.
            ttl_ms: The Time-To-Live of the message in milliseconds (if specified). Can be None.

        Returns:
            True if the message passed all checks, False otherwise.
        """
        now_ms: int = int(time.time() * 1000)

        # 1. Expiration check (if ttl and timestamp are specified)
        if timestamp_ms is not None and ttl_ms is not None:
            expires_at: int = timestamp_ms + ttl_ms
            if now_ms > expires_at:
                logger.debug(
                    "Gossip message from %s expired (now: %d ms, expires: %d ms)",
                    sender_node_id, now_ms, expires_at
                )
                return False
            # Check for messages from too far in the future
            if timestamp_ms > now_ms + self.max_clock_skew_ms:
                logger.debug(
                    "Gossip message from %s from too far future (skew: %d ms, max_skew: %d ms)",
                    sender_node_id, timestamp_ms - now_ms, self.max_clock_skew_ms
                )
                return False
            # Check for messages too old, even if not expired by TTL
            if timestamp_ms < now_ms - self.max_clock_skew_ms:
                logger.debug(
                    "Gossip message from %s is too old (skew: %d ms, max_skew: %d ms)",
                    sender_node_id, now_ms - timestamp_ms, self.max_clock_skew_ms
                )
                return False


        # 2. Replay protection using nonce (if nonce is specified)
        if nonce is not None:
            seen: Set[str] = self._seen_nonces.setdefault(sender_node_id, set())
            if nonce in seen:
                logger.debug("Replay nonce detected for %s: %s", sender_node_id, nonce)
                return False
            seen.add(nonce)
            # Optionally limit cache size for this sender
            if len(seen) > 10000:
                # Simple cleanup: clear the entire set.
                # A more sophisticated LRU or rolling window might be preferred
                # to avoid potential replay issues immediately after a cache clear.
                # For high-volume systems, this should be a more robust LRU cache.
                logger.warning(
                    "Nonce cache for sender %s exceeded 10000 entries, clearing it. "
                    "Consider a more robust LRU cache if replay protection is critical over long periods.",
                    sender_node_id
                )
                seen.clear()

        # 3. Monotonic sequence number (if specified)
        if seq_no is not None:
            last: int = self._last_seq.get(sender_node_id, -1)
            if seq_no <= last:
                logger.debug(
                    "Non-monotonic seq_no from %s: %d <= %d (last_seq: %d)",
                    sender_node_id, seq_no, last, last
                )
                return False
            self._last_seq[sender_node_id] = seq_no

        return True

    def reset(self, sender_node_id: str) -> None:
        """
        Resets the state (seen nonces and last sequence number) for a specific sender.
        This might be called upon detecting a sender restart or a significant protocol error.

        Args:
            sender_node_id: The ID of the sender node for which to reset the state.
        """
        self._seen_nonces.pop(sender_node_id, None)
        self._last_seq.pop(sender_node_id, None)
        logger.info(f"GossipFilter state reset for sender: {sender_node_id}")