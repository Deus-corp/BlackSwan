"""
Episodic Memory (L1) – запоминает рыночные ситуации и связанные с ними лучшие стратегии.
Используется для инициализации популяции и адаптации к повторяющимся условиям.
"""
from typing import Dict, List, Optional, Tuple
import math
import time

class EpisodicMemory:
    def __init__(self, max_size: int = 1000):
        self.records: List[Dict] = []  # список записей (volatility, dq, capital, params, fitness)
        self.max_size = max_size
        self.decay_factor = 0.9  # коэффициент забывания (0..1)
        self.cleanup_interval = 100  # каждые 100 добавлений – очистка
        self.add_count = 0

    def add(self, market_volatility: float, dq: float, capital: float, params: Dict, fitness: float):
        """Добавляет запись о рыночной ситуации и лучшей стратегии."""
        record = {
            "volatility": market_volatility,
            "dq": dq,
            "capital": capital,
            "params": params,
            "fitness": fitness,
        }
        self.add_count += 1
        if self.add_count % self.cleanup_interval == 0:
            self._forget_old_entries()
        self.records.append(record)
        if len(self.records) > self.max_size:
            self.records.pop(0)  # удаляем самую старую

    def find_similar(self, current_volatility: float, current_dq: float, top_k: int = 3) -> List[Dict]:
        """
        Ищет записи, наиболее похожие на текущую рыночную ситуацию.
        Возвращает список из top_k записей, отсортированных по схожести.
        """
        if not self.records:
            return []

        scored = []
        for rec in self.records:
            # Евклидово расстояние в нормализованном пространстве
            vol_diff = (rec["volatility"] - current_volatility) / max(0.01, current_volatility)
            dq_diff = (rec["dq"] - current_dq) / max(0.01, current_dq)
            dist = math.sqrt(vol_diff**2 + dq_diff**2)
            scored.append((dist, rec))

        scored.sort(key=lambda x: x[0])
        return [rec for _, rec in scored[:top_k]]

    def to_dict_list(self) -> List[Dict]:
        return [dict(rec) for rec in self.records]

    def from_dict_list(self, data: List[Dict]):
        self.records = [dict(rec) for rec in data[-self.max_size:]]

    def __len__(self):
        return len(self.records)
    
    def _forget_old_entries(self):
        """Удаляет записи с низким весом (экспоненциальное забывание)."""
        if not self.records:
            return
        now = time.time()
        # Вычисляем вес: чем старше запись, тем ниже вес
        for rec in self.records:
            age = now - rec.get("timestamp", now)
            rec["weight"] = math.exp(-age / 3600.0)  # период полураспада ~1 час
        # Удаляем записи с весом < 0.1
        self.records = [r for r in self.records if r.get("weight", 1.0) >= 0.1]
        # Если после очистки всё ещё больше max_size, обрезаем
        if len(self.records) > self.max_size:
            self.records = sorted(self.records, key=lambda r: r.get("weight", 0), reverse=True)
            self.records = self.records[:self.max_size]