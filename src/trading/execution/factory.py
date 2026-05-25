"""
Factory for creating ExecutionBackend instances based on the configured mode.
"""
import os
import sys
from typing import Any, Callable, TypeVar, cast

# Define a type for the leadership check function
LeadershipFunc = Callable[[int], bool]

def _load_config() -> Any:
    """
    Attempts to load the swarm_config module.

    Dynamically adjusts sys.path if the module is not initially found relative to
    the execution path or PYTHONPATH.

    Returns:
        The loaded configuration object.

    Raises:
        ImportError: If the configuration cannot be resolved after path adjustment.
    """
    try:
        from swarm_config import config
        return config
    except ImportError:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "../../.."))
        
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        
        try:
            from swarm_config import config
            return config
        except ImportError as e:
            raise ImportError(
                "Could not import 'config' from 'swarm_config'. "
                "Ensure swarm_config.py is in the PYTHONPATH or relative to project root."
            ) from e

# Global config instance
config = _load_config()

from .backend import ExecutionBackend
from .sim_backend import SimExecutionBackend
from .live_backend import LiveExecutionBackend

def build_backend(
    node_id: str, 
    adapter: Any, 
    is_leader_func: LeadershipFunc
) -> ExecutionBackend:
    """
    Builds and returns an appropriate ExecutionBackend instance based on market_mode.

    Args:
        node_id: The identifier for the current node.
        adapter: The adapter object (e.g., Web3 provider) for live systems.
        is_leader_func: Function mapping block number to leadership status.

    Returns:
        An instance of SimExecutionBackend or LiveExecutionBackend.

    Raises:
        ValueError: If an unsupported market mode is configured.
    """
    mode = getattr(config, "market_mode", "sim")
    
    if mode == "sim":
        return SimExecutionBackend()
    
    if mode in ("web3", "live"):
        return LiveExecutionBackend(node_id, adapter, is_leader_func)
    
    raise ValueError(f"Unsupported market mode: {mode}")