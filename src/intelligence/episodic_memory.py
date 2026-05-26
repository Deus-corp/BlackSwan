"""Episodic Memory (L1) for market situations and associated strategies."""

from __future__ import annotations

import copy
import math
import time
from typing import Any, Optional, TypedDict


class MemoryRecord(TypedDict, total=False):
    """Type definition for an episodic memory record."""

    volatility: float
    dq: float
    capital: float
    params: dict[str, Any]
    fitness: float
    timestamp: float
    weight: Optional[float]
    niche: str


class EpisodicMemory:
    """Bounded in-memory store for strategy episodes under market conditions."""

    __slots__ = ("records", "max_size", "cleanup_interval", "add_count", "decay_seconds", "min_weight")

    DEFAULT_MAX_SIZE = 1000
    DEFAULT_CLEANUP_INTERVAL = 100
    DEFAULT_DECAY_SECONDS = 3600.0
    DEFAULT_MIN_WEIGHT = 0.1

    def __init__(
        self,
        max_size: int = DEFAULT_MAX_SIZE,
        *,
        cleanup_interval: int = DEFAULT_CLEANUP_INTERVAL,
        decay_seconds: float = DEFAULT_DECAY_SECONDS,
        min_weight: float = DEFAULT_MIN_WEIGHT,
    ) -> None:
        self.max_size = max(1, int(max_size))
        self.cleanup_interval = max(1, int(cleanup_interval))
        self.decay_seconds = max(1.0, float(decay_seconds))
        self.min_weight = max(0.0, min(1.0, float(min_weight)))

        self.records: list[MemoryRecord] = []
        self.add_count = 0

    def add(
        self,
        market_volatility: float,
        dq: float,
        capital: float,
        params: dict[str, Any],
        fitness: float,
        niche: str = "",
    ) -> None:
        """Add a market/strategy episode."""
        if not isinstance(params, dict):
            raise TypeError("params must be a dictionary")

        record: MemoryRecord = {
            "volatility": self._safe_float(market_volatility),
            "dq": self._safe_float(dq),
            "capital": self._safe_float(capital),
            "params": copy.deepcopy(params),
            "fitness": self._safe_float(fitness),
            "timestamp": time.time(),
            "weight": None,
        }

        clean_niche = str(niche or "").strip()
        if clean_niche:
            record["niche"] = clean_niche

        self.records.append(record)
        self.add_count += 1

        if self.add_count >= self.cleanup_interval:
            self._forget_old_entries()
            self.add_count = 0

        self._trim_to_max_size()

    def find_similar(
        self,
        current_volatility: float,
        current_dq: float,
        top_k: int = 3,
        *,
        min_fitness: Optional[float] = None,
    ) -> list[MemoryRecord]:
        """Find records most similar to current volatility/DQ conditions."""
        if not self.records:
            return []

        limit = max(0, int(top_k))
        if limit == 0:
            return []

        cur_vol = self._safe_float(current_volatility)
        cur_dq = self._safe_float(current_dq)

        safe_vol = max(0.01, abs(cur_vol))
        safe_dq = max(0.01, abs(cur_dq))
        min_fit = None if min_fitness is None else self._safe_float(min_fitness)

        candidates = [
            record
            for record in self.records
            if min_fit is None or self._safe_float(record.get("fitness"), 0.0) >= min_fit
        ]

        def score(record: MemoryRecord) -> tuple[float, float, float]:
            vol_diff = (self._safe_float(record.get("volatility"), 0.0) - cur_vol) / safe_vol
            dq_diff = (self._safe_float(record.get("dq"), 0.0) - cur_dq) / safe_dq
            distance = math.sqrt(vol_diff**2 + dq_diff**2)

            fitness = self._safe_float(record.get("fitness"), 0.0)
            weight = self._safe_float(record.get("weight"), 1.0)
            return distance, -fitness, -weight

        return [copy.deepcopy(record) for record in sorted(candidates, key=score)[:limit]]

    def to_dict_list(self) -> list[dict[str, Any]]:
        """Return a deep-copy list of records."""
        return [copy.deepcopy(dict(record)) for record in self.records]

    def from_dict_list(self, data: list[dict[str, Any]]) -> None:
        """Load records from dictionaries, normalizing fields and respecting max_size."""
        if not isinstance(data, list):
            raise TypeError("data must be a list of dictionaries")

        loaded: list[MemoryRecord] = []
        for item in data[-self.max_size :]:
            record = self._normalize_record(item)
            if record is not None:
                loaded.append(record)

        self.records = loaded[-self.max_size :]
        self.add_count = 0

    def clear(self) -> None:
        """Clear all memory records."""
        self.records.clear()
        self.add_count = 0

    def best(self, top_k: int = 5) -> list[MemoryRecord]:
        """Return top records by fitness."""
        limit = max(0, int(top_k))
        if limit == 0:
            return []

        records = sorted(
            self.records,
            key=lambda record: self._safe_float(record.get("fitness"), 0.0),
            reverse=True,
        )
        return [copy.deepcopy(record) for record in records[:limit]]

    def __len__(self) -> int:
        return len(self.records)

    def _forget_old_entries(self) -> None:
        """Apply exponential age decay and drop weak records."""
        if not self.records:
            return

        now = time.time()
        kept: list[MemoryRecord] = []

        for record in self.records:
            age = max(0.0, now - self._safe_float(record.get("timestamp"), now))
            weight = math.exp(-age / self.decay_seconds)
            record["weight"] = weight

            if weight >= self.min_weight:
                kept.append(record)

        self.records = kept
        self._trim_to_max_size()

    def _trim_to_max_size(self) -> None:
        if len(self.records) <= self.max_size:
            return

        self.records.sort(
            key=lambda record: (
                self._safe_float(record.get("weight"), 1.0),
                self._safe_float(record.get("fitness"), 0.0),
                self._safe_float(record.get("timestamp"), 0.0),
            ),
            reverse=True,
        )
        self.records = self.records[: self.max_size]

    def _normalize_record(self, item: Any) -> Optional[MemoryRecord]:
        if not isinstance(item, dict):
            return None

        params = item.get("params", {})
        if not isinstance(params, dict):
            return None

        record: MemoryRecord = {
            "volatility": self._safe_float(item.get("volatility"), 0.0),
            "dq": self._safe_float(item.get("dq"), 0.0),
            "capital": self._safe_float(item.get("capital"), 0.0),
            "params": copy.deepcopy(params),
            "fitness": self._safe_float(item.get("fitness"), 0.0),
            "timestamp": self._safe_float(item.get("timestamp"), time.time()),
            "weight": None,
        }

        weight = item.get("weight")
        if weight is not None:
            record["weight"] = self._safe_float(weight, 1.0)

        niche = str(item.get("niche", "") or "").strip()
        if niche:
            record["niche"] = niche

        return record

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default

        if not math.isfinite(number):
            return default

        return number