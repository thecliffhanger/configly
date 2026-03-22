"""Type coercion for configly — converts raw string values to typed Python values."""


from __future__ import annotations

import re
from typing import Any, get_args, get_origin


_BOOL_TRUE = frozenset({"true", "1", "yes", "on", "t", "y"})
_BOOL_FALSE = frozenset({"false", "0", "no", "off", "f", "n"})


def coerce_bool(value: str) -> bool:
    """Coerce a string to bool."""
    v = value.strip().lower()
    if v in _BOOL_TRUE:
        return True
    if v in _BOOL_FALSE:
        return False
    raise ValueError(f"Cannot coerce {value!r} to bool")


def coerce_int(value: str) -> int:
    """Coerce a string to int."""
    v = value.strip()
    # Handle decimal strings by truncating
    if "." in v:
        return int(float(v))
    return int(v, 0)  # supports 0x, 0o, 0b prefixes


def coerce_float(value: str) -> float:
    """Coerce a string to float."""
    return float(value.strip())


def coerce_str(value: str) -> str:
    """Coerce a string to str (strip whitespace, handle quotes)."""
    v = value.strip()
    # Remove surrounding quotes
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        v = v[1:-1]
    return v


def coerce_list(value: str, inner_type: type | None = None) -> list:
    """Coerce a comma-separated string to a list, optionally with inner type coercion."""
    v = value.strip()
    # Handle JSON-like bracket notation
    if v.startswith("[") and v.endswith("]"):
        import json
        parsed = json.loads(v)
        if isinstance(parsed, list):
            if inner_type:
                return [_coerce_single(str(item), inner_type) for item in parsed]
            return parsed
    # Comma-split
    if not v:
        return []
    items = [s.strip() for s in v.split(",") if s.strip()]
    if inner_type:
        items = [_coerce_single(item, inner_type) for item in items]
    return items


def _coerce_single(value: str, target_type: type) -> Any:
    """Coerce a single value to the given type."""
    if target_type is bool:
        return coerce_bool(value)
    if target_type is int:
        return coerce_int(value)
    if target_type is float:
        return coerce_float(value)
    if target_type is str:
        return coerce_str(value)
    return value  # fallback


def coerce(value: Any, target_type: Any) -> Any:
    """Coerce a value to the given type.
    
    Handles: str, int, float, bool, list, list[T], dict, nested @config classes.
    """
    if value is None:
        return None

    origin = get_origin(target_type)
    args = get_args(target_type)

    # Plain types
    if target_type is str:
        return coerce_str(str(value))
    if target_type is int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        return coerce_int(str(value))
    if target_type is float:
        if isinstance(value, (int, float)):
            return float(value)
        return coerce_float(str(value))
    if target_type is bool:
        if isinstance(value, bool):
            return value
        return coerce_bool(str(value))

    # list or list[T] (bare list has no origin)
    if target_type is list or origin is list:
        if isinstance(value, list):
            if args:
                return [_coerce_single(str(item), args[0]) if not isinstance(item, args[0]) else item for item in value]
            return value
        return coerce_list(str(value), args[0] if args else None)

    # dict
    if origin is dict or target_type is dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            import json
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise ValueError(f"Cannot coerce {value!r} to dict")
        raise ValueError(f"Cannot coerce {type(value).__name__} to dict")

    # Optional / Union types
    if origin is type(None) or (hasattr(origin, '__name__') and 'Union' in str(origin)):
        # It's Optional[X] — try to coerce to the non-None type
        non_none_args = [a for a in args if a is not type(None)]
        if non_none_args:
            return coerce(value, non_none_args[0])
        return value

    # bytes
    if target_type is bytes:
        if isinstance(value, bytes):
            return value
        return str(value).encode()

    # Nested config class (check for _configly_marker)
    if isinstance(target_type, type) and hasattr(target_type, '_configly_marker'):
        if isinstance(value, target_type):
            return value
        # Could be a dict from config file
        if isinstance(value, dict):
            instance = target_type.__new__(target_type)
            for k, v in value.items():
                setattr(instance, k, v)
            return instance
        raise ValueError(f"Cannot coerce {type(value).__name__} to {target_type.__name__}")

    return value
