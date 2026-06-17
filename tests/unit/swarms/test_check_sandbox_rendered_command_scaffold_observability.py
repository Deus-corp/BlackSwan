from tests.unit.swarms.test_check_sandbox_command_render_plan_scaffold_observability import (
    _command_render_plan_record,
    _envelope_record,
    _input_plan_record,
    _materialization_record,
    _matrix_record,
    _preflight_record,
    _preparation_record,
    _valid_scaffold_record,
    _workspace_plan_record,
)
from src.testing.build_real_execution_sandbox_rendered_command_scaffold import (
    build_real_execution_sandbox_rendered_command_scaffold_record,
)
from src.testing.check_sandbox_rendered_command_scaffold_observability import (
    _exit_code_for_result,
    _format_result,
    check_sandbox_rendered_command_scaffold_observability_from_records,
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


def test_check_sandbox_rendered_command_scaffold_observability_passes_for_fail_closed_scaffold() -> None:
    result = check_sandbox_rendered_command_scaffold_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(),
            _envelope_record(),
            _materialization_record(),
            _workspace_plan_record(),
            _preparation_record(),
            _input_plan_record(),
            _command_render_plan_record(),
            _rendered_command_scaffold_record(),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "passed"
    assert result["failed_checks"] == []
    assert result["sandbox_rendered_command_scaffold_observed"] is True
    assert result["sandbox_rendered_command_scaffold_records"] == 1
    assert result["sandbox_rendered_command_scaffold_linkage_complete"] is True
    assert result["sandbox_rendered_command_scaffold_orphans"] == 0
    assert result["sandbox_rendered_command_scaffold_blocked"] == 1
    assert result["sandbox_rendered_command_scaffold_fail_closed"] == 1
    assert result["sandbox_rendered_command_scaffold_deny_by_default"] == 1
    assert result["sandbox_rendered_command_scaffold_generation_enabled"] == 0
    assert result["sandbox_rendered_command_scaffold_materialized"] == 0
    assert result["sandbox_rendered_command_scaffold_executable"] == 0
    assert result["sandbox_rendered_command_scaffold_validated"] == 0
    assert (
        result["sandbox_rendered_command_scaffold_command_plan_generation_enabled"]
        == 0
    )
    assert result["sandbox_rendered_command_scaffold_command_plan_materialized"] == 0
    assert result["sandbox_rendered_command_scaffold_command_plan_executable"] == 0
    assert result["sandbox_rendered_command_scaffold_command_rendering_enabled"] == 0
    assert result["sandbox_rendered_command_scaffold_command_rendered"] == 0
    assert result["sandbox_rendered_command_scaffold_sandbox_execution_enabled"] == 0
    assert result["sandbox_rendered_command_scaffold_execution_performed"] == 0
    assert result["sandbox_rendered_command_scaffold_subprocess_invoked"] == 0
    assert result["sandbox_rendered_command_scaffold_real_execution_enabled"] == 0
    assert (
        result["brief_key_metrics"][
            "security_real_execution_sandbox_rendered_command_scaffolds"
        ]
        == 1
    )
    assert "Sandbox rendered command scaffold observed" in result["brief_summary"]


def test_check_sandbox_rendered_command_scaffold_observability_fails_when_generation_enabled() -> None:
    result = check_sandbox_rendered_command_scaffold_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(),
            _envelope_record(),
            _materialization_record(),
            _workspace_plan_record(),
            _preparation_record(),
            _input_plan_record(),
            _command_render_plan_record(),
            _rendered_command_scaffold_record(
                sandbox_rendered_command_generation_enabled=True,
            ),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "failed"
    assert (
        "sandbox_rendered_command_scaffold_does_not_generate_rendered_command"
        in result["failed_checks"]
    )


def test_check_sandbox_rendered_command_scaffold_observability_fails_when_materialized() -> None:
    result = check_sandbox_rendered_command_scaffold_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(),
            _envelope_record(),
            _materialization_record(),
            _workspace_plan_record(),
            _preparation_record(),
            _input_plan_record(),
            _command_render_plan_record(),
            _rendered_command_scaffold_record(
                sandbox_rendered_command_materialized=True,
            ),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "failed"
    assert (
        "sandbox_rendered_command_scaffold_does_not_materialize_rendered_command"
        in result["failed_checks"]
    )


def test_check_sandbox_rendered_command_scaffold_observability_fails_when_validated() -> None:
    result = check_sandbox_rendered_command_scaffold_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(),
            _envelope_record(),
            _materialization_record(),
            _workspace_plan_record(),
            _preparation_record(),
            _input_plan_record(),
            _command_render_plan_record(),
            _rendered_command_scaffold_record(
                sandbox_rendered_command_validated=True,
            ),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "failed"
    assert (
        "sandbox_rendered_command_scaffold_does_not_validate_rendered_command"
        in result["failed_checks"]
    )


def test_check_sandbox_rendered_command_scaffold_observability_fails_when_command_rendered() -> None:
    result = check_sandbox_rendered_command_scaffold_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(),
            _envelope_record(),
            _materialization_record(),
            _workspace_plan_record(),
            _preparation_record(),
            _input_plan_record(),
            _command_render_plan_record(),
            _rendered_command_scaffold_record(
                sandbox_command_rendered=True,
            ),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "failed"
    assert "sandbox_rendered_command_scaffold_does_not_render_command" in result[
        "failed_checks"
    ]


def test_check_sandbox_rendered_command_scaffold_observability_fails_when_executes() -> None:
    result = check_sandbox_rendered_command_scaffold_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(),
            _envelope_record(),
            _materialization_record(),
            _workspace_plan_record(),
            _preparation_record(),
            _input_plan_record(),
            _command_render_plan_record(),
            _rendered_command_scaffold_record(
                sandbox_execution_enabled=True,
                execution_performed=True,
                subprocess_invoked=True,
            ),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "failed"
    assert (
        "sandbox_rendered_command_scaffold_does_not_enable_sandbox_execution"
        in result["failed_checks"]
    )
    assert "sandbox_rendered_command_scaffold_does_not_execute" in result[
        "failed_checks"
    ]
    assert "sandbox_rendered_command_scaffold_does_not_invoke_subprocess" in result[
        "failed_checks"
    ]


def test_check_sandbox_rendered_command_scaffold_observability_format_and_exit_code() -> None:
    result = check_sandbox_rendered_command_scaffold_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(),
            _envelope_record(),
            _materialization_record(),
            _workspace_plan_record(),
            _preparation_record(),
            _input_plan_record(),
            _command_render_plan_record(),
            _rendered_command_scaffold_record(),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    text = _format_result(result)

    assert _exit_code_for_result(result) == 0
    assert "Sandbox rendered command scaffold observability: status=passed" in text
    assert "observed=true" in text
    assert "generation_enabled=0" in text
    assert "materialized=0" in text
    assert "executable=0" in text
    assert "validated=0" in text
    assert "command_plan_generation_enabled=0" in text
    assert "command_rendering_enabled=0" in text
    assert "command_rendered=0" in text
    assert "sandbox_execution_enabled=0" in text
    assert "real_execution_enabled=0" in text