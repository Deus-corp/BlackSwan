"""
Детерминированный выбор лидера роя.
Использует SHA-256, чтобы результат был одинаковым на всех машинах.
"""
import hashlib

def select_leader(node_id: str, block_number: int, total_nodes: int) -> int:
    """
    Возвращает индекс узла-лидера (0..total_nodes-1).
    """
    seed = f"{node_id}:{block_number}".encode('utf-8')
    h = hashlib.sha256(seed).hexdigest()
    # Преобразуем хэш в целое число и берём модуль
    leader_index = int(h, 16) % total_nodes
    return leader_index