from tests.unit.swarms.test_check_sandbox_rendered_command_scaffold_observability import (
    _command_render_plan_record,
    _envelope_record,
    _input_plan_record,
    _materialization_record,
    _matrix_record,
    _preflight_record,
    _preparation_record,
    _rendered_command_scaffold_record,
    _valid_scaffold_record,
    _workspace_plan_record,
)
from src.testing.build_real_execution_sandbox_rendered_command_validation_scaffold import (
    build_real_execution_sandbox_rendered_command_validation_scaffold_record,
)
from src.testing.check_sandbox_rendered_command_validation_scaffold_observability import (
    _exit_code_for_result,
    _format_result,
    check_sandbox_rendered_command_validation_scaffold_observability_from_records,
)


def _validation_scaffold_record(**overrides):
    item = build_real_execution_sandbox_rendered_command_validation_scaffold_record(
        _rendered_command_scaffold_record()
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


def test_check_sandbox_rendered_command_validation_scaffold_observability_passes_for_fail_closed_scaffold() -> None:
    result = (
        check_sandbox_rendered_command_validation_scaffold_observability_from_records(
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
                _validation_scaffold_record(),
            ],
            proposal_id="proposal-1",
            rendered_command_id="rendered-1",
        )
    )

    assert result["status"] == "passed"
    assert result["failed_checks"] == []
    assert result["sandbox_rendered_command_validation_scaffold_observed"] is True
    assert result["sandbox_rendered_command_validation_scaffold_records"] == 1
    assert (
        result["sandbox_rendered_command_validation_scaffold_linkage_complete"]
        is True
    )
    assert result["sandbox_rendered_command_validation_scaffold_orphans"] == 0
    assert result["sandbox_rendered_command_validation_scaffold_blocked"] == 1
    assert result["sandbox_rendered_command_validation_scaffold_fail_closed"] == 1
    assert result["sandbox_rendered_command_validation_scaffold_deny_by_default"] == 1
    assert result["sandbox_rendered_command_validation_scaffold_validation_enabled"] == 0
    assert result["sandbox_rendered_command_validation_scaffold_validation_performed"] == 0
    assert result["sandbox_rendered_command_validation_scaffold_validation_passed"] == 0
    assert result["sandbox_rendered_command_validation_scaffold_validation_failed"] == 0
    assert result["sandbox_rendered_command_validation_scaffold_generation_enabled"] == 0
    assert result["sandbox_rendered_command_validation_scaffold_materialized"] == 0
    assert result["sandbox_rendered_command_validation_scaffold_executable"] == 0
    assert result["sandbox_rendered_command_validation_scaffold_validated"] == 0
    assert (
        result["sandbox_rendered_command_validation_scaffold_sandbox_execution_enabled"]
        == 0
    )
    assert result["sandbox_rendered_command_validation_scaffold_execution_performed"] == 0
    assert result["sandbox_rendered_command_validation_scaffold_subprocess_invoked"] == 0
    assert result["sandbox_rendered_command_validation_scaffold_real_execution_enabled"] == 0
    assert (
        result["brief_key_metrics"][
            "security_real_execution_sandbox_rendered_command_validation_scaffolds"
        ]
        == 1
    )
    assert (
        "Sandbox rendered command validation scaffold observed"
        in result["brief_summary"]
    )


def test_check_sandbox_rendered_command_validation_scaffold_observability_fails_when_validation_enabled() -> None:
    result = (
        check_sandbox_rendered_command_validation_scaffold_observability_from_records(
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
                _validation_scaffold_record(
                    sandbox_rendered_command_validation_enabled=True,
                ),
            ],
            proposal_id="proposal-1",
            rendered_command_id="rendered-1",
        )
    )

    assert result["status"] == "failed"
    assert (
        "sandbox_rendered_command_validation_scaffold_does_not_enable_validation"
        in result["failed_checks"]
    )


def test_check_sandbox_rendered_command_validation_scaffold_observability_fails_when_validation_performed() -> None:
    result = (
        check_sandbox_rendered_command_validation_scaffold_observability_from_records(
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
                _validation_scaffold_record(
                    sandbox_rendered_command_validation_performed=True,
                ),
            ],
            proposal_id="proposal-1",
            rendered_command_id="rendered-1",
        )
    )

    assert result["status"] == "failed"
    assert (
        "sandbox_rendered_command_validation_scaffold_does_not_perform_validation"
        in result["failed_checks"]
    )


def test_check_sandbox_rendered_command_validation_scaffold_observability_fails_when_validation_passed() -> None:
    result = (
        check_sandbox_rendered_command_validation_scaffold_observability_from_records(
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
                _validation_scaffold_record(
                    sandbox_rendered_command_validation_passed=True,
                ),
            ],
            proposal_id="proposal-1",
            rendered_command_id="rendered-1",
        )
    )

    assert result["status"] == "failed"
    assert (
        "sandbox_rendered_command_validation_scaffold_does_not_pass_validation"
        in result["failed_checks"]
    )


def test_check_sandbox_rendered_command_validation_scaffold_observability_fails_when_rendered_command_validated() -> None:
    result = (
        check_sandbox_rendered_command_validation_scaffold_observability_from_records(
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
                _validation_scaffold_record(
                    sandbox_rendered_command_validated=True,
                ),
            ],
            proposal_id="proposal-1",
            rendered_command_id="rendered-1",
        )
    )

    assert result["status"] == "failed"
    assert (
        "sandbox_rendered_command_validation_scaffold_does_not_mark_rendered_command_validated"
        in result["failed_checks"]
    )


def test_check_sandbox_rendered_command_validation_scaffold_observability_fails_when_executes() -> None:
    result = (
        check_sandbox_rendered_command_validation_scaffold_observability_from_records(
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
                _validation_scaffold_record(
                    sandbox_execution_enabled=True,
                    execution_performed=True,
                    subprocess_invoked=True,
                ),
            ],
            proposal_id="proposal-1",
            rendered_command_id="rendered-1",
        )
    )

    assert result["status"] == "failed"
    assert (
        "sandbox_rendered_command_validation_scaffold_does_not_enable_sandbox_execution"
        in result["failed_checks"]
    )
    assert "sandbox_rendered_command_validation_scaffold_does_not_execute" in result[
        "failed_checks"
    ]
    assert (
        "sandbox_rendered_command_validation_scaffold_does_not_invoke_subprocess"
        in result["failed_checks"]
    )


def test_check_sandbox_rendered_command_validation_scaffold_observability_format_and_exit_code() -> None:
    result = (
        check_sandbox_rendered_command_validation_scaffold_observability_from_records(
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
                _validation_scaffold_record(),
            ],
            proposal_id="proposal-1",
            rendered_command_id="rendered-1",
        )
    )

    text = _format_result(result)

    assert _exit_code_for_result(result) == 0
    assert (
        "Sandbox rendered command validation scaffold observability: status=passed"
        in text
    )
    assert "observed=true" in text
    assert "validation_enabled=0" in text
    assert "validation_performed=0" in text
    assert "validation_passed=0" in text
    assert "validation_failed=0" in text
    assert "executable=0" in text
    assert "validated=0" in text
    assert "sandbox_execution_enabled=0" in text
    assert "real_execution_enabled=0" in text