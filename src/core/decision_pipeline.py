"""
A module defining the DecisionPipeline for processing proposals within a D2BFT-like system.
"""

import logging
from typing import Any, Dict, Final
from .global_state import GlobalState
from .event_bus import EventBus

logger = logging.getLogger(__name__)

class DecisionPipeline:
    """
    A pipeline for evaluating and executing proposals in the system.

    The pipeline processes incoming proposals by validating structure, evaluating safety, 
    and updating the global system state.

    Attributes:
        state (GlobalState): Reference to the central system state.
        event_bus (EventBus): Bus for broadcasting pipeline lifecycle events.
    """

    __slots__ = ("_state", "_event_bus")

    def __init__(self, state: GlobalState, event_bus: EventBus) -> None:
        """
        Initializes the pipeline with required system dependencies.

        Args:
            state: Instance of GlobalState.
            event_bus: Instance of EventBus.

        Raises:
            TypeError: If provided dependencies are not the correct types.
        """
        if not isinstance(state, GlobalState):
            raise TypeError("state must be an instance of GlobalState.")
        if not isinstance(event_bus, EventBus):
            raise TypeError("event_bus must be an instance of EventBus.")

        self._state: Final = state
        self._event_bus: Final = event_bus
        logger.debug("DecisionPipeline initialized.")

    def __repr__(self) -> str:
        return f"DecisionPipeline(state_id={id(self._state)}, event_bus_id={id(self._event_bus)})"

    async def process(self, proposal: Dict[str, Any]) -> bool:
        """
        Orchestrates the evaluation and execution of a given proposal.

        Args:
            proposal: A dictionary containing at least an 'id' key.

        Returns:
            True if the proposal was successfully processed, False otherwise.
        """
        if not isinstance(proposal, dict):
            await self._report_failure(proposal, "Proposal is not a dictionary", 3)
            return False

        proposal_id = proposal.get("id")
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            await self._report_failure(proposal, "Invalid or missing 'id'", 3)
            return False

        proposal["id"] = proposal_id.strip()
        current_id: str = proposal["id"]

        logger.info("Processing proposal '%s'...", current_id)

        if not self._evaluate(proposal):
            await self._report_failure(proposal, "Evaluation failed", 2)
            logger.info("Proposal '%s' rejected during evaluation.", current_id)
            return False

        self._state.update("execution_state", {"last_proposal_id": current_id})
        
        await self._event_bus.publish(
            "execution",
            {"proposal": proposal, "status": "executed", "details": f"Proposal {current_id} processed."},
            "decision_pipeline",
            sensitivity=1
        )
        
        logger.info("Proposal '%s' successfully executed.", current_id)
        return True

    async def _report_failure(self, proposal: Any, reason: str, sensitivity: int) -> None:
        """Helper to standardize failure reporting to the event bus."""
        logger.warning("Rejected proposal: %s. Data: %r", reason, proposal)
        await self._event_bus.publish(
            "execution",
            {"proposal": proposal, "status": "rejected", "reason": reason},
            "decision_pipeline",
            sensitivity=sensitivity
        )

    def _evaluate(self, proposal: Dict[str, Any]) -> bool:
        """
        Evaluates safety constraints for a proposal.

        Args:
            proposal: The proposal dictionary to check.

        Returns:
            False if marked as 'dangerous', True otherwise.
        """
        is_dangerous = proposal.get("dangerous", False)

        if not isinstance(is_dangerous, bool):
            logger.warning("Non-boolean 'dangerous' flag for %s. Defaulting to safe.", proposal.get("id"))
            is_dangerous = False

        return not is_dangerous