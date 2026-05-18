"""
Episodic Memory (L1) – stores records of market situations and associated optimal strategies.
It is used for population initialization and adaptation to recurring conditions.
"""
import math
import time
from typing import Any, Dict, List, Tuple

class EpisodicMemory:
    """
    Episodic Memory stores records of market situations and associated optimal strategies.
    It's used for population initialization and adaptation to recurring conditions.

    Each record typically contains:
    - "volatility" (float): Market volatility.
    - "dq" (float): Delta-Q metric.
    - "capital" (float): Capital at the time of strategy.
    - "params" (Dict[str, Any]): Dictionary of strategy parameters.
    - "fitness" (float): Fitness score of the strategy.
    - "timestamp" (float): Unix timestamp when the record was added.
    - "weight" (float, added dynamically): Calculated decay weight based on age (used in cleanup).
    """
    def __init__(self, max_size: int = 1000) -> None:
        """
        Initializes the EpisodicMemory with a maximum capacity.

        Args:
            max_size (int): The maximum number of records to store.
        """
        self.records: List[Dict[str, Any]] = []  # List of records
        self.max_size: int = max_size
        # self.decay_factor: float = 0.9  # Coefficient for forgetting (0..1) - currently unused, time-based decay is used.
        self.cleanup_interval: int = 100  # Interval (in additions) for triggering cleanup
        self.add_count: int = 0

    def add(self, market_volatility: float, dq: float, capital: float, params: Dict[str, Any], fitness: float) -> None:
        """
        Adds a record of a market situation and an associated optimal strategy.

        Args:
            market_volatility (float): The current market volatility.
            dq (float): The delta-Q metric.
            capital (float): The capital at the time of the strategy.
            params (Dict[str, Any]): Dictionary of strategy parameters.
            fitness (float): The fitness score of the strategy.
        """
        record: Dict[str, Any] = {
            "volatility": market_volatility,
            "dq": dq,
            "capital": capital,
            "params": params,
            "fitness": fitness,
            "timestamp": time.time(), # Add timestamp when the record is created
        }
        self.records.append(record)
        self.add_count += 1

        if self.add_count % self.cleanup_interval == 0:
            self._forget_old_entries()
        
        # This ensures max_size limit is strictly adhered to, even if cleanup doesn't remove enough.
        # It removes the oldest entry (first added) if the capacity is exceeded.
        if len(self.records) > self.max_size:
            self.records.pop(0)

    def find_similar(self, current_volatility: float, current_dq: float, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Finds records most similar to the current market situation.
        Returns a list of top_k records, sorted by similarity (lowest distance first).

        Similarity is calculated using Euclidean distance in a normalized space
        of volatility and delta-Q, where normalization is done relative to current values.

        Args:
            current_volatility (float): The current market volatility.
            current_dq (float): The current delta-Q metric.
            top_k (int): The number of most similar records to return.

        Returns:
            List[Dict[str, Any]]: A list of the top_k most similar records.
        """
        if not self.records:
            return []

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for rec in self.records:
            # Euclidean distance in normalized space
            # Using max(0.01, ...) in the denominator to prevent division by zero or extremely small numbers.
            # This scales differences relative to the current values, which can be sensitive if current values are very low.
            vol_diff = (rec["volatility"] - current_volatility) / max(0.01, current_volatility)
            dq_diff = (rec["dq"] - current_dq) / max(0.01, current_dq)
            dist = math.sqrt(vol_diff**2 + dq_diff**2)
            scored.append((dist, rec))

        # Sort by distance (ascending) to get the most similar records first.
        scored.sort(key=lambda x: x[0])
        # Return only the records, discarding the distance, and truncate to top_k.
        return [rec for _, rec in scored[:top_k]]

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """
        Converts the stored records into a list of dictionaries.
        Each dictionary returned is a shallow copy of the internal record to prevent
        unintended external modification of the internal state.

        Returns:
            List[Dict[str, Any]]: A list of all records as dictionaries.
        """
        return [dict(rec) for rec in self.records]

    def from_dict_list(self, data: List[Dict[str, Any]]) -> None:
        """
        Loads records from a list of dictionaries.
        Only the most recent `max_size` records (based on their order in the input `data` list) are kept.
        If a record in `data` lacks a 'timestamp' key, it will be treated as if it has a current timestamp
        when decay is calculated, effectively giving it maximum weight.

        Args:
            data (List[Dict[str, Any]]): A list of dictionaries representing records.
        """
        # Ensure only up to max_size records are loaded, taking the newest ones if `data` is ordered
        # from oldest to newest. Create shallow copies for robustness.
        self.records = [dict(rec) for rec in data[-self.max_size:]]
        # Reset add_count after loading, as the history of additions is unknown.
        # This means `_forget_old_entries` will run after `cleanup_interval` more calls to `add`.
        self.add_count = 0

    def __len__(self) -> int:
        """
        Returns the number of records currently stored in memory.

        Returns:
            int: The current number of records.
        """
        return len(self.records)
    
    def _forget_old_entries(self) -> None:
        """
        Removes old records based on an exponential decay weight tied to their age.
        Records without a 'timestamp' (e.g., legacy data or deserialized without it)
        will be assigned a default weight (1.0), preventing immediate forgetting.
        The decay uses a half-life of approximately 1 hour (3600 seconds).

        If, after decay filtering, the number of records still exceeds `max_size`,
        the lowest-weighted records are removed until the `max_size` limit is met.
        """
        if not self.records:
            return
        
        now: float = time.time()
        
        # Calculate weight for each record. If 'timestamp' is missing, age is 0, weight is 1.0.
        for rec in self.records:
            age: float = now - rec.get("timestamp", now)
            rec["weight"] = math.exp(-age / 3600.0)  # Exponential decay with ~1 hour half-life
        
        # Filter out records with a weight below a threshold (0.1).
        # Records missing a 'weight' key are implicitly given a weight of 1.0, preserving them.
        self.records = [r for r in self.records if r.get("weight", 1.0) >= 0.1]
        
        # If after filtering, the number of records still exceeds max_size,
        # sort by weight (descending) and truncate to max_size.
        if len(self.records) > self.max_size:
            # Sort by weight (descending). Records without 'weight' will be treated as 0.0,
            # ensuring they are at the end and are the first to be removed if truncation is necessary.
            self.records = sorted(self.records, key=lambda r: r.get("weight", 0.0), reverse=True)
            self.records = self.records[:self.max_size]
