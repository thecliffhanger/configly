"""Tests for secret masking."""
import pytest
from configly import config, secret
from configly.secret import SecretValue, is_secret


class TestSecretValue:
    def test_str_masked(self):
        s = secret("sk-12345")
        assert str(s) == "***"

    def test_repr_masked(self):
        s = secret("sk-12345")
        assert repr(s) == "***"

    def test_value_accessible(self):
        s = secret("sk-12345")
        assert s.value == "sk-12345"

    def test_bool_true(self):
        s = secret("anything")
        assert bool(s) is True

    def test_bool_false(self):
        s = secret("")
        assert bool(s) is False

    def test_equality(self):
        assert secret("a") == secret("a")
        assert secret("a") != secret("b")
        assert secret("a") == "a"

    def test_hash(self):
        assert hash(secret("a")) == hash(secret("a"))

    def test_len(self):
        s = secret("hello")
        assert len(s) == 5

    def test_iterable(self):
        s = secret([1, 2, 3])
        assert list(s) == [1, 2, 3]

    def test_is_secret(self):
        assert is_secret(secret("val"))
        assert not is_secret("val")
        assert not is_secret(None)

    def test_none_value(self):
        s = secret()
        assert s.value is None

    def test_key_stored(self):
        s = secret("val", key="API_KEY")
        assert s._key == "API_KEY"


class TestSecretInConfig:
    def test_secret_field_masked_in_repr(self):
        @config
        class Settings:
            PORT: int = 8000
            API_KEY: str = secret("sk-123")
        
        s = Settings()
        assert "API_KEY=***" in repr(s)
        assert "PORT=8000" in repr(s)

    def test_secret_field_masked_in_str(self):
        @config
        class Settings:
            API_KEY: str = secret("sk-123")
        
        s = Settings()
        assert "API_KEY=***" in str(s)

    def test_secret_field_masked_in_to_dict(self):
        @config
        class Settings:
            API_KEY: str = secret("sk-123")
            PORT: int = 8000
        
        s = Settings()
        d = s.to_dict()
        assert d["API_KEY"] == "***"
        assert d["PORT"] == 8000

    def test_secret_masked_method(self):
        @config
        class Settings:
            API_KEY: str = secret("sk-123")
        
        s = Settings()
        d = s.masked()
        assert d["API_KEY"] == "***"

    def test_secret_env_override(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "sk-from-env")
        @config
        class Settings:
            API_KEY: str = secret("sk-default")
        
        s = Settings()
        assert s.API_KEY == "sk-from-env"
        # But repr should still mask
        assert "API_KEY=***" in repr(s)

    def test_multiple_secrets(self):
        @config
        class Settings:
            API_KEY: str = secret("sk-123")
            WEBHOOK: str = secret("wh-456")
        
        s = Settings()
        d = s.masked()
        assert d["API_KEY"] == "***"
        assert d["WEBHOOK"] == "***"
