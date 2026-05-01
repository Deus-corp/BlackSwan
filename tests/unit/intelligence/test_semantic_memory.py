import pytest
from src.intelligence.episodic_memory import EpisodicMemory
from src.intelligence.semantic_memory import SemanticMemory

def test_derive_and_apply_rules():
    mem = EpisodicMemory()
    mem.add(market_volatility=0.5, dq=0.1, capital=1000, params={"max_risk_per_trade": 0.1, "phi_llm": 0.15}, fitness=0.8)
    mem.add(market_volatility=0.1, dq=0.05, capital=2000, params={"max_risk_per_trade": 0.8, "phi_llm": 0.35}, fitness=0.9)

    sm = SemanticMemory()
    sm.derive_rules(mem.to_dict_list())

    params = {"max_risk_per_trade": 0.6, "phi_llm": 0.3}
    adjusted = sm.apply_rules(params, market_volatility=0.6, dq=0.1)
    assert adjusted["max_risk_per_trade"] <= 0.6