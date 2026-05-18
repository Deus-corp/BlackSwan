# src/core/gossip_filter.py
"""
Gossip message filter: replay protection, monotonic sequence numbers, timestamp validation.
"""
import time
import logging
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)

class GossipFilter:
    """
    Проверяет каждое входящее gossip-сообщение (независимо от типа).
    Хранит seen-кэш nonces и последние seq_no для каждого отправителя.
    """

    _seen_nonces: Dict[str, Set[str]] # Added type hint for instance variable
    _last_seq: Dict[str, int] # Added type hint for instance variable

    def __init__(self, max_clock_skew_ms: int = 10_000):
        self.max_clock_skew_ms = max_clock_skew_ms
        self._seen_nonces: Dict[str, Set[str]] = {}   # sender_node_id -> set of nonces
        self._last_seq: Dict[str, int] = {}            # sender_node_id -> last seq_no

    def check(self, sender_node_id: str, nonce: Optional[str], seq_no: Optional[int],
              timestamp_ms: Optional[int], ttl_ms: Optional[int] = None) -> bool:
        """
        Проверяет сообщение по криптографическим и временным меткам.
        Возвращает True, если сообщение можно принять.

        :param sender_node_id: Идентификатор узла-отправителя сообщения.
        :param nonce: Одноразовый номер (nonce) для защиты от повторной отправки.
        :param seq_no: Последовательный номер для обеспечения монотонности.
        :param timestamp_ms: Метка времени сообщения в миллисекундах.
        :param ttl_ms: Время жизни сообщения в миллисекундах (если указано).
        :return: True, если сообщение прошло все проверки, иначе False.
        """
        now_ms: int = int(time.time() * 1000)

        # 1. Проверка срока действия (если указан ttl и timestamp)
        if timestamp_ms is not None and ttl_ms is not None:
            expires_at: int = timestamp_ms + ttl_ms
            if now_ms > expires_at:
                logger.debug("Gossip message expired (now: %d ms, expires: %d ms)", now_ms, expires_at)
                return False
            # Check for messages from too far in the future
            if timestamp_ms > now_ms + self.max_clock_skew_ms:
                logger.debug("Gossip message from too far future (skew: %d ms, max_skew: %d ms)", timestamp_ms - now_ms, self.max_clock_skew_ms)
                return False

        # 2. Replay protection по nonce (если nonce указан)
        if nonce is not None:
            seen: Set[str] = self._seen_nonces.setdefault(sender_node_id, set())
            if nonce in seen:
                logger.debug("Replay nonce detected for %s: %s", sender_node_id, nonce)
                return False
            seen.add(nonce)
            # Ограничиваем размер кэша (опционально)
            if len(seen) > 10000:
                # Простейшая очистка: удаляем половину старых (нет порядка, но для безопасности)
                # Note: Current implementation clears the entire set, not just half.
                logger.warning("Nonce cache for sender %s exceeded 10000 entries, clearing it.", sender_node_id)
                seen.clear()  # или более сложный LRU, пока сбросим

        # 3. Монотонный seq_no (если указан)
        if seq_no is not None:
            last: int = self._last_seq.get(sender_node_id, -1)
            if seq_no <= last:
                logger.debug("Non-monotonic seq_no from %s: %d <= %d (last_seq: %d)", sender_node_id, seq_no, last, last)
                return False
            self._last_seq[sender_node_id] = seq_no

        return True

    def reset(self, sender_node_id: str) -> None: # Added return type hint
        """Сбросить состояние для конкретного отправителя (при перезапуске)."""
        self._seen_nonces.pop(sender_node_id, None)
        self._last_seq.pop(sender_node_id, None)