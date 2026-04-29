"""
Минимальный прототип D2BFT консенсуса.
Узлы голосуют за значение, консенсус достигается при 2/3 голосов.
"""
import json
from typing import Any, Optional

class D2BFTNode:
    def __init__(self, node_id: str, total_nodes: int = 3):
        self.node_id = node_id
        self.total_nodes = total_nodes
        self.current_view = 0
        self.votes: dict[str, Any] = {}  # node_id -> value
        self.decision: Optional[Any] = None

    def propose(self, value: Any) -> str:
        """Предложить значение для текущего раунда."""
        self.votes = {self.node_id: value}
        self.decision = None
        return value

    def receive_vote(self, from_node: str, value: Any) -> bool:
        """
        Принять голос от другого узла.
        Возвращает True, если достигнут консенсус.
        """
        if from_node not in self.votes:
            self.votes[from_node] = value
        # Считаем голоса
        count = {}
        for v in self.votes.values():
            count[v] = count.get(v, 0) + 1
        # Проверяем большинство (2/3)
        for v, cnt in count.items():
            if cnt >= (2 * self.total_nodes // 3) + 1:
                self.decision = v
                return True
        return False

    def get_decision(self) -> Optional[Any]:
        return self.decision