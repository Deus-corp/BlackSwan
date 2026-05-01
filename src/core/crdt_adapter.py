"""
Адаптер, который заменяет CRDTState на GenomeCRDT с SQLite‑персистентностью.
Совместим с текущим node_agent.py.
"""
import uuid
import os
import time
import asyncio
from typing import Any, Dict, Optional
from src.core.crdt_layer import GenomeCRDT, CRDTStorage

DB_PATH = os.environ.get("CRDT_DB_PATH", "./crdt_state.db")

class CRDTAdapter:
    def __init__(self, node_id: str):
        self.node_id = node_id
        storage = CRDTStorage(DB_PATH)
        self.crdt = GenomeCRDT(node_id, storage=storage)

    async def add_genome(self, genome: Dict[str, Any]) -> str:
        """Добавляет геном и возвращает gid."""
        # Извлекаем gid из генома, если есть, иначе генерируем
        gid = genome.get("gid") or str(uuid.uuid4())
        payload = {
            "params": genome.get("params", {}),
            "fitness": genome.get("fitness", 0.0),
            "niche": genome.get("niche", "exploration"),
            "origin": genome.get("origin", self.node_id),
            "lineage": genome.get("lineage", [self.node_id]),
            "ts": genome.get("ts", time.time()),
            "ver": genome.get("ver", 0),
            "node": genome.get("node", self.node_id),
        }
        self.crdt.upsert(gid, payload)
        return gid

    async def merge(self, remote_items: Dict[str, Dict[str, Any]]) -> None:
        """Принимает словарь {gid: genome_dict} от других узлов."""
        for gid, genome in remote_items.items():
            # Превращаем в операцию upsert; новый CRDT сам разберётся,
            # применять ли её (по версии и node_id)
            self.crdt.upsert(gid, genome)

    async def get_delta(self, known_versions: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
        """
        Возвращает словарь геномов, которые новее, чем known_versions.
        Для совместимости с текущим gossip.
        """
        # Получаем все объекты, у которых версия больше, чем в known_versions
        all_state = self.crdt.state()
        delta = {}
        for gid, payload in all_state.items():
            ver = payload.get("ver", 0)
            if gid not in known_versions or known_versions[gid] < ver:
                delta[gid] = payload
        return delta

    async def get_versions(self) -> Dict[str, int]:
        """Возвращает {gid: ver} для всех геномов."""
        all_state = self.crdt.state()
        return {gid: payload.get("ver", 0) for gid, payload in all_state.items()}

    async def get_top(self, n: int = 5):
        """Возвращает топ-N геномов по фитнесу."""
        all_state = self.crdt.state()
        sorted_genomes = sorted(all_state.values(), key=lambda x: x.get("fitness", 0.0), reverse=True)
        return sorted_genomes[:n]

    async def prune(self) -> None:
        """Удаляет старые записи (реализовано на уровне CRDTStorage по TTL)."""
        # В адаптере можно не вызывать, т.к. старый CRDTState сам чистил по TTL.
        # В новом CRDT очистка делается в CRDTStorage при необходимости.
        pass

    @property
    def state(self):
        """Для обратной совместимости с crdt_size в логах."""
        return self.crdt.state()