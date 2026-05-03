# src/memory/quarantine.py
"""
Quarantine buffer for incoming MemoryRecords.
Validates signature, sender reputation, and confidence before storing.
"""
import logging
from typing import Any, Dict, Optional
from src.memory.local_memory import MemoryRecord, LocalMemoryAPI
from src.security.crypto_manager import CryptoManager
from src.security.reputation_manager import ReputationManager

logger = logging.getLogger(__name__)

class QuarantineBuffer:
    """Фильтр для входящих записей. Принимает решение, можно ли сохранить запись в память."""

    def __init__(self, memory_api: LocalMemoryAPI, reputation: ReputationManager):
        self.memory = memory_api
        self.reputation = reputation

    async def process(self, raw: Dict[str, Any]) -> bool:
        """
        Проверяет и сохраняет входящий MemoryRecord.
        Возвращает True, если запись принята.
        """
        # 1. Преобразуем в объект MemoryRecord
        try:
            record = MemoryRecord(**raw)
        except Exception as e:
            logger.warning(f"Quarantine: invalid record format: {e}")
            return False

        # 2. Проверка confidence
        if record.confidence < 0.3:
            logger.warning(f"Quarantine: low confidence {record.confidence}, discarding")
            return False

        # 3. Проверка подписи, если есть
        if record.signature:
            pubkey_hex = record.source.get("origin_pubkey")
            if not pubkey_hex:
                logger.warning("Quarantine: signature without pubkey, discarding")
                return False

            # Используем CryptoManager для проверки
            payload = {"payload": record.payload, "kind": record.kind, "scope": record.scope}
            if not CryptoManager.verify(payload, record.signature, pubkey_hex):
                logger.warning("Quarantine: signature verification failed")
                return False

        # 4. Проверка репутации отправителя
        origin_node = record.source.get("origin_node_id") or record.source.get("originNodeId")
        origin_pubkey = record.source.get("origin_pubkey")
        if origin_node or origin_pubkey:
            pubkey_to_check = origin_pubkey or origin_node
            if not self.reputation.is_trusted(pubkey_to_check):
                logger.warning(f"Quarantine: untrusted source {pubkey_to_check}, discarding")
                return False

        # 5. Сохраняем в память
        record.verified = True
        await self.memory.remember(record)
        logger.debug(f"Quarantine: accepted record {record.id} from {origin_node}")
        return True