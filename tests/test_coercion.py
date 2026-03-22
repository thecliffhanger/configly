"""Tests for type coercion."""
import pytest
from configly.coercion import coerce, coerce_bool, coerce_int, coerce_float, coerce_str, coerce_list


class TestCoerceBool:
    def test_true_values(self):
        for v in ["true", "True", "TRUE", "1", "yes", "Yes", "YES", "on", "On", "ON", "t", "T", "y", "Y"]:
            assert coerce_bool(v) is True, f"Failed for {v}"

    def test_false_values(self):
        for v in ["false", "False", "FALSE", "0", "no", "No", "NO", "off", "Off", "OFF", "f", "F", "n", "N"]:
            assert coerce_bool(v) is False, f"Failed for {v}"

    def test_invalid_bool(self):
        with pytest.raises(ValueError):
            coerce_bool("maybe")

    def test_whitespace_handling(self):
        assert coerce_bool("  true  ") is True


class TestCoerceInt:
    def test_basic(self):
        assert coerce_int("42") == 42
        assert coerce_int("0") == 0
        assert coerce_int("-5") == -5

    def test_hex(self):
        assert coerce_int("0xff") == 255
        assert coerce_int("0xFF") == 255

    def test_octal(self):
        assert coerce_int("0o77") == 63

    def test_binary(self):
        assert coerce_int("0b1010") == 10

    def test_decimal_truncation(self):
        assert coerce_int("3.14") == 3
        assert coerce_int("-2.7") == -2

    def test_whitespace(self):
        assert coerce_int("  42  ") == 42

    def test_invalid_int(self):
        with pytest.raises(ValueError):
            coerce_int("abc")


class TestCoerceFloat:
    def test_basic(self):
        assert coerce_float("3.14") == 3.14
        assert coerce_float("0.0") == 0.0
        assert coerce_float("-1.5") == -1.5

    def test_scientific(self):
        assert coerce_float("1e10") == 1e10

    def test_integer_string(self):
        assert coerce_float("42") == 42.0

    def test_whitespace(self):
        assert coerce_float("  3.14  ") == 3.14

    def test_invalid_float(self):
        with pytest.raises(ValueError):
            coerce_float("abc")


class TestCoerceStr:
    def test_basic(self):
        assert coerce_str("hello") == "hello"

    def test_whitespace_stripped(self):
        assert coerce_str("  hello  ") == "hello"

    def test_double_quotes(self):
        assert coerce_str('"hello"') == "hello"

    def test_single_quotes(self):
        assert coerce_str("'hello'") == "hello"

    def test_empty(self):
        assert coerce_str("") == ""

    def test_nested_quotes(self):
        assert coerce_str('"hello world"') == "hello world"


class TestCoerceList:
    def test_comma_split(self):
        assert coerce_list("a,b,c") == ["a", "b", "c"]

    def test_whitespace_items(self):
        assert coerce_list("a, b, c") == ["a", "b", "c"]

    def test_empty_string(self):
        assert coerce_list("") == []

    def test_json_array(self):
        assert coerce_list('["a","b","c"]') == ["a", "b", "c"]

    def test_single_item(self):
        assert coerce_list("hello") == ["hello"]

    def test_trailing_comma(self):
        result = coerce_list("a,b,")
        assert result == ["a", "b"]

    def test_int_inner_type(self):
        assert coerce_list("1,2,3", inner_type=int) == [1, 2, 3]

    def test_float_inner_type(self):
        assert coerce_list("1.0,2.5,3.7", inner_type=float) == [1.0, 2.5, 3.7]

    def test_bool_inner_type(self):
        assert coerce_list("true,false,yes", inner_type=bool) == [True, False, True]


class TestCoerceFunction:
    def test_str_type(self):
        assert coerce("hello", str) == "hello"
        assert coerce(42, str) == "42"

    def test_int_type(self):
        assert coerce("42", int) == 42
        assert coerce(42, int) == 42
        assert coerce(True, int) == 1  # bool coerces to int

    def test_float_type(self):
        assert coerce("3.14", float) == 3.14
        assert coerce(3, float) == 3.0

    def test_bool_type(self):
        assert coerce("true", bool) is True
        assert coerce("false", bool) is False
        assert coerce(True, bool) is True

    def test_list_str(self):
        assert coerce("a,b,c", list[str]) == ["a", "b", "c"]

    def test_list_int(self):
        assert coerce("1,2,3", list[int]) == [1, 2, 3]

    def test_list_passthrough(self):
        assert coerce([1, 2, 3], list) == [1, 2, 3]

    def test_dict_passthrough(self):
        assert coerce({"a": 1}, dict) == {"a": 1}

    def test_dict_from_json_string(self):
        assert coerce('{"a": 1}', dict) == {"a": 1}

    def test_none_passthrough(self):
        assert coerce(None, str) is None

    def test_bytes_type(self):
        assert coerce(b"hello", bytes) == b"hello"
        assert coerce("hello", bytes) == b"hello"

    def test_list_of_floats(self):
        assert coerce("1.1,2.2,3.3", list[float]) == [1.1, 2.2, 3.3]

    def test_list_of_bools(self):
        result = coerce("true,false,yes,no", list[bool])
        assert result == [True, False, True, False]

    def test_int_from_float_string(self):
        assert coerce("3.14", int) == 3
