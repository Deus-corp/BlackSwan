"""
Initializes the execution package, exposing core components.
"""
from typing import List

from .backend import ExecutionBackend
from .factory import build_backend

__all__: List[str] = ["ExecutionBackend", "build_backend"]