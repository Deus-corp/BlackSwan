import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
import uuid

# Define the expected signature for an event callback
EventCallback = Callable[[Dict[str, Any]], Any]

class EventBus:
    """
    Единая асинхронная шина для взаимодействия компонентов.
    Поддерживает подписку по топикам, публикацию событий и простейший аудит.
    """

    def __init__(self) -> None:
        # Топик -> список callback-функций
        self._subscribers: Dict[str, List[EventCallback]] = {}
        self._event_log: List[Dict[str, Any]] = []

    def subscribe(self, topic: str, callback: EventCallback) -> None:
        """Подписаться на события определённого топика."""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback: EventCallback) -> None:
        """Отписаться от событий определённого топика."""
        if topic in self._subscribers:
            # Note: list.remove() raises ValueError if the item is not present.
            # This behavior is preserved from the original code.
            self._subscribers[topic].remove(callback)

    async def publish(self, topic: str, payload: Any, source_component: str = "unknown",
                      sensitivity: int = 1, visibility: str = "local") -> None:
        """
        Опубликовать событие.
        - topic: economic, infra, security, execution, knowledge, command и т.д.
        - payload: данные события (dict/list)
        - source_component: имя компонента-отправителя
        - sensitivity: 1-5 (чем выше, тем критичнее)
        - visibility: local / swarm / global
        """
        event = {
            "event_id": str(uuid.uuid4()),
            "topic": topic,
            "source_component": source_component,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
            "sensitivity": sensitivity,
            "visibility": visibility,
            "signature": "ed25519:..."  # заглушка, в реальности – криптоподпись
        }
        self._event_log.append(event)
        # Доставляем подписчикам
        callbacks = self._subscribers.get(topic, [])
        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event)
                else:
                    cb(event)
            except Exception as e:
                print(f"Error delivering event to {cb}: {e}")

    def get_log(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получить лог всех или отфильтрованных по топику событий."""
        if topic:
            return [e for e in self._event_log if e["topic"] == topic]
        return self._event_log

    def clear_log(self) -> None:
        """Очистить лог событий."""
        self._event_log.clear()