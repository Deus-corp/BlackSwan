"""
Execution package initialization.

Provides a clean entry point for the execution subsystem by exposing the
base ExecutionBackend class and the factory function used to instantiate
concrete implementations.
"""

from typing import Final

from .backend import ExecutionBackend
from .factory import build_backend

__all__: Final[list[str]] = [
    "ExecutionBackend",
    "build_backend",
]