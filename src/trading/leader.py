"""
Deterministic leader selection for a swarm using SHA-256.
"""
import hashlib


def select_leader(node_id: str, block_number: int, total_nodes: int) -> int:
    """
    Selects the swarm leader deterministically based on an SHA-256 hash.

    This function combines a node identifier and a block number to create a
    unique seed, hashing it to determine the leader index. This ensures 
    consistent outcomes across distributed nodes.

    Args:
        node_id: A unique identifier for the node.
        block_number: The current block or round index.
        total_nodes: The number of active nodes in the swarm.

    Returns:
        An integer index within the range [0, total_nodes - 1].

    Raises:
        ValueError: If total_nodes is not a positive integer.
    """
    if not isinstance(total_nodes, int) or total_nodes <= 0:
        raise ValueError(f"total_nodes must be a positive integer, got {total_nodes}.")

    # Generate consistent hash input
    seed: bytes = f"{node_id}:{block_number}".encode("utf-8")
    
    # Compute SHA-256 hash and map to index space
    hash_hex: str = hashlib.sha256(seed).hexdigest()
    return int(hash_hex, 16) % total_nodes