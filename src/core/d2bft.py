"""
Минимальный прототип D2BFT консенсуса.
Узлы голосуют за значение, консенсус достигается при 2/3 голосов.
"""
import json
from typing import Any, Dict, Optional

class D2BFTNode:
    """
    Minimal prototype for a D2BFT consensus node.
    Nodes vote on a value, and consensus is reached with a 2/3 majority (or simple majority for this implementation).
    """
    def __init__(self, node_id: str, total_nodes: int = 3):
        self.node_id: str = node_id
        self.total_nodes: int = total_nodes
        self.current_view: int = 0
        self.votes: Dict[str, Any] = {}  # node_id -> value
        self.decision: Optional[Any] = None

    def propose(self, value: Any) -> Any:
        """
        Предложить значение для текущего раунда.
        Сбрасывает предыдущие голоса и решение.
        """
        self.votes = {self.node_id: value}
        self.decision = None
        return value

    def receive_vote(self, from_node: str, value: Any) -> bool:
        """
        Принять голос от другого узла.
        Проверяет, достигнуто ли большинство голосов для принятия решения.
        Возвращает True, если решение было принято в результате этого голоса.
        """
        if from_node not in self.votes:
            self.votes[from_node] = value
        
        count: Dict[Any, int] = {}
        for v in self.votes.values():
            count[v] = count.get(v, 0) + 1
            
        # Для 3 узлов достаточно 2 одинаковых голосов (большинство)
        # The condition `cnt > self.total_nodes // 2` checks for a simple majority.
        # For N=3, N//2 = 1, so `cnt > 1` means `cnt >= 2`, which is 2/3 of 3.
        for v, cnt in count.items():
            if cnt > self.total_nodes // 2:          # большинство
                self.decision = v
                return True
        return False

    def get_decision(self) -> Optional[Any]:
        """
        Возвращает текущее принятое решение.
        Возвращает None, если решение еще не принято.
        """
        return self.decision