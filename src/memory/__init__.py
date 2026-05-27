"""Memory package for BlackSwan resilient memory backends."""

from src.memory.publisher import build_memory_record_event, publish_memory_record
from src.memory.contracts import (
    MemoryBackendProtocol,
    MemoryEnvelope,
    MemoryIdentity,
    MemoryKind,
    MemoryQuery,
    MemoryScope,
    MemoryStats,
)

__all__ = [
    "MemoryBackendProtocol",
    "MemoryEnvelope",
    "MemoryIdentity",
    "MemoryKind",
    "MemoryQuery",
    "MemoryScope",
    "MemoryStats",
    "build_memory_record_event",
    "publish_memory_record",
]