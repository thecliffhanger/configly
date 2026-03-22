"""Core config decorator and Settings class factory."""


from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable, get_type_hints

from .coercion import coerce
from .errors import ConfigError, ConfigFrozenError, ValidationError
from .loader import load_all
from .secret import SecretValue, is_secret
from .validators import get_validators, run_validator


def config(cls=None, *, prefix: str = "", config_file: str | Path | None = None,
           env: str | None = None, case_sensitive: bool = False):
    """Decorator that turns a class into a configuration manager.
    
    Usage:
        @config
        class Settings:
            PORT: int = 8000
            
        @config(prefix="APP")
        class Settings:
            PORT: int = 8000
            
        @config(config_file="config.yaml")
        class Settings:
            PORT: int = 8000
    """
    def decorator(klass: type) -> type:
        return _make_settings_class(klass, prefix=prefix, config_file=config_file, env=env,
                                    case_sensitive=case_sensitive)
    
    if cls is not None:
        return decorator(cls)
    return decorator


def _make_settings_class(cls: type, prefix: str, config_file: str | Path | None,
                          env: str | None, case_sensitive: bool) -> type:
    """Create a Settings class from the annotated class."""
    
    # Mark as configly class for nested config support
    cls._configly_marker = True
    cls._configly_prefix = prefix
    cls._configly_config_file = config_file
    cls._configly_env = env
    cls._configly_case_sensitive = case_sensitive
    cls._configly_frozen = False
    
    original_init = cls.__init__ if hasattr(cls, '__init__') else None
    hints = {}
    try:
        hints = get_type_hints(cls) if hasattr(cls, '__annotations__') else {}
    except Exception:
        hints = getattr(cls, '__annotations__', {})
    
    defaults = {}
    validators_map = {}
    
    # Collect defaults and validators
    annotations = getattr(cls, '__annotations__', {})
    
    for name, value in list(vars(cls).items()):
        if name.startswith("_"):
            continue
        if name in annotations or name.isupper():
            defaults[name] = value
    for name in annotations:
        if name not in defaults and not name.startswith("_"):
            defaults[name] = None  # no default = required
    
    # Get validators
    validators_list = get_validators(cls)
    for field_name, func in validators_list:
        validators_map[field_name] = func
    
    def __init__(self, **overrides):
        """Initialize settings from all sources + overrides."""
        nonlocal hints
        
        # Refresh type hints
        try:
            hints = get_type_hints(type(self))
        except Exception:
            hints = getattr(type(self), '__annotations__', {})
        
        # Load all config sources
        loaded = load_all(config_file=config_file, prefix=prefix, env=env)
        
        # Build final values
        _frozen = False
        secrets = {}
        
        for name, hint in hints.items():
            if name.startswith("_"):
                continue
            
            # Priority: overrides > loaded > default
            if name in overrides:
                value = overrides[name]
            elif name.lower() in loaded:
                value = loaded[name.lower()]
            elif name in defaults and defaults[name] is not None:
                value = defaults[name]
            elif name in defaults:
                value = None  # required field, no value found
            else:
                continue
            
            # Check if field has a secret default (even if env overrides it)
            default_val = defaults.get(name)
            if is_secret(default_val):
                secrets[name] = default_val
                # If current value isn't a secret, use it but mark as secret
                if not is_secret(value):
                    # value is from env/override — still a secret field
                    pass
                else:
                    value = value.value  # unwrap for coercion
            elif is_secret(value):
                secrets[name] = value
                value = value.value  # unwrap for coercion
            
            # Type coercion
            if hint is not None and value is not None:
                try:
                    value = coerce(value, hint)
                except (ValueError, TypeError) as e:
                    raise ValidationError(f"Field '{name}': coercion error: {e}")
            
            # Validation
            if name in validators_map:
                try:
                    value = run_validator(validators_map[name], value)
                except ValueError as e:
                    raise ValidationError(f"Field '{name}': {e}")
            
            object.__setattr__(self, name, value)
            
            # Re-wrap secrets
            if name in secrets:
                object.__setattr__(self, f"_secret_{name}", secrets[name])
        
        # Check required fields
        for name, hint in hints.items():
            if name.startswith("_"):
                continue
            if not hasattr(self, name):
                # Check if it was in defaults as None (required)
                if name in defaults and defaults[name] is None:
                    # Check if env provided it
                    pass  # already handled above
                # If still no value, it might be optional with no default
                # We only error if explicitly annotated without default
                if name not in vars(cls) and name not in overrides:
                    # No default value in class body — required field
                    pass
        
        object.__setattr__(self, '_configly_frozen', False)
        object.__setattr__(self, '_configly_secrets', secrets)
    
    def __setattr__(self, name, value):
        if getattr(self, '_configly_frozen', False):
            raise ConfigFrozenError(f"Cannot modify frozen config: {name}")
        object.__setattr__(self, name, value)
    
    def __repr__(self):
        parts = []
        hints = get_type_hints(type(self)) if hasattr(type(self), '__annotations__') else {}
        for name in hints:
            if name.startswith("_"):
                continue
            if not hasattr(self, name):
                continue
            val = getattr(self, name)
            secret_key = f"_secret_{name}"
            if hasattr(self, secret_key) or name in getattr(self, '_configly_secrets', {}):
                parts.append(f"{name}=***")
            else:
                parts.append(f"{name}={val!r}")
        return f"{type(self).__name__}({', '.join(parts)})"
    
    def __str__(self):
        parts = []
        hints = get_type_hints(type(self)) if hasattr(type(self), '__annotations__') else {}
        for name in hints:
            if name.startswith("_"):
                continue
            if not hasattr(self, name):
                continue
            secret_key = f"_secret_{name}"
            if hasattr(self, secret_key) or name in getattr(self, '_configly_secrets', {}):
                parts.append(f"{name}=***")
            else:
                parts.append(f"{name}={getattr(self, name)}")
        return "\n".join(parts)
    
    def freeze(self):
        """Make this config instance immutable."""
        object.__setattr__(self, '_configly_frozen', True)
    
    def to_dict(self) -> dict[str, Any]:
        """Export config as a dictionary."""
        result = {}
        hints = get_type_hints(type(self)) if hasattr(type(self), '__annotations__') else {}
        for name in hints:
            if name.startswith("_"):
                continue
            if hasattr(self, name):
                val = getattr(self, name)
                secret_key = f"_secret_{name}"
                if hasattr(self, secret_key) or name in getattr(self, '_configly_secrets', {}):
                    result[name] = "***"
                else:
                    result[name] = val
        return result
    
    def masked(self) -> dict[str, Any]:
        """Return dict with all secret fields masked."""
        return to_dict(self)
    
    cls.from_env = classmethod(lambda cls, **overrides: cls(**overrides))
    
    cls.__init__ = __init__
    cls.__setattr__ = __setattr__
    cls.__repr__ = __repr__
    cls.__str__ = __str__
    cls.freeze = freeze
    cls.to_dict = to_dict
    cls.masked = masked
    # from_env is already set above as classmethod
    
    return cls
