"""
Episodic Memory (L1) – запоминает рыночные ситуации и связанные с ними лучшие стратегии.
Используется для инициализации популяции и адаптации к повторяющимся условиям.
"""
from typing import Dict, List, Optional, Tuple, Any
import math
import time

class EpisodicMemory:
    """
    Episodic Memory stores records of market situations and associated optimal strategies.
    It's used for population initialization and adaptation to recurring conditions.
    """
    def __init__(self, max_size: int = 1000):
        """
        Initializes the EpisodicMemory with a maximum capacity.

        Args:
            max_size (int): The maximum number of records to store.
        """
        self.records: List[Dict[str, Any]] = []  # список записей (volatility, dq, capital, params, fitness, timestamp, weight)
        self.max_size = max_size
        self.decay_factor = 0.9  # коэффициент забывания (0..1) - currently unused, _forget_old_entries uses time-based decay
        self.cleanup_interval = 100  # каждые 100 добавлений – очистка
        self.add_count = 0

    def add(self, market_volatility: float, dq: float, capital: float, params: Dict, fitness: float) -> None:
        """
        Добавляет запись о рыночной ситуации и лучшей стратегии.

        Args:
            market_volatility (float): The current market volatility.
            dq (float): The delta-Q metric.
            capital (float): The capital at the time of the strategy.
            params (Dict): Dictionary of strategy parameters.
            fitness (float): The fitness score of the strategy.
        """
        record: Dict[str, Any] = {
            "volatility": market_volatility,
            "dq": dq,
            "capital": capital,
            "params": params,
            "fitness": fitness,
            "timestamp": time.time(), # Добавляем отметку времени при добавлении
        }
        self.records.append(record)
        self.add_count += 1

        if self.add_count % self.cleanup_interval == 0:
            self._forget_old_entries()
        
        if len(self.records) > self.max_size:
            # If records exceed max_size after potential cleanup, remove the oldest (first added)
            # This ensures max_size limit is strictly adhered to, even if cleanup doesn't remove enough
            self.records.pop(0)

    def find_similar(self, current_volatility: float, current_dq: float, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Ищет записи, наиболее похожие на текущую рыночную ситуацию.
        Возвращает список из top_k записей, отсортированных по схожести.

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
            # Евклидово расстояние в нормализованном пространстве
            # Using max(0.01, ...) to prevent division by zero or very small numbers
            vol_diff = (rec["volatility"] - current_volatility) / max(0.01, current_volatility)
            dq_diff = (rec["dq"] - current_dq) / max(0.01, current_dq)
            dist = math.sqrt(vol_diff**2 + dq_diff**2)
            scored.append((dist, rec))

        scored.sort(key=lambda x: x[0])
        return [rec for _, rec in scored[:top_k]]

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """
        Converts the stored records into a list of dictionaries.

        Returns:
            List[Dict[str, Any]]: A list of all records as dictionaries.
        """
        return [dict(rec) for rec in self.records]

    def from_dict_list(self, data: List[Dict[str, Any]]) -> None:
        """
        Loads records from a list of dictionaries. Only the most recent `max_size` records are kept.

        Args:
            data (List[Dict[str, Any]]): A list of dictionaries representing records.
        """
        self.records = [dict(rec) for rec in data[-self.max_size:]]

    def __len__(self) -> int:
        """
        Returns the number of records currently stored in memory.
        """
        return len(self.records)
    
    def _forget_old_entries(self) -> None:
        """
        Удаляет записи с низким весом (экспоненциальное забывание).
        Records are weighted based on their age (timestamp) and removed if weight falls below a threshold.
        If after cleanup the memory still exceeds max_size, it's truncated by weight.
        """
        if not self.records:
            return
        
        now = time.time()
        
        # Calculate weight for each record. Records without a timestamp get a default weight.
        # This loop now relies on 'timestamp' being present, which is added in the 'add' method.
        for rec in self.records:
            age = now - rec.get("timestamp", now) # If timestamp is missing, age is 0, weight is 1.0
            rec["weight"] = math.exp(-age / 3600.0)  # период полураспада ~1 час (3600 seconds)
        
        # Filter out records with a weight below 0.1
        # Default weight for new records (without an initial timestamp) is 1.0, so they are not forgotten immediately.
        self.records = [r for r in self.records if r.get("weight", 1.0) >= 0.1]
        
        # If after cleanup, the number of records still exceeds max_size,
        # sort by weight (descending) and truncate to max_size.
        if len(self.records) > self.max_size:
            self.records = sorted(self.records, key=lambda r: r.get("weight", 0.0), reverse=True)
            self.records = self.records[:self.max_size]