"""Configly — Zero-boilerplate configuration management."""


from .config import config
from .validators import validator
from .secret import secret
from .errors import ConfigError, ValidationError, ConfigFrozenError

__all__ = ["config", "validator", "secret", "ConfigError", "ValidationError", "ConfigFrozenError"]
__version__ = "0.1.0"
