# configly — Code Review

## Summary

Tested thoroughly: 203 tests all passing (160 existing + 43 new adversarial/integration).

## Bugs Found & Fixed (3)

### 1. Bare `list` type not coerced from env strings
**File:** `coercion.py`  
**Issue:** `list` (bare, without `[]`) has no `get_origin`, so the `origin is list` check missed it. Annotated fields like `PORTS: list` would receive the raw string from env vars.  
**Fix:** Added `target_type is list or origin is list` guard.

### 2. `from_env()` returned `None`
**File:** `config.py`  
**Issue:** `from_env` was a plain function assigned to the class. When called as `Settings.from_env()`, no `self`/`cls` was passed (it's not a descriptor), so `cls_self_or_instance=None`, leading to `type(None)()` → `None`.  
**Fix:** Rewrote as `classmethod(lambda cls, **overrides: cls(**overrides))`.

### 3. Non-UTF-8 `.env` files crash
**File:** `loader.py`  
**Issue:** `parse_dotenv` / `parse_dotenv_v2` opened files with strict UTF-8 encoding, crashing on binary garbage.  
**Fix:** Added `errors="replace"` to both file opens.

## Design Notes & Limitations

### Good
- **Priority order is correct:** defaults < config file < .env < .env.local < .env.{env} < env vars < CLI args < init overrides
- **Secret masking** works in `str()`, `repr()`, `to_dict()`, `masked()` — even when env vars override secret defaults
- **Type coercion** is solid: bool, int, float, str, list, list[T], dict, bytes, nested config classes, Optional
- **Freeze enforcement** works correctly via `__setattr__` override
- **Validators** run after coercion and can modify values
- **.env parsing** handles comments, empty lines, quoted values, multiline values, export prefix
- **Config file loading** with graceful ImportError messages for missing optional deps

### Issues (not bugs, but worth noting)
1. **Missing required fields don't raise errors** — Fields with no default and no env value are silently set to `None` instead of raising `ValidationError`. The "required field" check in `__init__` is a no-op (all branches end with `pass`).

2. **`dict` type fields can't be populated from nested config files** — `flatten_dict` turns `{"database": {"host": "x"}}` into `database_host=x`, so a `DATABASE: dict` field can't reconstruct the original dict. Must use init override or flat top-level keys.

3. **Thread safety** — No locking anywhere. Concurrent access + mutation could race. Freeze helps but only for writes after init.

4. **Dead code** — `parse_dotenv` (v1), module-level `quote_char`, and `_fix_quote_char` are unused after `parse_dotenv_v2` was added.

5. **`masked()` is redundant** — It's identical to `to_dict()` (both mask secrets). Could be removed or `masked()` could mask *all* values.

6. **Env var cleanup** — `load_env_vars` reads `os.environ` but doesn't modify it, so no leak concerns. Good.

## New Test Coverage

### Adversarial (29 tests)
- Missing required fields (no default, no env)
- Invalid coercion (int, bool, float)
- Malformed .env content (bad lines, binary garbage)
- Very long values (100K chars, 10K-item lists)
- Unicode values
- Conflicting sources (priority verification)
- Freeze enforcement
- Secret masking (str, repr, value access, env override)
- Missing optional dependencies
- Edge cases (empty class, None default, bytes, validator value modification)

### Integration (14 tests)
- Full pipeline priority chain (default → config file → .env → env var → override)
- Real .env file parsing with multiple types
- Real YAML nested config with flatten_dict
- `masked()` and `to_dict()` output
- Dict fields via override (documents limitation)
- Environment switching (.env.test, .env.production, missing env file)
- `from_env()` reload
- .env.local override behavior
- Priority: .env.test > .env.local > .env
