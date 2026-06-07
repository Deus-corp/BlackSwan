"""Allowlist parser for future controlled retry command execution.

This module only parses and validates rendered retry command strings. It does
not execute commands.
"""

from __future__ import annotations

import shlex
from typing import Any


ALLOWED_MODULE = "src.testing.run_replay_evidence_check"
ALLOWED_TIMEOUT_PROFILES = {"standard", "patient"}
FORBIDDEN_TOKENS = {
    ";",
    "&&",
    "||",
    "|",
    "`",
    "$(",
    ">",
    ">>",
    "<",
    "\n",
    "\r",
}


def parse_controlled_retry_command(command: str) -> dict[str, Any]:
    """Parse and validate a controlled retry command without executing it."""
    clean_command = str(command or "").strip()
    reasons: list[str] = []

    if not clean_command:
        return _result(
            valid=False,
            allowlist_matched=False,
            reasons=["missing_command"],
            argv=[],
            module="",
            args={},
        )

    forbidden = _find_forbidden_tokens(clean_command)
    if forbidden:
        reasons.extend(f"forbidden_token:{token}" for token in forbidden)

    try:
        argv = shlex.split(clean_command)
    except ValueError:
        return _result(
            valid=False,
            allowlist_matched=False,
            reasons=["invalid_shell_quoting"],
            argv=[],
            module="",
            args={},
        )

    if len(argv) < 3:
        reasons.append("command_too_short")

    executable = argv[0] if argv else ""
    module = ""

    if executable not in {"python", "python3"}:
        reasons.append("invalid_executable")

    if len(argv) >= 2 and argv[1] != "-m":
        reasons.append("missing_python_module_flag")

    if len(argv) >= 3:
        module = argv[2]
    else:
        reasons.append("missing_module")

    if module and module != ALLOWED_MODULE:
        reasons.append("module_not_allowlisted")

    parsed_args, arg_reasons = _parse_flags(argv[3:] if len(argv) > 3 else [])
    reasons.extend(arg_reasons)

    if not parsed_args.get("scenario_id"):
        reasons.append("missing_scenario_id")
    if not parsed_args.get("directive_id"):
        reasons.append("missing_directive_id")

    timeout_profile = parsed_args.get("timeout_profile")
    if not timeout_profile:
        reasons.append("missing_timeout_profile")
    elif timeout_profile not in ALLOWED_TIMEOUT_PROFILES:
        reasons.append("invalid_timeout_profile")

    db_path = parsed_args.get("db_path")
    if db_path and _is_unsafe_db_path(db_path):
        reasons.append("unsafe_db_path")

    allowlist_matched = (
        executable in {"python", "python3"}
        and len(argv) >= 3
        and argv[1] == "-m"
        and module == ALLOWED_MODULE
        and not forbidden
    )

    return _result(
        valid=not reasons,
        allowlist_matched=allowlist_matched and not reasons,
        reasons=reasons,
        argv=argv,
        module=module,
        args=parsed_args,
    )


def _parse_flags(argv: list[str]) -> tuple[dict[str, str], list[str]]:
    args: dict[str, str] = {}
    reasons: list[str] = []
    index = 0

    allowed_flags = {
        "--scenario-id": "scenario_id",
        "--directive-id": "directive_id",
        "--timeout-profile": "timeout_profile",
        "--db-path": "db_path",
        "--action": "action",
    }

    while index < len(argv):
        token = argv[index]

        if not token.startswith("--"):
            reasons.append(f"unexpected_positional:{token}")
            index += 1
            continue

        if token not in allowed_flags:
            reasons.append(f"unknown_flag:{token}")
            index += 1
            continue

        if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
            reasons.append(f"missing_value:{token}")
            index += 1
            continue

        args[allowed_flags[token]] = argv[index + 1]
        index += 2

    return args, reasons


def _find_forbidden_tokens(command: str) -> list[str]:
    return sorted(token for token in FORBIDDEN_TOKENS if token in command)


def _is_unsafe_db_path(path: str) -> bool:
    clean_path = str(path or "").strip()
    if not clean_path:
        return False

    if "\x00" in clean_path:
        return True

    if clean_path.startswith(("/", "~")):
        return True

    parts = clean_path.replace("\\", "/").split("/")
    return ".." in parts


def _result(
    *,
    valid: bool,
    allowlist_matched: bool,
    reasons: list[str],
    argv: list[str],
    module: str,
    args: dict[str, str],
) -> dict[str, Any]:
    return {
        "type": "controlled_retry_command_parse_result",
        "valid": valid,
        "allowlist_matched": allowlist_matched,
        "reasons": reasons,
        "argv": argv,
        "module": module,
        "args": args,
        "execution_performed": False,
    }