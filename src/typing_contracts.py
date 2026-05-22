"""Centralized type definitions and runtime validation for core domain objects."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

@runtime_checkable
class ConfigProtocol(Protocol):
    """Protocol for swarm configuration objects."""
    def validate(self) -> bool: ...
