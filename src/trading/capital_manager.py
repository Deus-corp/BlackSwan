"""
Manages swarm node capital and survival status.
"""
import logging
from typing import Any, Dict, Tuple, Optional, Protocol, runtime_checkable, Final

from swarm_config import config

logger: Final = logging.getLogger(__name__)


@runtime_checkable
class SurvivalEvaluatorProtocol(Protocol):
    """
    A protocol defining the expected interface for a SurvivalEvaluator.
    
    Attributes:
        dq: float - Decentralization Quotient, must be in range [0.0, 1.0].
        liveness: float - Liveness metric, must be in range [0.0, 1.0].
    """
    dq: float
    liveness: float


class CapitalManager:
    """
    Manages the capital, burn rate, and survival status of the swarm node.

    This class tracks the node's capital, applies a defined burn rate,
    processes the financial outcomes of trades, and evaluates the node's
    operational liveness based on its capital and a linked SurvivalEvaluator.
    
    Attributes:
        capital: float - Current capital of the node.
        burn_rate: float - Rate at which capital is depleted per burn cycle.
        alert_threshold: float - Threshold for capital alerts.
        survival: Optional[SurvivalEvaluatorProtocol] - Linked survival evaluator.
    """
    __slots__ = ('capital', 'burn_rate', 'alert_threshold', 'survival')

    def __init__(self, capital: float = 1000.0) -> None:
        """
        Initializes the CapitalManager with a starting capital and configuration settings.

        Args:
            capital: The starting capital for the node. Must be non-negative. Defaults to 1000.0.

        Raises:
            ValueError: If capital, config.burn_rate, or config.capital_alert_threshold is negative.
        """
        if capital < 0:
            raise ValueError("Capital must be non-negative.")
        if config.burn_rate < 0:
            raise ValueError("Burn rate must be non-negative.")
        if config.capital_alert_threshold < 0:
            raise ValueError("Capital alert threshold must be non-negative.")

        self.capital: float = capital
        self.burn_rate: float = config.burn_rate
        self.alert_threshold: float = config.capital_alert_threshold
        self.survival: Optional[SurvivalEvaluatorProtocol] = None

    def set_survival(self, survival_evaluator: SurvivalEvaluatorProtocol) -> None:
        """
        Connects a SurvivalEvaluator instance to the CapitalManager.

        This allows the CapitalManager to query the SurvivalEvaluator for
        liveness and DQ (Decentralization Quotient) metrics.

        Args:
            survival_evaluator: An instance of SurvivalEvaluatorProtocol or a similar object
                             that provides 'dq' and 'liveness' attributes. Both attributes must be
                             in the range [0.0, 1.0].

        Raises:
            ValueError: If dq or liveness attributes are outside the range [0.0, 1.0].
        """
        if not (0.0 <= survival_evaluator.dq <= 1.0):
            raise ValueError("DQ must be in the range [0.0, 1.0].")
        if not (0.0 <= survival_evaluator.liveness <= 1.0):
            raise ValueError("Liveness must be in the range [0.0, 1.0].")
        self.survival = survival_evaluator

    def burn(self) -> None:
        """
        Deducts the configured burn rate from the current capital.

        Ensures that capital does not fall below zero.
        """
        self.capital = max(0.0, self.capital - self.burn_rate)
        logger.debug(f"Capital after burn: {self.capital:.4f}")

    def apply_trade(self, result: Dict[str, Any]) -> float:
        """
        Processes the financial result of a trade.

        This method is currently a placeholder. In a complete implementation,
        it would update the capital based on the trade's profit/loss and fees.

        Args:
            result: A dictionary containing details of the trade outcome.
                    Expected keys/values are not specified in the current stub.

        Returns:
            The change in capital resulting from the trade. Currently always returns 0.0.
        """
        logger.info(f"Trade result received: {result}. Capital not updated as method is a stub.")
        return 0.0

    def is_alive(self) -> bool:
        """
        Checks if the capital is greater than zero.

        Returns:
            True if capital is positive, False otherwise.
        """
        return self.capital > 0

    def health_snapshot(self) -> Dict[str, float]:
        """
        Returns a dictionary containing key health metrics of the capital manager.

        Includes current capital, burn rate, and if available, DQ and liveness
        from the linked SurvivalEvaluator.

        Returns:
            A dictionary with current capital, burn_rate, dq, and liveness.
        """
        dq_value = self.survival.dq if self.survival else 0.0
        liveness_value = self.survival.liveness if self.survival else 1.0
        return {
            "capital": self.capital,
            "burn_rate": self.burn_rate,
            "dq": dq_value,
            "liveness": liveness_value,
        }

    def apply_dq_delta(self, delta: float = 0.001) -> None:
        """
        Increases the DQ (Decentralization Quotient) in the linked SurvivalEvaluator.

        The DQ is capped at 1.0. This is typically called upon successful operations
        or trades.

        Args:
            delta: The amount by which to increase the DQ. Must be non-negative. Defaults to 0.001.

        Raises:
            ValueError: If delta is negative.
        """
        if delta < 0:
            raise ValueError("Delta must be non-negative.")
        if self.survival:
            self.survival.dq = min(1.0, self.survival.dq + delta)
            logger.debug(f"DQ updated to: {self.survival.dq:.4f}")
        else:
            logger.warning("Attempted to apply DQ delta, but no SurvivalEvaluator is set.")