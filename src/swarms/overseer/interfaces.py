"""Shared interfaces for the overseer subsystem."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StateSource(Protocol):
    @property
    def state(self) -> Mapping[str, Any]:
        """Return the current CRDT-backed state snapshot."""


@runtime_checkable
class GenomeSink(Protocol):
    async def add_genome(self, genome: Mapping[str, Any]) -> None:
        """Persist a genome/command into the coordination layer."""


@runtime_checkable
class LLMGenerator(Protocol):
    def generate(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        """Generate a completion from a prompt."""