"""
Deterministic leader selection for a swarm.
Uses SHA-256 to ensure consistent results across all machines.
"""
import hashlib
from typing import str as Str # Alias str to Str to avoid confusion with the type hint 'str' used as a parameter name in the docstring

def select_leader(node_id: str, block_number: int, total_nodes: int) -> int:
    """
    Selects the swarm leader deterministically based on an SHA-256 hash.

    Generates a unique hash using the node ID and block number, then uses it
    to deterministically select a leader from the total number of nodes.
    This approach ensures consistency in leader selection across different machines,
    as SHA-256 is a cryptographically strong hash function.

    Args:
        node_id: A unique string identifier for the current node.
        block_number: An integer representing the current block or round number,
                      used to vary the hash seed.
        total_nodes: The total count of nodes in the swarm. This determines
                     the range of the leader index (from 0 to total_nodes-1).

    Returns:
        The index of the leader node (an integer from 0 to total_nodes-1).

    Raises:
        ValueError: If `total_nodes` is not a positive integer.
    """
    if not isinstance(total_nodes, int) or total_nodes <= 0:
        raise ValueError("total_nodes must be a positive integer.")

    seed: bytes = f"{node_id}:{block_number}".encode('utf-8')
    h: str = hashlib.sha256(seed).hexdigest()
    # Convert the hexadecimal hash string to an integer and take its modulo
    # with the total number of nodes to get an index within the desired range.
    leader_index: int = int(h, 16) % total_nodes
    return leader_index