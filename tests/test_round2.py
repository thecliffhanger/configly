"""Round 2 tests — hypothesis-based and edge cases."""
import os
import sys
import pytest
from hypothesis import given, strategies as st, assume
from configly import config, validator, ValidationError, ConfigError
from configly.coercion import coerce, coerce_bool, coerce_int, coerce_float, coerce_list
from configly.loader import parse_dotenv_v2, parse_cli_args, flatten_dict
from configly.secret import secret, is_secret


# === Hypothesis tests for coercion ===

@given(st.integers(min_value=-1000000, max_value=1000000))
def test_int_roundtrip_int(v):
    result = coerce_int(str(v))
    assert result == v


@given(st.floats(allow_nan=False, allow_infinity=False, min_value=-1e15, max_value=1e15))
def test_float_roundtrip(v):
    result = coerce_float(str(v))
    assert abs(result - v) < 1e-10


@given(st.text(min_size=1, max_size=100))
def test_str_passthrough(s):
    from configly.coercion import coerce_str
    assert coerce_str(s) == s.strip()


@given(st.lists(st.integers(min_value=0, max_value=100), min_size=0, max_size=10))
def test_list_int_roundtrip(items):
    s = ",".join(str(i) for i in items)
    assert coerce_list(s, inner_type=int) == items


@given(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=1, max_size=50))
def test_coerce_str_does_not_crash(s):
    result = coerce(s, str)
    assert isinstance(result, str)


# === Edge cases ===

class TestEdgeCases:
    def test_all_types_together(self):
        @config
        class Settings:
            A_INT: int = 1
            A_FLOAT: float = 1.0
            A_BOOL: bool = False
            A_STR: str = "hi"
            A_LIST: list[str] = []
            A_DICT: dict = {}
        
        s = Settings()
        assert s.A_INT == 1
        assert s.A_FLOAT == 1.0
        assert s.A_BOOL is False
        assert s.A_STR == "hi"
        assert s.A_LIST == []
        assert s.A_DICT == {}

    def test_override_all_types(self, monkeypatch):
        monkeypatch.setenv("A_INT", "42")
        monkeypatch.setenv("A_FLOAT", "3.14")
        monkeypatch.setenv("A_BOOL", "true")
        monkeypatch.setenv("A_STR", "hello")
        monkeypatch.setenv("A_LIST", "x,y,z")
        
        @config
        class Settings:
            A_INT: int = 0
            A_FLOAT: float = 0.0
            A_BOOL: bool = False
            A_STR: str = ""
            A_LIST: list[str] = []
        
        s = Settings()
        assert s.A_INT == 42
        assert s.A_FLOAT == 3.14
        assert s.A_BOOL is True
        assert s.A_STR == "hello"
        assert s.A_LIST == ["x", "y", "z"]

    def test_coercion_error(self, monkeypatch):
        monkeypatch.setenv("PORT", "not_a_number")
        @config
        class Settings:
            PORT: int = 8000
        
        with pytest.raises(ValidationError):
            Settings()

    def test_many_validators(self):
        errors = []
        
        @config
        class Settings:
            A: int = 0
            B: str = ""
            C: float = 0.0
            
            @validator("A")
            def va(cls, v):
                if v < 0:
                    raise ValueError("A negative")
                return v
            
            @validator("B")
            def vb(cls, v):
                if len(v) > 10:
                    raise ValueError("B too long")
                return v
            
            @validator("C")
            def vc(cls, v):
                if v > 100:
                    raise ValueError("C too big")
                return v
        
        s = Settings()
        assert s.A == 0
        
        with pytest.raises(ValidationError):
            Settings(A=-1)
        
        with pytest.raises(ValidationError):
            Settings(B="x" * 11)

    def test_freeze_then_read_all(self):
        @config
        class Settings:
            PORT: int = 8000
            HOST: str = "localhost"
            DEBUG: bool = True
        
        s = Settings()
        s.freeze()
        assert s.PORT == 8000
        assert s.HOST == "localhost"
        assert s.DEBUG is True
        with pytest.raises(ConfigError):
            s.PORT = 9000
        with pytest.raises(ConfigError):
            s.NEW = "field"

    def test_nested_dict_from_config(self, monkeypatch):
        monkeypatch.setenv("DATABASE", '{"host":"prod","port":5432}')
        @config
        class Settings:
            DATABASE: dict
        
        s = Settings()
        assert s.DATABASE["host"] == "prod"

    def test_empty_str_field(self, monkeypatch):
        monkeypatch.setenv("NAME", "")
        @config
        class Settings:
            NAME: str = "default"
        
        s = Settings()
        assert s.NAME == ""

    def test_large_list(self, monkeypatch):
        items = ",".join(f"item{i}" for i in range(100))
        monkeypatch.setenv("ITEMS", items)
        @config
        class Settings:
            ITEMS: list[str] = []
        
        s = Settings()
        assert len(s.ITEMS) == 100
        assert s.ITEMS[0] == "item0"

    def test_config_with_no_defaults(self):
        @config
        class Settings:
            pass
        
        s = Settings()
        # Should not crash

    def test_dotenv_empty_file(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("")
        result = parse_dotenv_v2(f)
        assert result == {}

    def test_dotenv_only_comments(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("# comment\n# another\n")
        result = parse_dotenv_v2(f)
        assert result == {}

    def test_dotenv_multiline_single_quotes(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("KEY='line1\nline2'\n")
        result = parse_dotenv_v2(f)
        assert result["KEY"] == "line1\nline2"

    def test_flatten_dict_deep(self):
        d = {"a": {"b": {"c": {"d": 1}}}}
        assert flatten_dict(d) == {"a_b_c_d": 1}

    def test_cli_empty_value(self):
        result = parse_cli_args(["--config.KEY="])
        assert result["key"] == ""

    def test_cli_no_equals(self):
        result = parse_cli_args(["--config.KEY"])
        assert result == {}

    def test_coerce_bool_already_bool(self):
        assert coerce(True, bool) is True
        assert coerce(False, bool) is False

    def test_coerce_int_already_int(self):
        assert coerce(42, int) == 42

    def test_coerce_float_from_int(self):
        assert coerce(42, float) == 42.0

    def test_coerce_none(self):
        assert coerce(None, int) is None
        assert coerce(None, str) is None

    def test_secret_no_args(self):
        s = secret()
        assert s.value is None
        assert str(s) == "***"

    def test_secret_with_numeric_value(self):
        s = secret(12345)
        assert s.value == 12345
        assert str(s) == "***"

    def test_multiple_instances_independent(self):
        @config
        class Settings:
            PORT: int = 8000
        
        s1 = Settings()
        s2 = Settings(PORT=9000)
        assert s1.PORT == 8000
        assert s2.PORT == 9000

    def test_from_env_reloads(self, monkeypatch):
        monkeypatch.setenv("PORT", "3000")
        @config
        class Settings:
            PORT: int = 8000
        
        s1 = Settings()
        assert s1.PORT == 3000
        s2 = Settings()
        assert s2.PORT == 3000

    def test_validator_not_triggered_for_other_fields(self):
        @config
        class Settings:
            PORT: int = 8000
            HOST: str = "localhost"
            
            @validator("PORT")
            def vp(cls, v):
                if v < 1:
                    raise ValueError("should not be called for HOST")
                return v
        
        s = Settings(HOST="other")
        assert s.HOST == "other"
        assert s.PORT == 8000
