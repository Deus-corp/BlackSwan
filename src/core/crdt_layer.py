from __future__ import annotations

"""
Operation-based CRDT for genome records.

Этот модуль реализует CRDT (Conflict-free Replicated Data Type) на основе операций
для управления записями генома. Он разработан для обеспечения детерминированного
Last-Write-Wins (LWW) на уровне полей/сущностей, используя логи операций,
часы Лампорта и персистентность на основе SQLite.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple
import json
import os
import sqlite3
import threading
import time
import uuid


# =========================
# DATA MODEL
# =========================

@dataclass(frozen=True, slots=True)
class CRDTOperation:
    """
    Представляет одну операцию CRDT (upsert или delete) над записью генома.

    Атрибуты:
        op_id (str): Уникальный идентификатор операции.
        node_id (str): Идентификатор узла, создавшего операцию.
        clock (int): Значение часов Лампорта узла во время создания операции.
        kind (str): Тип операции: "upsert" (вставка/обновление) или "delete" (удаление).
        gid (str): Глобально уникальный идентификатор записи генома, на которую действует операция.
        payload (Dict[str, Any]): Полезная нагрузка (данные) операции (пусто для "delete").
        ts (float): Временная метка Unix, когда операция была создана.
    """
    op_id: str
    node_id: str
    clock: int
    kind: str  # "upsert" | "delete"
    gid: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует экземпляр CRDTOperation в словарь.

        Returns:
            Dict[str, Any]: Словарь, представляющий операцию.
        """
        return {
            "op_id": self.op_id,
            "node_id": self.node_id,
            "clock": self.clock,
            "kind": self.kind,
            "gid": self.gid,
            "payload": self.payload,
            "ts": self.ts,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> CRDTOperation:
        """
        Создает экземпляр CRDTOperation из словаря.

        Args:
            data (Dict[str, Any]): Словарь, содержащий данные операции.

        Returns:
            CRDTOperation: Созданный экземпляр CRDTOperation.
        """
        return CRDTOperation(
            op_id=str(data["op_id"]),
            node_id=str(data["node_id"]),
            clock=int(data["clock"]),
            kind=str(data["kind"]),
            gid=str(data["gid"]),
            payload=dict(data.get("payload", {})),
            ts=float(data.get("ts", time.time())),
        )


@dataclass(slots=True)
class VersionVector:
    """
    Вектор версий отслеживает наибольшее значение часов, наблюдаемое от каждого узла.
    Используется для определения причинного порядка и выявления отсутствующих операций
    во время синхронизации.

    Атрибуты:
        clocks (Dict[str, int]): Словарь, сопоставляющий `node_id` с их максимальным
                                 известным значением часов.
    """
    clocks: Dict[str, int] = field(default_factory=dict)

    def bump(self, node_id: str) -> int:
        """
        Увеличивает часы для заданного узла и возвращает новое значение часов.

        Args:
            node_id (str): Идентификатор узла, чьи часы нужно увеличить.

        Returns:
            int: Новое значение часов для узла.
        """
        self.clocks[node_id] = self.clocks.get(node_id, 0) + 1
        return self.clocks[node_id]

    def observe(self, node_id: str, clock: int) -> None:
        """
        Обновляет часы для заданного узла, если новое значение часов выше текущего.

        Args:
            node_id (str): Идентификатор узла.
            clock (int): Значение часов для наблюдения.
        """
        self.clocks[node_id] = max(self.clocks.get(node_id, 0), int(clock))

    def seen(self, node_id: str, clock: int) -> bool:
        """
        Проверяет, было ли замечено конкретное значение часов для узла.

        Args:
            node_id (str): Идентификатор узла.
            clock (int): Значение часов для проверки.

        Returns:
            bool: True, если значение часов было замечено (т.е. текущие часы >= `clock`),
                  False в противном случае.
        """
        return self.clocks.get(node_id, 0) >= int(clock)

    def merge(self, other: VersionVector) -> None:
        """
        Объединяет другой VersionVector с этим, обновляя часы до их максимальных значений.

        Args:
            other (VersionVector): Другой VersionVector для объединения.
        """
        for node_id, clock in other.clocks.items():
            self.observe(node_id, clock)

    def to_dict(self) -> Dict[str, int]:
        """
        Преобразует VersionVector в словарь.

        Returns:
            Dict[str, int]: Словарь, представляющий вектор версий.
        """
        return dict(self.clocks)

    @staticmethod
    def from_dict(data: Optional[Dict[str, int]]) -> VersionVector:
        """
        Создает экземпляр VersionVector из словаря.

        Args:
            data (Optional[Dict[str, int]]): Словарь, содержащий данные вектора версий.
                                            Может быть None, в этом случае будет создан пустой VV.

        Returns:
            VersionVector: Созданный экземпляр VersionVector.
        """
        vv = VersionVector()
        for k, v in (data or {}).items():
            vv.clocks[str(k)] = int(v)
        return vv


@dataclass(slots=True)
class CRDTRecord:
    """
    Представляет текущее состояние записи генома в CRDT.

    Атрибуты:
        gid (str): Глобально уникальный идентификатор записи.
        payload (Dict[str, Any]): Данные (полезная нагрузка) генома.
        clock (int): Значение часов Лампорта последней операции, повлиявшей на эту запись.
        node_id (str): Идентификатор узла, создавшего последнюю операцию, повлиявшую на эту запись.
        deleted (bool): Флаг, указывающий, является ли запись удаленной (tombstone).
        ts (float): Временная метка Unix последней модификации записи.
    """
    gid: str
    payload: Dict[str, Any]
    clock: int
    node_id: str
    deleted: bool = False
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует экземпляр CRDTRecord в словарь.

        Returns:
            Dict[str, Any]: Словарь, представляющий запись.
        """
        return {
            "gid": self.gid,
            "payload": self.payload,
            "clock": self.clock,
            "node_id": self.node_id,
            "deleted": self.deleted,
            "ts": self.ts,
        }


# =========================
# STORAGE
# =========================

class CRDTStorage:
    """
    Управляет персистентностью для операций CRDT, записей, вектора версий
    и снимков памяти с использованием базы данных SQLite.
    """
    def __init__(self, path: str) -> None:
        """
        Инициализирует CRDTStorage с заданным путем к базе данных.

        Args:
            path (str): Путь к файлу базы данных SQLite.
        """
        self.path = path
        self._lock = threading.RLock() # Reentrant lock for thread safety
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """
        Устанавливает и возвращает соединение с базой данных SQLite.

        Returns:
            sqlite3.Connection: Объект соединения SQLite.
        """
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row # Allows accessing columns by name
        return conn

    def _init_db(self) -> None:
        """
        Инициализирует схему базы данных, создавая необходимые таблицы, если они не существуют.
        """
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ops (
                    op_id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    clock INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    gid TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    ts REAL NOT NULL
                ) STRICT
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    gid TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    clock INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    deleted INTEGER NOT NULL,
                    ts REAL NOT NULL
                ) STRICT
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS version_vector (
                    node_id TEXT PRIMARY KEY,
                    clock INTEGER NOT NULL
                ) STRICT
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_snapshots (
                    key TEXT PRIMARY KEY,
                    data BLOB,
                    updated_at REAL
                ) STRICT
                """
            )
            conn.commit()

    def save_op(self, op: CRDTOperation) -> None:
        """
        Сохраняет операцию CRDT в базу данных.

        Args:
            op (CRDTOperation): Операция для сохранения.
        """
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO ops(op_id, node_id, clock, kind, gid, payload, ts)
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    op.op_id,
                    op.node_id,
                    op.clock,
                    op.kind,
                    op.gid,
                    json.dumps(op.payload, sort_keys=True), # Deterministic serialization
                    op.ts,
                ),
            )
            conn.commit()

    def load_ops(self) -> List[CRDTOperation]:
        """
        Загружает все операции CRDT из базы данных, упорядоченные по временной метке и часам.

        Returns:
            List[CRDTOperation]: Список загруженных операций.
        """
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT op_id, node_id, clock, kind, gid, payload, ts FROM ops ORDER BY ts ASC, clock ASC"
            ).fetchall()
            out: List[CRDTOperation] = []
            for row in rows:
                out.append(
                    CRDTOperation(
                        op_id=row["op_id"],
                        node_id=row["node_id"],
                        clock=int(row["clock"]),
                        kind=row["kind"],
                        gid=row["gid"],
                        payload=json.loads(row["payload"]),
                        ts=float(row["ts"]),
                    )
                )
            return out

    def save_record(self, record: CRDTRecord) -> None:
        """
        Сохраняет запись CRDT (представляющую текущее состояние генома) в базу данных.
        Обновляет существующую запись или вставляет новую.

        Args:
            record (CRDTRecord): Запись для сохранения.
        """
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO records(gid, payload, clock, node_id, deleted, ts)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(gid) DO UPDATE SET
                    payload=excluded.payload,
                    clock=excluded.clock,
                    node_id=excluded.node_id,
                    deleted=excluded.deleted,
                    ts=excluded.ts
                """,
                (
                    record.gid,
                    json.dumps(record.payload, sort_keys=True), # Deterministic serialization
                    record.clock,
                    record.node_id,
                    int(record.deleted),
                    record.ts,
                ),
            )
            conn.commit()

    def load_records(self) -> Dict[str, CRDTRecord]:
        """
        Загружает все записи CRDT (текущее состояние геномов) из базы данных.

        Returns:
            Dict[str, CRDTRecord]: Словарь, сопоставляющий GID с экземплярами CRDTRecord.
        """
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT gid, payload, clock, node_id, deleted, ts FROM records"
            ).fetchall()
            out: Dict[str, CRDTRecord] = {}
            for row in rows:
                out[row["gid"]] = CRDTRecord(
                    gid=row["gid"],
                    payload=json.loads(row["payload"]),
                    clock=int(row["clock"]),
                    node_id=row["node_id"],
                    deleted=bool(row["deleted"]),
                    ts=float(row["ts"]),
                )
            return out

    def load_vv(self) -> VersionVector:
        """
        Загружает VersionVector из базы данных.

        Returns:
            VersionVector: Загруженный вектор версий.
        """
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT node_id, clock FROM version_vector").fetchall()
            vv = VersionVector()
            for row in rows:
                vv.clocks[row["node_id"]] = int(row["clock"])
            return vv

    def save_vv(self, vv: VersionVector) -> None:
        """
        Сохраняет VersionVector в базу данных.

        Args:
            vv (VersionVector): Вектор версий для сохранения.
        """
        with self._lock, self._connect() as conn:
            for node_id, clock in vv.clocks.items():
                conn.execute(
                    """
                    INSERT INTO version_vector(node_id, clock)
                    VALUES(?,?)
                    ON CONFLICT(node_id) DO UPDATE SET clock=excluded.clock
                    """,
                    (node_id, int(clock)),
                )
            conn.commit()

    def save_snapshot(self, key: str, data: bytes) -> None:
        """
        Сохраняет бинарный снимок памяти по заданному ключу.

        Args:
            key (str): Уникальный ключ для снимка памяти.
            data (bytes): Бинарные данные снимка.
        """
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memory_snapshots (key, data, updated_at) VALUES (?, ?, ?)",
                (key, data, time.time())
            )
            conn.commit()

    def load_snapshot(self, key: str) -> Optional[bytes]:
        """
        Загружает бинарный снимок памяти по заданному ключу.

        Args:
            key (str): Уникальный ключ для снимка памяти.

        Returns:
            Optional[bytes]: Бинарные данные снимка, если найден, иначе None.
        """
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM memory_snapshots WHERE key = ?",
                (key,)
            ).fetchone()
            if row:
                return row["data"] # Access by column name
            return None


# =========================
# CRDT CORE
# =========================

class GenomeCRDT:
    """
    Operation-based CRDT для управления записями генома с детерминированной
    семантикой Last-Write-Wins (LWW).

    Правила разрешения конфликтов:
    - Каждый GID сопоставляется с одной записью.
    - Побеждает операция с более высоким значением часов (Lamport clock).
    - При равных значениях часов побеждает операция с лексикографически большим `node_id`.
    - Операция удаления (tombstone) имеет приоритет над более старыми обновлениями.
    - Дублирующиеся операции игнорируются по `op_id`.
    """

    def __init__(self, node_id: str, storage: Optional[CRDTStorage] = None) -> None:
        """
        Инициализирует экземпляр GenomeCRDT.

        Args:
            node_id (str): Уникальный идентификатор для этого узла.
            storage (Optional[CRDTStorage]): Необязательный бэкенд хранилища для персистентности.
                                             Если None, CRDT работает только в памяти.
        """
        self.node_id = node_id
        self.clock: int = 0 # Local Lamport clock
        self.vv: VersionVector = VersionVector() # Tracks highest clocks from all nodes
        self.storage: Optional[CRDTStorage] = storage
        self._lock = threading.RLock() # Reentrant lock for concurrent access

        # In-memory state
        self._records: Dict[str, CRDTRecord] = {} # Current state of all genome records by GID
        self._seen_ops: set[str] = set() # Set of unique operation IDs already processed

        if self.storage is not None:
            self._bootstrap_from_storage()

    def _bootstrap_from_storage(self) -> None:
        """
        Загружает начальное состояние из настроенного бэкенда хранилища.
        Это включает записи, вектор версий и отметку уже обработанных операций.
        """
        self._records = self.storage.load_records()
        self.vv = self.storage.load_vv()
        # Replay ops to update _seen_ops and ensure clock and VV are fully caught up
        for op in self.storage.load_ops():
            self._seen_ops.add(op.op_id)
            self.clock = max(self.clock, op.clock) # Maximize local clock based on all seen ops
            self.vv.observe(op.node_id, op.clock)

    def _next_clock(self) -> int:
        """
        Увеличивает локальные часы узла и обновляет вектор версий для этого узла.

        Returns:
            int: Новое значение часов.
        """
        self.clock += 1
        self.vv.observe(self.node_id, self.clock)
        return self.clock

    def _should_apply(self, current: Optional[CRDTRecord], op: CRDTOperation) -> bool:
        """
        Определяет, следует ли применять входящую операцию на основе правил LWW.

        Args:
            current (Optional[CRDTRecord]): Текущее состояние записи для данного GID,
                                            или None, если запись отсутствует.
            op (CRDTOperation): Входящая операция.

        Returns:
            bool: True, если операцию следует применить; False в противном случае.
        """
        if current is None:
            return True
        if op.clock > current.clock:
            return True
        if op.clock < current.clock:
            return False
        # Tie-breaker: If clocks are equal, lexicographically larger node_id wins
        return op.node_id > current.node_id

    def _apply_op(self, op: CRDTOperation) -> bool:
        """
        Применяет операцию CRDT к локальному состоянию и сохраняет ее, если включено хранилище.
        Обновляет `_seen_ops` и `vv` независимо от того, была ли операция фактически применена
        к `_records`.

        Args:
            op (CRDTOperation): Операция для применения.

        Returns:
            bool: True, если операция была успешно применена к локальным записям;
                  False, если это была дублирующаяся операция или она была отклонена
                  в соответствии с правилами LWW.
        """
        if op.op_id in self._seen_ops:
            return False

        # First, update seen_ops and VV, as we have observed this operation regardless of application
        self._seen_ops.add(op.op_id)
        self.vv.observe(op.node_id, op.clock)

        current = self._records.get(op.gid)
        # Check if the operation should be applied based on LWW rules
        if current is not None and not self._should_apply(current, op):
            if self.storage is not None:
                self.storage.save_op(op)
                self.storage.save_vv(self.vv) # Also save VV if op is rejected, as we've seen it
            return False

        if op.kind not in ("upsert", "delete"):
            raise ValueError(f"Unknown operation kind: {op.kind}")

        if op.kind == "delete":
            record = CRDTRecord(
                gid=op.gid,
                payload={}, # Payload is typically empty for deletes
                clock=op.clock,
                node_id=op.node_id,
                deleted=True,
                ts=op.ts,
            )
        else:  # kind == "upsert"
            record = CRDTRecord(
                gid=op.gid,
                payload=dict(op.payload), # Create a copy to ensure immutability
                clock=op.clock,
                node_id=op.node_id,
                deleted=False,
                ts=op.ts,
            )

        self._records[op.gid] = record

        # Persist the operation and the updated record/VV if storage is available
        if self.storage is not None:
            self.storage.save_op(op)
            self.storage.save_record(record)
            self.storage.save_vv(self.vv)

        return True

    def upsert(self, gid: str, payload: Dict[str, Any], op_id: Optional[str] = None) -> CRDTOperation:
        """
        Создает и применяет операцию 'upsert' для записи генома.

        Args:
            gid (str): Глобально уникальный идентификатор для записи генома.
            payload (Dict[str, Any]): Данные (полезная нагрузка) для генома.
            op_id (Optional[str]): Необязательный уникальный ID для операции.
                                    Если None, будет сгенерирован новый UUID.

        Returns:
            CRDTOperation: Созданная и примененная операция CRDT.
        """
        with self._lock:
            clock = self._next_clock()
            op = CRDTOperation(
                op_id=op_id or str(uuid.uuid4()),
                node_id=self.node_id,
                clock=clock,
                kind="upsert",
                gid=gid,
                payload=dict(payload), # Create a copy to ensure payload immutability
                ts=time.time(),
            )
            self._apply_op(op) # This will also save op to storage
            return op

    def delete(self, gid: str, op_id: Optional[str] = None) -> CRDTOperation:
        """
        Создает и применяет операцию 'delete' для записи генома.

        Args:
            gid (str): Глобально уникальный идентификатор записи генома для удаления.
            op_id (Optional[str]): Необязательный уникальный ID для операции.
                                    Если None, будет сгенерирован новый UUID.

        Returns:
            CRDTOperation: Созданная и примененная операция CRDT.
        """
        with self._lock:
            clock = self._next_clock()
            op = CRDTOperation(
                op_id=op_id or str(uuid.uuid4()),
                node_id=self.node_id,
                clock=clock,
                kind="delete",
                gid=gid,
                payload={}, # Payload is empty for delete operations
                ts=time.time(),
            )
            self._apply_op(op) # This will also save op to storage
            return op

    def merge(self, remote_ops: Iterable[Dict[str, Any] | CRDTOperation]) -> int:
        """
        Объединяет коллекцию удаленных операций CRDT с локальным состоянием.

        Args:
            remote_ops (Iterable[Dict[str, Any] | CRDTOperation]): Итерируемый объект операций,
                                                                  которые могут быть словарями
                                                                  или объектами CRDTOperation.

        Returns:
            int: Количество уникальных операций, успешно примененных к локальному состоянию.
        """
        applied_count = 0
        with self._lock:
            for item in remote_ops:
                op = item if isinstance(item, CRDTOperation) else CRDTOperation.from_dict(item)

                # Special handling for ops originating from this node: just record as seen and update VV.
                # No need to re-apply the operation to records as it was already applied locally.
                if op.node_id == self.node_id and op.op_id in self._seen_ops:
                    self.vv.observe(op.node_id, op.clock)
                    # Even if already seen, ensure it's in storage if storage is active.
                    if self.storage is not None:
                        self.storage.save_op(op)
                        self.storage.save_vv(self.vv)
                    continue

                if self._apply_op(op):
                    applied_count += 1
            return applied_count

    def get(self, gid: str) -> Optional[Dict[str, Any]]:
        """
        Извлекает payload записи генома по ее GID, если она существует и не удалена.

        Args:
            gid (str): Глобально уникальный идентификатор записи генома.

        Returns:
            Optional[Dict[str, Any]]: Payload генома, или None, если запись не найдена или удалена.
        """
        with self._lock:
            record = self._records.get(gid)
            if record is None or record.deleted:
                return None
            return dict(record.payload) # Return a copy to prevent external modification of internal state

    def state(self) -> Dict[str, Dict[str, Any]]:
        """
        Возвращает текущее состояние всех активных (не удаленных) записей генома.

        Returns:
            Dict[str, Dict[str, Any]]: Словарь, сопоставляющий GID с их соответствующими payloads.
                                        Возвращаются копии payloads.
        """
        with self._lock:
            return {
                gid: dict(rec.payload) # Return a copy of the payload
                for gid, rec in self._records.items()
                if not rec.deleted
            }

    def tombstones(self) -> List[str]:
        """
        Возвращает список GID записей, которые были помечены как удаленные (tombstones).

        Returns:
            List[str]: Список GID, которые в настоящее время являются tombstones.
        """
        with self._lock:
            return [gid for gid, rec in self._records.items() if rec.deleted]

    def delta_since(self, other_vv: VersionVector | Dict[str, int]) -> List[Dict[str, Any]]:
        """
        Вычисляет набор операций, неизвестных другому узлу, на основе его VersionVector.

        Args:
            other_vv (VersionVector | Dict[str, int]): VersionVector другого узла
                                                       или его представление в виде словаря.

        Returns:
            List[Dict[str, Any]]: Список операций (в виде словарей), которые другой узел должен получить.
        """
        if isinstance(other_vv, dict):
            other_vv = VersionVector.from_dict(other_vv)

        with self._lock:
            out: List[Dict[str, Any]] = []
            # We iterate through all operations (from storage or synthesized)
            for _, op in self._load_ops_from_state():
                if not other_vv.seen(op.node_id, op.clock):
                    out.append(op.to_dict())
            return out

    def _load_ops_from_state(self) -> List[Tuple[str, CRDTOperation]]:
        """
        Вспомогательный метод для загрузки операций из хранилища или их синтеза
        из текущих записей, если хранилище не настроено.

        Если хранилище отсутствует, операции синтезируются из текущего состояния
        `_records` для обеспечения функциональности `delta_since` без полного журнала.
        """
        if self.storage is not None:
            return [(op.op_id, op) for op in self.storage.load_ops()]

        # If no storage, synthesize a minimal log from current in-memory state
        out: List[Tuple[str, CRDTOperation]] = []
        for gid, rec in self._records.items():
            kind = "delete" if rec.deleted else "upsert"
            op = CRDTOperation(
                op_id=f"synth-{gid}-{rec.clock}-{rec.node_id}", # Unique synthetic op_id
                node_id=rec.node_id,
                clock=rec.clock,
                kind=kind,
                gid=gid,
                payload=dict(rec.payload),
                ts=rec.ts,
            )
            out.append((op.op_id, op))
        return out

    def compact(self) -> None:
        """
        В режиме с поддержкой хранилища, компактизация удаляет журнал операций (`ops`)
        и сохраняет только последние записи (`records`) и снимок вектора версий.
        В режиме только в памяти эта операция не выполняет никаких действий.
        """
        if self.storage is None:
            return

        with self._lock, self.storage._connect() as conn:
            conn.execute("DELETE FROM ops")
            conn.commit()

    def known_versions(self) -> Dict[str, int]:
        """
        Возвращает текущий VersionVector в виде словаря.

        Returns:
            Dict[str, int]: Словарь, сопоставляющий `node_id` с их наивысшими
                            наблюдаемыми значениями часов.
        """
        with self._lock:
            return self.vv.to_dict()

    def record_count(self) -> int:
        """
        Возвращает общее количество записей (включая tombstones),
        хранящихся в CRDT.

        Returns:
            int: Количество всех записей.
        """
        with self._lock:
            return len(self._records)

    def max_clock(self) -> int:
        """
        Возвращает наибольшее значение часов, сгенерированное этим узлом.

        Returns:
            int: Максимальное значение часов.
        """
        with self._lock:
            return self.clock