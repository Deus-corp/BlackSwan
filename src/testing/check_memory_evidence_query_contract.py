from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


EXPECTED_TYPE = "memory_evidence_query_result"
EXPECTED_RETRIEVAL_VERSION = "memory_retrieval_v0_1"
EXPECTED_RETRIEVAL_MODE = "deterministic"

ALLOWED_EMBEDDING_STATUSES = {
    "not_computed",
    "pending",
    "failed",
    "computed",
}

SAFETY_FLAGS = (
    "external_write_performed",
    "real_execution_enabled",
    "production_paths_mutated",
    "production_secrets_accessed",
)


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_memory_evidence_query_contract(
    result: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []

    if result.get("type") != EXPECTED_TYPE:
        errors.append(f"type must be {EXPECTED_TYPE}")

    if result.get("retrieval_contract_version") != EXPECTED_RETRIEVAL_VERSION:
        errors.append(
            "retrieval_contract_version must be "
            f"{EXPECTED_RETRIEVAL_VERSION}"
        )

    if result.get("retrieval_mode") != EXPECTED_RETRIEVAL_MODE:
        errors.append(f"retrieval_mode must be {EXPECTED_RETRIEVAL_MODE}")

    if bool(result.get("hybrid_retrieval_enabled")):
        errors.append("hybrid_retrieval_enabled must be false")

    if bool(result.get("semantic_retrieval_enabled")):
        errors.append("semantic_retrieval_enabled must be false")

    semantic_candidates = result.get("semantic_candidates")
    if semantic_candidates != []:
        errors.append("semantic_candidates must be an empty list")

    embedding_status = str(result.get("embedding_status") or "").strip()
    if embedding_status not in ALLOWED_EMBEDDING_STATUSES:
        errors.append(f"invalid embedding_status: {embedding_status!r}")

    embedding_dim = _safe_int(result.get("embedding_dim"), default=0)
    if embedding_dim < 0:
        errors.append("embedding_dim must be >= 0")

    for flag in SAFETY_FLAGS:
        if bool(result.get(flag)):
            errors.append(f"{flag} must be false")

    results = result.get("results")
    if not isinstance(results, list):
        errors.append("results must be a list")
        results = []

    deterministic_candidates = result.get("deterministic_candidates")
    if not isinstance(deterministic_candidates, list):
        errors.append("deterministic_candidates must be a list")
        deterministic_candidates = []

    result_count = _safe_int(result.get("result_count"), default=-1)
    if result_count != len(results):
        errors.append(
            "result_count must equal len(results): "
            f"result_count={result_count}, len(results)={len(results)}"
        )

    deterministic_candidate_count = _safe_int(
        result.get("deterministic_candidate_count"),
        default=-1,
    )
    if deterministic_candidate_count != len(deterministic_candidates):
        errors.append(
            "deterministic_candidate_count must equal "
            "len(deterministic_candidates): "
            f"deterministic_candidate_count={deterministic_candidate_count}, "
            f"len(deterministic_candidates)={len(deterministic_candidates)}"
        )

    for index, candidate in enumerate(deterministic_candidates, start=1):
        if not isinstance(candidate, Mapping):
            errors.append(f"deterministic candidate #{index} must be a mapping")
            continue

        if _safe_int(candidate.get("rank"), default=0) != index:
            errors.append(
                f"deterministic candidate #{index} rank must equal {index}"
            )

        if candidate.get("retrieval_path") != "deterministic_catalog_query":
            errors.append(
                f"deterministic candidate #{index} retrieval_path must be "
                "deterministic_catalog_query"
            )

    return errors


def assert_memory_evidence_query_contract(result: Mapping[str, Any]) -> None:
    errors = validate_memory_evidence_query_contract(result)
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise AssertionError(
            "memory evidence query contract failed:\n"
            f"{details}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check memory evidence query JSON contract.",
    )
    parser.add_argument("json_path", help="Path to memory query JSON result.")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    path = Path(args.json_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert_memory_evidence_query_contract(payload)

    print("✅ memory evidence query contract OK")


if __name__ == "__main__":
    main()