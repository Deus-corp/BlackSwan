"""Utility modules for the BlackSwan project.

Provides core infrastructure for logging, serialization, and import optimization.
"""

from src.utils.import_optimizer import optimize_imports
from src.utils.logging import setup_logging
from src.utils.serialization import serialize, deserialize

__all__ = [
    "optimize_imports",
    "setup_logging",
    "serialize",
    "deserialize",
]