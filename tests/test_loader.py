"""Tests for config loaders."""
import json
import os
import pytest
from pathlib import Path
from configly.loader import (
    parse_dotenv_v2, load_env_vars, flatten_dict,
    parse_cli_args, load_json, load_config_file,
)


class TestParseDotenv:
    def test_basic_kv(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("PORT=8000\nDEBUG=true\n")
        result = parse_dotenv_v2(f)
        assert result["PORT"] == "8000"
        assert result["DEBUG"] == "true"

    def test_comments(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("# comment\nPORT=8000\n# another\n")
        result = parse_dotenv_v2(f)
        assert result == {"PORT": "8000"}

    def test_empty_lines(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("\n\nPORT=8000\n\n")
        result = parse_dotenv_v2(f)
        assert result == {"PORT": "8000"}

    def test_quoted_values(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text('NAME="hello world"\nSINGLE=\'quoted\'\n')
        result = parse_dotenv_v2(f)
        assert result["NAME"] == "hello world"
        assert result["SINGLE"] == "quoted"

    def test_export_prefix(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("export PORT=8000\n")
        result = parse_dotenv_v2(f)
        assert result["PORT"] == "8000"

    def test_multiline_value(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text('KEY="line1\nline2\nline3"\n')
        result = parse_dotenv_v2(f)
        assert result["KEY"] == "line1\nline2\nline3"

    def test_nonexistent_file(self):
        result = parse_dotenv_v2("/nonexistent/.env")
        assert result == {}

    def test_value_with_equals(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("CONN=host=localhost&port=5432\n")
        result = parse_dotenv_v2(f)
        assert result["CONN"] == "host=localhost&port=5432"

    def test_empty_value(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("EMPTY=\n")
        result = parse_dotenv_v2(f)
        assert result["EMPTY"] == ""


class TestLoadEnvVars:
    def test_basic(self, monkeypatch):
        monkeypatch.setenv("PORT", "8000")
        monkeypatch.setenv("DEBUG", "true")
        result = load_env_vars()
        assert result["port"] == "8000"
        assert result["debug"] == "true"

    def test_prefix(self, monkeypatch):
        monkeypatch.setenv("APP_PORT", "8000")
        monkeypatch.setenv("OTHER", "val")
        result = load_env_vars(prefix="APP_")
        assert result["port"] == "8000"
        assert "other" not in result

    def test_no_prefix(self, monkeypatch):
        monkeypatch.setenv("A", "1")
        result = load_env_vars()
        assert result["a"] == "1"

    def test_empty(self, monkeypatch):
        # Clear relevant env vars by using a unique prefix
        result = load_env_vars(prefix="NONEXISTENT_PREFIX_")
        assert result == {}


class TestFlattenDict:
    def test_flat(self):
        assert flatten_dict({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_nested(self):
        d = {"db": {"host": "localhost", "port": 5432}}
        assert flatten_dict(d) == {"db_host": "localhost", "db_port": 5432}

    def test_deep_nesting(self):
        d = {"a": {"b": {"c": 1}}}
        assert flatten_dict(d) == {"a_b_c": 1}

    def test_mixed(self):
        d = {"a": 1, "b": {"c": 2}}
        assert flatten_dict(d) == {"a": 1, "b_c": 2}


class TestParseCliArgs:
    def test_basic(self):
        args = ["--config.PORT=9000", "--config.DEBUG=true"]
        result = parse_cli_args(args)
        assert result["port"] == "9000"
        assert result["debug"] == "true"

    def test_no_config_args(self):
        result = parse_cli_args(["--help", "--version"])
        assert result == {}

    def test_mixed_args(self):
        args = ["--help", "--config.PORT=9000", "positional"]
        result = parse_cli_args(args)
        assert result["port"] == "9000"

    def test_custom_prefix(self):
        args = ["--app.PORT=9000"]
        result = parse_cli_args(args, prefix="--app.")
        assert result["port"] == "9000"

    def test_value_with_equals(self):
        args = ["--config.URL=http://example.com?x=1"]
        result = parse_cli_args(args)
        assert result["url"] == "http://example.com?x=1"


class TestLoadJson:
    def test_basic(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text('{"port": 8000, "debug": true}')
        result = load_json(f)
        assert result == {"port": 8000, "debug": True}

    def test_nested(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text('{"db": {"host": "localhost"}}')
        result = load_json(f)
        assert result == {"db": {"host": "localhost"}}

    def test_nonexistent(self):
        result = load_json("/nonexistent/config.json")
        assert result == {}


class TestLoadConfigFile:
    def test_json_extension(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text('{"port": 8000}')
        result = load_config_file(f)
        assert result == {"port": 8000}

    def test_unsupported_extension(self, tmp_path):
        f = tmp_path / "config.xml"
        f.write_text("<config/>")
        with pytest.raises(ValueError):
            load_config_file(f)


class TestLoadYaml:
    def test_yaml_loading(self, tmp_path):
        pytest.importorskip("yaml")
        from configly.loader import load_yaml
        f = tmp_path / "config.yaml"
        f.write_text("port: 8000\ndebug: true\n")
        result = load_yaml(f)
        assert result == {"port": 8000, "debug": True}

    def test_yaml_nested(self, tmp_path):
        pytest.importorskip("yaml")
        from configly.loader import load_yaml
        f = tmp_path / "config.yaml"
        f.write_text("db:\n  host: localhost\n  port: 5432\n")
        result = load_yaml(f)
        assert result == {"db": {"host": "localhost", "port": 5432}}


class TestLoadToml:
    def test_toml_loading(self, tmp_path):
        from configly.loader import load_toml
        f = tmp_path / "config.toml"
        f.write_text('port = 8000\ndebug = true\n')
        result = load_toml(f)
        assert result == {"port": 8000, "debug": True}

    def test_toml_nested(self, tmp_path):
        from configly.loader import load_toml
        f = tmp_path / "config.toml"
        f.write_text('[db]\nhost = "localhost"\nport = 5432\n')
        result = load_toml(f)
        assert result == {"db": {"host": "localhost", "port": 5432}}

    def test_toml_nonexistent(self):
        from configly.loader import load_toml
        assert load_toml("/nonexistent/config.toml") == {}
