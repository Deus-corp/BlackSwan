"""Centralized validation utilities for consistent input verification."""
from typing import Any, Dict, List, Type, TypeVar

_T = TypeVar("_T")

def validate_not_empty(value: Any, field_name: str) -> None:
    """
    Validate that the provided value is not empty.

    Args:
        value: The value to check for emptiness.
        field_name: The descriptive name of the field for error reporting.

    Raises:
        ValueError: If the value is considered empty (None, empty string, collection, etc.).
    """
    if not value:
        raise ValueError(f"{field_name} cannot be empty")

def validate_type(value: Any, expected_type: Type[_T], field_name: str) -> None:
    """
    Validate that the provided value matches the expected type.

    Args:
        value: The value to inspect.
        expected_type: The expected class or type.
        field_name: The descriptive name of the field for error reporting.

    Raises:
        TypeError: If the value is not an instance of the expected type.
    """
    if not isinstance(value, expected_type):
        raise TypeError(f"{field_name} must be of type {expected_type.__name__}")

def validate_dict_keys(data: Dict[str, Any], required_keys: List[str]) -> None:
    """
    Validate that a dictionary contains all required keys.

    Args:
        data: The dictionary to inspect.
        required_keys: A list of keys that must be present in the data.

    Raises:
        KeyError: If one or more required keys are missing from the data.
    """
    for key in required_keys:
        if key not in data:
            raise KeyError(f"Missing required key: {key}")