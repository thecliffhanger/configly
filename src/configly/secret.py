"""Secret field helper — masks values in str() and repr()."""


from __future__ import annotations

from typing import Any


class SecretValue:
    """Wraps a value so str() and repr() show '***'."""
    
    def __init__(self, value: Any = None, key: str | None = None):
        self._value = value
        self._key = key
    
    @property
    def value(self) -> Any:
        """Get the actual (unmasked) value."""
        return self._value
    
    def __str__(self) -> str:
        return "***"
    
    def __repr__(self) -> str:
        return "***"
    
    def __bool__(self) -> bool:
        return bool(self._value)
    
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SecretValue):
            return self._value == other._value
        return self._value == other
    
    def __hash__(self) -> int:
        return hash(self._value)
    
    def __len__(self) -> int:
        return len(self._value) if hasattr(self._value, '__len__') else 0
    
    def __iter__(self):
        return iter(self._value)


def secret(value: Any = None, key: str | None = None) -> SecretValue:
    """Create a masked secret value.
    
    Usage:
        API_KEY: str = secret("sk-12345")
        API_KEY: str = secret()  # no default
    """
    return SecretValue(value=value, key=key)


def is_secret(value: Any) -> bool:
    """Check if a value is a SecretValue."""
    return isinstance(value, SecretValue)
