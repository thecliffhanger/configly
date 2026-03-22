"""Integration tests for configly — full pipeline, real files, environment switching."""


import json
import os
from pathlib import Path

import pytest

from configly import config, secret, validator, ValidationError, ConfigFrozenError


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Clean env vars that might leak between integration tests."""
    for k in list(os.environ.keys()):
        for prefix in ("PORT", "HOST", "DEBUG", "LOG_LEVEL", "SSL", "FEATURES", "API_KEY", "SERVER_PORT", "SERVER_HOST", "DATABASE_URL", "DATA", "NAME"):
            if k == prefix or k.endswith(f"_{prefix}") or k == prefix:
                monkeypatch.delenv(k, raising=False)


# ---------------------------------------------------------------------------
# Full pipeline: .env + YAML + env vars + CLI override
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_priority_order(self, tmp_path, monkeypatch):
        """Verify: default < config file < .env < env var < init override."""
        monkeypatch.chdir(tmp_path)

        cfg = tmp_path / "config.yaml"
        cfg.write_text("port: 3000\nhost: file-host\n")

        env = tmp_path / ".env"
        env.write_text("PORT=4000\nHOST=env-file-host\n")

        monkeypatch.setenv("PORT", "5000")

        @config(config_file=str(cfg), prefix="")
        class Settings:
            PORT: int = 2000
            HOST: str = "default-host"

        s = Settings()
        assert s.PORT == 5000
        assert s.HOST == "env-file-host"

        s2 = Settings(PORT=9000, HOST="override-host")
        assert s2.PORT == 9000
        assert s2.HOST == "override-host"


# ---------------------------------------------------------------------------
# Real .env file from disk
# ---------------------------------------------------------------------------

class TestRealDotenv:
    def test_dotenv_with_various_types(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        env_file = tmp_path / ".env"
        env_file.write_text("PORT=8080\nDEBUG=true\nHOST=localhost\nFEATURES=email,sms,push\nAPI_KEY=\"quoted-key-123\"\n")

        @config
        class Settings:
            PORT: int = 0
            DEBUG: bool = False
            HOST: str = ""
            FEATURES: list = []
            API_KEY: str = ""

        s = Settings()
        assert s.PORT == 8080
        assert s.DEBUG is True
        assert s.HOST == "localhost"
        assert s.API_KEY == "quoted-key-123"


# ---------------------------------------------------------------------------
# Real YAML config file
# ---------------------------------------------------------------------------

class TestRealYaml:
    def test_yaml_nested_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "config.yaml"
        cfg.write_text("server:\n  port: 8080\n  host: 0.0.0.0\ndatabase:\n  url: postgres://localhost/db\ndebug: true\n")

        @config(config_file=str(cfg))
        class Settings:
            SERVER_PORT: int = 0
            SERVER_HOST: str = ""
            DATABASE_URL: str = ""
            DEBUG: bool = False

        s = Settings()
        assert s.SERVER_PORT == 8080
        assert s.SERVER_HOST == "0.0.0.0"
        assert s.DATABASE_URL == "postgres://localhost/db"
        assert s.DEBUG is True


# ---------------------------------------------------------------------------
# Settings.masked() / to_dict() output
# ---------------------------------------------------------------------------

class TestMaskedOutput:
    def test_masked_masks_secrets(self):
        @config
        class Settings:
            PORT: int = 8000
            API_KEY: str = secret("sk-secret")
            PUBLIC_NAME: str = "hello"

        s = Settings()
        masked = s.masked()
        assert masked["PORT"] == 8000
        assert masked["API_KEY"] == "***"
        assert masked["PUBLIC_NAME"] == "hello"

    def test_masked_same_as_to_dict(self):
        @config
        class Settings:
            API_KEY: str = secret("sk-secret")
            PORT: int = 8000

        s = Settings()
        assert s.masked() == s.to_dict()


# ---------------------------------------------------------------------------
# Settings.to_dict() output
# ---------------------------------------------------------------------------

class TestToDictOutput:
    def test_to_dict_export(self):
        @config
        class Settings:
            PORT: int = 8000
            HOST: str = "localhost"
            DEBUG: bool = True

        s = Settings()
        d = s.to_dict()
        assert d == {"PORT": 8000, "HOST": "localhost", "DEBUG": True}

    def test_to_dict_with_overrides(self):
        @config
        class Settings:
            PORT: int = 8000

        s = Settings(PORT=9000)
        d = s.to_dict()
        assert d["PORT"] == 9000


# ---------------------------------------------------------------------------
# Nested dataclass config
# ---------------------------------------------------------------------------

class TestNestedConfig:
    def test_dict_field_from_override(self):
        """Dict fields can be set via init override."""
        @config
        class Settings:
            DATABASE: dict = {}

        s = Settings(DATABASE={"host": "localhost", "port": 5432})
        assert s.DATABASE["host"] == "localhost"
        assert s.DATABASE["port"] == 5432

    def test_dict_field_nested_config_keys_flattened(self, tmp_path, monkeypatch):
        """NOTE: Nested config keys are flattened (database_host), not reconstructable as dict.
        This is a known limitation — dict fields should be set via env or override."""
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"database_host": "localhost", "database_port": 5432}))

        @config(config_file=str(cfg))
        class Settings:
            DATABASE_HOST: str = ""
            DATABASE_PORT: int = 0

        s = Settings()
        assert s.DATABASE_HOST == "localhost"
        assert s.DATABASE_PORT == 5432


# ---------------------------------------------------------------------------
# Environment switching (.env.test vs .env.production)
# ---------------------------------------------------------------------------

class TestEnvironmentSwitching:
    def test_env_test_overrides_base(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        (tmp_path / ".env").write_text("PORT=8000\nDEBUG=true\nLOG_LEVEL=debug\n")
        (tmp_path / ".env.test").write_text("PORT=3000\nDEBUG=false\n")

        @config(env="test")
        class Settings:
            PORT: int = 0
            DEBUG: bool = False
            LOG_LEVEL: str = ""

        s = Settings()
        assert s.PORT == 3000
        assert s.DEBUG is False
        assert s.LOG_LEVEL == "debug"

    def test_env_production(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        (tmp_path / ".env").write_text("PORT=8000\n")
        (tmp_path / ".env.production").write_text("PORT=443\nSSL=true\n")

        @config(env="production")
        class Settings:
            PORT: int = 0
            SSL: bool = False

        s = Settings()
        assert s.PORT == 443
        assert s.SSL is True

    def test_no_env_file_uses_base(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        (tmp_path / ".env").write_text("PORT=8000\n")

        @config(env="staging")
        class Settings:
            PORT: int = 0

        s = Settings()
        assert s.PORT == 8000


# ---------------------------------------------------------------------------
# from_env reload
# ---------------------------------------------------------------------------

class TestFromEnv:
    def test_from_env_reloads(self, monkeypatch):
        @config
        class Settings:
            PORT: int = 8000

        s1 = Settings()
        assert s1.PORT == 8000

        monkeypatch.setenv("PORT", "3000")
        s2 = Settings.from_env()
        assert s2.PORT == 3000


# ---------------------------------------------------------------------------
# .env.local overrides .env
# ---------------------------------------------------------------------------

class TestDotenvLocal:
    def test_local_overrides_base(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        (tmp_path / ".env").write_text("PORT=8000\nHOST=localhost\n")
        (tmp_path / ".env.local").write_text("PORT=9000\n")

        @config
        class Settings:
            PORT: int = 0
            HOST: str = ""

        s = Settings()
        assert s.PORT == 9000
        assert s.HOST == "localhost"


# ---------------------------------------------------------------------------
# Priority chain
# ---------------------------------------------------------------------------

class TestDotenvPriority:
    def test_env_specific_overrides_local(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        (tmp_path / ".env").write_text("PORT=8000\n")
        (tmp_path / ".env.local").write_text("PORT=9000\n")
        (tmp_path / ".env.test").write_text("PORT=3000\n")

        @config(env="test")
        class Settings:
            PORT: int = 0

        s = Settings()
        assert s.PORT == 3000
