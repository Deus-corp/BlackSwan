"""
Factory for creating ExecutionBackend instances based on the configured mode.
"""
import os
import sys
from typing import Any, Callable

def _load_config():
    """Attempts to import swarm_config, modifying sys.path if necessary."""
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

config = _load_config()

from .backend import ExecutionBackend
from .sim_backend import SimExecutionBackend
from .live_backend import LiveExecutionBackend

def build_backend(
    node_id: str, 
    adapter: Any, 
    is_leader_func: Callable[[int], bool]
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
    mode = config.market_mode
    
    if mode == "sim":
        return SimExecutionBackend()
    
    if mode in ("web3", "live"):
        return LiveExecutionBackend(node_id, adapter, is_leader_func)
    
    raise ValueError(f"Unsupported market mode: {mode}")