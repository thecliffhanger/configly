"""Tests for the validator decorator."""
import pytest
from configly import config, validator, ValidationError


class TestValidatorBasic:
    def test_simple_validator(self):
        @config
        class Settings:
            PORT: int = 8000
            
            @validator("PORT")
            def check_port(cls, v):
                if v < 1:
                    raise ValueError("PORT must be >= 1")
                return v
        
        s = Settings()
        assert s.PORT == 8000
        s2 = Settings(PORT=3000)
        assert s2.PORT == 3000

    def test_validator_raises_on_invalid(self):
        @config
        class Settings:
            PORT: int = 8000
            
            @validator("PORT")
            def check_port(cls, v):
                if v < 1:
                    raise ValueError("PORT must be >= 1")
                return v
        
        with pytest.raises(ValidationError):
            Settings(PORT=0)

    def test_validator_with_string_field(self):
        @config
        class Settings:
            DATABASE_URL: str = "sqlite:///db.sqlite"
            
            @validator("DATABASE_URL")
            def check_db(cls, v):
                if not v.startswith("sqlite://"):
                    raise ValueError("Must be sqlite")
                return v
        
        s = Settings(DATABASE_URL="sqlite:///test.db")
        assert s.DATABASE_URL == "sqlite:///test.db"
        
        with pytest.raises(ValidationError):
            Settings(DATABASE_URL="postgres://localhost")

    def test_validator_modifies_value(self):
        @config
        class Settings:
            NAME: str = "default"
            
            @validator("NAME")
            def uppercase(cls, v):
                return v.upper()
        
        s = Settings(NAME="hello")
        assert s.NAME == "HELLO"

    def test_validator_with_bool(self):
        @config
        class Settings:
            DEBUG: bool = False
            
            @validator("DEBUG")
            def check_debug(cls, v):
                assert isinstance(v, bool)
                return v
        
        s = Settings(DEBUG=True)
        assert s.DEBUG is True

    def test_validator_with_list(self):
        @config
        class Settings:
            PORTS: list[int] = []
            
            @validator("PORTS")
            def check_ports(cls, v):
                if len(v) > 0 and v[0] < 1024:
                    raise ValueError("First port must be >= 1024")
                return v
        
        s = Settings(PORTS=[8080, 443])
        assert s.PORTS == [8080, 443]
        
        with pytest.raises(ValidationError):
            Settings(PORTS=[80, 443])

    def test_multiple_validators(self):
        @config
        class Settings:
            PORT: int = 8000
            HOST: str = "localhost"
            
            @validator("PORT")
            def check_port(cls, v):
                if not 1 <= v <= 65535:
                    raise ValueError("PORT out of range")
                return v
            
            @validator("HOST")
            def check_host(cls, v):
                if not v:
                    raise ValueError("HOST required")
                return v
        
        s = Settings()
        assert s.PORT == 8000
        assert s.HOST == "localhost"
        
        with pytest.raises(ValidationError):
            Settings(PORT=70000)
        
        with pytest.raises(ValidationError):
            Settings(HOST="")

    def test_validator_with_float(self):
        @config
        class Settings:
            TIMEOUT: float = 30.0
            
            @validator("TIMEOUT")
            def check_timeout(cls, v):
                if v <= 0:
                    raise ValueError("TIMEOUT must be positive")
                return v
        
        s = Settings(TIMEOUT=60.5)
        assert s.TIMEOUT == 60.5
        
        with pytest.raises(ValidationError):
            Settings(TIMEOUT=-1.0)

    def test_validator_runs_after_coercion(self):
        @config
        class Settings:
            PORT: int = 8000
            
            @validator("PORT")
            def check_port(cls, v):
                # v should already be int
                assert isinstance(v, int), f"Expected int, got {type(v)}"
                return v
        
        # When env provides a string, coercion happens first, then validation
        s = Settings(PORT=9000)
        assert s.PORT == 9000

    def test_validator_on_env_value(self, monkeypatch):
        monkeypatch.setenv("PORT", "99999")
        
        @config
        class Settings:
            PORT: int = 8000
            
            @validator("PORT")
            def check_port(cls, v):
                if v > 65535:
                    raise ValueError("PORT out of range")
                return v
        
        with pytest.raises(ValidationError):
            Settings()
