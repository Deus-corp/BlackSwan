"""Shared protocols and interfaces for the overseer subsystem.

These protocols are intentionally structural. They describe only the minimum
capabilities the overseer_core needs from runtime components.

Compatibility note:
    Current CRDTAdapter is expected to satisfy StateSource + GenomeSink through:
        .state
        async .add_genome(...)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StateSource(Protocol):
    """Protocol for components that expose a CRDT-backed state snapshot."""

    @property
    def state(self) -> Mapping[str, Any]:
        """Return current shared state snapshot."""
        ...


@runtime_checkable
class GenomeSink(Protocol):
    """Protocol for components that accept serialized CRDT records.

    The name add_genome is kept for compatibility with the existing CRDT layer.
    In the new common runtime this method may receive:
    - canonical swarm_command
    - canonical swarm_event
    - canonical swarm_heartbeat
    - legacy records
    """

    async def add_genome(self, genome: Mapping[str, Any]) -> None:
        """Persist a genome/command/event/heartbeat into the coordination layer."""
        ...


@runtime_checkable
class RecordSink(Protocol):
    """Optional protocol for future generic record sinks."""

    async def add_record(self, record: Mapping[str, Any]) -> None:
        """Persist a generic canonical swarm record."""
        ...


@runtime_checkable
class EventSink(Protocol):
    """Optional protocol for future event-specific sinks."""

    async def add_event(self, event: Mapping[str, Any]) -> None:
        """Persist a canonical swarm event."""
        ...


@runtime_checkable
class CommandSink(Protocol):
    """Optional protocol for future command-specific sinks."""

    async def add_command(self, command: Mapping[str, Any]) -> None:
        """Persist a canonical swarm command."""
        ...


@runtime_checkable
class LLMGenerator(Protocol):
    """Protocol for LLM-based text generation services.

    Compatible with the existing LLMClient.generate(prompt, *, max_tokens, temperature)
    and tolerant of richer API clients that accept more keyword arguments.
    """

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
        **kwargs: Any,
    ) -> str:
        """Generate a text completion from a prompt."""
        ...