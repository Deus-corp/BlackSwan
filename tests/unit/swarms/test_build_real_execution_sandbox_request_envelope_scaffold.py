import pytest

from tests.unit.swarms.test_build_real_execution_sandbox_adapter_request_preflight import (
    _scaffold_record,
)
from src.testing.build_real_execution_sandbox_adapter_request_preflight import (
    build_real_execution_sandbox_adapter_request_preflight_record,
)
from src.testing.build_real_execution_sandbox_request_envelope_scaffold import (
    SANDBOX_REQUEST_ENVELOPE_SCAFFOLD_SCHEMA_VERSION,
    SANDBOX_REQUEST_ENVELOPE_SCAFFOLD_TYPE,
    build_real_execution_sandbox_request_envelope_scaffold_record,
)


def _preflight_record(**overrides):
    item = build_real_execution_sandbox_adapter_request_preflight_record(
        _scaffold_record()
    )
    item.update(overrides)
    item["payload"] = {
        **dict(item.get("payload") or {}),
        **{
            key: value
            for key, value in overrides.items()
            if key != "payload"
        },
    }
    return item


def test_build_sandbox_request_envelope_scaffold_record_is_fail_closed() -> None:
    record = build_real_execution_sandbox_request_envelope_scaffold_record(
        _preflight_record()
    )

    assert record["type"] == SANDBOX_REQUEST_ENVELOPE_SCAFFOLD_TYPE
    assert record["schema_version"] == SANDBOX_REQUEST_ENVELOPE_SCAFFOLD_SCHEMA_VERSION
    assert record["sandbox_request_envelope_scaffold_status"] == "blocked"
    assert (
        record["sandbox_request_envelope_scaffold_kind"]
        == "fail_closed_sandbox_request_envelope_scaffold"
    )
    assert record["sandbox_request_envelope_scaffold_exists"] is True
    assert record["sandbox_request_envelope_scaffold_fail_closed"] is True
    assert record["sandbox_request_envelope_scaffold_deny_by_default"] is True
    assert record["sandbox_request_envelope_requires_preflight"] is True
    assert record["sandbox_request_allowed_input_paths"] == []
    assert record["sandbox_request_allowed_output_paths"] == []
    assert record["sandbox_request_envelope_generation_allowed"] is False
    assert record["sandbox_request_envelope_generation_enabled"] is False
    assert record["sandbox_request_envelope_materialized"] is False
    assert record["sandbox_request_envelope_executable"] is False
    assert record["sandbox_adapter_request_generation_enabled"] is False
    assert record["sandbox_workspace_creation_enabled"] is False
    assert record["sandbox_input_materialization_enabled"] is False
    assert record["sandbox_command_rendering_enabled"] is False
    assert record["sandbox_execution_enabled"] is False
    assert record["sandbox_result_generation_enabled"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert record["real_execution_enabled"] is False
    assert record["external_side_effects_performed"] is False
    assert record["production_paths_mutated"] is False
    assert record["production_secrets_accessed"] is False
    assert record["sandbox_network_policy"] == "deny"
    assert record["sandbox_secret_policy"] == "deny"
    assert record["sandbox_filesystem_policy"] == "no_production_writes"
    assert (
        record["recommended_next_action"]
        == "surface_sandbox_request_envelope_scaffold_observability"
    )
    assert (
        record["reason"]
        == "sandbox_request_envelope_scaffold_defined_blocked_not_runnable"
    )
    assert record["payload"]["real_execution_sandbox_request_envelope_scaffold_id"] == (
        record["real_execution_sandbox_request_envelope_scaffold_id"]
    )


def test_build_sandbox_request_envelope_scaffold_record_is_stable() -> None:
    first = build_real_execution_sandbox_request_envelope_scaffold_record(
        _preflight_record()
    )
    second = build_real_execution_sandbox_request_envelope_scaffold_record(
        _preflight_record()
    )

    assert first["real_execution_sandbox_request_envelope_scaffold_id"] == (
        second["real_execution_sandbox_request_envelope_scaffold_id"]
    )


def test_build_sandbox_request_envelope_scaffold_rejects_enabled_request_generation() -> None:
    with pytest.raises(
        ValueError,
        match="sandbox_adapter_request_generation_enabled=false",
    ):
        build_real_execution_sandbox_request_envelope_scaffold_record(
            _preflight_record(sandbox_adapter_request_generation_enabled=True)
        )


def test_build_sandbox_request_envelope_scaffold_rejects_workspace_creation_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="sandbox_workspace_creation_enabled=false",
    ):
        build_real_execution_sandbox_request_envelope_scaffold_record(
            _preflight_record(sandbox_workspace_creation_enabled=True)
        )


def test_build_sandbox_request_envelope_scaffold_rejects_sandbox_execution_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="sandbox_execution_enabled=false",
    ):
        build_real_execution_sandbox_request_envelope_scaffold_record(
            _preflight_record(sandbox_execution_enabled=True)
        )