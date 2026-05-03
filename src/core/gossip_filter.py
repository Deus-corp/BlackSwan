# src/core/gossip_filter.py
"""
Gossip message filter: replay protection, monotonic sequence numbers, timestamp validation.
"""
import time
import logging
from typing import Dict, Set

logger = logging.getLogger(__name__)

class GossipFilter:
    """
    Проверяет каждое входящее gossip-сообщение (независимо от типа).
    Хранит seen-кэш nonces и последние seq_no для каждого отправителя.
    """

    def __init__(self, max_clock_skew_ms: int = 10_000):
        self.max_clock_skew_ms = max_clock_skew_ms
        self._seen_nonces: Dict[str, Set[str]] = {}   # sender_node_id -> set of nonces
        self._last_seq: Dict[str, int] = {}            # sender_node_id -> last seq_no

    def check(self, sender_node_id: str, nonce: Optional[str], seq_no: Optional[int],
              timestamp_ms: Optional[int], ttl_ms: Optional[int] = None) -> bool:
        """
        Проверяет сообщение по криптографическим и временным меткам.
        Возвращает True, если сообщение можно принять.
        """
        now_ms = int(time.time() * 1000)

        # 1. Проверка срока действия (если указан ttl и timestamp)
        if timestamp_ms is not None and ttl_ms is not None:
            expires_at = timestamp_ms + ttl_ms
            if now_ms > expires_at:
                logger.debug("Gossip message expired")
                return False
            if timestamp_ms > now_ms + self.max_clock_skew_ms:
                logger.debug("Gossip message from too far future")
                return False

        # 2. Replay protection по nonce (если nonce указан)
        if nonce is not None:
            seen = self._seen_nonces.setdefault(sender_node_id, set())
            if nonce in seen:
                logger.debug("Replay nonce detected for %s", sender_node_id)
                return False
            seen.add(nonce)
            # Ограничиваем размер кэша (опционально)
            if len(seen) > 10000:
                # Простейшая очистка: удаляем половину старых (нет порядка, но для безопасности)
                seen.clear()  # или более сложный LRU, пока сбросим

        # 3. Монотонный seq_no (если указан)
        if seq_no is not None:
            last = self._last_seq.get(sender_node_id, -1)
            if seq_no <= last:
                logger.debug("Non-monotonic seq_no from %s: %d <= %d", sender_node_id, seq_no, last)
                return False
            self._last_seq[sender_node_id] = seq_no

        return True

    def reset(self, sender_node_id: str):
        """Сбросить состояние для конкретного отправителя (при перезапуске)."""
        self._seen_nonces.pop(sender_node_id, None)
        self._last_seq.pop(sender_node_id, None)