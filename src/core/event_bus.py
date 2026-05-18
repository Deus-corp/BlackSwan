import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
import uuid

# Set up logging for the event bus
logger = logging.getLogger(__name__)

# Define the expected signature for an event callback
EventCallback = Callable[[Dict[str, Any]], Any]

class EventBus:
    """
    A unified asynchronous event bus for component interaction.

    Supports subscribing to topics, publishing events, and basic event logging
    for auditing purposes. Events contain metadata such as topic, source,
    timestamp, sensitivity, and visibility, along with a free-form payload.
    """

    def __init__(self) -> None:
        """
        Initializes the EventBus.
        """
        # Topic -> List of callback functions
        self._subscribers: Dict[str, List[EventCallback]] = {}
        # A chronological log of all published events
        self._event_log: List[Dict[str, Any]] = []

    def subscribe(self, topic: str, callback: EventCallback) -> None:
        """
        Subscribes a callback function to events of a specific topic.

        Args:
            topic: The topic string to subscribe to (e.g., "economic", "infra").
            callback: The function to be called when an event for the given
                      topic is published. It should accept one argument, the event
                      dictionary (Dict[str, Any]). Can be a regular function or a coroutine.
        """
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)
        logger.debug(f"Subscribed callback {callback.__name__} to topic '{topic}'")

    def unsubscribe(self, topic: str, callback: EventCallback) -> None:
        """
        Unsubscribes a callback function from events of a specific topic.

        Raises:
            ValueError: If the callback is not subscribed to the specified topic.
                        This matches the behavior of list.remove().

        Args:
            topic: The topic string to unsubscribe from.
            callback: The function to unsubscribe.
        """
        if topic in self._subscribers:
            # Note: list.remove() raises ValueError if the item is not present.
            # This behavior is preserved from the original code and indicates
            # an attempt to remove a non-existent subscription.
            self._subscribers[topic].remove(callback)
            if not self._subscribers[topic]: # Clean up empty topic lists
                del self._subscribers[topic]
            logger.debug(f"Unsubscribed callback {callback.__name__} from topic '{topic}'")
        else:
            # If the topic itself doesn't exist, the callback can't be subscribed to it.
            raise ValueError(f"Topic '{topic}' has no subscribers, cannot unsubscribe callback.")


    async def publish(self, topic: str, payload: Any, source_component: str = "unknown",
                      sensitivity: int = 1, visibility: str = "local") -> None:
        """
        Publishes a new event to the bus.

        Events are logged and then delivered to all subscribed callbacks for the topic.
        Asynchronous callbacks are awaited, while synchronous callbacks are called directly.
        Errors during callback execution are logged but do not prevent other deliveries.

        Args:
            topic: The category or subject of the event (e.g., "economic", "infra", "security",
                   "execution", "knowledge", "command").
            payload: The actual data content of the event. This can be any serializable type
                     (e.g., dict, list, str, int, float, bool, None).
            source_component: The identifier of the component originating the event.
                              Defaults to "unknown".
            sensitivity: An integer rating the criticality or sensitivity of the event,
                         typically 1-5 (higher values indicate higher criticality). Defaults to 1.
            visibility: The scope of the event's intended visibility (e.g., "local", "swarm", "global").
                        Defaults to "local".
        """
        event: Dict[str, Any] = {
            "event_id": str(uuid.uuid4()),
            "topic": topic,
            "source_component": source_component,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
            "sensitivity": sensitivity,
            "visibility": visibility,
            "signature": "ed25519:..."  # Placeholder for actual cryptographic signature
        }
        self._event_log.append(event)
        logger.info(f"Published event '{topic}' from '{source_component}' (ID: {event['event_id']})")

        # Deliver to subscribers
        callbacks = self._subscribers.get(topic, [])
        if not callbacks:
            logger.debug(f"No subscribers for topic '{topic}'.")

        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event)
                else:
                    cb(event)
            except Exception as e:
                # Log errors in callbacks, but don't stop the bus or other deliveries
                logger.error(
                    f"Error delivering event (ID: {event['event_id']}, topic: '{topic}') "
                    f"to callback '{getattr(cb, '__name__', str(cb))}': {e}",
                    exc_info=True # Include traceback in log
                )

    def get_log(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves a copy of the event log, optionally filtered by topic.

        Returns:
            A list of event dictionaries. Each dictionary represents a logged event.
        """
        if topic:
            return [e for e in self._event_log if e["topic"] == topic]
        return list(self._event_log) # Return a copy to prevent external modification

    def clear_log(self) -> None:
        """
        Clears all events from the internal event log.
        """
        self._event_log.clear()
        logger.info("Event log cleared.")