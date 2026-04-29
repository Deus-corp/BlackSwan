"""
LWW-Register CRDT для репликации состояния.
Каждый ключ хранит значение и timestamp.
При конфликте побеждает запись с наибольшим timestamp.
"""
import time
from typing import Any, Dict, Optional

class CRDTState:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.state: Dict[str, Dict[str, Any]] = {}  # key -> {value, timestamp}

    def update(self, key: str, value: Any) -> None:
        """Локальное обновление ключа (всегда принимается, т.к. локальное время новее)."""
        self.state[key] = {
            "value": value,
            "timestamp": time.time()
        }

    def merge(self, remote_state: Dict[str, Dict[str, Any]]) -> bool:
        """
        Слияние с удалённым состоянием.
        Возвращает True, если были изменения.
        """
        changed = False
        for key, remote_entry in remote_state.items():
            if key not in self.state:
                self.state[key] = remote_entry
                changed = True
            elif remote_entry["timestamp"] > self.state[key]["timestamp"]:
                self.state[key] = remote_entry
                changed = True
        return changed

    def get(self, key: str) -> Optional[Any]:
        entry = self.state.get(key)
        return entry["value"] if entry else None

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация для передачи по сети."""
        return self.state