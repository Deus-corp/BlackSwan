"""Testing helpers package.

Keep this package initializer lightweight. Unit tests may import small helper
modules such as ``src.testing.seed_directive``; importing this package must not
eagerly import heavyweight runtime smoke modules or optional swarms.
"""

from __future__ import annotations

__all__ = [
    "fixtures",
    "seed_directive",
    "swarm_runtime_smoke",
]