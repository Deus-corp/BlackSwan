"""
A module providing a unified asynchronous event bus for inter-component communication.

This event bus supports subscribing to topics, publishing events with metadata,
and basic event logging for auditing purposes.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Literal, TypeAlias # Added Literal, TypeAlias
import uuid

# Set up logging for the event bus
logger = logging.getLogger(__name__)

# Define the expected signature for an event callback.
# Callbacks receive a single argument: the event dictionary.
# They can return Any, including None, or be awaitable if they are coroutines.
EventCallback: TypeAlias = Callable[[Dict[str, Any]], Any]

# Define a Literal type for event visibility scopes for improved type safety and validation.
VisibilityScope: TypeAlias = Literal["local", "swarm", "global"]

class EventBus:
    """
    A unified asynchronous event bus for component interaction.

    Supports subscribing to topics, publishing events, and basic event logging
    for auditing purposes. Events contain rich metadata such as topic, source,
    timestamp, sensitivity, and visibility, along with a free-form payload.
    """
    __slots__ = ('_subscribers', '_event_log') # Added __slots__ for minor memory optimization

    def __init__(self) -> None:
        """
        Initializes the EventBus.

        Sets up internal structures for managing subscribers and logging events.
        """
        # Topic (str) -> List of callback functions (EventCallback)
        self._subscribers: Dict[str, List[EventCallback]] = {}
        # A chronological log of all published events (list of Dict[str, Any])
        self._event_log: List[Dict[str, Any]] = []
        logger.debug("EventBus initialized.")

    def __repr__(self) -> str:
        """
        Returns a string representation of the EventBus instance.
        """
        num_topics = len(self._subscribers)
        num_events = len(self._event_log)
        return f"EventBus(topics={num_topics}, logged_events={num_events})"

    def subscribe(self, topic: str, callback: EventCallback) -> None:
        """
        Subscribes a callback function to events of a specific topic.

        The callback will be invoked whenever an event for the given topic is
        published. Callbacks can be regular functions or asynchronous coroutines.

        Args:
            topic: The topic string to subscribe to (e.g., "economic", "infra", "security").
            callback: The function or coroutine to be called when an event for the
                      given topic is published. It must accept one argument: the
                      event dictionary (`Dict[str, Any]`).

        Raises:
            ValueError: If topic is not a non-empty string.
            TypeError: If callback is not callable.
        """
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("topic must be a non-empty string.")
        if not callable(callback):
            raise TypeError("callback must be a callable function or coroutine.")

        topic_cleaned = topic.strip()
        if topic_cleaned not in self._subscribers:
            self._subscribers[topic_cleaned] = []
        self._subscribers[topic_cleaned].append(callback)
        logger.debug(f"Subscribed callback '{getattr(callback, '__name__', str(callback))}' to topic '{topic_cleaned}'")

    def unsubscribe(self, topic: str, callback: EventCallback) -> None:
        """
        Unsubscribes a callback function from events of a specific topic.

        Args:
            topic: The topic string to unsubscribe from.
            callback: The function to unsubscribe.

        Raises:
            ValueError: If the topic does not exist, or if the callback is not
                        subscribed to the specified topic.
            TypeError: If callback is not callable.
        """
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("topic must be a non-empty string.")
        if not callable(callback):
            raise TypeError("callback must be a callable function or coroutine.")

        topic_cleaned = topic.strip()
        if topic_cleaned not in self._subscribers:
            raise ValueError(f"Topic '{topic_cleaned}' has no subscribers, cannot unsubscribe callback.")
        
        # list.remove() raises ValueError if the item is not present.
        # This behavior is explicitly preserved.
        self._subscribers[topic_cleaned].remove(callback)
        if not self._subscribers[topic_cleaned]: # Clean up empty topic lists
            del self._subscribers[topic_cleaned]
        logger.debug(f"Unsubscribed callback '{getattr(callback, '__name__', str(callback))}' from topic '{topic_cleaned}'")


    async def publish(self, topic: str, payload: Any, source_component: str = "unknown",
                      sensitivity: int = 1, visibility: VisibilityScope = "local") -> None:
        """
        Publishes a new event to the bus.

        Constructs an event dictionary with rich metadata and payload.
        The event is logged and then delivered to all subscribed callbacks
        for the given topic. Asynchronous callbacks are awaited, while
        synchronous callbacks are called directly. Errors during callback
        execution are logged but do not prevent other deliveries.

        Args:
            topic: The category or subject of the event (e.g., "economic", "infra",
                   "security", "execution", "knowledge", "command").
            payload: The actual data content of the event. This can be any serializable
                     type (e.g., dict, list, str, int, float, bool, None).
            source_component: The identifier of the component originating the event.
                              Defaults to "unknown".
            sensitivity: An integer rating the criticality or sensitivity of the event.
                         Typically on a scale of 1-5 (higher values indicate higher
                         criticality/sensitivity). Defaults to 1.
            visibility: The scope of the event's intended visibility (e.g., "local",
                        "swarm", "global"). Defaults to "local".

        Raises:
            ValueError: If topic, source_component, sensitivity, or visibility are invalid.
        """
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("topic must be a non-empty string.")
        if not isinstance(source_component, str) or not source_component.strip():
            raise ValueError("source_component must be a non-empty string.")
        if not isinstance(sensitivity, int) or not (1 <= sensitivity <= 5):
            raise ValueError("sensitivity must be an integer between 1 and 5.")
        # Validate visibility against the Literal type arguments
        if not isinstance(visibility, str) or visibility not in VisibilityScope.__args__:
            raise ValueError(f"visibility must be one of {list(VisibilityScope.__args__)}. Got '{visibility}'.")

        topic_cleaned = topic.strip()
        source_component_cleaned = source_component.strip()

        event: Dict[str, Any] = {
            "event_id": str(uuid.uuid4()),
            "topic": topic_cleaned,
            "source_component": source_component_cleaned,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds'), # Added timespec for precision
            "payload": payload,
            "sensitivity": sensitivity,
            "visibility": visibility,
            "signature": "ed25519:..."  # Placeholder for actual cryptographic signature in a real system
        }
        self._event_log.append(event)
        logger.info(
            f"Published event '{topic_cleaned}' from '{source_component_cleaned}' "
            f"(ID: {event['event_id']}, Sensitivity: {sensitivity}, Visibility: {visibility})",
            extra={"event": event} # Added event to log record extra for structured logging
        )

        # Deliver to subscribers for this topic
        callbacks = self._subscribers.get(topic_cleaned, [])
        if not callbacks:
            logger.debug(f"No subscribers for topic '{topic_cleaned}'. Event ID: {event['event_id']}")
            return # No need to proceed if no callbacks

        # Concurrently deliver to all callbacks
        delivery_tasks = []
        for cb_idx, cb in enumerate(callbacks):
            try:
                if asyncio.iscoroutinefunction(cb):
                    delivery_tasks.append(cb(event))
                else:
                    # Run synchronous callbacks directly
                    cb(event)
            except Exception as e:
                # Log errors in synchronous callbacks, but don't stop the bus or other deliveries
                logger.error(
                    f"Error delivering event (ID: {event['event_id']}, topic: '{topic_cleaned}') "
                    f"to synchronous callback '{getattr(cb, '__name__', str(cb))}': {e}",
                    exc_info=True # Include traceback in log
                )
        
        # Await all asynchronous callbacks concurrently
        if delivery_tasks:
            # Using gather to run tasks concurrently and handle potential exceptions in each
            results = await asyncio.gather(*delivery_tasks, return_exceptions=True)
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    # Ensure we reference the correct callback that caused the exception
                    failed_callback = callbacks[i]
                    logger.error(
                        f"Error delivering event (ID: {event['event_id']}, topic: '{topic_cleaned}') "
                        f"to asynchronous callback '{getattr(failed_callback, '__name__', str(failed_callback))}': {res}",
                        exc_info=True # Include traceback in log
                    )


    def get_log(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves a copy of the event log, optionally filtered by topic.

        Args:
            topic: An optional topic string to filter the log. If None, all
                   events in the log are returned.

        Returns:
            A list of event dictionaries. Each dictionary represents a logged event.
            The list is a shallow copy to prevent external modification of the
            internal log.

        Raises:
            ValueError: If topic is provided but is not a non-empty string.
        """
        if topic is not None:
            if not isinstance(topic, str) or not topic.strip():
                raise ValueError("topic must be a non-empty string or None.")
            topic_cleaned = topic.strip()
            return [e for e in self._event_log if e["topic"] == topic_cleaned]
        return list(self._event_log) # Return a copy to prevent external modification

    def clear_log(self) -> None:
        """
        Clears all events from the internal event log.

        This action is irreversible and empties the `_event_log` list.
        """
        self._event_log.clear()
        logger.info("Event log cleared.")