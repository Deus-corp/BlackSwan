"""
Episodic Memory (L1) – stores records of market situations and associated optimal strategies.
It is used for population initialization and adaptation to recurring conditions.
"""

import math
import time
from typing import Any, Dict, List, Optional, TypedDict


class MemoryRecord(TypedDict):
    """Type definition for an episodic memory record."""
    volatility: float
    dq: float
    capital: float
    params: Dict[str, Any]
    fitness: float
    timestamp: float
    weight: Optional[float]


class EpisodicMemory:
    """
    Episodic Memory stores records of market situations and associated optimal strategies.
    It's used for population initialization and adaptation to recurring conditions.
    """

    __slots__ = ("records", "max_size", "cleanup_interval", "add_count")

    def __init__(self, max_size: int = 1000) -> None:
        """
        Initializes the EpisodicMemory with a maximum capacity.

        Args:
            max_size (int): The maximum number of records to store in memory.
        """
        self.records: List[MemoryRecord] = []
        self.max_size: int = max_size
        self.cleanup_interval: int = 100
        self.add_count: int = 0

    def add(
        self,
        market_volatility: float,
        dq: float,
        capital: float,
        params: Dict[str, Any],
        fitness: float,
    ) -> None:
        """
        Adds a record of a market situation and an associated optimal strategy.
        """
        record: MemoryRecord = {
            "volatility": float(market_volatility),
            "dq": float(dq),
            "capital": float(capital),
            "params": params,
            "fitness": float(fitness),
            "timestamp": time.time(),
            "weight": None,
        }
        self.records.append(record)
        self.add_count += 1

        if self.add_count >= self.cleanup_interval:
            self._forget_old_entries()
            self.add_count = 0

        if len(self.records) > self.max_size:
            self.records.pop(0)

    def find_similar(self, current_volatility: float, current_dq: float, top_k: int = 3) -> List[MemoryRecord]:
        """
        Finds records most similar to the current market situation.
        Uses Euclidean distance in a normalized space.
        """
        if not self.records:
            return []

        cur_vol = float(current_volatility)
        cur_dq = float(current_dq)

        safe_vol = max(0.01, abs(cur_vol))
        safe_dq = max(0.01, abs(cur_dq))

        def calculate_distance(rec: MemoryRecord) -> float:
            vol_diff = (rec["volatility"] - cur_vol) / safe_vol
            dq_diff = (rec["dq"] - cur_dq) / safe_dq
            return math.sqrt(vol_diff**2 + dq_diff**2)

        return sorted(self.records, key=calculate_distance)[:top_k]

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Converts the stored records into a list of dictionaries."""
        return [dict(rec) for rec in self.records]

    def from_dict_list(self, data: List[Dict[str, Any]]) -> None:
        """Loads records from a list of dictionaries, ensuring max_size compliance."""
        self.records = [dict(rec) for rec in data[-self.max_size:]]
        self.add_count = 0

    def __len__(self) -> int:
        """Returns the number of records currently stored in memory."""
        return len(self.records)

    def _forget_old_entries(self) -> None:
        """
        Removes old records based on exponential decay (~1 hour half-life).
        """
        if not self.records:
            return

        now = time.time()
        decay_constant = 3600.0

        for rec in self.records:
            age = now - rec.get("timestamp", now)
            rec["weight"] = math.exp(-abs(age) / decay_constant)

        self.records = [r for r in self.records if (r.get("weight") or 1.0) >= 0.1]
        
        if len(self.records) > self.max_size:
            self.records.sort(key=lambda r: r.get("weight", 0.0), reverse=True)
            self.records = self.records[:self.max_size]