"""
Manages swarm node capital and survival status.
"""
import logging
from typing import Any, Dict, Final, Optional, Protocol, runtime_checkable

from swarm_config import config

logger: Final = logging.getLogger(__name__)


@runtime_checkable
class SurvivalEvaluatorProtocol(Protocol):
    """
    A protocol defining the expected interface for a SurvivalEvaluator.
    """
    dq: float
    liveness: float


class CapitalManager:
    """
    Manages the capital, burn rate, and survival status of the swarm node.

    This class tracks the node's capital, applies a defined burn rate,
    processes trade outcomes, and evaluates operational liveness.
    """

    __slots__ = ("capital", "burn_rate", "alert_threshold", "survival")

    def __init__(self, capital: float = 1000.0) -> None:
        """
        Initializes the CapitalManager with validated configuration settings.

        Args:
            capital: The starting capital (must be non-negative).

        Raises:
            ValueError: If any input parameters are negative.
        """
        if capital < 0:
            raise ValueError("Capital must be non-negative.")
        if config.burn_rate < 0:
            raise ValueError("Burn rate must be non-negative.")
        if config.capital_alert_threshold < 0:
            raise ValueError("Capital alert threshold must be non-negative.")

        self.capital: float = float(capital)
        self.burn_rate: float = float(config.burn_rate)
        self.alert_threshold: float = float(config.capital_alert_threshold)
        self.survival: Optional[SurvivalEvaluatorProtocol] = None

    def set_survival(self, survival_evaluator: SurvivalEvaluatorProtocol) -> None:
        """
        Connects a SurvivalEvaluator instance to the CapitalManager.

        Args:
            survival_evaluator: An object providing 'dq' and 'liveness' attributes.

        Raises:
            ValueError: If metrics are outside the [0.0, 1.0] range.
        """
        if not (0.0 <= survival_evaluator.dq <= 1.0):
            raise ValueError("DQ must be in the range [0.0, 1.0].")
        if not (0.0 <= survival_evaluator.liveness <= 1.0):
            raise ValueError("Liveness must be in the range [0.0, 1.0].")
        self.survival = survival_evaluator

    def burn(self) -> None:
        """
        Deducts the configured burn rate from the current capital.
        """
        self.capital = max(0.0, self.capital - self.burn_rate)
        logger.debug("Capital after burn: %.4f", self.capital)

    def apply_trade(self, result: Dict[str, Any]) -> float:
        """
        Processes the financial result of a trade.

        Args:
            result: Dictionary containing trade outcome metadata.

        Returns:
            The delta in capital (currently 0.0).
        """
        logger.info("Trade result received: %s. Capital not updated as method is a stub.", result)
        return 0.0

    def is_alive(self) -> bool:
        """
        Checks if the node is still operational based on capital.

        Returns:
            True if capital is greater than zero, otherwise False.
        """
        return self.capital > 0

    def health_snapshot(self) -> Dict[str, float]:
        """
        Returns a summary of current capital and survival metrics.

        Returns:
            Dictionary with capital, burn_rate, dq, and liveness.
        """
        return {
            "capital": self.capital,
            "burn_rate": self.burn_rate,
            "dq": float(self.survival.dq) if self.survival else 0.0,
            "liveness": float(self.survival.liveness) if self.survival else 1.0,
        }

    def apply_dq_delta(self, delta: float = 0.001) -> None:
        """
        Increments the DQ metric within the linked SurvivalEvaluator.

        Args:
            delta: Non-negative value to add to the current DQ.

        Raises:
            ValueError: If delta is negative.
        """
        if delta < 0:
            raise ValueError("Delta must be non-negative.")

        if self.survival:
            self.survival.dq = min(1.0, self.survival.dq + delta)
            logger.debug("DQ updated to: %.4f", self.survival.dq)
        else:
            logger.warning("Attempted to apply DQ delta, but no SurvivalEvaluator is set.")