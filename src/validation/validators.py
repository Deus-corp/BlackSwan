"""Centralized validation utilities for consistent input verification."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, TypeVar

_T = TypeVar("_T")


def validate_not_empty(value: Any, field_name: str) -> None:
    """Validate that value is not empty."""
    name = _field_name(field_name)

    if value is None:
        raise ValueError(f"{name} cannot be empty")

    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{name} cannot be empty")

    if isinstance(value, (Mapping, Sequence, set, frozenset)) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) == 0:
            raise ValueError(f"{name} cannot be empty")


def validate_type(value: Any, expected_type: type[_T] | tuple[type[Any], ...], field_name: str) -> None:
    """Validate that value matches the expected type."""
    if not isinstance(value, expected_type):
        raise TypeError(f"{_field_name(field_name)} must be of type {_type_name(expected_type)}")


def validate_dict_keys(data: Mapping[str, Any], required_keys: Iterable[str]) -> None:
    """Validate that a mapping contains all required keys."""
    if not isinstance(data, Mapping):
        raise TypeError("data must be a mapping")

    missing = [key for key in required_keys if key not in data]
    if missing:
        raise KeyError(f"Missing required key(s): {', '.join(map(str, missing))}")


def validate_number(
    value: Any,
    field_name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    inclusive: bool = True,
) -> float:
    """Validate finite numeric value and optional bounds."""
    name = _field_name(field_name)

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be numeric") from exc

    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")

    if minimum is not None:
        if inclusive and number < minimum:
            raise ValueError(f"{name} must be >= {minimum}")
        if not inclusive and number <= minimum:
            raise ValueError(f"{name} must be > {minimum}")

    if maximum is not None:
        if inclusive and number > maximum:
            raise ValueError(f"{name} must be <= {maximum}")
        if not inclusive and number >= maximum:
            raise ValueError(f"{name} must be < {maximum}")

    return number


def validate_int(
    value: Any,
    field_name: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Validate integer value and optional bounds."""
    name = _field_name(field_name)

    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")

    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be an integer") from exc

    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{name} must be <= {maximum}")

    return number


def validate_choice(value: Any, choices: Iterable[Any], field_name: str) -> Any:
    """Validate that value is one of the allowed choices."""
    allowed = tuple(choices)
    if value not in allowed:
        raise ValueError(f"{_field_name(field_name)} must be one of {allowed!r}")
    return value


def validate_optional_type(
    value: Any,
    expected_type: type[_T] | tuple[type[Any], ...],
    field_name: str,
) -> None:
    """Validate type only when value is not None."""
    if value is not None:
        validate_type(value, expected_type, field_name)


def _field_name(field_name: str) -> str:
    name = str(field_name or "").strip()
    return name or "value"


def _type_name(expected_type: type[Any] | tuple[type[Any], ...]) -> str:
    if isinstance(expected_type, tuple):
        return " or ".join(item.__name__ for item in expected_type)
    return expected_type.__name__