from __future__ import annotations

from typing import Any, Mapping


MEMORY_VECTOR_READY_DEFAULTS: dict[str, Any] = {
    "semantic_retrieval_enabled": False,
    "embedding_status": "not_computed",
    "embedding_model": "",
    "embedding_dim": 0,
    "embedding_hash": "",
    "embedding_vector_ref": "",
    "embedding_updated_at": 0.0,
}

_ALLOWED_EMBEDDING_STATUSES = {
    "not_computed",
    "pending",
    "failed",
    "computed",
}


def memory_vector_ready_defaults() -> dict[str, Any]:
    """Return default vector-ready memory fields.

    This is schema-only. It does not compute embeddings, does not connect to a
    vector database, and does not enable semantic retrieval.
    """
    return dict(MEMORY_VECTOR_READY_DEFAULTS)


def normalize_memory_vector_ready_fields(
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize vector-ready fields for memory records/catalog items.

    In PR 39.5a semantic retrieval is explicitly disabled. Future PRs can add an
    embedding backend and controlled activation, but this contract keeps current
    retrieval deterministic and dataflow-only.
    """
    source = source if isinstance(source, Mapping) else {}

    embedding_status = str(
        source.get("embedding_status")
        or MEMORY_VECTOR_READY_DEFAULTS["embedding_status"]
    ).strip().lower()
    if embedding_status not in _ALLOWED_EMBEDDING_STATUSES:
        embedding_status = "not_computed"

    try:
        embedding_dim = int(source.get("embedding_dim") or 0)
    except (TypeError, ValueError):
        embedding_dim = 0

    try:
        embedding_updated_at = float(source.get("embedding_updated_at") or 0.0)
    except (TypeError, ValueError):
        embedding_updated_at = 0.0

    # 39.5a is vector-ready only. Do not allow accidental activation.
    return {
        "semantic_retrieval_enabled": False,
        "embedding_status": embedding_status,
        "embedding_model": str(source.get("embedding_model") or "").strip(),
        "embedding_dim": max(0, embedding_dim),
        "embedding_hash": str(source.get("embedding_hash") or "").strip(),
        "embedding_vector_ref": str(source.get("embedding_vector_ref") or "").strip(),
        "embedding_updated_at": max(0.0, embedding_updated_at),
    }


def attach_memory_vector_ready_fields(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Return payload with normalized vector-ready fields attached."""
    out = dict(payload)
    out.update(normalize_memory_vector_ready_fields(payload))
    return out