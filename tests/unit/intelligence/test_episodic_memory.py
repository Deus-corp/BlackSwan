import pytest
from src.intelligence.episodic_memory import EpisodicMemory

def test_add_and_find_similar():
    mem = EpisodicMemory(max_size=10)
    mem.add(market_volatility=0.1, dq=0.05, capital=1000, params={"max_risk": 0.2}, fitness=0.9)
    mem.add(market_volatility=0.3, dq=0.1, capital=5000, params={"max_risk": 0.1}, fitness=0.7)
    similar = mem.find_similar(current_volatility=0.12, current_dq=0.06, top_k=1)
    assert len(similar) == 1
    assert similar[0]["params"]["max_risk"] == 0.2

def test_max_size():
    mem = EpisodicMemory(max_size=2)
    mem.add(market_volatility=0.1, dq=0.1, capital=100, params={"x": 1}, fitness=0.5)
    mem.add(market_volatility=0.2, dq=0.2, capital=200, params={"x": 2}, fitness=0.6)
    mem.add(market_volatility=0.3, dq=0.3, capital=300, params={"x": 3}, fitness=0.7)
    assert len(mem) == 2