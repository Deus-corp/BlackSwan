"""Gossip message filter with replay, sequence, and timestamp protection."""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from typing import Final, Optional

logger: Final = logging.getLogger(__name__)


class GossipFilter:
    """Validate incoming gossip metadata before payload processing."""

    __slots__ = (
        "max_clock_skew_ms",
        "max_nonce_cache",
        "_seen_nonces",
        "_last_seq",
    )

    def __init__(self, max_clock_skew_ms: int = 10_000, max_nonce_cache: int = 10_000) -> None:
        self.max_clock_skew_ms = max(0, int(max_clock_skew_ms))
        self.max_nonce_cache = max(1, int(max_nonce_cache))
        self._seen_nonces: dict[str, OrderedDict[str, None]] = {}
        self._last_seq: dict[str, int] = {}

    def check(
        self,
        sender_node_id: str,
        nonce: Optional[str],
        seq_no: Optional[int],
        timestamp_ms: Optional[int],
        ttl_ms: Optional[int] = None,
    ) -> bool:
        """Return True when a gossip message passes replay/order/time checks."""
        sender = str(sender_node_id or "").strip()
        if not sender:
            logger.debug("Gossip rejection: missing sender_node_id")
            return False

        now_ms = int(time.time() * 1000)

        if timestamp_ms is not None and not self._check_timestamp(
            sender=sender,
            timestamp_ms=timestamp_ms,
            ttl_ms=ttl_ms,
            now_ms=now_ms,
        ):
            return False

        if nonce is not None and not self._check_nonce(sender=sender, nonce=nonce):
            return False

        if seq_no is not None and not self._check_sequence(sender=sender, seq_no=seq_no):
            return False

        return True

    def reset(self, sender_node_id: str) -> None:
        """Clear cached replay/order state for one sender."""
        sender = str(sender_node_id or "").strip()
        if not sender:
            return

        self._seen_nonces.pop(sender, None)
        self._last_seq.pop(sender, None)
        logger.info("GossipFilter state reset for sender=%s", sender)

    def clear(self) -> None:
        """Clear all cached replay/order state."""
        self._seen_nonces.clear()
        self._last_seq.clear()
        logger.info("GossipFilter state cleared.")

    def stats(self) -> dict[str, int]:
        """Return lightweight cache statistics."""
        return {
            "senders_with_nonces": len(self._seen_nonces),
            "senders_with_sequences": len(self._last_seq),
            "nonce_count": sum(len(items) for items in self._seen_nonces.values()),
            "max_nonce_cache": self.max_nonce_cache,
            "max_clock_skew_ms": self.max_clock_skew_ms,
        }

    def _check_timestamp(
        self,
        *,
        sender: str,
        timestamp_ms: int,
        ttl_ms: Optional[int],
        now_ms: int,
    ) -> bool:
        try:
            ts = int(timestamp_ms)
        except (TypeError, ValueError):
            logger.debug("Gossip rejection: invalid timestamp from %s: %r", sender, timestamp_ms)
            return False

        skew = abs(now_ms - ts)
        if skew > self.max_clock_skew_ms:
            logger.debug(
                "Gossip rejection: clock skew %sms exceeds limit %sms for %s",
                skew,
                self.max_clock_skew_ms,
                sender,
            )
            return False

        if ttl_ms is not None:
            try:
                ttl = int(ttl_ms)
            except (TypeError, ValueError):
                logger.debug("Gossip rejection: invalid ttl from %s: %r", sender, ttl_ms)
                return False

            if ttl < 0:
                logger.debug("Gossip rejection: negative ttl from %s: %s", sender, ttl)
                return False

            if now_ms > ts + ttl:
                logger.debug("Gossip rejection: expired message from %s", sender)
                return False

        return True

    def _check_nonce(self, *, sender: str, nonce: str) -> bool:
        clean_nonce = str(nonce or "").strip()
        if not clean_nonce:
            logger.debug("Gossip rejection: empty nonce from %s", sender)
            return False

        seen = self._seen_nonces.setdefault(sender, OrderedDict())
        if clean_nonce in seen:
            logger.debug("Gossip rejection: replay from %s nonce=%s", sender, clean_nonce)
            return False

        seen[clean_nonce] = None
        seen.move_to_end(clean_nonce)

        while len(seen) > self.max_nonce_cache:
            seen.popitem(last=False)

        return True

    def _check_sequence(self, *, sender: str, seq_no: int) -> bool:
        try:
            seq = int(seq_no)
        except (TypeError, ValueError):
            logger.debug("Gossip rejection: invalid seq_no from %s: %r", sender, seq_no)
            return False

        if seq < 0:
            logger.debug("Gossip rejection: negative seq_no from %s: %s", sender, seq)
            return False

        last_seq = self._last_seq.get(sender, -1)
        if seq <= last_seq:
            logger.debug(
                "Gossip rejection: non-monotonic seq_no from %s seq=%s last=%s",
                sender,
                seq,
                last_seq,
            )
            return False

        self._last_seq[sender] = seq
        return True