"""
Swarm Sync — CRDT/Gossip/Genome import.

This module provides the SwarmSync class, which manages the synchronization
of genomes within a swarm. It handles pushing local genomes to a gossip network
and pulling superior genomes from a CRDT (Conflict-Free Replicated Data Type)
for integration.
"""
import logging
import random
from typing import Any, List, Dict, Union

# Assuming 'mvp/lab_swarm_demo' is in PYTHONPATH or the script
# is run from the project root.
from swarm_config import config

logger = logging.getLogger(__name__)

class SwarmSync:
    """
    Manages synchronization for a swarm node, handling genome pushes to a gossip network
    and pulls from a CRDT for genome import.

    This class orchestrates the distribution of locally optimized genomes
    and the acquisition of superior genomes from the wider swarm.
    """
    def __init__(self, node: Any) -> None:
        """
        Initializes the SwarmSync component.

        Args:
            node: The node instance this sync component is associated with.
                  Expected attributes on `node`:
                  - `step_count` (int): Current step/iteration count of the node.
                  - `gossip_interval` (Union[int, float, str]): Interval for gossip pushes.
                  - `make_genome` (Callable): Method to create a genome from parameters and fitness.
                  - `current_params` (Dict[str, Any]): The node's current parameters.
                  - `engine` (Any): An object with a `champion` attribute (e.g., list/tuple [genome, fitness])
                                    and an `add_genome` method.
                  - `gossip_private_key` (Any): Private key for signing gossip messages.
                  - `gossip_key_id` (Any): ID for the gossip private key.
                  - `gossip` (Any): An object with a `broadcast` async method.
                  - `crdt` (Any): An object with an `get_top` async method.
                  - `accept_genome` (Callable): Method to determine if a genome should be accepted.
                  - `dict_to_genome` (Callable): Method to convert a dictionary to a genome object.
                  - `last_import_step` (int): Last step count when genomes were imported.
                  - `import_cooldown` (int): Minimum steps between genome imports.
        """
        self.node = node

    async def push(self) -> None:
        # Публикуем геном в CRDT; SafeGossipAdapter сам распространит его через дельты
        try:
            gossip_interval = int(self.node.gossip_interval)
        except (ValueError, TypeError):
            return
        if self.node.step_count % gossip_interval != 0:
            return

        champion_value: float = 0.0
        if hasattr(self.node.engine, 'champion') and self.node.engine.champion:
            champ = self.node.engine.champion
            if isinstance(champ, (list, tuple)) and len(champ) > 1:
                try:
                    champion_value = float(champ[1])
                except (TypeError, ValueError):
                    pass

        genome = self.node.make_genome(self.node.current_params, champion_value)
        # Сохраняем в CRDT – механизм дельт сам доставит соседям
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
            imported_count = 0
            for g_dict in imported:
                # Validate and convert the genome before adding to the engine
                if self.node.accept_genome(g_dict):
                    gen = self.node.dict_to_genome(g_dict)
                    self.node.engine.add_genome(gen)
                    imported_count += 1
            self.node.last_import_step = self.node.step_count
            logger.debug(f"Node {self.node.node_id} imported {imported_count} genomes from CRDT.")
        except Exception as e:
            # BUG FIX: Swallowing all exceptions with 'pass' is bad practice.
            # Log the error to aid debugging and maintain system visibility.
            logger.error(f"CRDT pull failed for node {self.node.node_id}: {e}", exc_info=True)

    async def reconcile(self) -> None:
        """
        Performs a full synchronization cycle: pushing local genomes and pulling remote ones.
        """
        await self.push()
        await self.pull()