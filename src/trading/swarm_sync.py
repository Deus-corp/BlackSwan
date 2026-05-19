"""
Swarm Sync — CRDT/Gossip/Genome import.

This module provides the SwarmSync class, which manages the synchronization
of genomes within a swarm. It handles pushing local genomes to a gossip network
and pulling superior genomes from a CRDT (Conflict-Free Replicated Data Type)
for integration.
"""
import logging
import random
from typing import Any, List, Dict, Union, Callable, Protocol, Optional, Tuple

# Project root is in PYTHONPATH
# is run from the project root.
from swarm_config import config

logger = logging.getLogger(__name__)

# Define a Protocol for the node to improve type hinting and clarify expectations
class NodeLike(Protocol):
    """
    Protocol defining the expected interface for the node object
    that SwarmSync interacts with.
    """
    node_id: str
    step_count: int
    gossip_interval: Union[int, float, str]
    make_genome: Callable[[Dict[str, Any], float], Any] # genome creation method
    current_params: Dict[str, Any]
    engine: Any # Expected to have a 'champion' attribute (e.g., list/tuple [genome, fitness]) and an 'add_genome' method.
    gossip_private_key: Any # Not directly used by SwarmSync, but often part of node context.
    gossip_key_id: Any # Not directly used by SwarmSync, but often part of node context.
    gossip: Any # Expected to have an async 'broadcast' method, though not directly used in current SwarmSync logic.
    crdt: Any # Expected to have an async 'add_genome' method and an async 'get_top' method.
    accept_genome: Callable[[Dict[str, Any]], bool]
    dict_to_genome: Callable[[Dict[str, Any]], Any]
    last_import_step: int
    import_cooldown: int


class SwarmSync:
    """
    Manages synchronization for a swarm node, handling genome pushes to a gossip network
    and pulls from a CRDT for genome import.

    This class orchestrates the distribution of locally optimized genomes
    and the acquisition of superior genomes from the wider swarm.
    """
    def __init__(self, node: NodeLike) -> None:
        """
        Initializes the SwarmSync component.

        Args:
            node: The node instance this sync component is associated with.
                  Must conform to the `NodeLike` protocol, providing attributes like:
                  - `node_id` (str): Unique identifier for the node.
                  - `step_count` (int): Current step/iteration count of the node.
                  - `gossip_interval` (Union[int, float, str]): Interval for gossip pushes.
                  - `make_genome` (Callable): Method to create a genome from parameters and fitness.
                  - `current_params` (Dict[str, Any]): The node's current parameters.
                  - `engine` (Any): An object with a `champion` attribute (expected to be a list/tuple `[genome, fitness]`)
                                    and an `add_genome` method (`add_genome(genome: Any) -> None`).
                  - `gossip_private_key` (Any): Private key for signing gossip messages (not directly used by SwarmSync).
                  - `gossip_key_id` (Any): ID for the gossip private key (not directly used by SwarmSync).
                  - `gossip` (Any): An object with a `broadcast` async method (not directly used by SwarmSync).
                  - `crdt` (Any): An object with an `add_genome` async method (`add_genome(genome: Any) -> None`)
                                  and an `get_top` async method (`get_top(count: int) -> List[Dict[str, Any]]`).
                  - `accept_genome` (Callable): Method to determine if a genome should be accepted (`accept_genome(genome_dict: Dict[str, Any]) -> bool`).
                  - `dict_to_genome` (Callable): Method to convert a dictionary to a genome object (`dict_to_genome(genome_dict: Dict[str, Any]) -> Any`).
                  - `last_import_step` (int): Last step count when genomes were imported.
                  - `import_cooldown` (int): Minimum steps between genome imports.
        """
        self.node = node

    async def push(self) -> None:
        """
        Pushes the node's current champion genome to the CRDT network for distribution.

        This method checks if the current step aligns with the `gossip_interval`.
        It retrieves the champion genome from the node's engine, creates a genome
        representation, and attempts to add it to the CRDT.
        """
        # Publish genome to CRDT; SafeGossipAdapter will propagate it via deltas.
        gossip_interval: int
        try:
            gossip_interval = int(self.node.gossip_interval)
        except (ValueError, TypeError) as e:
            logger.warning(f"Node {self.node.node_id}: Invalid gossip_interval '{self.node.gossip_interval}'. Skipping push. Error: {e}")
            return
        
        if self.node.step_count % gossip_interval != 0:
            return

        champion_value: float = 0.0
        # Check if engine has a champion and it's a valid list/tuple with fitness
        champ: Optional[Union[List[Any], Tuple[Any, float]]] = getattr(self.node.engine, 'champion', None)
        
        if champ is not None and isinstance(champ, (list, tuple)) and len(champ) > 1:
            try:
                champion_value = float(champ[1])
            except (TypeError, ValueError) as e:
                logger.warning(f"Node {self.node.node_id}: Could not convert champion fitness '{champ[1]}' to float. Using 0.0. Error: {e}")
                pass # Use default 0.0 if conversion fails

        genome: Any = self.node.make_genome(self.node.current_params, champion_value)
        
        # Save to CRDT – the delta mechanism will deliver it to neighbors
        try:
            await self.node.crdt.add_genome(genome)
            logger.debug(f"Node {self.node.node_id} successfully pushed genome to CRDT.")
        except Exception as e:
            logger.error(f"CRDT push error for node {self.node.node_id}: {e}", exc_info=True)

    async def pull(self) -> None:
        """
        Imports top genomes from the CRDT (Conflict-Free Replicated Data Type) into the node's engine.

        This method respects a `import_cooldown` period to prevent excessive imports.
        It retrieves a batch of top genomes, filters them using `accept_genome`,
        and adds valid ones to the node's evolutionary engine.
        """
        # Respect the import cooldown period
        if self.node.step_count - self.node.last_import_step <= self.node.import_cooldown:
            return

        logger.debug(f"Node {self.node.node_id} pulling genomes from CRDT at step {self.node.step_count}...")
        try:
            # Retrieve a batch of top genomes from CRDT
            imported: List[Dict[str, Any]] = await self.node.crdt.get_top(10)
            imported_count: int = 0
            for g_dict in imported:
                # Validate and convert the genome before adding to the engine
                if self.node.accept_genome(g_dict):
                    gen: Any = self.node.dict_to_genome(g_dict)
                    self.node.engine.add_genome(gen)
                    imported_count += 1
            self.node.last_import_step = self.node.step_count
            logger.debug(f"Node {self.node.node_id} imported {imported_count} genomes from CRDT.")
        except Exception as e:
            # The original code's comment indicated a bug fix here (swallowing exceptions).
            # This updated code ensures the error is logged for debugging.
            logger.error(f"CRDT pull failed for node {self.node.node_id}: {e}", exc_info=True)

    async def reconcile(self) -> None:
        """
        Performs a full synchronization cycle: pushing local genomes and pulling remote ones.
        """
        await self.push()
        await self.pull()