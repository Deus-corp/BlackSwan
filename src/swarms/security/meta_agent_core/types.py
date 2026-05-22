"""Shared types and protocols for the security meta-agent."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, Protocol, runtime_checkable, TypedDict

SecurityAction = Literal[
    "MAINTAIN",
    "UNBLOCK_ALL",
    "PARTIAL_UNBLOCK",
    "EMERGENCY_FLUSH_INPUT",
    "BLOCK_MORE",
    "ESCALATE",
]

SecurityIncidentType = Literal[
    "file_integrity_alert",
    "vulnerability_alert",
    "open_ports_detected",
    "ip_blocked",
    "all_ips_unblocked",
]

SecurityLLMOutput = TypedDict(
    "SecurityLLMOutput",
    {
        "action": str,
        "confidence": float,
        "rationale": str,
        "allow_global_unblock": bool,
        "allow_partial_unblock": bool,
        "allow_emergency_flush_input": bool,
        "block_new_ips": bool,
    },
    total=False,
)


@runtime_checkable
class StateSource(Protocol):
    @property
    def state(self) -> Mapping[str, Any]:
        ...


@runtime_checkable
class GenomeSink(Protocol):
    async def add_genome(self, genome: Mapping[str, Any]) -> None:
        ...


@runtime_checkable
class LLMGenerator(Protocol):
    def generate(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        ...