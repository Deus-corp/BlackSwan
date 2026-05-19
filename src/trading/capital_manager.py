"""
Manages swarm node capital and survival status.
"""
import logging
from typing import Dict, Optional, Protocol, runtime_checkable

# Assuming 'swarm_config' module provides a 'config' object with necessary attributes.
from swarm_config import config

logger = logging.getLogger(__name__)


# Define a Protocol for SurvivalEvaluator to provide better type hints
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
    processes the financial outcomes of trades, and evaluates the node's
    operational liveness based on its capital and a linked SurvivalEvaluator.
    """
    def __init__(self, capital: float = 1000.0) -> None:
        """
        Initializes the CapitalManager with a starting capital and configuration settings.

        Args:
            capital: The starting capital for the node. Defaults to 1000.0.
                     Consider loading this from `config` if it needs to be dynamically configured.
        """
        self.capital: float = capital
        self.burn_rate: float = config.burn_rate
        self.alert_threshold: float = config.capital_alert_threshold

        # The 'survival' attribute is expected to be an instance of SurvivalEvaluatorProtocol
        # and is set externally after initialization.
        self.survival: Optional[SurvivalEvaluatorProtocol] = None

    def set_survival(self, survival_evaluator: SurvivalEvaluatorProtocol) -> None:
        """
        Connects a SurvivalEvaluator instance to the CapitalManager.

        This allows the CapitalManager to query the SurvivalEvaluator for
        liveness and DQ (Decentralization Quotient) metrics.

        Args:
            survival_evaluator: An instance of SurvivalEvaluatorProtocol or a similar object
                                 that provides 'dq' and 'liveness' attributes.
        """
        self.survival = survival_evaluator

    def burn(self) -> None:
        """
        Deducts the configured burn rate from the current capital.

        Ensures that capital does not fall below zero.
        """
        self.capital -= self.burn_rate
        # Ensure capital does not go below zero, indicating complete depletion.
        self.capital = max(0.0, self.capital)
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
        # TODO: Implement actual capital update based on trade results.
        # This is a placeholder; real calculation should be moved here from external logic.
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
            delta: The amount by which to increase the DQ. Defaults to 0.001.
        """
        if self.survival:
            # Assuming 'dq' is a mutable attribute of the survival object
            self.survival.dq = min(1.0, self.survival.dq + delta)
            logger.debug(f"DQ updated to: {self.survival.dq:.4f}")
        else:
            logger.warning("Attempted to apply DQ delta, but no SurvivalEvaluator is set.")