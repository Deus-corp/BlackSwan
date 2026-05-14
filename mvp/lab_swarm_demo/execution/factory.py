"""
Фабрика для создания ExecutionBackend в зависимости от режима.
"""
from .backend import ExecutionBackend
from .sim_backend import SimExecutionBackend
from .live_backend import LiveExecutionBackend
from swarm_config import config


def build_backend(node_id: str, adapter, is_leader_func) -> ExecutionBackend:
    mode = config.market_mode
    if mode == "sim":
        return SimExecutionBackend()
    elif mode in ("web3", "live"):
        return LiveExecutionBackend(node_id, adapter, is_leader_func)
    else:
        raise ValueError(f"Unsupported market mode: {mode}")