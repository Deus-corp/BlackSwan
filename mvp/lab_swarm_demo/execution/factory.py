"""
Фабрика для создания ExecutionBackend в зависимости от режима.
"""
import os
import sys
from typing import Any, Callable

# Assuming swarm_config is importable and has a 'config' object with 'market_mode' attribute.
# Added robust import handling for `swarm_config`.
try:
    from swarm_config import config
except ImportError:
    # Fallback for local testing if swarm_config is not directly importable.
    # Assumes swarm_config.py is in 'mvp/lab_swarm_demo/' or its parent directory.
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    _root_dir = os.path.join(_current_dir, "../../..") # Adjust path as necessary for swarm_config location
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)
    try:
        from swarm_config import config
    except ImportError:
        # If still not found, raise the original error or a more specific one.
        raise ImportError(
            "Could not import 'config' from 'swarm_config'. "
            "Ensure swarm_config.py is accessible in PYTHONPATH or located correctly relative to 'execution'."
        )


from .backend import ExecutionBackend
from .sim_backend import SimExecutionBackend
from .live_backend import LiveExecutionBackend


def build_backend(node_id: str, adapter: Any, is_leader_func: Callable[[int], bool]) -> ExecutionBackend:
    """
    Builds and returns an appropriate ExecutionBackend instance based on the configured market mode.

    Args:
        node_id (str): The identifier for the current node.
        adapter (Any): An adapter object, typically used by live execution backends
                       to interact with external systems (e.g., a Web3 provider).
                       Its specific interface depends on the chosen backend implementation.
                       Refer to `LiveExecutionBackend.__init__` for expected adapter methods.
        is_leader_func (Callable[[int], bool]): A callable function that takes an integer
                                                 (representing a blockchain block number) and returns
                                                 True if the current node is the leader
                                                 for that block, False otherwise.

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
        # The `is_leader_func` type hint is corrected here to `Callable[[int], bool]`
        # to match the `LiveExecutionBackend.__init__` signature, ensuring type consistency.
        return LiveExecutionBackend(node_id, adapter, is_leader_func)
    else:
        raise ValueError(f"Unsupported market mode: {mode}")