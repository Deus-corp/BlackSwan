import pytest

from tests.unit.swarms.test_build_real_execution_sandbox_rendered_command_scaffold import (
    _command_render_plan_record,
)
from src.testing.build_real_execution_sandbox_rendered_command_scaffold import (
    build_real_execution_sandbox_rendered_command_scaffold_record,
)
from src.testing.build_real_execution_sandbox_rendered_command_validation_scaffold import (
    SANDBOX_RENDERED_COMMAND_VALIDATION_SCAFFOLD_SCHEMA_VERSION,
    SANDBOX_RENDERED_COMMAND_VALIDATION_SCAFFOLD_TYPE,
    build_real_execution_sandbox_rendered_command_validation_scaffold_record,
)


def _rendered_command_scaffold_record(**overrides):
    item = build_real_execution_sandbox_rendered_command_scaffold_record(
        _command_render_plan_record()
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


def test_build_sandbox_rendered_command_validation_scaffold_record_is_fail_closed() -> None:
    record = build_real_execution_sandbox_rendered_command_validation_scaffold_record(
        _rendered_command_scaffold_record()
    )

    assert record["type"] == SANDBOX_RENDERED_COMMAND_VALIDATION_SCAFFOLD_TYPE
    assert (
        record["schema_version"]
        == SANDBOX_RENDERED_COMMAND_VALIDATION_SCAFFOLD_SCHEMA_VERSION
    )
    assert record["sandbox_rendered_command_validation_scaffold_status"] == "blocked"
    assert record["sandbox_rendered_command_validation_scaffold_kind"] == (
        "fail_closed_sandbox_rendered_command_validation_scaffold"
    )
    assert record["sandbox_rendered_command_validation_scaffold_exists"] is True
    assert record["sandbox_rendered_command_validation_scaffold_fail_closed"] is True
    assert record["sandbox_rendered_command_validation_scaffold_deny_by_default"] is True
    assert (
        record[
            "sandbox_rendered_command_validation_requires_rendered_command_scaffold"
        ]
        is True
    )
    assert record["sandbox_rendered_command_validation_requires_command_render_plan"] is True
    assert record["sandbox_request_allowed_input_paths"] == []
    assert record["sandbox_request_allowed_output_paths"] == []
    assert record["sandbox_rendered_command_validation_allowed"] is False
    assert record["sandbox_rendered_command_validation_enabled"] is False
    assert record["sandbox_rendered_command_validation_performed"] is False
    assert record["sandbox_rendered_command_validation_passed"] is False
    assert record["sandbox_rendered_command_validation_failed"] is False
    assert record["sandbox_rendered_command_generation_enabled"] is False
    assert record["sandbox_rendered_command_materialized"] is False
    assert record["sandbox_rendered_command_executable"] is False
    assert record["sandbox_rendered_command_validated"] is False
    assert record["sandbox_command_render_plan_generation_enabled"] is False
    assert record["sandbox_command_render_plan_materialized"] is False
    assert record["sandbox_command_render_plan_executable"] is False
    assert record["sandbox_command_rendering_enabled"] is False
    assert record["sandbox_command_rendered"] is False
    assert record["sandbox_input_materialization_plan_generation_enabled"] is False
    assert record["sandbox_input_materialization_plan_materialized"] is False
    assert record["sandbox_input_materialization_plan_executable"] is False
    assert record["sandbox_input_materialization_enabled"] is False
    assert record["sandbox_inputs_materialized"] is False
    assert record["sandbox_workspace_created"] is False
    assert record["sandbox_workspace_cleanup_registered"] is False
    assert record["sandbox_execution_enabled"] is False
    assert record["sandbox_result_generation_enabled"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert record["real_execution_enabled"] is False
    assert record["external_side_effects_performed"] is False
    assert record["production_paths_mutated"] is False
    assert record["production_secrets_accessed"] is False
    assert record["sandbox_rendered_command_strategy"] == (
        "scaffold_only_no_rendered_command"
    )
    assert record["sandbox_rendered_command_validation_strategy"] == (
        "scaffold_only_no_validation"
    )
    assert record["sandbox_network_policy"] == "deny"
    assert record["sandbox_secret_policy"] == "deny"
    assert record["sandbox_filesystem_policy"] == "no_production_writes"
    assert record["recommended_next_action"] == (
        "surface_sandbox_rendered_command_validation_scaffold_observability"
    )
    assert record["reason"] == (
        "sandbox_rendered_command_validation_scaffold_defined_blocked_not_runnable"
    )
    assert (
        record["payload"][
            "real_execution_sandbox_rendered_command_validation_scaffold_id"
        ]
        == record["real_execution_sandbox_rendered_command_validation_scaffold_id"]
    )


def test_build_sandbox_rendered_command_validation_scaffold_record_is_stable() -> None:
    first = build_real_execution_sandbox_rendered_command_validation_scaffold_record(
        _rendered_command_scaffold_record()
    )
    second = build_real_execution_sandbox_rendered_command_validation_scaffold_record(
        _rendered_command_scaffold_record()
    )

    assert first[
        "real_execution_sandbox_rendered_command_validation_scaffold_id"
    ] == second["real_execution_sandbox_rendered_command_validation_scaffold_id"]


def test_build_sandbox_rendered_command_validation_scaffold_rejects_rendered_command_generation_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="sandbox_rendered_command_generation_enabled=false",
    ):
        build_real_execution_sandbox_rendered_command_validation_scaffold_record(
            _rendered_command_scaffold_record(
                sandbox_rendered_command_generation_enabled=True,
            )
        )


def test_build_sandbox_rendered_command_validation_scaffold_rejects_rendered_command_materialized() -> None:
    with pytest.raises(
        ValueError,
        match="sandbox_rendered_command_materialized=false",
    ):
        build_real_execution_sandbox_rendered_command_validation_scaffold_record(
            _rendered_command_scaffold_record(
                sandbox_rendered_command_materialized=True,
            )
        )


def test_build_sandbox_rendered_command_validation_scaffold_rejects_rendered_command_executable() -> None:
    with pytest.raises(
        ValueError,
        match="sandbox_rendered_command_executable=false",
    ):
        build_real_execution_sandbox_rendered_command_validation_scaffold_record(
            _rendered_command_scaffold_record(
                sandbox_rendered_command_executable=True,
            )
        )


def test_build_sandbox_rendered_command_validation_scaffold_rejects_rendered_command_validated() -> None:
    with pytest.raises(
        ValueError,
        match="sandbox_rendered_command_validated=false",
    ):
        build_real_execution_sandbox_rendered_command_validation_scaffold_record(
            _rendered_command_scaffold_record(
                sandbox_rendered_command_validated=True,
            )
        )


def test_build_sandbox_rendered_command_validation_scaffold_rejects_sandbox_execution_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="sandbox_execution_enabled=false",
    ):
        build_real_execution_sandbox_rendered_command_validation_scaffold_record(
            _rendered_command_scaffold_record(sandbox_execution_enabled=True)
        )


def test_build_sandbox_rendered_command_validation_scaffold_rejects_real_execution_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="real_execution_enabled=false",
    ):
        build_real_execution_sandbox_rendered_command_validation_scaffold_record(
            _rendered_command_scaffold_record(real_execution_enabled=True)
        )