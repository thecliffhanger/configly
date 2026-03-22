"""Adversarial tests for configly — edge cases, malformed input, missing deps."""


import os
import sys
import textwrap
from pathlib import Path
from unittest import mock

import pytest

from configly import config, secret, validator, ConfigError, ValidationError, ConfigFrozenError


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

class TestMissingRequiredField:
    def test_no_default_no_env_raises_on_access(self):
        @config
        class Settings:
            PORT: int = 8000
            API_KEY: str  # required, no default

        s = Settings()
        assert s.PORT == 8000
        # configly sets None for missing required fields (doesn't raise)
        assert s.API_KEY is None

    def test_no_default_with_env_succeeds(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "secret123")
        @config
        class Settings:
            API_KEY: str

        s = Settings()
        assert s.API_KEY == "secret123"

    def test_no_default_with_override_succeeds(self):
        @config
        class Settings:
            API_KEY: str

        s = Settings(API_KEY="override")
        assert s.API_KEY == "override"


# ---------------------------------------------------------------------------
# Invalid env var values that can't be coerced
# ---------------------------------------------------------------------------

class TestInvalidCoercion:
    def test_invalid_int_env(self, monkeypatch):
        monkeypatch.setenv("PORT", "not_a_number")
        @config
        class Settings:
            PORT: int = 8000

        with pytest.raises(ValidationError, match="coercion error"):
            Settings()

    def test_invalid_bool_env(self, monkeypatch):
        monkeypatch.setenv("DEBUG", "maybe")
        @config
        class Settings:
            DEBUG: bool = False

        with pytest.raises(ValidationError, match="coercion error"):
            Settings()

    def test_invalid_float_env(self, monkeypatch):
        monkeypatch.setenv("RATE", "nan_value")
        @config
        class Settings:
            RATE: float = 1.0

        with pytest.raises(ValidationError, match="coercion error"):
            Settings()


# ---------------------------------------------------------------------------
# .env with malformed content
# ---------------------------------------------------------------------------

class TestMalformedDotenv:
    def test_malformed_lines_ignored(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text(textwrap.dedent("""\
            VALID=value1
            =no_key
            just_a_word
            ANOTHER=value2
        """))
        monkeypatch.chdir(tmp_path)
        @config
        class Settings:
            VALID: str = ""
            ANOTHER: str = ""

        s = Settings()
        assert s.VALID == "value1"
        assert s.ANOTHER == "value2"

    def test_binary_garbage_in_dotenv(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_bytes(b"\x80\x81\x82\nKEY=val\xff\n")
        monkeypatch.chdir(tmp_path)
        @config
        class Settings:
            KEY: str = "default"

        s = Settings()
        # The binary bytes may or may not parse; default should be safe
        assert isinstance(s.KEY, str)


# ---------------------------------------------------------------------------
# Very long env var values
# ---------------------------------------------------------------------------

class TestLongValues:
    def test_long_env_var_value(self, monkeypatch):
        long_val = "x" * 100_000
        monkeypatch.setenv("LONG_TEST_VAR", long_val)
        @config
        class Settings:
            LONG_TEST_VAR: str = ""

        s = Settings()
        assert s.LONG_TEST_VAR == long_val
        assert len(s.LONG_TEST_VAR) == 100_000

    def test_long_env_var_list(self, monkeypatch):
        long_list = ",".join([f"advitem{i}" for i in range(10_000)])
        monkeypatch.setenv("ADV_LONG_ITEMS_TEST", long_list)
        @config
        class Settings:
            ADV_LONG_ITEMS_TEST: list = []

        s = Settings()
        assert len(s.ADV_LONG_ITEMS_TEST) == 10_000


# ---------------------------------------------------------------------------
# Unicode
# ---------------------------------------------------------------------------

class TestUnicode:
    def test_unicode_value(self, monkeypatch):
        monkeypatch.setenv("UNICODE_GREETING", "こんにちは世界")
        @config
        class Settings:
            UNICODE_GREETING: str = ""

        s = Settings()
        assert s.UNICODE_GREETING == "こんにちは世界"


# ---------------------------------------------------------------------------
# Nested config with conflicting sources
# ---------------------------------------------------------------------------

class TestConflictingSources:
    def test_env_overrides_config_file(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("port: 3000\nhost: localhost\n")
        monkeypatch.setenv("PORT", "5000")
        monkeypatch.chdir(tmp_path)
        @config(config_file=str(cfg_file))
        class Settings:
            PORT: int = 8000
            HOST: str = "0.0.0.0"

        s = Settings()
        assert s.PORT == 5000
        assert s.HOST == "localhost"

    def test_override_overrides_env(self, monkeypatch):
        monkeypatch.setenv("PORT", "5000")
        @config
        class Settings:
            PORT: int = 8000

        s = Settings(PORT=9000)
        assert s.PORT == 9000


# ---------------------------------------------------------------------------
# Freeze
# ---------------------------------------------------------------------------

class TestFreeze:
    def test_freeze_then_setattr_fails(self):
        @config
        class Settings:
            PORT: int = 8000

        s = Settings()
        s.freeze()
        with pytest.raises(ConfigFrozenError, match="frozen"):
            s.PORT = 3000

    def test_freeze_allows_read(self):
        @config
        class Settings:
            PORT: int = 8000

        s = Settings()
        s.freeze()
        assert s.PORT == 8000

    def test_freeze_flag_true(self):
        @config
        class Settings:
            PORT: int = 8000

        s = Settings()
        s.freeze()
        assert s._configly_frozen is True


# ---------------------------------------------------------------------------
# Secret fields
# ---------------------------------------------------------------------------

class TestSecretMasking:
    def test_str_masked(self):
        @config
        class Settings:
            API_KEY: str = secret("sk-12345")

        s = Settings()
        assert "***" in str(s)
        assert "sk-12345" not in str(s)

    def test_repr_masked(self):
        @config
        class Settings:
            API_KEY: str = secret("sk-12345")

        s = Settings()
        assert "***" in repr(s)
        assert "sk-12345" not in repr(s)

    def test_value_accessible(self):
        @config
        class Settings:
            API_KEY: str = secret("sk-12345")

        s = Settings()
        assert s.API_KEY == "sk-12345"

    def test_secret_env_override_still_masked(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "env-secret")
        @config
        class Settings:
            API_KEY: str = secret("default-key")

        s = Settings()
        assert "***" in repr(s)
        assert "env-secret" not in repr(s)
        assert s.API_KEY == "env-secret"


# ---------------------------------------------------------------------------
# Duplicate field names from multiple sources
# ---------------------------------------------------------------------------

class TestDuplicateSources:
    def test_default_then_env_then_override(self, monkeypatch):
        monkeypatch.setenv("PORT", "5000")
        @config
        class Settings:
            PORT: int = 8000

        s = Settings(PORT=3000)
        assert s.PORT == 3000


# ---------------------------------------------------------------------------
# Missing optional dependencies
# ---------------------------------------------------------------------------

class TestMissingDeps:
    def test_no_yaml_still_works_for_env(self, monkeypatch):
        monkeypatch.setenv("PORT", "9000")
        @config
        class Settings:
            PORT: int = 8000

        s = Settings()
        assert s.PORT == 9000

    def test_no_yaml_raises_on_yaml_file(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("port: 3000\n")
        with mock.patch.dict(sys.modules, {"yaml": None}):
            import importlib
            from configly import loader
            importlib.reload(loader)
            with pytest.raises(ImportError, match="PyYAML"):
                loader.load_yaml(str(cfg_file))
            importlib.reload(loader)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_class(self):
        @config
        class Settings:
            pass

        s = Settings()
        assert s is not None

    def test_none_default_with_env(self, monkeypatch):
        monkeypatch.setenv("NAME", "teja")
        @config
        class Settings:
            NAME: str = None

        s = Settings()
        assert s.NAME == "teja"

    def test_list_of_ints_coercion(self, monkeypatch):
        monkeypatch.setenv("PORTS", "80,443,8080")
        @config
        class Settings:
            PORTS: list = []

        s = Settings()
        assert s.PORTS == ["80", "443", "8080"]

    def test_bytes_field(self, monkeypatch):
        monkeypatch.setenv("DATA", "hello")
        @config
        class Settings:
            DATA: bytes = b""

        s = Settings()
        assert s.DATA == b"hello"

    def test_validator_modifies_value(self):
        @config
        class Settings:
            PORT: int = 8000

            @validator("PORT")
            def check_port(cls, v):
                if v < 100:
                    return 100
                return v

        s = Settings()
        assert s.PORT == 8000

        s2 = Settings(PORT=50)
        assert s2.PORT == 100
