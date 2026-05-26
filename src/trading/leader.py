"""Deterministic leader selection helpers for swarm execution."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence


def select_leader(node_id: str, block_number: int, total_nodes: int) -> int:
    """Select a deterministic leader index in range [0, total_nodes - 1]."""
    clean_node_id = str(node_id or "").strip()
    if not clean_node_id:
        raise ValueError("node_id must be a non-empty string")
    if not isinstance(block_number, int) or block_number < 0:
        raise ValueError(f"block_number must be a non-negative integer, got {block_number!r}")
    if not isinstance(total_nodes, int) or total_nodes <= 0:
        raise ValueError(f"total_nodes must be a positive integer, got {total_nodes!r}")

    seed = f"{clean_node_id}:{block_number}:{total_nodes}".encode("utf-8")
    return int(hashlib.sha256(seed).hexdigest(), 16) % total_nodes


def select_leader_node(nodes: Sequence[str], block_number: int) -> str:
    """Select a deterministic leader node id from a sequence of node ids."""
    normalized_nodes = sorted({str(node or "").strip() for node in nodes if str(node or "").strip()})
    if not normalized_nodes:
        raise ValueError("nodes must contain at least one non-empty node id")

    seed = f"{block_number}:{'|'.join(normalized_nodes)}".encode("utf-8")
    index = int(hashlib.sha256(seed).hexdigest(), 16) % len(normalized_nodes)
    return normalized_nodes[index]


def is_leader(node_id: str, nodes: Sequence[str], block_number: int) -> bool:
    """Return True when node_id is selected as leader for the given block."""
    clean_node_id = str(node_id or "").strip()
    if not clean_node_id:
        raise ValueError("node_id must be a non-empty string")

    return select_leader_node(nodes, block_number) == clean_node_id