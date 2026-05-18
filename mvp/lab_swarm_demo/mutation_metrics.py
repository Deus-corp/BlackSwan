"""
Глобальные счётчики мутаций LLM, вынесенные из node_agent для избежания циклических импортов.
Refactored into a class for better state management.
"""
from typing import Tuple, Optional
from prometheus_client import Counter, Gauge

class MutationMetrics:
    """
    Manages global LLM mutation counters and their corresponding Prometheus metrics.
    Encapsulates mutation count, total impact, and last known capital to avoid global variables.
    """
    def __init__(self) -> None:
        """
        Initializes the mutation metrics, including Prometheus counters and gauges.
        """
        self._llm_mutation_count: int = 0
        self._llm_mutation_total_impact: float = 0.0
        self._last_capital: Optional[float] = None

        self.mutation_counter = Counter(
            'swarm_mutations_total',
            'Total number of LLM mutations across all nodes'
        )
        self.mutation_impact_gauge = Gauge(
            'swarm_mutation_impact',
            'Average impact of LLM mutations on capital'
        )

    def note_llm_mutation(self) -> None:
        """
        Increments the LLM mutation counter and updates the Prometheus counter.
        """
        self._llm_mutation_count += 1
        self.mutation_counter.inc()

    def update_llm_impact(self, current_capital: float) -> None:
        """
        Calculates the impact of the last mutation on capital, updates the total impact,
        and sets the Prometheus gauge for average impact.

        Args:
            current_capital: The current capital value after a mutation.
        """
        if self._last_capital is not None:
            impact = current_capital - self._last_capital
            self._llm_mutation_total_impact += impact
        self._last_capital = current_capital

        # Update average impact gauge
        if self._llm_mutation_count > 0:
            avg = self._llm_mutation_total_impact / self._llm_mutation_count
        else:
            avg = 0.0
        self.mutation_impact_gauge.set(avg)

    def get_llm_stats(self) -> Tuple[int, float]:
        """
        Returns the current LLM mutation count and the average impact of mutations.

        Returns:
            A tuple containing:
                - The total number of LLM mutations (int).
                - The average impact of mutations on capital (float).
        """
        if self._llm_mutation_count > 0:
            avg = self._llm_mutation_total_impact / self._llm_mutation_count
        else:
            avg = 0.0
        return self._llm_mutation_count, avg

# Instantiate the metrics manager for use across modules
mutation_metrics = MutationMetrics()

# Expose the methods for backward compatibility, though direct use of mutation_metrics.method is preferred
note_llm_mutation = mutation_metrics.note_llm_mutation
update_llm_impact = mutation_metrics.update_llm_impact
get_llm_stats = mutation_metrics.get_llm_stats