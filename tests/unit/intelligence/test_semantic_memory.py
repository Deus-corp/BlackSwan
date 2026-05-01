import pytest
from src.intelligence.episodic_memory import EpisodicMemory
from src.intelligence.semantic_memory import SemanticMemory

def test_derive_and_apply_rules():
    mem = EpisodicMemory()
    # высокая волатильность -> маленький max_risk
    mem.add(0.5, 0.1, 1000, {"max_risk_per_trade": 0.1, "phi_llm": 0.15}, 0.8)
    # низкая волатильность -> большой max_risk
    mem.add(0.1, 0.05, 2000, {"max_risk_per_trade": 0.8, "phi_llm": 0.35}, 0.9)

    sm = SemanticMemory()
    sm.derive_rules(mem.to_dict_list())

    # при высокой волатильности max_risk должен быть уменьшен
    params = {"max_risk_per_trade": 0.6, "phi_llm": 0.3}
    adjusted = sm.apply_rules(params, current_volatility=0.6, current_dq=0.1)
    assert adjusted["max_risk_per_trade"] < 0.6