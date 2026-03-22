# PRD — configly v1.0

## What It Is
Zero-boilerplate configuration management. Load from env vars, .env files, YAML, TOML, JSON — with type coercion, validation, defaults, and secrets management. One decorator, done.

## Why It Matters
- `pydantic-settings` is great but heavy (pulls in pydantic)
- `python-dotenv` only loads .env, doesn't validate or coerce
- `dynaconf` is bloated for simple projects
- Nobody owns the "lightweight config" space cleanly
- Config is THE most universal pain point — every project needs it

## Core Features

### 1. Decorator-based config
```python
from configly import config

@config
class Settings:
    DATABASE_URL: str = "sqlite:///db.sqlite"
    DEBUG: bool = False
    PORT: int = 8000
    WORKERS: int = 4
    SECRET_KEY: str  # required, no default
    API_KEYS: list[str] = []

settings = Settings()
```

### 2. Auto env var loading
```python
# Automatically reads:
# - Environment variables
# - .env file (if exists)
# - .env.local (if exists)
# - Config file (.yaml, .toml, .json)

# Env var precedence: env > .env.local > .env > config file > defaults
```

### 3. Type coercion
```python
PORT: int = 8000       # "8080" from env → 8080
DEBUG: bool = False    # "true"/"1"/"yes" → True
WORKERS: int = 4       # "8" → 8
API_KEYS: list[str]    # "key1,key2,key3" → ["key1", "key2", "key3"]
TIMEOUT: float = 30.0  # "60.5" → 60.5
LOG_LEVEL: str = "INFO" # reads directly
```

### 4. Validation
```python
from configly import config, validator

@config
class Settings:
    PORT: int = 8000
    HOST: str = "localhost"
    DATABASE_URL: str

    @validator("PORT")
    def port_range(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError(f"PORT must be 1-65535, got {v}")
        return v

    @validator("DATABASE_URL")
    def db_scheme(cls, v):
        if not v.startswith(("sqlite://", "postgres://", "mysql://")):
            raise ValueError("Invalid database scheme")
        return v
```

### 5. Nested config
```python
@config
class Database:
    HOST: str = "localhost"
    PORT: int = 5432
    NAME: str = "myapp"
    POOL_SIZE: int = 10

@config(prefix="DB")
class Settings:
    DEBUG: bool = False
    database: Database
```

### 6. Config file support
```yaml
# config.yaml
database:
  host: prod-db.example.com
  port: 5432
debug: false
```

```python
@config(config_file="config.yaml")
class Settings:
    database: dict
    debug: bool = False
```

### 7. Secrets management
```python
from configly import config, secret

@config
class Settings:
    DATABASE_URL: str
    API_KEY: str = secret("API_KEY")  # masks in str(), repr()
    WEBHOOK_SECRET: str = secret()

settings = Settings()
print(settings)  # API_KEY=***, WEBHOOK_SECRET=***
print(settings.API_KEY)  # actual value
settings.masked()  # {"API_KEY": "***", "WEBHOOK_SECRET": "***", ...}
```

### 8. Freeze / immutability
```python
settings.freeze()  # all attributes become read-only
settings.PORT = 9000  # raises ConfigFrozenError
```

### 9. Environment switch
```python
settings = Settings(env="production")  # loads .env.production
settings = Settings(env="test")        # loads .env.test
```

### 10. CLI override
```bash
python app.py --config.port=9000 --config.debug=true
```

## API Surface
- `@config` — decorator for config classes
- `@validator(field)` — field validation
- `secret()` / `secret(key)` — masked fields
- `Settings.masked()` — all secrets masked
- `Settings.freeze()` — immutability
- `Settings.to_dict()` — export
- `Settings.from_env()` — manual loading

## Dependencies
- Zero required (stdlib only)
- Optional: `pyyaml` for YAML, `tomli` for TOML (Python <3.11)

## Testing
- 120+ tests
- Type coercion edge cases
- Env precedence ordering
- Nested config
- Validation
- Secret masking
- File loading (YAML, TOML, JSON, .env)
- Freeze/immutability

## Target
- Python 3.10+
- MIT license
