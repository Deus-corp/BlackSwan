"""
A module providing a unified asynchronous event bus for inter-component communication.

This event bus supports subscribing to topics, publishing events with metadata,
and basic event logging for auditing purposes.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Literal, TypeAlias, Awaitable, Union

# Set up logging for the event bus
logger = logging.getLogger(__name__)

# Define the expected signature for an event callback.
EventCallback: TypeAlias = Callable[[Dict[str, Any]], Union[None, Awaitable[None]]]

# Define a Literal type for event visibility scopes.
VisibilityScope: TypeAlias = Literal["local", "swarm", "global"]
VALID_VISIBILITY_SCOPES: tuple[VisibilityScope, ...] = ("local", "swarm", "global")

class EventBus:
    """
    A unified asynchronous event bus for component interaction.
    """
    __slots__ = ('_subscribers', '_event_log')

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[EventCallback]] = {}
        self._event_log: List[Dict[str, Any]] = []
        logger.debug("EventBus initialized.")

    def __repr__(self) -> str:
        return f"EventBus(topics={len(self._subscribers)}, logged_events={len(self._event_log)})"

    def subscribe(self, topic: str, callback: EventCallback) -> None:
        """
        Subscribes a callback function to events of a specific topic.

        Args:
            topic: The topic name to subscribe to.
            callback: The function or coroutine to execute on event.
        """
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("topic must be a non-empty string.")
        if not callable(callback):
            raise TypeError("callback must be a callable function or coroutine.")

        topic_cleaned = topic.strip()
        if topic_cleaned not in self._subscribers:
            self._subscribers[topic_cleaned] = []
        self._subscribers[topic_cleaned].append(callback)

    def unsubscribe(self, topic: str, callback: EventCallback) -> None:
        """
        Unsubscribes a callback function from events of a specific topic.

        Args:
            topic: The topic name to unsubscribe from.
            callback: The previously subscribed callback.
        """
        topic_cleaned = topic.strip()
        if topic_cleaned not in self._subscribers or callback not in self._subscribers[topic_cleaned]:
            raise ValueError(f"Callback not found for topic '{topic_cleaned}'.")
        
        self._subscribers[topic_cleaned].remove(callback)
        if not self._subscribers[topic_cleaned]:
            del self._subscribers[topic_cleaned]

    async def publish(self, topic: str, payload: Any, source_component: str = "unknown",
                      sensitivity: int = 1, visibility: VisibilityScope = "local") -> None:
        """
        Publishes a new event to the bus and triggers subscribers concurrently.

        Args:
            topic: The event topic.
            payload: The event data content.
            source_component: Identifier of the origin component.
            sensitivity: Integer level from 1 to 5.
            visibility: The dissemination scope of the event.
        """
        if not (1 <= sensitivity <= 5):
            raise ValueError("sensitivity must be an integer between 1 and 5.")
        if visibility not in VALID_VISIBILITY_SCOPES:
            raise ValueError(f"visibility must be one of {VALID_VISIBILITY_SCOPES}.")

        topic_cleaned = topic.strip()
        event: Dict[str, Any] = {
            "event_id": str(uuid.uuid4()),
            "topic": topic_cleaned,
            "source_component": source_component,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
            "payload": payload,
            "sensitivity": sensitivity,
            "visibility": visibility
        }
        self._event_log.append(event)
        
        callbacks = self._subscribers.get(topic_cleaned, [])
        if not callbacks:
            return

        tasks: List[Awaitable[Any]] = []
        for cb in callbacks:
            try:
                result = cb(event)
                if asyncio.iscoroutine(result):
                    tasks.append(result)
            except Exception as e:
                logger.error(f"Synchronous callback failed in topic '{topic_cleaned}': {e}", exc_info=True)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    logger.error(f"Asynchronous callback failed in topic '{topic_cleaned}': {res}", exc_info=True)

    def get_log(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves a copy of the event log, optionally filtered by topic.
        """
        if topic:
            topic_cleaned = topic.strip()
            return [e for e in self._event_log if e["topic"] == topic_cleaned]
        return list(self._event_log)

    def clear_log(self) -> None:
        """
        Clears all events from the internal event log.
        """
        self._event_log.clear()