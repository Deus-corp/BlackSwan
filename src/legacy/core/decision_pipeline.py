"""Decision pipeline for validating, evaluating, and executing proposals."""

from __future__ import annotations

import copy
import logging
import time
from typing import Any, Final

from .event_bus import EventBus
from .global_state import GlobalState

logger = logging.getLogger(__name__)


class DecisionPipeline:
    """Evaluate proposals, update global state, and publish lifecycle events."""

    __slots__ = ("_state", "_event_bus")

    SOURCE_COMPONENT: Final[str] = "decision_pipeline"
    EVENT_TOPIC: Final[str] = "execution"

    def __init__(self, state: GlobalState, event_bus: EventBus) -> None:
        if not isinstance(state, GlobalState):
            raise TypeError("state must be an instance of GlobalState")
        if not isinstance(event_bus, EventBus):
            raise TypeError("event_bus must be an instance of EventBus")

        self._state: Final[GlobalState] = state
        self._event_bus: Final[EventBus] = event_bus
        logger.debug("DecisionPipeline initialized.")

    async def process(self, proposal: dict[str, Any]) -> bool:
        """Validate, evaluate, and execute a proposal."""
        normalized = self._normalize_proposal(proposal)
        if normalized is None:
            await self._report_failure(proposal, "Proposal must be a dictionary", sensitivity=3)
            return False

        proposal_id = normalized.get("id")
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            await self._report_failure(normalized, "Invalid or missing 'id'", sensitivity=3)
            return False

        normalized["id"] = proposal_id.strip()
        normalized.setdefault("processed_at", time.time())

        logger.info("Processing proposal '%s'.", normalized["id"])

        allowed, reason = self._evaluate(normalized)
        if not allowed:
            await self._report_failure(normalized, reason, sensitivity=2)
            logger.info("Proposal '%s' rejected: %s", normalized["id"], reason)
            return False

        self._execute(normalized)

        await self._event_bus.publish(
            self.EVENT_TOPIC,
            {
                "proposal": copy.deepcopy(normalized),
                "status": "executed",
                "proposal_id": normalized["id"],
                "details": f"Proposal {normalized['id']} processed.",
                "timestamp": time.time(),
            },
            self.SOURCE_COMPONENT,
            sensitivity=1,
        )

        logger.info("Proposal '%s' successfully executed.", normalized["id"])
        return True

    def _execute(self, proposal: dict[str, Any]) -> None:
        """Apply the proposal side effects to GlobalState."""
        self._state.update(
            "execution_state",
            {
                "last_proposal_id": proposal["id"],
                "last_proposal_status": "executed",
                "last_proposal_ts": time.time(),
            },
        )

    async def _report_failure(self, proposal: Any, reason: str, sensitivity: int) -> None:
        """Publish a standardized rejection event."""
        logger.warning("Rejected proposal: %s. Data: %r", reason, proposal)

        payload = {
            "proposal": copy.deepcopy(proposal) if isinstance(proposal, dict) else proposal,
            "status": "rejected",
            "reason": reason,
            "timestamp": time.time(),
        }

        if isinstance(proposal, dict) and proposal.get("id"):
            payload["proposal_id"] = proposal.get("id")

        await self._event_bus.publish(
            self.EVENT_TOPIC,
            payload,
            self.SOURCE_COMPONENT,
            sensitivity=sensitivity,
        )

    def _evaluate(self, proposal: dict[str, Any]) -> tuple[bool, str]:
        """Return whether a proposal passes safety checks plus a reason."""
        if bool(proposal.get("dangerous", False)):
            return False, "Proposal marked dangerous"

        if proposal.get("action") in {"enable_live_execution", "set_execution_enabled"}:
            approval = proposal.get("approval")
            safety_gate = str(proposal.get("safety_gate", "")).lower()
            if approval is not True or safety_gate not in {"approved", "allow", "enabled"}:
                return False, "Explicit approval required for live execution"

        return True, "ok"

    @staticmethod
    def _normalize_proposal(proposal: Any) -> dict[str, Any] | None:
        if not isinstance(proposal, dict):
            return None
        return dict(proposal)

    def __repr__(self) -> str:
        return (
            f"DecisionPipeline(state_id={id(self._state)}, "
            f"event_bus_id={id(self._event_bus)})"
        )