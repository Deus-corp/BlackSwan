"""Memory package for BlackSwan resilient memory backends."""

from src.memory.publisher import build_memory_record_event, publish_memory_record
from src.memory.summary import MemorySummary, build_memory_summary

from src.memory.contracts import (
    MemoryBackendProtocol,
    MemoryEnvelope,
    MemoryIdentity,
    MemoryKind,
    MemoryQuery,
    MemoryScope,
    MemoryStats,
)

from src.memory.resilience import (
    DEFAULT_MEMORY_RESILIENCE_POLICY,
    MemoryAvailability,
    MemoryHealth,
    MemoryLayer,
    MemoryResiliencePolicy,
    MemoryRoutePlan,
)

from src.memory.recognition import (
    MemoryRecognizer,
    RecognitionConfig,
    RecognitionLabel,
    RecognitionResult,
    RecognitionSignal,
    canonical_fingerprint,
)

from src.memory.recognition_policy import (
    DEFAULT_MEMORY_RECOGNITION_POLICY,
    MemoryRecognitionPolicy,
    RecognitionAction,
    RecognitionDecision,
    RecognitionPolicyConfig,
)

from src.memory.gold_filter import (
    ExperienceSample,
    memory_record_to_experience_sample,
    select_gold_memory_samples,
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
    "DEFAULT_MEMORY_RESILIENCE_POLICY",
    "MemoryAvailability",
    "MemoryHealth",
    "MemoryLayer",
    "MemoryResiliencePolicy",
    "MemoryRoutePlan",
    "MemoryRecognizer",
    "RecognitionConfig",
    "RecognitionLabel",
    "RecognitionResult",
    "RecognitionSignal",
    "canonical_fingerprint",
    "DEFAULT_MEMORY_RECOGNITION_POLICY",
    "MemoryRecognitionPolicy",
    "RecognitionAction",
    "RecognitionDecision",
    "RecognitionPolicyConfig",
    "ExperienceSample",
    "memory_record_to_experience_sample",
    "select_gold_memory_samples",
    "MemorySummary",
    "build_memory_summary",
]