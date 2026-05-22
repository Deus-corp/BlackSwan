"""Shared protocols and interfaces for the overseer subsystem."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StateSource(Protocol):
    """Protocol for components that expose an immutable state snapshot."""

    @property
    def state(self) -> Mapping[str, Any]:
        """Return the current CRDT-backed state snapshot."""
        ...


@runtime_checkable
class GenomeSink(Protocol):
    """Protocol for components that accept serialized genomes or commands."""

    async def add_genome(self, genome: Mapping[str, Any]) -> None:
        """Persist a genome or command structure into the coordination layer."""
        ...


@runtime_checkable
class LLMGenerator(Protocol):
    """Protocol for LLM-based text generation services."""

    def generate(
        self, 
        prompt: str, 
        *, 
        max_tokens: int,
        temperature: float
    ) -> str:
        """Generate a text completion from a prompt with specific constraints."""
        ...