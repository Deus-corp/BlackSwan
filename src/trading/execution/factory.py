"""
Factory for creating ExecutionBackend instances based on the configured mode.
"""
import os
import sys
from typing import Any, Callable, TYPE_CHECKING

# This block handles the import of `swarm_config.config` with a fallback mechanism.
# It first attempts a standard import. If that fails (e.g., during local development
# where `swarm_config` might not be in the PYTHONPATH or installed as a package),
# it temporarily modifies `sys.path` to look in the project's root directory.
# This approach is generally for specific project structures and should be used with caution.
try:
    from swarm_config import config
except ImportError:
    _current_dir: str = os.path.dirname(os.path.abspath(__file__))
   
    _root_dir: str = os.path.join(_current_dir, "../../..")
    
    # Only add to sys.path if not already present to avoid redundant entries
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)
    try:
        from swarm_config import config
    except ImportError:
        # If still not found, raise a more informative error.
        raise ImportError(
            "Could not import 'config' from 'swarm_config'. "
            "Ensure swarm_config.py is accessible in PYTHONPATH or located correctly "
            "relative to 'execution' (expected at the project root)."
        )

# Type-checking import for potential circular dependencies or to avoid runtime imports
if TYPE_CHECKING:
    # We might need to import these classes for type hints if they were only used in return types
    # or if we wanted to avoid runtime import issues, but in this case, direct import is fine.
    pass

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
        return LiveExecutionBackend(node_id, adapter, is_leader_func)
    else:
        raise ValueError(f"Unsupported market mode: {mode}")