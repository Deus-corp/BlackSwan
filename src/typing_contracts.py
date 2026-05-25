"""Centralized type definitions and runtime validation for core domain objects."""

from __future__ import annotations
from typing import Protocol, runtime_checkable

@runtime_checkable
class ConfigProtocol(Protocol):
    """Protocol for swarm configuration objects, ensuring they provide a validation mechanism.

    Classes implementing this protocol must provide a `validate` method that
    checks the integrity of the configuration parameters.
    """

    def validate(self) -> bool:
        """Validates the configuration object's internal state.

        Returns:
            bool: True if the configuration state is valid, False otherwise.
        """
        ...