from typing import Dict, Any
from .global_state import GlobalState
from .event_bus import EventBus

class DecisionPipeline:
    """
    A placeholder for a universal decision-making pipeline.
    In the MVP, it implements only the Proposal → Validation (stub) → Execution (stub) stages.
    """

    def __init__(self, state: GlobalState, event_bus: EventBus):
        """
        Initializes the DecisionPipeline with a reference to the global state and an event bus.

        Args:
            state: An instance of GlobalState to interact with.
            event_bus: An instance of EventBus to publish events.
        """
        self.state: GlobalState = state
        self.event_bus: EventBus = event_bus

    async def process(self, proposal: Dict[str, Any]) -> bool:
        """
        Processes a proposed object through the decision-making pipeline.
        This includes evaluation and (stubbed) execution stages.

        Args:
            proposal: A dictionary representing the proposal to be processed.
                      It is expected to have an "id" key and potentially a "dangerous" key.

        Returns:
            True if the proposal was successfully evaluated and executed, False otherwise.
        """
        # 1. Proposal is already received by this stage.
        # 2. Evaluation
        if not self._evaluate(proposal):
            # Publish event for rejected proposal
            await self.event_bus.publish("execution", {"proposal": proposal, "status": "rejected"}, "decision_pipeline")
            return False
        
        # 3. Execution (stub)
        # In a real system, this would involve applying changes to the state
        # after successful consensus. For this prototype, we just update
        # a placeholder in the global state to indicate processing.
        self.state.update("execution_state", {"last_proposal": proposal["id"]})
        
        # Publish event for successfully executed proposal
        await self.event_bus.publish("execution", {"proposal": proposal, "status": "executed"}, "decision_pipeline")
        return True

    def _evaluate(self, proposal: Dict[str, Any]) -> bool:
        """
        Evaluates a proposal based on predefined rules.
        In this stub implementation, proposals marked as "dangerous" are rejected.

        Args:
            proposal: The proposal (dictionary) to evaluate.

        Returns:
            True if the proposal is considered valid and can proceed, False otherwise.
        """
        # Simple check: all proposals except those explicitly marked as 'dangerous' are accepted.
        if proposal.get("dangerous"):
            return False
        return True
