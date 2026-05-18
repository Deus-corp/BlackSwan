"""
Фабрика для создания ExecutionBackend в зависимости от режима.
"""
from typing import Any, Callable

from .backend import ExecutionBackend
from .sim_backend import SimExecutionBackend
from .live_backend import LiveExecutionBackend
from swarm_config import config


def build_backend(node_id: str, adapter: Any, is_leader_func: Callable[[], bool]) -> ExecutionBackend:
    """
    Builds and returns an appropriate ExecutionBackend instance based on the configured market mode.

    Args:
        node_id (str): The identifier for the current node.
        adapter (Any): An adapter object, typically used by live execution backends
                       to interact with external systems (e.g., a Web3 provider).
        is_leader_func (Callable[[], bool]): A callable function that returns
                                              True if the current node is the leader, False otherwise.

    Returns:
        ExecutionBackend: An instance of either SimExecutionBackend or LiveExecutionBackend,
                          configured according to the market mode.

    Raises:
        ValueError: If an unsupported market mode is configured in `swarm_config.config.market_mode`.
    """
    mode: str = config.market_mode
    if mode == "sim":
        return SimExecutionBackend()
    elif mode in ("web3", "live"):
        return LiveExecutionBackend(node_id, adapter, is_leader_func)
    else:
        raise ValueError(f"Unsupported market mode: {mode}")