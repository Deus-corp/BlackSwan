"""Testing helpers package.

Keep this package initializer lightweight.

Unit tests may import small helper modules such as ``src.testing.seed_directive``.
Importing ``src.testing`` must not eagerly import runtime smoke modules or
optional swarm implementations.
"""

from __future__ import annotations

__all__ = [
    "fixtures",
    "seed_directive",
    "swarm_runtime_smoke",
]