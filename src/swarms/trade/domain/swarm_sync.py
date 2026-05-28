"""CRDT-based genome synchronization and gossip distribution for trade nodes."""

from __future__ import annotations

import inspect
import logging
import math
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class NodeLike(Protocol):
    """Expected interface for a node interacting with SwarmSync."""

    node_id: str
    step_count: int
    gossip_interval: int | float | str
    current_params: dict[str, Any]
    last_import_step: int
    import_cooldown: int
    engine: Any
    crdt: Any

    def make_genome(self, params: dict[str, Any], fitness: float) -> Any:
        ...

    def accept_genome(self, genome_dict: dict[str, Any]) -> bool:
        ...

    def dict_to_genome(self, genome_dict: dict[str, Any]) -> Any:
        ...


class SwarmSync:
    """Synchronize local genomes with a distributed CRDT network."""

    DEFAULT_TOP_N = 10

    def __init__(self, node: NodeLike, *, top_n: int = DEFAULT_TOP_N) -> None:
        self.node = node
        self.top_n = max(1, int(top_n))

    async def push(self) -> bool:
        """Push the local champion genome to CRDT when gossip interval matches."""
        interval = self._gossip_interval()
        if interval is None:
            return False

        step_count = self._safe_int(getattr(self.node, "step_count", 0), 0)
        if step_count <= 0 or step_count % interval != 0:
            return False

        champion_fitness = self._champion_fitness()
        genome = self.node.make_genome(dict(getattr(self.node, "current_params", {}) or {}), champion_fitness)

        try:
            await self._maybe_await(self.node.crdt.add_genome(genome))
            logger.debug("[%s] pushed genome to CRDT fitness=%.6f", self.node.node_id, champion_fitness)
            return True
        except Exception:
            logger.exception("[%s] CRDT genome push failed.", self.node.node_id)
            return False

    async def pull(self) -> int:
        """Import acceptable superior genomes from CRDT into local evolutionary engine."""
        step_count = self._safe_int(getattr(self.node, "step_count", 0), 0)
        last_import_step = self._safe_int(getattr(self.node, "last_import_step", 0), 0)
        import_cooldown = max(0, self._safe_int(getattr(self.node, "import_cooldown", 0), 0))

        if step_count - last_import_step <= import_cooldown:
            return 0

        try:
            imported_genomes = await self._maybe_await(self.node.crdt.get_top(self.top_n))
        except Exception:
            logger.exception("[%s] CRDT genome pull failed.", self.node.node_id)
            return 0

        if not isinstance(imported_genomes, list):
            logger.warning("[%s] crdt.get_top returned %s, expected list.", self.node.node_id, type(imported_genomes).__name__)
            return 0

        imported_count = 0

        for genome_dict in imported_genomes:
            if not isinstance(genome_dict, dict):
                continue

            try:
                if not bool(self.node.accept_genome(genome_dict)):
                    continue

                genome = self.node.dict_to_genome(genome_dict)
                self.node.engine.add_genome(genome)
                imported_count += 1

            except Exception:
                logger.debug("[%s] Skipped invalid imported genome: %r", self.node.node_id, genome_dict, exc_info=True)

        self.node.last_import_step = step_count

        if imported_count:
            logger.debug("[%s] imported %d genome(s) from CRDT.", self.node.node_id, imported_count)

        return imported_count

    async def reconcile(self) -> dict[str, Any]:
        """Run one full synchronization cycle and return cycle stats."""
        pushed = await self.push()
        imported = await self.pull()

        return {
            "node_id": str(getattr(self.node, "node_id", "")),
            "pushed": pushed,
            "imported": imported,
            "step_count": self._safe_int(getattr(self.node, "step_count", 0), 0),
        }

    def _gossip_interval(self) -> int | None:
        raw_interval = getattr(self.node, "gossip_interval", 0)

        try:
            interval = int(float(raw_interval))
        except (TypeError, ValueError):
            logger.warning("[%s] Invalid gossip_interval=%r.", self.node.node_id, raw_interval)
            return None

        if interval <= 0:
            logger.warning("[%s] gossip_interval must be positive, got %r.", self.node.node_id, raw_interval)
            return None

        return interval

    def _champion_fitness(self) -> float:
        champion = getattr(getattr(self.node, "engine", None), "champion", None)

        if isinstance(champion, (list, tuple)) and len(champion) > 1:
            return self._safe_float(champion[1], 0.0)

        if isinstance(champion, dict):
            return self._safe_float(champion.get("fitness"), 0.0)

        return self._safe_float(getattr(champion, "fitness", 0.0), 0.0)

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default