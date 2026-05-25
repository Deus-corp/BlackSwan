"""Testing utilities module for the BlackSwan swarm ecosystem.

This module provides shared fixtures, runtime smoke test utilities, and
common testing helper functions to ensure consistency across the test suite.
"""

from src.testing import fixtures, swarm_runtime_smoke

__all__ = [
    "fixtures",
    "swarm_runtime_smoke",
]