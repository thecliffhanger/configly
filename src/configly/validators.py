"""Validator decorator for configly."""


from __future__ import annotations

import inspect
from typing import Any, Callable


def validator(field_name: str) -> Callable:
    """Decorator to register a field validator.
    
    Usage:
        @validator("PORT")
        def port_range(cls, v):
            if not 1 <= v <= 65535:
                raise ValueError(f"PORT must be 1-65535, got {v}")
            return v
    """
    def decorator(func: Callable) -> Callable:
        func._configly_validator_field = field_name
        func._configly_is_validator = True
        return func

    return decorator


def get_validators(cls: type) -> list[tuple[str, Callable]]:
    """Extract all validators from a class."""
    validators = []
    for name in dir(cls):
        attr = getattr(cls, name, None)
        if attr is not None and getattr(attr, '_configly_is_validator', False):
            field_name = attr._configly_validator_field
            validators.append((field_name, attr))
    return validators


def run_validator(func: Callable, value: Any) -> Any:
    """Run a validator function on a value.
    
    Handles both classmethod-style (cls, value) and plain (value) signatures.
    """
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    if len(params) >= 2:
        # classmethod-style: (cls, value)
        return func(None, value)
    elif len(params) == 1:
        return func(value)
    return func(None, value)
