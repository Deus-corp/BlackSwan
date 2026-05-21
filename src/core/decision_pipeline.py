"""
A module defining the DecisionPipeline, a placeholder for processing proposals
in a D2BFT-like system.
"""
from typing import Dict, Any
import logging # Added logging import
from .global_state import GlobalState
from .event_bus import EventBus

# Configure logging for this module
logger = logging.getLogger(__name__)

class DecisionPipeline:
    """
    A placeholder for a universal decision-making pipeline.

    In the Minimal Viable Product (MVP) phase, it implements only the
    Proposal → Evaluation (stub) → Execution (stub) stages.
    It interacts with the global state and publishes events via an event bus.
    """

    def __init__(self, state: GlobalState, event_bus: EventBus):
        """
        Initializes the DecisionPipeline with a reference to the global state and an event bus.

        Args:
            state: An instance of `GlobalState` to interact with.
            event_bus: An instance of `EventBus` to publish events related to pipeline progress.

        Raises:
            TypeError: If `state` is not an instance of `GlobalState` or `event_bus` is not an instance of `EventBus`.
        """
        if not isinstance(state, GlobalState):
            raise TypeError("state must be an instance of GlobalState.")
        if not isinstance(event_bus, EventBus):
            raise TypeError("event_bus must be an instance of EventBus.")

        self.state: GlobalState = state
        self.event_bus: EventBus = event_bus
        logger.debug("DecisionPipeline initialized.")

    def __repr__(self) -> str:
        """
        Returns a string representation of the DecisionPipeline instance.
        """
        return f"DecisionPipeline(state_ref={id(self.state)}, event_bus_ref={id(self.event_bus)})"

    async def process(self, proposal: Dict[str, Any]) -> bool:
        """
        Processes a proposed object through the decision-making pipeline.

        This asynchronous method orchestrates the evaluation and (stubbed)
        execution stages of a proposal. It publishes events to the event bus
        indicating the outcome.

        Args:
            proposal: A dictionary representing the proposal to be processed.
                      It is expected to have an "id" key and potentially a
                      "dangerous" boolean key for evaluation.

        Returns:
            True if the proposal was successfully evaluated and executed,
            False otherwise (e.g., if evaluation failed).
        """
        if not isinstance(proposal, dict):
            await self.event_bus.publish(
                "execution",
                {"proposal": proposal, "status": "rejected", "reason": "Proposal is not a dictionary."},
                "decision_pipeline",
                sensitivity=3
            )
            logger.warning(f"Rejected proposal: Not a dictionary. Proposal: {proposal!r}")
            return False

        proposal_id = proposal.get("id")
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            await self.event_bus.publish(
                "execution",
                {"proposal": proposal, "status": "rejected", "reason": "Invalid or missing 'id' in proposal."},
                "decision_pipeline",
                sensitivity=3
            )
            logger.warning(f"Rejected proposal: Missing or invalid 'id'. Proposal: {proposal!r}")
            return False

        # Use the stripped ID for all further operations
        proposal["id"] = proposal_id.strip()
        current_proposal_id = proposal["id"]

        logger.info(f"Processing proposal '{current_proposal_id}'...")
        
        # 1. Proposal is already received by this stage.
        
        # 2. Evaluation
        if not self._evaluate(proposal):
            # Publish event for rejected proposal
            await self.event_bus.publish(
                "execution",
                {"proposal": proposal, "status": "rejected", "reason": "Evaluation failed"},
                "decision_pipeline",
                sensitivity=2
            )
            logger.info(f"Proposal '{current_proposal_id}' rejected during evaluation.")
            return False
        
        # 3. Execution (stub)
        # In a real system, this would involve applying changes to the state
        # after successful consensus. For this prototype, we just update
        # a placeholder in the global state to indicate processing.
        self.state.update("execution_state", {"last_proposal_id": current_proposal_id})
        logger.debug(f"Global state updated with last_proposal_id: '{current_proposal_id}'.")
        
        # Publish event for successfully executed proposal
        await self.event_bus.publish(
            "execution",
            {"proposal": proposal, "status": "executed", "details": f"Proposal {current_proposal_id} processed."},
            "decision_pipeline",
            sensitivity=1
        )
        logger.info(f"Proposal '{current_proposal_id}' successfully processed and executed.")
        return True

    def _evaluate(self, proposal: Dict[str, Any]) -> bool:
        """
        Evaluates a proposal based on predefined rules.

        In this stub implementation, any proposal marked with `{"dangerous": True}`
        is rejected. All other proposals are considered valid.

        Args:
            proposal: The proposal (dictionary) to evaluate.

        Returns:
            True if the proposal is considered valid and can proceed to execution,
            False otherwise.
        """
        current_proposal_id = proposal.get("id", "<unknown_id>")
        # Simple check: all proposals except those explicitly marked as 'dangerous' are accepted.
        is_dangerous = proposal.get("dangerous", False)

        if not isinstance(is_dangerous, bool):
            logger.warning(
                f"Proposal '{current_proposal_id}' has non-boolean 'dangerous' flag: {is_dangerous!r}. "
                f"Treating as not dangerous for safety."
            )
            is_dangerous = False # Default to safe if not a boolean

        if is_dangerous:
            logger.debug(f"Proposal '{current_proposal_id}' deemed dangerous during evaluation.")
            return False
        logger.debug(f"Proposal '{current_proposal_id}' passed evaluation.")
        return True