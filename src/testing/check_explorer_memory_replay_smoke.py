from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


EXPECTED_TYPE = "explorer_memory_replay_smoke_result"
EXPECTED_STATUS = "passed"
EXPECTED_RETRIEVAL_MODE = "deterministic"

SAFETY_FLAGS = (
    "external_write_performed",
    "real_execution_enabled",
    "production_paths_mutated",
    "production_secrets_accessed",
)

YIELD_COUNTER_FIELDS = (
    "records_published",
    "artifact_records",
    "artifact_available_records",
    "records_seen",
    "records_replayed",
    "query_results",
)

YIELD_RATIO_FIELDS = (
    "artifact_capture_ratio",
    "artifact_availability_ratio",
    "replay_visibility_ratio",
    "replay_acceptance_ratio",
    "query_result_ratio",
    "full_replay_path_ratio",
)


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _expected_ratio(
    numerator: int,
    denominator: int,
    *,
    precision: int = 4,
) -> float:
    if denominator <= 0:
        return 0.0

    return round(float(numerator) / float(denominator), precision)


def _ratio_matches(
    actual: Any,
    expected: float,
    *,
    tolerance: float = 0.00001,
) -> bool:
    return abs(_safe_float(actual, default=-1.0) - expected) <= tolerance


def validate_explorer_memory_replay_smoke(
    result: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []

    if result.get("type") != EXPECTED_TYPE:
        errors.append(f"type must be {EXPECTED_TYPE}")

    if result.get("status") != EXPECTED_STATUS:
        errors.append(f"status must be {EXPECTED_STATUS}")

    if result.get("explorer_contract_ok") is not True:
        errors.append("explorer_contract_ok must be true")

    if result.get("memory_query_contract_ok") is not True:
        errors.append("memory_query_contract_ok must be true")

    if result.get("retrieval_mode") != EXPECTED_RETRIEVAL_MODE:
        errors.append(f"retrieval_mode must be {EXPECTED_RETRIEVAL_MODE}")

    if bool(result.get("hybrid_retrieval_enabled")):
        errors.append("hybrid_retrieval_enabled must be false")

    if bool(result.get("semantic_retrieval_enabled")):
        errors.append("semantic_retrieval_enabled must be false")

    if result.get("semantic_candidates") != []:
        errors.append("semantic_candidates must be an empty list")

    for flag in SAFETY_FLAGS:
        if bool(result.get(flag)):
            errors.append(f"{flag} must be false")

    yield_metrics = result.get("memory_replay_yield")
    if not isinstance(yield_metrics, Mapping):
        errors.append("memory_replay_yield must be a mapping")
        return errors

    for field in YIELD_COUNTER_FIELDS:
        if _safe_int(yield_metrics.get(field), default=-1) < 0:
            errors.append(f"memory_replay_yield.{field} must be >= 0")

    records_published = _safe_int(
        result.get("total_memory_records_published"),
        default=0,
    )
    artifact_records = _safe_int(
        result.get("memory_replay_artifact_record_count"),
        default=0,
    )
    artifact_available_records = _safe_int(
        result.get("memory_replay_artifact_available_record_count"),
        default=0,
    )
    records_seen = _safe_int(
        result.get("explorer_memory_records_seen"),
        default=0,
    )
    records_replayed = _safe_int(
        result.get("explorer_memory_records_replayed"),
        default=0,
    )
    query_results = _safe_int(
        result.get("memory_query_result_count"),
        default=0,
    )

    expected_counters = {
        "records_published": records_published,
        "artifact_records": artifact_records,
        "artifact_available_records": artifact_available_records,
        "records_seen": records_seen,
        "records_replayed": records_replayed,
        "query_results": query_results,
    }

    for field, expected in expected_counters.items():
        actual = _safe_int(yield_metrics.get(field), default=-1)
        if actual != expected:
            errors.append(
                f"memory_replay_yield.{field} must match summary counter: "
                f"actual={actual}, expected={expected}"
            )

    if artifact_available_records < artifact_records:
        errors.append(
            "memory_replay_artifact_available_record_count must be >= "
            "memory_replay_artifact_record_count"
        )

    if records_seen > artifact_records:
        errors.append(
            "explorer_memory_records_seen must be <= "
            "memory_replay_artifact_record_count"
        )

    if records_replayed > records_seen:
        errors.append(
            "explorer_memory_records_replayed must be <= "
            "explorer_memory_records_seen"
        )

    if query_results > records_replayed:
        errors.append(
            "memory_query_result_count must be <= "
            "explorer_memory_records_replayed"
        )

    for field in YIELD_RATIO_FIELDS:
        value = _safe_float(yield_metrics.get(field), default=-1.0)
        if value < 0.0 or value > 1.0:
            errors.append(f"memory_replay_yield.{field} must be between 0.0 and 1.0")

    expected_ratios = {
        "artifact_capture_ratio": _expected_ratio(
            artifact_records,
            records_published,
        ),
        "artifact_availability_ratio": _expected_ratio(
            artifact_available_records,
            records_published,
        ),
        "replay_visibility_ratio": _expected_ratio(
            records_seen,
            artifact_records,
        ),
        "replay_acceptance_ratio": _expected_ratio(
            records_replayed,
            records_seen,
        ),
        "query_result_ratio": _expected_ratio(
            query_results,
            records_replayed,
        ),
        "full_replay_path_ratio": _expected_ratio(
            query_results,
            records_published,
        ),
    }

    for field, expected in expected_ratios.items():
        actual = yield_metrics.get(field)
        if not _ratio_matches(actual, expected):
            errors.append(
                f"memory_replay_yield.{field} must equal {expected}: "
                f"actual={actual}"
            )

    return errors


def assert_explorer_memory_replay_smoke(
    result: Mapping[str, Any],
) -> None:
    errors = validate_explorer_memory_replay_smoke(result)
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise AssertionError(
            "explorer memory replay smoke contract failed:\n"
            f"{details}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check explorer memory replay smoke summary contract.",
    )
    parser.add_argument(
        "json_path",
        help="Path to explorer memory replay smoke summary JSON.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    path = Path(args.json_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, Mapping):
        raise AssertionError("explorer memory replay smoke payload must be a mapping")

    assert_explorer_memory_replay_smoke(payload)

    print("✅ explorer memory replay smoke contract OK")


if __name__ == "__main__":
    main()