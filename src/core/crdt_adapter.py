"""
Адаптер, который заменяет CRDTState на GenomeCRDT с SQLite‑персистентностью.
Совместим с текущим node_agent.py.
"""
import asyncio
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Union

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.core.crdt_layer import CRDTStorage, GenomeCRDT
from src.core.gossip_filter import GossipFilter
from src.security.gossip_envelope import GossipEnvelope, b64decode, verify_envelope
from swarm_config import config

logger = logging.getLogger(__name__)

# Forward declaration for QuarantineBuffer to avoid circular imports at module level
class QuarantineBuffer:
    """
    Dummy class for type hinting QuarantineBuffer, which is imported conditionally
    to prevent circular dependencies.
    """
    def __init__(self, memory_api: Any, reputation: Any) -> None:
        """Initializes the dummy QuarantineBuffer."""
        pass
    async def process(self, genome: Dict[str, Any]) -> None:
        """Processes a genome, dummy implementation."""
        pass


class CRDTAdapter:
    """
    Адаптер, интегрирующий GenomeCRDT с SQLite-персистентностью.
    Предоставляет интерфейс, совместимый с `node_agent.py`, позволяя использовать
    распределенную структуру данных CRDT для управления геномами.

    Этот адаптер отвечает за:
    - Инициализацию и взаимодействие с GenomeCRDT для хранения и управления геномами.
    - Обработку входящих сообщений, включая GossipEnvelope, проверку подписей
      и применение фильтров.
    - Интеграцию с системой карантина для подозрительных фактов памяти.
    - Управление специальными записями, такими как nonce'ы и heartbeat'ы.
    - Предоставление методов для запроса состояния CRDT, дельт и лучших геномов.
    """
    # Type hints for instance attributes initialized outside __init__ or in conditional branches
    _seen_nonces: Dict[str, Set[str]]
    _last_seq: Dict[str, int]
    quarantine: Optional[QuarantineBuffer] # Use the dummy class for type hinting
    storage: CRDTStorage
    crdt: GenomeCRDT
    memory_api: Optional[Any] # Could be more specific if a Protocol is defined for MemoryAPI
    reputation: Optional[Any] # Could be more specific if a Protocol is defined for ReputationSystem
    gossip_filter: GossipFilter

    def __init__(self,
                 node_id: str,
                 memory_api: Optional[Any] = None,
                 reputation: Optional[Any] = None,
                 db_path: Optional[str] = None) -> None:
        """
        Инициализирует CRDTAdapter.

        Args:
            node_id (str): Уникальный идентификатор текущего узла.
            memory_api (Optional[Any]): Объект API памяти, если доступен.
                                        Используется для взаимодействия с модулем памяти
                                        (например, для карантина).
            reputation (Optional[Any]): Объект системы репутации, если доступен.
                                        Используется для оценки доверия к сообщениям
                                        (например, для карантина).
            db_path (Optional[str]): Путь к файлу базы данных SQLite.
                                      Если None, используется значение из `config.crdt_db_path`.
        """
        self.node_id = node_id
        # Если db_path не передан, используем значение из конфига
        path: str = db_path or config.crdt_db_path
        self.storage = CRDTStorage(path)
        self.crdt = GenomeCRDT(node_id, storage=self.storage)
        self._seen_nonces = {} # Tracks nonces for each sender_node_id to prevent replay attacks
        self._last_seq = {} # Tracks last sequence number for each sender_node_id for ordered delivery
        self.memory_api = memory_api
        self.reputation = reputation
        self.gossip_filter = GossipFilter(max_clock_skew_ms=config.gossip_max_clock_skew_ms) # Use config value
        self.quarantine = None

        if memory_api and reputation:
            # Import QuarantineBuffer here to avoid circular dependencies
            # if memory_api or reputation themselves depend on CRDTAdapter.
            from src.memory.quarantine import QuarantineBuffer # pylint: disable=import-outside-toplevel
            self.quarantine = QuarantineBuffer(memory_api, reputation)

    async def add_genome(self, genome: Dict[str, Any]) -> str:
        """
        Добавляет геном или обрабатывает входящий gossip-конверт, сохраняя данные в CRDT.

        Этот метод интеллектуально определяет тип входящих данных:
        1. GossipEnvelope: Верифицирует подпись (если включено), применяет фильтры,
           обрабатывает карантин для фактов памяти, затем извлекает и добавляет payload.
        2. Пользовательские типы данных (напр., heartbeat, meta_command): Сохраняет их
           как есть, если они содержат поле "type".
        3. Стандартный геном: Преобразует в канонический формат и сохраняет.

        Args:
            genome (Dict[str, Any]): Геном или gossip-конверт (в виде словаря),
                                     который необходимо добавить.

        Returns:
            str: Глобально уникальный идентификатор (GID) добавленного генома.
                 Возвращает пустую строку, если геном был недействителен, отклонен
                 фильтром, или верификация не удалась.
        """
        sender_id: str = "local" # Default sender for logging, updated if it's a gossip envelope
        processed_payload: Dict[str, Any] = genome # Payload might be updated from envelope

        # --- PROCESS GOSSIP ENVELOPE ---
        if isinstance(genome, dict) and genome.get("domain") == "blackswan-gossip-v1":
            try:
                # Validate and parse the envelope
                envelope = GossipEnvelope(**genome)
            except (TypeError, ValueError) as e:
                logger.warning(f"Invalid gossip envelope format, discarding: {e} | Envelope data: {genome}")
                return ""

            sender_id = envelope.sender_node_id # Update sender_id for logging

            # Apply gossip filter (e.g., anti-entropy, deduplication based on sequence/nonce/timestamp)
            if not self.gossip_filter.check(
                sender_node_id=envelope.sender_node_id,
                nonce=envelope.nonce,
                seq_no=envelope.seq_no,
                timestamp_ms=envelope.timestamp_ms,
                ttl_ms=envelope.ttl_ms
            ):
                logger.warning(
                    f"Gossip message from {envelope.sender_node_id} "
                    f"with nonce {envelope.nonce} rejected by filter."
                )
                return ""

            if config.gossip_signing_enabled:
                # Decode public key from base64
                try:
                    sender_pubkey_bytes: bytes = b64decode(envelope.sender_pubkey)
                    pubkey: Ed25519PublicKey = Ed25519PublicKey.from_public_bytes(sender_pubkey_bytes)
                except Exception as e: # Catch broader exceptions for key decoding issues
                    logger.warning(f"Invalid public key in envelope from {sender_id}, discarding: {e}")
                    return ""

                now_ms = int(time.time() * 1000)
                seen_nonces = self._seen_nonces.setdefault(envelope.sender_node_id, set())
                last_seq = self._last_seq.get(envelope.sender_node_id, -1)

                valid, reason = verify_envelope(envelope, pubkey, seen_nonces, last_seq, now_ms)
                if not valid:
                    logger.warning(f"Ignoring invalid signed genome from {sender_id}: {reason}")
                    return ""

                # Update local state after successful verification
                seen_nonces.add(envelope.nonce)
                self._last_seq[envelope.sender_node_id] = envelope.seq_no
                processed_payload = envelope.payload
            else:
                # Signature verification disabled, extract payload directly
                processed_payload = envelope.payload

            # --- QUARANTINE FOR memory.fact (applies whether signed or not, if enabled) ---
            if (self.quarantine and envelope.payload_type == "memory.fact"
                    and config.quarantine_enabled):
                await self.quarantine.process(processed_payload)

        # --- CUSTOM DATA TYPES (e.g., heartbeat, meta_command) ---
        # Note: 'processed_payload' holds the actual data after potential envelope unwrapping
        if isinstance(processed_payload, dict) and "type" in processed_payload:
            # Generate GID if not present
            gid: str = processed_payload.get("gid") or str(uuid.uuid4())
            # Add/update `node` and `ts` for consistency, if not already present
            if "node" not in processed_payload:
                processed_payload["node"] = self.node_id
            if "ts" not in processed_payload:
                processed_payload["ts"] = time.time()
            self.crdt.upsert(gid, processed_payload)
            logger.info(
                f"✅ Custom data imported: {gid[:8]}... (type={processed_payload.get('type')}) "
                f"from {sender_id}"
            )
            return gid

        # --- STANDARD GENOME PROCESSING ---
        # Generate GID if not present
        gid = processed_payload.get("gid") or str(uuid.uuid4())
        payload_to_upsert: Dict[str, Any] = {
            "params": processed_payload.get("params", {}),
            "fitness": processed_payload.get("fitness", 0.0),
            "niche": processed_payload.get("niche", "exploration"),
            "origin": processed_payload.get("origin", self.node_id), # Origin could be remote or local
            "lineage": processed_payload.get("lineage", [self.node_id]),
            "ts": processed_payload.get("ts", time.time()),
            "ver": processed_payload.get("ver", 0),
            "node": processed_payload.get("node", self.node_id), # Node that processed it, typically local
        }
        self.crdt.upsert(gid, payload_to_upsert)
        # Use 'sender_id' which is correctly set for gossip or defaults to 'local'
        logger.info(f"✅ Genome imported: {gid[:8]}... from {sender_id}")
        return gid

    async def merge(self, remote_items: Dict[str, Dict[str, Any]]) -> None:
        """
        Объединяет удаленные элементы генома с локальным состоянием CRDT.
        Для каждого элемента выполняет 'upsert', создавая новую операцию CRDT
        с текущим node_id и временем.

        Args:
            remote_items (Dict[str, Dict[str, Any]]): Словарь элементов генома,
                                                      где ключи — это GID, а значения — это payloads генома.
        """
        # This method assumes `remote_items` are resolved genome states (not raw CRDT ops).
        # It creates a new local CRDT operation for each item.
        # If `node_agent.py` were sending raw CRDT operations, `self.crdt.merge()` would be used.
        for gid, genome_payload in remote_items.items():
            self.crdt.upsert(gid, genome_payload) # This creates a new op from THIS node_id

    async def get_nonce(self, account: str) -> int:
        """
        Извлекает текущий nonce для заданного аккаунта.
        Nonce хранится как специальная CRDT-запись.

        Args:
            account (str): Идентификатор аккаунта.

        Returns:
            int: Текущее значение nonce, по умолчанию 0, если не найдено или недействительно.
        """
        gid = f"nonce:{account}"
        record_payload = self.crdt.get(gid) # Use crdt.get to retrieve the payload
        if record_payload and isinstance(record_payload, dict):
            # The value could be int, but get() returns Any. Ensure it's an int.
            return int(record_payload.get("value", 0))
        return 0

    async def set_nonce(self, account: str, nonce: int) -> None:
        """
        Устанавливает nonce для заданного аккаунта.

        Args:
            account (str): Идентификатор аккаунта.
            nonce (int): Новое значение nonce.
        """
        gid = f"nonce:{account}"
        data: Dict[str, Any] = {
            "key": gid, # Often useful to have the key inside the payload too
            "value": nonce,
            "timestamp": time.time(),
            "node_id": self.node_id,
            "type": "nonce_record", # Added a 'type' for easier identification in CRDT state
        }
        self.crdt.upsert(gid, data)

    async def get_delta(self, known_versions: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
        """
        Вычисляет дельту (новые или обновленные геномы) по сравнению с известным набором версий.
        Этот метод возвращает полные payloads геномов, а не CRDT-операции.
        Примечание: `known_versions` здесь относится к application-level `ver` field
        внутри payload генома, а не к внутренним часам Лампорта CRDT.

        Args:
            known_versions (Dict[str, int]): Словарь GID к номеру версии (application-level 'ver'),
                                              представляющий знания вызывающей стороны.

        Returns:
            Dict[str, Dict[str, Any]]: Словарь GID и их полных payloads генома,
                                        которые новее, чем предоставленные `known_versions`.
        """
        all_state = self.crdt.state() # This returns only active (non-deleted) payloads
        delta: Dict[str, Dict[str, Any]] = {}
        for gid, payload in all_state.items():
            # Compare application-level 'ver' field
            app_ver = payload.get("ver", 0)
            if gid not in known_versions or known_versions[gid] < app_ver:
                delta[gid] = payload
        return delta

    async def get_versions(self) -> Dict[str, int]:
        """
        Извлекает текущую версию (поле 'ver') для всех активных геномов.

        Returns:
            Dict[str, int]: Словарь GID к номеру версии (application-level 'ver').
        """
        all_state = self.crdt.state()
        return {gid: payload.get("ver", 0) for gid, payload in all_state.items()}

    async def get_top(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        Извлекает 'n' лучших геномов на основе их показателя 'fitness'.

        Args:
            n (int): Количество лучших геномов для извлечения. По умолчанию 5.

        Returns:
            List[Dict[str, Any]]: Список словарей, каждый из которых представляет геном.
        """
        all_state = self.crdt.state()
        # Sort based on 'fitness', defaulting to 0.0 if not present. Ensure comparison type.
        sorted_genomes = sorted(
            all_state.values(),
            key=lambda x: float(x.get("fitness", 0.0)), # Cast to float explicitly for safety
            reverse=True
        )
        return sorted_genomes[:n]

    async def prune(self) -> None:
        """
        Выполняет обрезку и компактизацию CRDT.
        В настоящее время это включает компактизацию журнала операций CRDT.
        В будущих версиях здесь может быть реализована логика удаления старых или
        нерелевантных геномов из CRDT.
        """
        logger.debug("Running CRDT compaction...")
        self.crdt.compact()
        logger.debug("CRDT compaction finished.")


    async def prune_heartbeats(self, max_age_seconds: int = 600) -> None:
        """
        Удаляет записи 'heartbeat' из CRDT, которые старше `max_age_seconds`.

        Args:
            max_age_seconds (int): Максимальный возраст в секундах для сердцебиений,
                                   прежде чем они будут удалены. По умолчанию 600 секунд (10 минут).
        """
        now = time.time()
        to_delete: List[str] = []
        # Iterate over the current state of active genomes
        for gid, payload in self.crdt.state().items():
            if isinstance(payload, dict) and payload.get("type") == "heartbeat":
                # Ensure 'timestamp' is present and is a number for comparison
                ts = float(payload.get("timestamp", 0.0))
                if now - ts > max_age_seconds:
                    to_delete.append(gid)

        for gid in to_delete:
            self.crdt.delete(gid)
        if to_delete:
            logger.info(f"Pruned {len(to_delete)} old heartbeats from CRDT.")

    @property
    def state(self) -> Dict[str, Dict[str, Any]]:
        """
        Возвращает текущее состояние CRDT, исключая удаленные записи (tombstones).
        Каждый payload генома возвращается как копия, чтобы предотвратить
        случайные изменения внутреннего состояния CRDT.

        Returns:
            Dict[str, Dict[str, Any]]: Словарь, где ключи — это GID, а значения —
                                        активные payloads генома.
        """
        return self.crdt.state()
