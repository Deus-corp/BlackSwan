"""Minimal layered local memory API with snapshot/restore support."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.memory.contracts import MemoryQuery, MemoryStats

logger = logging.getLogger(__name__)


@runtime_checkable
class StorageProtocol(Protocol):
    """Expected interface for a memory snapshot storage backend."""

    def save_snapshot(self, node_id: str, data: bytes) -> None:
        ...

    def load_snapshot(self, node_id: str) -> Optional[bytes]:
        ...


def _now_ms() -> int:
    return int(time.time() * 1000)


def _canonical_json(data: Any) -> str:
    return json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _sha256_json(data: Any) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


class MemoryRecord(BaseModel):
    """Single atomic memory record."""

    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    kind: str = Field(description='Record type, e.g. "event", "fact", "summary", "policy".')
    scope: str = Field(default="local")
    topic: Optional[str] = None
    payload: Any = None
    payload_hash: str = ""
    source: dict[str, Any] = Field(
        default_factory=lambda: {"originNodeId": "", "originPeerId": "", "parents": []}
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    priority: int = Field(default=0, ge=0, le=100)
    ttl_ms: Optional[int] = Field(default=None, ge=0)
    valid_until: Optional[int] = Field(default=None, ge=0)
    created_at: int = Field(default_factory=_now_ms)
    updated_at: int = Field(default_factory=_now_ms)
    version: int = Field(default=1, ge=1)
    signature: Optional[str] = None
    verified: bool = False

    @field_validator("id", "kind", "scope", mode="before")
    @classmethod
    def _clean_required_text(cls, value: Any) -> str:
        clean_value = str(value or "").strip()
        if not clean_value:
            raise ValueError("value cannot be empty")
        return clean_value

    @model_validator(mode="after")
    def normalize_and_hash(self) -> MemoryRecord:
        if not isinstance(self.source, dict):
            self.source = {"originNodeId": "", "originPeerId": "", "parents": []}

        parents = self.source.get("parents", [])
        if not isinstance(parents, list):
            self.source["parents"] = []

        if self.ttl_ms is not None and self.valid_until is None:
            self.valid_until = int(self.created_at + self.ttl_ms)

        if not self.payload_hash and self.payload is not None:
            self.payload_hash = _sha256_json(self.payload)

        if self.updated_at < self.created_at:
            self.updated_at = self.created_at

        return self

    @property
    def expired(self) -> bool:
        return self.valid_until is not None and _now_ms() > self.valid_until


class FactStoreItem(BaseModel):
    """Structured semantic fact."""

    model_config = ConfigDict(validate_assignment=True)

    fact_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    subject: str
    predicate: str
    object: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_refs: list[str] = Field(default_factory=list)

    @field_validator("fact_id", "subject", "predicate", "object", mode="before")
    @classmethod
    def _clean_text(cls, value: Any) -> str:
        clean_value = str(value or "").strip()
        if not clean_value:
            raise ValueError("value cannot be empty")
        return clean_value


class EpisodeEvent(BaseModel):
    """Episodic event derived from a memory record."""

    model_config = ConfigDict(validate_assignment=True)

    event_id: str
    kind: str
    message: str
    ts: int = Field(default_factory=_now_ms)
    refs: list[str] = Field(default_factory=list)

    @field_validator("event_id", "kind", mode="before")
    @classmethod
    def _clean_required_text(cls, value: Any) -> str:
        clean_value = str(value or "").strip()
        if not clean_value:
            raise ValueError("value cannot be empty")
        return clean_value


class PolicyRule(BaseModel):
    """Policy or rule governing memory-backed behavior."""

    model_config = ConfigDict(validate_assignment=True)

    rule_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    description: str = ""
    enabled: bool = True
    priority: int = Field(default=0, ge=0, le=100)
    conditions: dict[str, Any] = Field(default_factory=dict)
    actions: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)

    @field_validator("rule_id", "name", mode="before")
    @classmethod
    def _clean_required_text(cls, value: Any) -> str:
        clean_value = str(value or "").strip()
        if not clean_value:
            raise ValueError("value cannot be empty")
        return clean_value


class MemorySnapshot(BaseModel):
    """Metadata for a memory snapshot."""

    model_config = ConfigDict(validate_assignment=True)

    snapshot_id: str
    node_id: str
    created_at: int
    semantic_hash: str = ""
    episodic_hash: str = ""
    policy_hash: str = ""
    records_hash: str = ""
    record_count: int = 0
    signature: str = ""


class LocalMemoryAPI:
    """Local layered memory implementation for records, episodes, facts, and policies."""

    def __init__(self, node_id: str = "unknown", storage: Optional[StorageProtocol] = None) -> None:
        clean_node_id = str(node_id or "").strip() or "unknown"

        self.node_id = clean_node_id
        self.storage = storage

        self._records: dict[str, MemoryRecord] = {}
        self._episodic: dict[str, EpisodeEvent] = {}
        self._semantic: dict[str, FactStoreItem] = {}
        self._policies: dict[str, PolicyRule] = {}
        self._snapshots: list[MemorySnapshot] = []

    async def remember(self, record: MemoryRecord) -> str:
        """Store a memory record and update derived layers when applicable."""
        if not isinstance(record, MemoryRecord):
            record = MemoryRecord.model_validate(record)

        now = _now_ms()
        record.updated_at = now

        if record.ttl_ms is not None and record.valid_until is None:
            record.valid_until = record.created_at + record.ttl_ms

        if not record.payload_hash and record.payload is not None:
            record.payload_hash = _sha256_json(record.payload)

        self._records[record.id] = record
        self._index_record(record)
        return record.id

    async def upsert_fact(self, fact: FactStoreItem) -> None:
        """Add or update a semantic fact."""
        if not isinstance(fact, FactStoreItem):
            fact = FactStoreItem.model_validate(fact)
        self._semantic[fact.fact_id] = fact

    async def store_policy(self, rule: PolicyRule) -> None:
        """Add or update a policy rule."""
        if not isinstance(rule, PolicyRule):
            rule = PolicyRule.model_validate(rule)
        self._policies[rule.rule_id] = rule

    async def get_by_id(self, record_id: str) -> Optional[MemoryRecord]:
        """Retrieve a non-expired record by ID."""
        record = self._records.get(str(record_id or "").strip())
        if record is None:
            return None
        if record.expired:
            await self.forget_ids([record.id])
            return None
        return record

    async def query(
        self,
        kind: Optional[str] = None,
        scope: Optional[str] = None,
        min_confidence: float = 0.0,
        topic: Optional[str] = None,
        include_expired: bool = False,
    ) -> list[MemoryRecord]:
        """Query records by kind, scope, topic, and minimum confidence."""
        min_confidence = max(0.0, min(1.0, float(min_confidence)))
        results: list[MemoryRecord] = []

        for record in self._records.values():
            if not include_expired and record.expired:
                continue
            if kind is not None and record.kind != kind:
                continue
            if scope is not None and record.scope != scope:
                continue
            if topic is not None and record.topic != topic:
                continue
            if record.confidence < min_confidence:
                continue
            results.append(record)

        results.sort(key=lambda item: (item.priority, item.updated_at), reverse=True)
        return results
    
    async def recall(self, query: MemoryQuery | dict[str, Any]) -> list[MemoryRecord]:
        """Recall records using canonical MemoryQuery contract."""
        if isinstance(query, dict):
            query = MemoryQuery(**query)
        elif not isinstance(query, MemoryQuery):
            query = MemoryQuery()

        safe_limit = max(0, int(query.limit))
        if safe_limit == 0:
            return []

        records = await self.query(
            kind=str(query.kind) if query.kind is not None else None,
            scope=str(query.scope) if query.scope is not None else None,
            include_expired=query.include_expired,
        )

        filtered: list[MemoryRecord] = []
        text = str(query.text or "").strip().lower()
        required_tags = {str(tag).strip().lower() for tag in query.tags if str(tag).strip()}

        for record in records:
            if query.owner_node_id:
                origin = self._record_origin(record)
                if origin != query.owner_node_id:
                    continue

            if query.swarm:
                swarm = self._record_swarm(record)
                if swarm != query.swarm:
                    continue

            if required_tags:
                record_tags = self._record_tags(record)
                if not required_tags.issubset(record_tags):
                    continue

            if text and text not in self._searchable_text(record):
                continue

            filtered.append(record)

            if len(filtered) >= safe_limit:
                break

        return filtered

    async def recent(self, kind: Optional[str] = None, limit: int = 50) -> list[MemoryRecord]:
        """Return recent non-expired records, optionally filtered by kind."""
        safe_limit = max(0, int(limit))
        if safe_limit == 0:
            return []

        records = [
            record
            for record in self._records.values()
            if not record.expired and (kind is None or record.kind == kind)
        ]
        records.sort(key=lambda item: item.created_at, reverse=True)
        return records[:safe_limit]

    async def get_all_facts(self) -> list[FactStoreItem]:
        """Return all semantic facts."""
        return list(self._semantic.values())

    async def get_all_policies(self) -> list[PolicyRule]:
        """Return all policy rules."""
        return list(self._policies.values())

    async def get_all_episodic_events(self) -> list[EpisodeEvent]:
        """Return all episodic events sorted by timestamp."""
        return sorted(self._episodic.values(), key=lambda item: item.ts, reverse=True)

    async def save_to_db(self) -> None:
        """Persist full memory state to configured storage backend."""
        if self.storage is None:
            logger.warning("No storage backend configured; memory state was not saved.")
            return

        data = self._dump_state()

        try:
            raw = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
            self.storage.save_snapshot(self.node_id, raw)
            logger.debug("Memory state saved for node_id=%s.", self.node_id)
        except Exception:
            logger.exception("Failed to save memory state for node_id=%s.", self.node_id)
            raise

    async def load_from_db(self) -> None:
        """Load full memory state from configured storage backend."""
        if self.storage is None:
            logger.warning("No storage backend configured; memory state was not loaded.")
            return

        raw_data = self.storage.load_snapshot(self.node_id)
        if not raw_data:
            logger.info("No previous memory state found for node_id=%s.", self.node_id)
            return

        try:
            data = json.loads(raw_data.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("memory snapshot root must be a JSON object")
            self._load_state(data)
            logger.info("Memory state loaded for node_id=%s.", self.node_id)
        except Exception:
            logger.exception("Failed to load memory state for node_id=%s.", self.node_id)
            raise

    async def snapshot(self) -> MemorySnapshot:
        """Create and store metadata snapshot for current memory layers."""
        snapshot = MemorySnapshot(
            snapshot_id=uuid.uuid4().hex,
            node_id=self.node_id,
            created_at=_now_ms(),
            record_count=len(self._records),
            records_hash=self._hash_records(),
            semantic_hash=self._hash_semantic(),
            episodic_hash=self._hash_episodic(),
            policy_hash=self._hash_policies(),
        )
        self._snapshots.append(snapshot)
        return snapshot

    async def restore(self, snapshot: MemorySnapshot, records: list[MemoryRecord]) -> None:
        """Restore records and reconstruct derived episodic/fact/policy layers when possible."""
        if not isinstance(snapshot, MemorySnapshot):
            snapshot = MemorySnapshot.model_validate(snapshot)

        self._records.clear()
        self._episodic.clear()
        self._semantic.clear()
        self._policies.clear()
        self._snapshots = [snapshot]

        for record in records:
            if not isinstance(record, MemoryRecord):
                record = MemoryRecord.model_validate(record)
            self._records[record.id] = record
            self._index_record(record)

    async def forget(
        self,
        kind: Optional[str] = None,
        older_than_ms: Optional[int] = None,
        expired_only: bool = False,
    ) -> int:
        """Delete records matching filters and return deletion count."""
        to_delete: list[str] = []
        cutoff = int(older_than_ms) if older_than_ms is not None else None

        for record_id, record in self._records.items():
            if kind is not None and record.kind != kind:
                continue
            if cutoff is not None and record.created_at >= cutoff:
                continue
            if expired_only and not record.expired:
                continue
            to_delete.append(record_id)

        return await self.forget_ids(to_delete)

    async def forget_ids(self, record_ids: list[str]) -> int:
        """Delete specific record IDs and cascade direct episodic references."""
        deleted = 0

        for record_id in record_ids:
            clean_id = str(record_id or "").strip()
            if not clean_id:
                continue

            if self._records.pop(clean_id, None) is not None:
                deleted += 1

            self._episodic.pop(clean_id, None)

        return deleted

    async def clear_all_memory(self) -> None:
        """Clear every memory layer."""
        self._records.clear()
        self._episodic.clear()
        self._semantic.clear()
        self._policies.clear()
        self._snapshots.clear()

    async def compress(self) -> dict[str, Any]:
        """Return memory usage metrics and cleanup expired records."""
        expired_deleted = await self.forget(expired_only=True)

        return {
            "node_id": self.node_id,
            "total_records": len(self._records),
            "episodic_count": len(self._episodic),
            "semantic_count": len(self._semantic),
            "policy_count": len(self._policies),
            "snapshot_count": len(self._snapshots),
            "expired_deleted": expired_deleted,
            "memory_usage_bytes": len(
                json.dumps(self._dump_state(), ensure_ascii=False, default=str).encode("utf-8")
            ),
        }
    
    async def stats(self) -> MemoryStats:
        """Return canonical memory backend statistics."""
        now = _now_ms()
        by_scope: dict[str, int] = {}
        by_kind: dict[str, int] = {}
        expired_records = 0
        verified_records = 0

        for record in self._records.values():
            by_scope[record.scope] = by_scope.get(record.scope, 0) + 1
            by_kind[record.kind] = by_kind.get(record.kind, 0) + 1

            if record.verified:
                verified_records += 1

            if record.valid_until is not None and now > record.valid_until:
                expired_records += 1

        return MemoryStats(
            total_records=len(self._records),
            by_scope=by_scope,
            by_kind=by_kind,
            verified_records=verified_records,
            expired_records=expired_records,
            backend="local",
            details={
                "node_id": self.node_id,
                "episodic_count": len(self._episodic),
                "semantic_count": len(self._semantic),
                "policy_count": len(self._policies),
                "snapshot_count": len(self._snapshots),
            },
        )

    async def seal(self) -> None:
        """Create a snapshot and persist state when storage is configured."""
        await self.snapshot()
        if self.storage is not None:
            await self.save_to_db()

    @staticmethod
    def _record_origin(record: MemoryRecord) -> str:
        source = record.source if isinstance(record.source, dict) else {}
        return str(
            source.get("originNodeId")
            or source.get("origin_node_id")
            or source.get("node_id")
            or source.get("originPeerId")
            or ""
        )

    @staticmethod
    def _record_swarm(record: MemoryRecord) -> str:
        source = record.source if isinstance(record.source, dict) else {}
        payload = record.payload if isinstance(record.payload, dict) else {}

        return str(
            source.get("swarm")
            or source.get("swarm_type")
            or payload.get("swarm")
            or payload.get("swarm_type")
            or ""
        )

    @staticmethod
    def _record_tags(record: MemoryRecord) -> set[str]:
        payload = record.payload if isinstance(record.payload, dict) else {}
        raw_tags = payload.get("tags", [])

        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]

        if not isinstance(raw_tags, list):
            raw_tags = []

        tags = {str(tag).strip().lower() for tag in raw_tags if str(tag).strip()}

        if record.topic:
            tags.add(str(record.topic).strip().lower())

        tags.add(str(record.kind).strip().lower())
        tags.add(str(record.scope).strip().lower())

        return tags

    @staticmethod
    def _searchable_text(record: MemoryRecord) -> str:
        parts = [
            record.id,
            record.kind,
            record.scope,
            record.topic or "",
            _canonical_json(record.payload),
            _canonical_json(record.source),
        ]
        return " ".join(str(part).lower() for part in parts)

    def _index_record(self, record: MemoryRecord) -> None:
        if record.kind == "event":
            self._episodic[record.id] = EpisodeEvent(
                event_id=record.id,
                kind=record.kind,
                message=self._payload_summary(record.payload),
                ts=record.created_at,
                refs=list(record.source.get("parents", [])) if isinstance(record.source, dict) else [],
            )

        if record.kind == "fact" and isinstance(record.payload, dict):
            fact = self._fact_from_record(record)
            if fact is not None:
                self._semantic[fact.fact_id] = fact

        if record.kind == "policy" and isinstance(record.payload, dict):
            policy = self._policy_from_record(record)
            if policy is not None:
                self._policies[policy.rule_id] = policy

    @staticmethod
    def _payload_summary(payload: Any) -> str:
        if isinstance(payload, str):
            return payload[:500]
        try:
            return json.dumps(payload, ensure_ascii=False, default=str)[:500]
        except TypeError:
            return str(payload)[:500]

    @staticmethod
    def _fact_from_record(record: MemoryRecord) -> Optional[FactStoreItem]:
        payload = record.payload
        if not isinstance(payload, dict):
            return None

        required = {"subject", "predicate", "object"}
        if not required.issubset(payload):
            return None

        try:
            return FactStoreItem(
                fact_id=str(payload.get("fact_id") or record.id),
                subject=str(payload["subject"]),
                predicate=str(payload["predicate"]),
                object=str(payload["object"]),
                confidence=float(payload.get("confidence", record.confidence)),
                source_refs=list(payload.get("source_refs", [record.id])),
            )
        except Exception:
            logger.debug("Failed to derive FactStoreItem from record=%s.", record.id, exc_info=True)
            return None

    @staticmethod
    def _policy_from_record(record: MemoryRecord) -> Optional[PolicyRule]:
        payload = record.payload
        if not isinstance(payload, dict) or "name" not in payload:
            return None

        try:
            return PolicyRule(
                rule_id=str(payload.get("rule_id") or record.id),
                name=str(payload["name"]),
                description=str(payload.get("description", "")),
                enabled=bool(payload.get("enabled", True)),
                priority=int(payload.get("priority", record.priority)),
                conditions=dict(payload.get("conditions", {})),
                actions=list(payload.get("actions", [])),
                version=int(payload.get("version", 1)),
            )
        except Exception:
            logger.debug("Failed to derive PolicyRule from record=%s.", record.id, exc_info=True)
            return None

    def _dump_state(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "records": [record.model_dump(mode="json") for record in self._records.values()],
            "episodic": [event.model_dump(mode="json") for event in self._episodic.values()],
            "semantic": [fact.model_dump(mode="json") for fact in self._semantic.values()],
            "policies": [policy.model_dump(mode="json") for policy in self._policies.values()],
            "snapshots": [snapshot.model_dump(mode="json") for snapshot in self._snapshots],
            "updated_at": _now_ms(),
        }

    def _load_state(self, data: dict[str, Any]) -> None:
        self.node_id = str(data.get("node_id") or self.node_id)

        self._records = {
            record.id: record
            for record in (
                MemoryRecord.model_validate(item)
                for item in data.get("records", [])
                if isinstance(item, dict)
            )
        }
        self._episodic = {
            event.event_id: event
            for event in (
                EpisodeEvent.model_validate(item)
                for item in data.get("episodic", [])
                if isinstance(item, dict)
            )
        }
        self._semantic = {
            fact.fact_id: fact
            for fact in (
                FactStoreItem.model_validate(item)
                for item in data.get("semantic", [])
                if isinstance(item, dict)
            )
        }
        self._policies = {
            policy.rule_id: policy
            for policy in (
                PolicyRule.model_validate(item)
                for item in data.get("policies", [])
                if isinstance(item, dict)
            )
        }
        self._snapshots = [
            MemorySnapshot.model_validate(item)
            for item in data.get("snapshots", [])
            if isinstance(item, dict)
        ]

    def _hash_records(self) -> str:
        return _sha256_json(
            sorted(
                [record.model_dump(mode="json") for record in self._records.values()],
                key=lambda item: item["id"],
            )
        )

    def _hash_semantic(self) -> str:
        return _sha256_json(
            sorted(
                [fact.model_dump(mode="json") for fact in self._semantic.values()],
                key=lambda item: item["fact_id"],
            )
        )

    def _hash_episodic(self) -> str:
        return _sha256_json(
            sorted(
                [event.model_dump(mode="json") for event in self._episodic.values()],
                key=lambda item: item["event_id"],
            )
        )

    def _hash_policies(self) -> str:
        return _sha256_json(
            sorted(
                [policy.model_dump(mode="json") for policy in self._policies.values()],
                key=lambda item: item["rule_id"],
            )
        )