"""Replay engine for deterministic historical event simulation."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class EventStoreProtocol(Protocol):
    """Expected interface for an event store."""

    def iter_events(self) -> Iterator[Any]:
        ...


@dataclass(slots=True)
class ReplayResult:
    """Replay execution summary."""

    status: str
    run_id: str
    events_count: int
    started_at: float
    completed_at: float
    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.completed_at - self.started_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run_id": self.run_id,
            "events_count": self.events_count,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "errors": list(self.errors),
        }


class ReplayEngine:
    """Replay historical events through an optional event handler."""

    __slots__ = ("_event_store", "_handler")

    def __init__(
        self,
        event_store: EventStoreProtocol,
        handler: Callable[[Any], None] | None = None,
    ) -> None:
        if not hasattr(event_store, "iter_events"):
            raise TypeError("event_store must provide iter_events()")

        self._event_store = event_store
        self._handler = handler

    def replay_run(
        self,
        run_id: str,
        *,
        max_events: int | None = None,
        stop_on_error: bool = False,
    ) -> dict[str, Any]:
        """Replay events and return execution metadata."""
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            raise ValueError("run_id cannot be empty")

        limit = None if max_events is None else max(0, int(max_events))
        started_at = time.time()
        event_count = 0
        errors: list[str] = []

        logger.info("Starting replay simulation run_id=%s max_events=%s", clean_run_id, limit)

        try:
            for event in self._event_store.iter_events():
                if limit is not None and event_count >= limit:
                    break

                try:
                    self._process_event(event)
                    event_count += 1
                except Exception as exc:
                    error = f"event_index={event_count}: {type(exc).__name__}: {exc}"
                    errors.append(error)
                    logger.warning("Replay event processing failed: %s", error)

                    if stop_on_error:
                        break

            status = "completed" if not errors or not stop_on_error else "failed"

        except Exception as exc:
            errors.append(f"event_store: {type(exc).__name__}: {exc}")
            logger.exception("Replay event store iteration failed for run_id=%s", clean_run_id)
            status = "failed"

        completed_at = time.time()

        result = ReplayResult(
            status=status,
            run_id=clean_run_id,
            events_count=event_count,
            started_at=started_at,
            completed_at=completed_at,
            errors=errors,
        )

        logger.info(
            "Replay finished run_id=%s status=%s events=%d duration=%.3fs errors=%d",
            clean_run_id,
            status,
            event_count,
            result.duration_seconds,
            len(errors),
        )

        return result.to_dict()

    def _process_event(self, event: Any) -> None:
        if self._handler is not None:
            self._handler(event)