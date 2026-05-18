"""
Адаптер, который заменяет CRDTState на GenomeCRDT с SQLite‑персистентностью.
Совместим с текущим node_agent.py.
"""
import uuid
import os
import time
import asyncio
import logging
from typing import Any, Dict, Optional, Set, List
from src.core.crdt_layer import GenomeCRDT, CRDTStorage
from src.security.gossip_envelope import GossipEnvelope, verify_envelope, b64decode
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from src.core.gossip_filter import GossipFilter
from swarm_config import config

logger = logging.getLogger(__name__)

# It's generally better to read config values at usage or pass them,
# but if DB_PATH is truly global and static after config load, this is acceptable.
# The original code used `config.crdt_db_path` directly in `__init__`,
# making this global DB_PATH potentially redundant or misleading if `db_path` arg is used.
# Removing DB_PATH global and relying on config.crdt_db_path or passed db_path for clarity.
# DB_PATH = config.crdt_db_path # Removed to avoid confusion with `db_path` argument

# Forward declaration for QuarantineBuffer to avoid circular imports at module level
class QuarantineBuffer:
    # This is a dummy class for type hinting, the real one is imported conditionally
    def __init__(self, memory_api: Any, reputation: Any) -> None: pass
    async def process(self, genome: Dict[str, Any]) -> None: pass


class CRDTAdapter:
    """
    Адаптер, интегрирующий GenomeCRDT с SQLite-персистентностью.
    Предоставляет интерфейс, совместимый с `node_agent.py`, позволяя использовать
    распределенную структуру данных CRDT для управления геномами.
    """
    # Type hints for instance attributes initialized outside __init__ or in conditional branches
    _seen_nonces: Dict[str, Set[str]]
    _last_seq: Dict[str, int]
    quarantine: Optional[QuarantineBuffer] # Use the dummy class for type hinting

    def __init__(self,
                 node_id: str,
                 memory_api: Optional[Any] = None, # Type could be more specific, e.g., 'MemoryAPI'
                 reputation: Optional[Any] = None, # Type could be more specific, e.g., 'ReputationSystem'
                 db_path: Optional[str] = None) -> None:
        """
        Инициализирует CRDTAdapter.

        Args:
            node_id (str): Уникальный идентификатор текущего узла.
            memory_api (Optional[Any]): Объект API памяти, если доступен.
                                        Используется для взаимодействия с модулем памяти.
            reputation (Optional[Any]): Объект системы репутации, если доступен.
                                        Используется для оценки доверия к сообщениям.
            db_path (Optional[str]): Путь к файлу базы данных SQLite.
                                      Если None, используется значение из `config.crdt_db_path`.
        """
        self.node_id = node_id
        # Если db_path не передан, используем значение из конфига
        path = db_path or config.crdt_db_path
        self.storage: CRDTStorage = CRDTStorage(path)
        self.crdt: GenomeCRDT = GenomeCRDT(node_id, storage=self.storage)
        self._seen_nonces = {} # Tracks nonces for each sender_node_id to prevent replay attacks
        self._last_seq = {} # Tracks last sequence number for each sender_node_id for ordered delivery
        self.memory_api = memory_api
        self.reputation = reputation
        self.gossip_filter = GossipFilter(max_clock_skew_ms=10_000)
        self.quarantine: Optional[QuarantineBuffer] = None

        if memory_api and reputation:
            # Import QuarantineBuffer here to avoid circular dependencies
            # if memory_api or reputation themselves depend on CRDTAdapter.
            from src.memory.quarantine import QuarantineBuffer
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
            genome (Dict[str, Any]): Геном или gossip-конверт, который необходимо добавить.

        Returns:
            str: Глобально уникальный идентификатор (GID) добавленного генома.
                 Возвращает пустую строку, если геном был недействителен или отклонен.
        """
        sender_id: str = "local" # Default sender for logging, updated if it's a gossip envelope
        processed_payload: Dict[str, Any] = genome # Payload might be updated from envelope

        # --- ПРОВЕРКА НА GOSSIP ENVELOPE ---
        if isinstance(genome, dict) and genome.get("domain") == "blackswan-gossip-v1":
            try:
                envelope = GossipEnvelope(**genome)
            except Exception as e:
                logger.warning(f"Invalid gossip envelope format, discarding: {e}")
                return ""

            sender_id = envelope.sender_node_id # Update sender_id for logging

            # --- GOSSIP FILTER ---
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
                # Декодируем публичный ключ из base64
                try:
                    sender_pubkey_bytes: bytes = b64decode(envelope.sender_pubkey)
                    pubkey: Ed25519PublicKey = Ed25519PublicKey.from_public_bytes(sender_pubkey_bytes)
                except Exception as e:
                    logger.warning(f"Invalid public key in envelope from {sender_id}, discarding: {e}")
                    return ""

                now_ms = int(time.time() * 1000)
                seen_nonces = self._seen_nonces.setdefault(envelope.sender_node_id, set())
                last_seq = self._last_seq.get(envelope.sender_node_id, -1)

                valid, reason = verify_envelope(envelope, pubkey, seen_nonces, last_seq, now_ms)
                if not valid:
                    logger.warning(f"Ignoring invalid signed genome from {sender_id}: {reason}")
                    return ""

                seen_nonces.add(envelope.nonce)
                self._last_seq[envelope.sender_node_id] = envelope.seq_no
                processed_payload = envelope.payload

                # --- КАРАНТИН ДЛЯ memory.fact ---
                if (self.quarantine and envelope.payload_type == "memory.fact"
                        and config.quarantine_enabled):
                    await self.quarantine.process(processed_payload)

            else:
                # Проверка подписи отключена, но фильтр уже применен выше.
                # Извлекаем payload без проверки подписи.
                processed_payload = envelope.payload

                # --- КАРАНТИН ДЛЯ memory.fact (даже если подпись отключена) ---
                if (self.quarantine and envelope.payload_type == "memory.fact"
                        and config.quarantine_enabled):
                    await self.quarantine.process(processed_payload)

        # --- Пользовательские типы данных (heartbeat, meta_command и т.д.) ---
        # Note: 'processed_payload' holds the actual data after potential envelope unwrapping
        if isinstance(processed_payload, dict) and "type" in processed_payload:
            gid: str = processed_payload.get("gid") or str(uuid.uuid4())
            # Сохраняем как есть, не преобразуем в стандартный genome
            self.crdt.upsert(gid, processed_payload)
            logger.info(f"✅ Custom data imported: {gid[:8]}... (type={processed_payload.get('type')}) from {sender_id}")
            return gid

        # --- Обычная обработка genome ---
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
        В настоящее время просто выполняет 'upsert' для каждого элемента.

        Args:
            remote_items (Dict[str, Dict[str, Any]]): Словарь элементов генома,
                                                      где ключи — это GID, а значения — это payloads генома.
        """
        for gid, genome in remote_items.items():
            self.crdt.upsert(gid, genome)

    async def get_nonce(self, account: str) -> int:
        """
        Извлекает текущий nonce для заданного аккаунта.
        Nonce хранится как специальный CRDT-запись.

        Args:
            account (str): Идентификатор аккаунта.

        Returns:
            int: Текущее значение nonce, по умолчанию 0, если не найдено.
        """
        gid = f"nonce:{account}"
        state = self.crdt.state()
        record = state.get(gid)
        if record and isinstance(record, dict):
            return record.get("value", 0)
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
            "key": gid,
            "value": nonce,
            "timestamp": time.time(),
            "node_id": self.node_id,
            "type": "nonce_record", # Added a 'type' for easier identification in CRDT state
        }
        self.crdt.upsert(gid, data)

    async def get_delta(self, known_versions: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
        """
        Вычисляет дельту (новые или обновленные геномы) по сравнению с известным набором версий.

        Args:
            known_versions (Dict[str, int]): Словарь GID к номеру версии,
                                              представляющий знания вызывающей стороны.

        Returns:
            Dict[str, Dict[str, Any]]: Словарь GID и их полных payloads генома,
                                        которые новее, чем предоставленные `known_versions`.
        """
        all_state = self.crdt.state()
        delta: Dict[str, Dict[str, Any]] = {}
        for gid, payload in all_state.items():
            ver = payload.get("ver", 0)
            if gid not in known_versions or known_versions[gid] < ver:
                delta[gid] = payload
        return delta

    async def get_versions(self) -> Dict[str, int]:
        """
        Извлекает текущую версию (поле 'ver') для всех активных геномов.

        Returns:
            Dict[str, int]: Словарь GID к номеру версии.
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
        # Sort based on 'fitness', defaulting to 0.0 if not present
        sorted_genomes = sorted(all_state.values(), key=lambda x: x.get("fitness", 0.0), reverse=True)
        return sorted_genomes[:n]

    async def prune(self) -> None:
        """
        Заглушка для логики обрезки (pruning). В текущей реализации не выполняет никаких действий.
        Метод предусмотрен для будущих расширений, где может потребоваться удаление старых или
        нерелевантных геномов из CRDT.
        """
        pass

    async def prune_heartbeats(self, max_age_seconds: int = 600) -> None:
        """
        Удаляет записи 'heartbeat' из CRDT, которые старше `max_age_seconds`.

        Args:
            max_age_seconds (int): Максимальный возраст в секундах для сердцебиений,
                                   прежде чем они будут удалены. По умолчанию 600 секунд (10 минут).
        """
        now = time.time()
        to_delete: List[str] = []
        for k, v in self.crdt.state().items():
            if isinstance(v, dict) and v.get("type") == "heartbeat":
                ts = v.get("timestamp", 0.0) # Ensure type is float for comparison
                if now - ts > max_age_seconds:
                    to_delete.append(k)
        for k in to_delete:
            self.crdt.delete(k)
        if to_delete:
            logger.info(f"Pruned {len(to_delete)} old heartbeats from CRDT.")

    @property
    def state(self) -> Dict[str, Dict[str, Any]]:
        """
        Возвращает текущее состояние CRDT, исключая удаленные записи (tombstones).

        Returns:
            Dict[str, Dict[str, Any]]: Словарь, где ключи — это GID, а значения —
                                        активные payloads генома.
        """
        return self.crdt.state()
