"""
Swarm Sync module for handling CRDT-based genome synchronization and gossip distribution.
"""
import logging
from typing import Any, Dict, List, Protocol, Optional, Union, Tuple

logger = logging.getLogger(__name__)

class NodeLike(Protocol):
    """Protocol defining the interface for a node interacting with SwarmSync."""
    node_id: str
    step_count: int
    gossip_interval: Union[int, float, str]
    current_params: Dict[str, Any]
    last_import_step: int
    import_cooldown: int
    engine: Any
    crdt: Any

    def make_genome(self, params: Dict[str, Any], fitness: float) -> Any: ...
    def accept_genome(self, genome_dict: Dict[str, Any]) -> bool: ...
    def dict_to_genome(self, genome_dict: Dict[str, Any]) -> Any: ...

class SwarmSync:
    """
    Orchestrates the synchronization of genomes between a local node and a distributed CRDT network.
    """
    def __init__(self, node: NodeLike) -> None:
        self.node = node

    async def push(self) -> None:
        """
        Pushes the local champion genome to the CRDT network based on the gossip interval.
        """
        try:
            interval = int(self.node.gossip_interval)
        except (ValueError, TypeError) as e:
            logger.warning(f"Node {self.node.node_id}: Invalid gossip_interval {self.node.gossip_interval}: {e}")
            return

        if self.node.step_count % interval != 0:
            return

        champion_fitness: float = 0.0
        champ = getattr(self.node.engine, 'champion', None)

        if isinstance(champ, (list, tuple)) and len(champ) > 1:
            try:
                champion_fitness = float(champ[1])
            except (TypeError, ValueError) as e:
                logger.debug(f"Node {self.node.node_id}: Failed to parse champion fitness: {e}")

        genome = self.node.make_genome(self.node.current_params, champion_fitness)

        try:
            await self.node.crdt.add_genome(genome)
            logger.debug(f"Node {self.node.node_id} successfully pushed genome to CRDT.")
        except Exception as e:
            logger.error(f"CRDT push error for node {self.node.node_id}: {e}", exc_info=True)

    async def pull(self) -> None:
        """
        Imports superior genomes from the CRDT network into the local evolutionary engine.
        """
        if self.node.step_count - self.node.last_import_step <= self.node.import_cooldown:
            return

        try:
            imported_genomes: List[Dict[str, Any]] = await self.node.crdt.get_top(10)
            imported_count = 0
            for g_dict in imported_genomes:
                if self.node.accept_genome(g_dict):
                    gen = self.node.dict_to_genome(g_dict)
                    self.node.engine.add_genome(gen)
                    imported_count += 1

            self.node.last_import_step = self.node.step_count
            if imported_count > 0:
                logger.debug(f"Node {self.node.node_id} imported {imported_count} genomes.")
        except Exception as e:
            logger.error(f"CRDT pull failed for node {self.node.node_id}: {e}", exc_info=True)

    async def reconcile(self) -> None:
        """
        Performs a complete synchronization cycle.
        """
        await self.push()
        await self.pull()