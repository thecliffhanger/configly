# configly

[![PyPI version](https://badge.fury.io/py/configly.svg)](https://pypi.org/project/configly)
[![Python versions](https://img.shields.io/pypi/pyversions/configly.svg)](https://pypi.org/project/configly)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Zero-boilerplate configuration management with env vars, validation, and secrets.

## Installation

```bash
pip install configly-lib
```

## Quick Start

```python
from configly import config, validator, secret

@config
class Settings:
    DATABASE_URL: str = "sqlite:///db.sqlite"
    DEBUG: bool = False
    PORT: int = 8000
    API_KEY: str = secret("sk-default")

    @validator("PORT")
    def port_range(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError(f"PORT must be 1-65535, got {v}")
        return v

settings = Settings()
print(settings.PORT)    # 8000
print(settings.API_KEY) # sk-default
print(settings.masked()) # {"DATABASE_URL": "...", "API_KEY": "***", ...}
```

## Features

- **Type coercion**: `str` → `int`, `float`, `bool`, `list`, `dict`
- **Env var loading**: automatic `os.environ` integration
- **`.env` file support**: `.env`, `.env.local`, `.env.{environment}`
- **Config files**: YAML, TOML, JSON
- **Validation**: `@validator("FIELD")` decorator
- **Secrets**: `secret()` masks values in `str()`/`repr()`
- **Freeze**: `settings.freeze()` makes config immutable
- **Priority**: CLI args > env vars > `.env.local` > `.env` > config file > defaults
- **Prefix**: `@config(prefix="APP_")` filters env vars
- **Zero dependencies**: pure stdlib (optional: pyyaml, tomli)

## License

MIT

---

Part of the [thecliffhanger](https://github.com/thecliffhanger) open source suite.
