from __future__ import annotations

from typing import Any, Iterable, Mapping


MEMORY_RETRIEVAL_CONTRACT_VERSION = "memory_retrieval_v0_1"
MEMORY_RETRIEVAL_MODE_DETERMINISTIC = "deterministic"


def memory_retrieval_contract_defaults() -> dict[str, Any]:
    """Return deterministic retrieval contract defaults.

    This is a placeholder contract for future hybrid retrieval. It does not
    compute embeddings, does not query a vector database, and does not enable
    semantic retrieval.
    """
    return {
        "retrieval_contract_version": MEMORY_RETRIEVAL_CONTRACT_VERSION,
        "retrieval_mode": MEMORY_RETRIEVAL_MODE_DETERMINISTIC,
        "hybrid_retrieval_enabled": False,
        "semantic_retrieval_enabled": False,
        "semantic_candidates": [],
    }


def deterministic_candidate_summary(
    items: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build compact deterministic candidate telemetry for query results."""
    out: list[dict[str, Any]] = []

    for rank, item in enumerate(items, start=1):
        if not isinstance(item, Mapping):
            continue

        out.append(
            {
                "rank": rank,
                "url": str(item.get("url") or "").strip(),
                "domain": str(item.get("domain") or "").strip(),
                "dedupe_key": str(item.get("dedupe_key") or "").strip(),
                "ranking_score": float(item.get("ranking_score") or 0.0),
                "source_score": float(item.get("source_score") or 0.0),
                "system_relevance_score": float(
                    item.get("system_relevance_score") or 0.0
                ),
                "retrieval_path": "deterministic_catalog_query",
            }
        )

    return out


def attach_memory_retrieval_contract(
    payload: Mapping[str, Any],
    *,
    deterministic_items: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Attach deterministic retrieval contract fields to a query payload."""
    out = dict(payload)
    out.update(memory_retrieval_contract_defaults())
    out["deterministic_candidates"] = deterministic_candidate_summary(
        deterministic_items
    )
    out["deterministic_candidate_count"] = len(out["deterministic_candidates"])
    return out