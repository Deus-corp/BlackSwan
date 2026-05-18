"""
Глобальные счётчики мутаций LLM, вынесенные из node_agent для избежания циклических импортов.
"""
from typing import Tuple, Optional
from prometheus_client import Counter, Gauge

_llm_mutation_count: int = 0
_llm_mutation_total_impact: float = 0.0
_last_capital: Optional[float] = None

mutation_counter = Counter('swarm_mutations_total', 'Total number of LLM mutations')
mutation_impact_gauge = Gauge('swarm_mutation_impact', 'Average impact of mutations on capital')

def note_llm_mutation() -> None:
    """
    Increments the LLM mutation counter and updates the Prometheus counter.
    """
    global _llm_mutation_count
    _llm_mutation_count += 1
    mutation_counter.inc()

def update_llm_impact(current_capital: float) -> None:
    """
    Calculates the impact of the last mutation on capital and updates the total impact
    and the Prometheus gauge for average impact.
    """
    global _llm_mutation_total_impact, _last_capital
    if _last_capital is not None:
        impact = current_capital - _last_capital
        _llm_mutation_total_impact += impact
    _last_capital = current_capital
    avg = _llm_mutation_total_impact / _llm_mutation_count if _llm_mutation_count else 0.0
    mutation_impact_gauge.set(avg)

def get_llm_stats() -> Tuple[int, float]:
    """
    Returns the current LLM mutation count and the average impact of mutations.
    """
    avg = _llm_mutation_total_impact / _llm_mutation_count if _llm_mutation_count else 0.0
    return _llm_mutation_count, avg