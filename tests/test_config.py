"""Tests for core config decorator and Settings class."""
import os
import pytest
from configly import config, ConfigError, ConfigFrozenError, ValidationError


class TestBasicConfig:
    def test_simple_config(self):
        @config
        class Settings:
            PORT: int = 8000
            DEBUG: bool = False
        
        s = Settings()
        assert s.PORT == 8000
        assert s.DEBUG is False

    def test_override_via_init(self):
        @config
        class Settings:
            PORT: int = 8000
        
        s = Settings(PORT=9000)
        assert s.PORT == 9000

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("PORT", "9000")
        @config
        class Settings:
            PORT: int = 8000
        
        s = Settings()
        assert s.PORT == 9000

    def test_str_coercion(self, monkeypatch):
        monkeypatch.setenv("HOST", "  example.com  ")
        @config
        class Settings:
            HOST: str = "localhost"
        
        s = Settings()
        assert s.HOST == "example.com"

    def test_int_coercion(self, monkeypatch):
        monkeypatch.setenv("PORT", "8080")
        @config
        class Settings:
            PORT: int = 8000
        
        s = Settings()
        assert s.PORT == 8080
        assert isinstance(s.PORT, int)

    def test_float_coercion(self, monkeypatch):
        monkeypatch.setenv("TIMEOUT", "60.5")
        @config
        class Settings:
            TIMEOUT: float = 30.0
        
        s = Settings()
        assert s.TIMEOUT == 60.5

    def test_bool_true_coercion(self, monkeypatch):
        for val in ["true", "1", "yes", "on", "True", "YES"]:
            monkeypatch.setenv("DEBUG", val)
            @config
            class S:
                DEBUG: bool = False
            assert S().DEBUG is True, f"Failed for {val}"

    def test_bool_false_coercion(self, monkeypatch):
        for val in ["false", "0", "no", "off", "False", "NO"]:
            monkeypatch.setenv("DEBUG", val)
            @config
            class S:
                DEBUG: bool = True
            assert S().DEBUG is False, f"Failed for {val}"

    def test_list_coercion(self, monkeypatch):
        monkeypatch.setenv("ITEMS", "a,b,c")
        @config
        class Settings:
            ITEMS: list[str] = []
        
        s = Settings()
        assert s.ITEMS == ["a", "b", "c"]

    def test_list_json_coercion(self, monkeypatch):
        monkeypatch.setenv("ITEMS", '["a","b","c"]')
        @config
        class Settings:
            ITEMS: list[str] = []
        
        s = Settings()
        assert s.ITEMS == ["a", "b", "c"]

    def test_list_int_coercion(self, monkeypatch):
        monkeypatch.setenv("PORTS", "80,443,8080")
        @config
        class Settings:
            PORTS: list[int] = []
        
        s = Settings()
        assert s.PORTS == [80, 443, 8080]

    def test_empty_list(self, monkeypatch):
        monkeypatch.setenv("ITEMS", "")
        @config
        class Settings:
            ITEMS: list[str] = []
        
        s = Settings()
        assert s.ITEMS == []

    def test_required_field_no_error_with_override(self):
        @config
        class Settings:
            NAME: str
        
        s = Settings(NAME="test")
        assert s.NAME == "test"

    def test_init_override_takes_priority_over_env(self, monkeypatch):
        monkeypatch.setenv("PORT", "9000")
        @config
        class Settings:
            PORT: int = 8000
        
        s = Settings(PORT=7000)
        assert s.PORT == 7000


class TestPrefix:
    def test_prefix_stripped(self, monkeypatch):
        monkeypatch.setenv("APP_PORT", "3000")
        @config(prefix="APP_")
        class Settings:
            PORT: int = 8000
        
        s = Settings()
        assert s.PORT == 3000


class TestFreeze:
    def test_freeze_prevents_mutation(self):
        @config
        class Settings:
            PORT: int = 8000
        
        s = Settings()
        s.freeze()
        with pytest.raises(ConfigFrozenError):
            s.PORT = 9000

    def test_freeze_allows_read(self):
        @config
        class Settings:
            PORT: int = 8000
        
        s = Settings()
        s.freeze()
        assert s.PORT == 8000


class TestToDict:
    def test_to_dict(self):
        @config
        class Settings:
            PORT: int = 8000
            DEBUG: bool = True
        
        s = Settings()
        d = s.to_dict()
        assert d == {"PORT": 8000, "DEBUG": True}

    def test_masked(self):
        from configly import secret
        
        @config
        class Settings:
            PORT: int = 8000
            API_KEY: str = secret("sk-123")
        
        s = Settings()
        d = s.masked()
        assert d["PORT"] == 8000
        assert d["API_KEY"] == "***"


class TestRepr:
    def test_repr_masks_secrets(self):
        from configly import secret
        
        @config
        class Settings:
            PORT: int = 8000
            API_KEY: str = secret("sk-123")
        
        s = Settings()
        r = repr(s)
        assert "PORT=8000" in r
        assert "API_KEY=***" in r


class TestEnvSwitch:
    def test_env_parameter(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env.production"
        env_file.write_text("PORT=3000\n")
        
        monkeypatch.chdir(tmp_path)
        @config(env="production")
        class Settings:
            PORT: int = 8000
        
        s = Settings()
        assert s.PORT == 3000


class TestCLI:
    def test_cli_override(self, monkeypatch):
        import sys
        monkeypatch.setattr(sys, "argv", ["prog", "--config.PORT=9000"])
        @config
        class Settings:
            PORT: int = 8000
        
        s = Settings()
        assert s.PORT == 9000


import sys


class TestNestedConfig:
    def test_dict_type(self, monkeypatch):
        monkeypatch.setenv("DATABASE", '{"host":"localhost","port":5432}')
        @config
        class Settings:
            DATABASE: dict = {}
        
        s = Settings()
        assert s.DATABASE == {"host": "localhost", "port": 5432}

    def test_nested_config_class(self):
        @config
        class Database:
            HOST: str = "localhost"
            PORT: int = 5432
        
        # Create instance directly
        db = Database()
        @config
        class Settings:
            database: dict = {"host": "localhost", "port": 5432}
        
        s = Settings()
        assert s.database["host"] == "localhost"


class TestValidation:
    def test_validator_runs(self):
        from configly import validator, ValidationError
        
        @config
        class Settings:
            PORT: int = 8000
            
            @validator("PORT")
            def port_range(cls, v):
                if not 1 <= v <= 65535:
                    raise ValueError(f"PORT out of range: {v}")
                return v
        
        s = Settings(PORT=80)
        assert s.PORT == 80
        
        with pytest.raises(ValidationError):
            Settings(PORT=99999)

    def test_invalid_bool_raises(self, monkeypatch):
        monkeypatch.setenv("DEBUG", "maybe")
        @config
        class Settings:
            DEBUG: bool = False
        
        with pytest.raises(ValidationError):
            Settings()
