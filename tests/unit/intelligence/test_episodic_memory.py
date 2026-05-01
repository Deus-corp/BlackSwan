import pytest
from src.intelligence.episodic_memory import EpisodicMemory

def test_add_and_find_similar():
    mem = EpisodicMemory(max_size=10)
    mem.add(volatility=0.1, dq=0.05, capital=1000, params={"max_risk": 0.2}, fitness=0.9)
    mem.add(volatility=0.3, dq=0.1, capital=5000, params={"max_risk": 0.1}, fitness=0.7)
    similar = mem.find_similar(current_volatility=0.12, current_dq=0.06, top_k=1)
    assert len(similar) == 1
    assert similar[0]["params"]["max_risk"] == 0.2

def test_max_size():
    mem = EpisodicMemory(max_size=2)
    mem.add(0.1, 0.1, 100, {"x": 1}, 0.5)
    mem.add(0.2, 0.2, 200, {"x": 2}, 0.6)
    mem.add(0.3, 0.3, 300, {"x": 3}, 0.7)
    assert len(mem) == 2