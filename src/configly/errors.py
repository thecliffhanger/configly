"""Custom exceptions for configly."""


class ConfigError(Exception):
    """Base exception for configly."""


class ValidationError(ConfigError):
    """Raised when a field fails validation."""


class ConfigFrozenError(ConfigError):
    """Raised when trying to modify a frozen config."""
