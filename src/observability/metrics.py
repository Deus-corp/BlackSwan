# src/observability/metrics.py
"""Минимальный коллектор метрик."""
from collections import defaultdict

class MetricsCollector:
    def __init__(self):
        self.counters = defaultdict(int)
        self.gauges = {}

    def inc(self, name: str, value: int = 1):
        self.counters[name] += value

    def set(self, name: str, value):
        self.gauges[name] = value

    def snapshot(self) -> dict:
        return {"counters": dict(self.counters), "gauges": dict(self.gauges)}