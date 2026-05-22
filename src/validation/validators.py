"""Centralized validation utilities."""
from typing import Any, Dict, List

def validate_not_empty(value: Any, field_name: str) -> None:
    """Raise ValueError if value is empty."""
    if not value:
        raise ValueError(f'{field_name} cannot be empty')

def validate_type(value: Any, expected_type: type, field_name: str) -> None:
    """Raise TypeError if value is not of expected type."""
    if not isinstance(value, expected_type):
        raise TypeError(f'{field_name} must be of type {expected_type.__name__}')

def validate_dict_keys(data: Dict[str, Any], required_keys: List[str]) -> None:
    """Raise KeyError if a required key is missing."""
    for key in required_keys:
        if key not in data:
            raise KeyError(f'Missing required key: {key}')
