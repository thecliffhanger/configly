"""Configuration loaders — env vars, .env files, YAML, TOML, JSON."""


from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


def load_env_vars(prefix: str = "", strip_prefix: bool = True) -> dict[str, str]:
    """Load configuration from environment variables."""
    result = {}
    for key, value in os.environ.items():
        if prefix:
            if not key.startswith(prefix):
                continue
            clean_key = key[len(prefix):] if strip_prefix else key
        else:
            clean_key = key
        # Convert MY_FIELD to my_field
        clean_key = clean_key.lower()
        result[clean_key] = value
    return result


def parse_dotenv(path: str | Path) -> dict[str, str]:
    """Parse a .env file. Supports comments, multiline values with quotes."""
    path = Path(path)
    if not path.exists():
        return {}

    result = {}
    current_key = None
    current_value = []
    in_multiline = False

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")

            if in_multiline:
                # Check for closing quote
                stripped = line.rstrip()
                if stripped and stripped[-1] == quote_char:
                    current_value.append(stripped[:-1])
                    result[current_key] = "\n".join(current_value)
                    in_multiline = False
                    current_key = None
                    current_value = []
                else:
                    current_value.append(line)
                continue

            # Skip empty lines and comments
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Match KEY=VALUE
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
            if match:
                key = match.group(1)
                value = match.group(2).strip()

                # Skip export prefix
                if key.startswith("export "):
                    key = key[7:]

                # Handle multiline values (opening quote with no closing)
                if value and value[0] in ('"', "'") and (len(value) < 2 or value[-1] != value[0]):
                    # Multiline
                    quote_char = value[0]
                    current_key = key
                    current_value = [value[1:]]
                    in_multiline = True
                    continue

                # Remove surrounding quotes from single-line values
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]

                result[key] = value

    return result


quote_char: str = '"'  # module-level for multiline parsing


def _fix_quote_char():
    global quote_char
    quote_char = '"'


# We need quote_char accessible in parse_dotenv closure — it's used via nonlocal-like pattern
# Actually let me refactor parse_dotenv to use a local variable properly.

def parse_dotenv_v2(path: str | Path) -> dict[str, str]:
    """Parse a .env file. Supports comments, multiline values with quotes."""
    path = Path(path)
    if not path.exists():
        return {}

    result = {}
    current_key = None
    current_value = []
    in_multiline = False
    _quote_char = '"'

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")

            if in_multiline:
                stripped = line.rstrip()
                if stripped and stripped[-1] == _quote_char:
                    current_value.append(stripped[:-1])
                    result[current_key] = "\n".join(current_value)
                    in_multiline = False
                    current_key = None
                    current_value = []
                else:
                    current_value.append(line)
                continue

            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            match = re.match(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
            if match:
                key = match.group(1)
                value = match.group(2).strip()

                if value and value[0] in ('"', "'") and (len(value) < 2 or value[-1] != value[0]):
                    _quote_char = value[0]
                    current_key = key
                    current_value = [value[1:]]
                    in_multiline = True
                    continue

                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]

                result[key] = value

    return result


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML config file. Graceful fallback if pyyaml not installed."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        raise ImportError("PyYAML is required for YAML config files. Install with: pip install pyyaml")


def load_json(path: str | Path) -> dict[str, Any]:
    """Load a JSON config file."""
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_toml(path: str | Path) -> dict[str, Any]:
    """Load a TOML config file. Uses tomllib (3.11+) or tomli fallback."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            raise ImportError("tomli is required for TOML config files on Python <3.11. Install with: pip install tomli")
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_config_file(path: str | Path) -> dict[str, Any]:
    """Load a config file based on its extension."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext in (".yaml", ".yml"):
        return load_yaml(path)
    if ext == ".json":
        return load_json(path)
    if ext == ".toml":
        return load_toml(path)
    raise ValueError(f"Unsupported config file format: {ext}")


def flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = "_") -> dict[str, Any]:
    """Flatten a nested dict, joining keys with sep."""
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key, sep))
        else:
            items[new_key] = v
    return items


def parse_cli_args(argv: list[str] | None = None, prefix: str = "--config.") -> dict[str, str]:
    """Parse CLI arguments like --config.KEY=VALUE."""
    if argv is None:
        import sys
        argv = sys.argv[1:]
    result = {}
    for arg in argv:
        if arg.startswith(prefix) and "=" in arg:
            key_val = arg[len(prefix):]
            key, _, value = key_val.partition("=")
            result[key.lower()] = value
    return result


def load_all(config_file: str | Path | None = None, prefix: str = "",
             env: str | None = None, argv: list[str] | None = None) -> dict[str, Any]:
    """Load configuration from all sources with correct priority.
    
    Priority (lowest to highest):
    1. defaults (handled by caller)
    2. config file
    3. .env
    4. .env.local
    5. .env.{env}
    6. environment variables
    7. CLI arguments
    """
    merged = {}

    # 2. Config file
    if config_file:
        file_data = load_config_file(config_file)
        merged.update(flatten_dict(file_data))

    # 3. .env
    env_data = parse_dotenv_v2(".env")
    for k, v in env_data.items():
        merged[k.lower()] = v

    # 4. .env.local
    env_local = parse_dotenv_v2(".env.local")
    for k, v in env_local.items():
        merged[k.lower()] = v

    # 5. .env.{env}
    if env:
        env_file = parse_dotenv_v2(f".env.{env}")
        for k, v in env_file.items():
            merged[k.lower()] = v

    # 6. Environment variables
    env_vars = load_env_vars(prefix=prefix)
    merged.update(env_vars)

    # 7. CLI arguments
    cli = parse_cli_args(argv)
    merged.update(cli)

    return merged
