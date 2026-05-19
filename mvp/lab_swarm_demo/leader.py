"""
Deterministic leader selection for a swarm.
Uses SHA-256 to ensure consistent results across all machines.
"""
import hashlib

def select_leader(node_id: str, block_number: int, total_nodes: int) -> int:
    """
    Selects the swarm leader deterministically based on an SHA-256 hash.

    This function generates a unique hash using the node's identifier and a block number,
    then uses this hash to deterministically select a leader from the total number of
    nodes. This approach ensures consistency in leader selection across different
    machines within the swarm, as SHA-256 is a cryptographically strong and
    deterministic hash function.

    Args:
        node_id (str): A unique string identifier for the current node.
        block_number (int): An integer representing the current block or round number,
                            used to vary the hash seed for each selection event.
        total_nodes (int): The total count of active nodes in the swarm. This parameter
                           determines the range of the leader index (from 0 to total_nodes-1).

    Returns:
        int: The index of the leader node (an integer from 0 to total_nodes-1).

    Raises:
        ValueError: If `total_nodes` is not a positive integer.
    """
    if not isinstance(total_nodes, int) or total_nodes <= 0:
        raise ValueError("total_nodes must be a positive integer.")

    # Construct a seed string that uniquely identifies the current selection context.
    # This ensures that for the same node_id and block_number, the leader selection
    # will always be identical across all nodes.
    seed: bytes = f"{node_id}:{block_number}".encode('utf-8')
    
    # Compute the SHA-256 hash of the seed.
    # .hexdigest() returns the hash as a string of hexadecimal digits.
    h: str = hashlib.sha256(seed).hexdigest()
    
    # Convert the hexadecimal hash string to an integer.
    # Taking the modulo with the total number of nodes ensures the result
    # is an index within the valid range [0, total_nodes - 1].
    leader_index: int = int(h, 16) % total_nodes
    
    return leader_index