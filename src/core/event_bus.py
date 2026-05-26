"""Asynchronous in-process event bus with structured event metadata."""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import (
    Any,
    Awaitable,
    Callable,
    DefaultDict,
    Final,
    Literal,
    TypeAlias,
)

logger = logging.getLogger(__name__)

Event: TypeAlias = dict[str, Any]
EventCallback: TypeAlias = Callable[[Event], Any]
VisibilityScope: TypeAlias = Literal["local", "swarm", "global"]

VALID_VISIBILITY_SCOPES: Final[tuple[VisibilityScope, ...]] = (
    "local",
    "swarm",
    "global",
)

DEFAULT_MAX_LOG_SIZE: Final[int] = 10_000


class EventBus:
    """
    Lightweight async event bus for swarm/runtime communication.

    Features:
    - async + sync subscriber support
    - bounded in-memory event log
    - safe subscriber isolation
    - topic-based dispatch
    - optional wildcard subscription via "*"
    """

    __slots__ = (
        "_subscribers",
        "_event_log",
        "_max_log_size",
        "_lock",
    )

    def __init__(self, max_log_size: int = DEFAULT_MAX_LOG_SIZE) -> None:
        if max_log_size < 1:
            raise ValueError("max_log_size must be >= 1")

        self._subscribers: DefaultDict[str, list[EventCallback]] = defaultdict(list)
        self._event_log: deque[Event] = deque(maxlen=max_log_size)
        self._max_log_size: Final[int] = max_log_size
        self._lock: threading.RLock = threading.RLock()

        logger.debug(
            "EventBus initialized (max_log_size=%s).",
            max_log_size,
        )

    def __repr__(self) -> str:
        with self._lock:
            topics = len(self._subscribers)
            subscribers = sum(len(v) for v in self._subscribers.values())
            logged = len(self._event_log)

        return (
            f"EventBus(topics={topics}, "
            f"subscribers={subscribers}, "
            f"logged_events={logged})"
        )

    def subscribe(self, topic: str, callback: EventCallback) -> None:
        """
        Subscribe a callback to a topic.

        Special topic:
            "*" => receive all events.
        """
        topic_cleaned = self._validate_topic(topic)

        if not callable(callback):
            raise TypeError("callback must be callable")

        with self._lock:
            if callback not in self._subscribers[topic_cleaned]:
                self._subscribers[topic_cleaned].append(callback)

        logger.debug(
            "Subscriber added topic=%s callback=%s",
            topic_cleaned,
            getattr(callback, "__name__", repr(callback)),
        )

    def unsubscribe(self, topic: str, callback: EventCallback) -> None:
        """Remove a callback subscription."""
        topic_cleaned = self._validate_topic(topic)

        with self._lock:
            callbacks = self._subscribers.get(topic_cleaned)
            if not callbacks or callback not in callbacks:
                return

            callbacks.remove(callback)

            if not callbacks:
                self._subscribers.pop(topic_cleaned, None)

        logger.debug(
            "Subscriber removed topic=%s callback=%s",
            topic_cleaned,
            getattr(callback, "__name__", repr(callback)),
        )

    async def publish(
        self,
        topic: str,
        payload: Any,
        source_component: str = "unknown",
        sensitivity: int = 1,
        visibility: VisibilityScope = "local",
    ) -> Event:
        """
        Publish an event to all subscribers.

        Returns:
            The constructed event dictionary.
        """
        topic_cleaned = self._validate_topic(topic)
        source_component = str(source_component).strip() or "unknown"

        if not (1 <= sensitivity <= 5):
            raise ValueError("sensitivity must be between 1 and 5")

        if visibility not in VALID_VISIBILITY_SCOPES:
            raise ValueError(
                f"visibility must be one of {VALID_VISIBILITY_SCOPES}"
            )

        event: Event = {
            "event_id": str(uuid.uuid4()),
            "topic": topic_cleaned,
            "source_component": source_component,
            "timestamp": datetime.now(timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "payload": payload,
            "sensitivity": int(sensitivity),
            "visibility": visibility,
        }

        with self._lock:
            self._event_log.append(event)

            callbacks = [
                *self._subscribers.get(topic_cleaned, []),
                *self._subscribers.get("*", []),
            ]

        if not callbacks:
            return event

        async_tasks: list[Awaitable[Any]] = []

        for callback in callbacks:
            try:
                result = callback(event)

                if inspect.isawaitable(result):
                    async_tasks.append(result)

            except Exception:
                logger.exception(
                    "Synchronous event callback failed "
                    "(topic=%s callback=%s)",
                    topic_cleaned,
                    getattr(callback, "__name__", repr(callback)),
                )

        if async_tasks:
            results = await asyncio.gather(
                *async_tasks,
                return_exceptions=True,
            )

            for result in results:
                if isinstance(result, Exception):
                    logger.exception(
                        "Asynchronous event callback failed "
                        "(topic=%s): %s",
                        topic_cleaned,
                        result,
                    )

        return event

    def get_log(self, topic: str | None = None) -> list[Event]:
        """Return a snapshot copy of the event log."""
        with self._lock:
            events = list(self._event_log)

        if topic is None:
            return events

        topic_cleaned = topic.strip()

        return [
            event
            for event in events
            if event.get("topic") == topic_cleaned
        ]

    def get_topics(self) -> list[str]:
        """Return registered topic names."""
        with self._lock:
            return sorted(self._subscribers.keys())

    def subscriber_count(self, topic: str | None = None) -> int:
        """Return subscriber count."""
        with self._lock:
            if topic is None:
                return sum(len(v) for v in self._subscribers.values())

            return len(self._subscribers.get(topic.strip(), []))

    def clear_log(self) -> None:
        """Clear the in-memory event log."""
        with self._lock:
            self._event_log.clear()

        logger.debug("Event log cleared.")

    @staticmethod
    def _validate_topic(topic: str) -> str:
        if not isinstance(topic, str):
            raise TypeError("topic must be a string")

        topic_cleaned = topic.strip()

        if not topic_cleaned:
            raise ValueError("topic cannot be empty")

        return topic_cleaned