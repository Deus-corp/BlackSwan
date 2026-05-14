import pytest
from mvp.lab_swarm_demo.leader import select_leader

def test_leader_deterministic():
    # Одинаковые входные данные → одинаковый лидер
    node_id = "test-node-1"
    block = 12345
    total = 4
    first = select_leader(node_id, block, total)
    second = select_leader(node_id, block, total)
    assert first == second

def test_leader_different_blocks():
    # Разные блоки → обычно разные лидеры (хотя возможны коллизии)
    node_id = "test-node-1"
    total = 4
    leader_1 = select_leader(node_id, 100, total)
    leader_2 = select_leader(node_id, 200, total)
    # Не обязательно разные, но для разных блоков высока вероятность
    # Просто проверяем, что функция возвращает корректный диапазон
    assert 0 <= leader_1 < total
    assert 0 <= leader_2 < total

def test_leader_range():
    # Проверяем, что лидер всегда в допустимом диапазоне
    node_id = "node-xyz"
    for block in range(0, 1000, 50):
        idx = select_leader(node_id, block, 5)
        assert 0 <= idx < 5