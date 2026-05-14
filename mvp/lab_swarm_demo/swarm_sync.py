"""
Swarm Sync — CRDT/Gossip/Genome import.
"""
import logging
import random
from swarm_config import config

logger = logging.getLogger(__name__)


class SwarmSync:
    def __init__(self, node):
        self.node = node

    async def push(self):
        """Отправляет свой геном в рой."""
        if self.node.step_count % int(self.node.gossip_interval) != 0:
            return
        try:
            genome_to_share = self.node.make_genome(
                self.node.current_params,
                self.node.engine.champion[1] if hasattr(self.node.engine, 'champion') and self.node.engine.champion else 0.0
            )
            envelope = sign_envelope(genome_to_share, self.node.gossip_private_key, self.node.gossip_key_id)
            await self.node.gossip.broadcast(envelope)
        except Exception as e:
            logger.debug(f"Gossip error: {e}")

    async def pull(self):
        """Импортирует лучшие геномы из CRDT."""
        if self.node.step_count - self.node.last_import_step <= self.node.import_cooldown:
            return
        try:
            imported = await self.node.crdt.get_top(10)
            for g in imported:
                if self.node.accept_genome(g):
                    gen = self.node.dict_to_genome(g)
                    self.node.engine.add_genome(gen)
            self.node.last_import_step = self.node.step_count
        except Exception:
            pass

    async def reconcile(self):
        """Полный цикл синхронизации: push + pull."""
        await self.push()
        await self.pull()