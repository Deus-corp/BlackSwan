# src/memory/local_memory.py
"""
Minimal LocalMemoryAPI implementation.
Provides layered memory (episodic, semantic, policy) and snapshot/restore.
"""
import time
import json
import hashlib
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# ---------- Data Models ----------

class MemoryRecord(BaseModel):
    id: str
    kind: str  # "event", "fact", "summary", "policy", "decision", "alert"
    scope: str = "local"   # "local", "swarm", "topic"
    topic: Optional[str] = None
    payload: Any = None
    payload_hash: str = ""
    source: Dict[str, Any] = Field(default_factory=lambda: {"originNodeId": "", "originPeerId": "", "parents": []})
    confidence: float = 1.0      # 0..1
    priority: int = 0            # 0..100
    ttl_ms: Optional[int] = None
    valid_until: Optional[int] = None
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    updated_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    version: int = 1
    signature: Optional[str] = None
    verified: bool = False

class FactStoreItem(BaseModel):
    fact_id: str
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    source_refs: List[str] = Field(default_factory=list)

class EpisodeEvent(BaseModel):
    event_id: str
    kind: str
    message: str
    ts: int = Field(default_factory=lambda: int(time.time() * 1000))
    refs: List[str] = Field(default_factory=list)

class PolicyRule(BaseModel):
    rule_id: str
    name: str
    description: str = ""
    enabled: bool = True
    priority: int = 0
    conditions: Dict[str, Any] = Field(default_factory=dict)
    actions: List[str] = Field(default_factory=list)
    version: int = 1

class MemorySnapshot(BaseModel):
    snapshot_id: str
    node_id: str
    created_at: int
    semantic_hash: str = ""
    episodic_hash: str = ""
    policy_hash: str = ""
    record_count: int = 0
    signature: str = ""

# ---------- Memory Implementation ----------

class LocalMemoryAPI:
    def __init__(self, node_id: str = "unknown"):
        self.node_id = node_id
        # Основное хранилище — словарь всех записей по id
        self._records: Dict[str, MemoryRecord] = {}
        # Отдельные слои (могут пересекаться с _records, но упрощают фильтрацию)
        self._episodic: List[EpisodeEvent] = []
        self._semantic: List[FactStoreItem] = []
        self._policies: List[PolicyRule] = []
        self._snapshots: List[MemorySnapshot] = []

    # ---------- WRITE METHODS ----------

    async def remember(self, record: MemoryRecord) -> str:
        """Сохранить запись и вернуть её id."""
        if not record.id:
            record.id = hashlib.sha256(json.dumps(record.payload, sort_keys=True).encode()).hexdigest()[:16]
        record.updated_at = int(time.time() * 1000)
        self._records[record.id] = record
        # Автоматическая классификация по kind (опционально)
        if record.kind == "event":
            self._episodic.append(EpisodeEvent(
                event_id=record.id,
                kind=record.kind,
                message=str(record.payload),
                refs=record.source.get("parents", [])
            ))
        return record.id

    async def upsert_fact(self, fact: FactStoreItem) -> None:
        existing = next((f for f in self._semantic if f.fact_id == fact.fact_id), None)
        if existing:
            self._semantic.remove(existing)
        self._semantic.append(fact)

    async def store_policy(self, rule: PolicyRule) -> None:
        self._policies.append(rule)

    # ---------- READ METHODS ----------

    async def get_by_id(self, record_id: str) -> Optional[MemoryRecord]:
        return self._records.get(record_id)

    async def query(self, kind: Optional[str] = None, scope: Optional[str] = None,
                    min_confidence: float = 0.0) -> List[MemoryRecord]:
        results = []
        for rec in self._records.values():
            if kind and rec.kind != kind:
                continue
            if scope and rec.scope != scope:
                continue
            if rec.confidence < min_confidence:
                continue
            results.append(rec)
        return results

    async def recent(self, kind: Optional[str] = None, limit: int = 50) -> List[MemoryRecord]:
        # Сортировка по времени убывания
        sorted_recs = sorted(self._records.values(), key=lambda r: r.created_at, reverse=True)
        if kind:
            sorted_recs = [r for r in sorted_recs if r.kind == kind]
        return sorted_recs[:limit]

    # ---------- SNAPSHOT / RESTORE ----------

    async def snapshot(self) -> MemorySnapshot:
        """Создать контрольную точку."""
        records_list = list(self._records.values())
        snapshot = MemorySnapshot(
            snapshot_id=hashlib.sha256(str(time.time()).encode()).hexdigest()[:12],
            node_id=self.node_id,
            created_at=int(time.time() * 1000),
            record_count=len(records_list),
            semantic_hash=hashlib.sha256(json.dumps([f.dict() for f in self._semantic], sort_keys=True).encode()).hexdigest(),
            episodic_hash=hashlib.sha256(json.dumps([e.dict() for e in self._episodic], sort_keys=True).encode()).hexdigest(),
            policy_hash=hashlib.sha256(json.dumps([p.dict() for p in self._policies], sort_keys=True).encode()).hexdigest(),
        )
        self._snapshots.append(snapshot)
        return snapshot

    async def restore(self, snapshot: MemorySnapshot, records: List[MemoryRecord]) -> None:
        """Загрузить данные из снапшота (предполагается, что records переданы отдельно)."""
        self._records.clear()
        for rec in records:
            self._records[rec.id] = rec
        # Восстановление дополнительных слоёв можно сделать через перебор kind,
        # но для простоты оставляем как есть.

    async def forget(self, kind: Optional[str] = None, older_than_ms: Optional[int] = None) -> int:
        """Удалить записи по критерию, вернуть количество удалённых."""
        to_delete = []
        for rid, rec in self._records.items():
            if kind and rec.kind != kind:
                continue
            if older_than_ms and rec.created_at > older_than_ms:
                continue
            to_delete.append(rid)
        for rid in to_delete:
            del self._records[rid]
        return len(to_delete)

    # ---------- UTILS ----------
    async def compress(self) -> Dict[str, Any]:
        """Заглушка — возвращает метрики."""
        return {
            "total_records": len(self._records),
            "episodic_count": len(self._episodic),
            "semantic_count": len(self._semantic),
            "policy_count": len(self._policies)
        }

    async def seal(self) -> None:
        """Заглушка — заморозка для аудита."""
        pass