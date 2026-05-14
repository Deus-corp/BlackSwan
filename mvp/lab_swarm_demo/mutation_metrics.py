"""
Глобальные счётчики мутаций LLM, вынесенные из node_agent для избежания циклических импортов.
"""
from typing import Tuple
from prometheus_client import Counter, Gauge

_llm_mutation_count = 0
_llm_mutation_total_impact = 0.0
_last_capital = None

mutation_counter = Counter('swarm_mutations_total', 'Total number of LLM mutations')
mutation_impact_gauge = Gauge('swarm_mutation_impact', 'Average impact of mutations on capital')

def note_llm_mutation():
    global _llm_mutation_count
    _llm_mutation_count += 1
    mutation_counter.inc()

def update_llm_impact(current_capital: float):
    global _llm_mutation_total_impact, _last_capital
    if _last_capital is not None:
        impact = current_capital - _last_capital
        _llm_mutation_total_impact += impact
    _last_capital = current_capital
    avg = _llm_mutation_total_impact / _llm_mutation_count if _llm_mutation_count else 0.0
    mutation_impact_gauge.set(avg)

def get_llm_stats() -> Tuple[int, float]:
    avg = _llm_mutation_total_impact / _llm_mutation_count if _llm_mutation_count else 0.0
    return _llm_mutation_count, avg