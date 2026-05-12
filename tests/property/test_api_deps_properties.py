"""Property tests for api/deps.py — API key authentication invariants (#339).

Tests:
- Missing / empty api_key always raises HTTP 401
- A key that does not match configured_key always raises HTTP 403
- A key that matches configured_key passes without raising
- The status codes are mutually exclusive: wrong-key always 403, never 401
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from hypothesis import given, settings
from hypothesis import strategies as st

from api.deps import require_api_key
from config.settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# secrets.compare_digest requires ASCII-only strings; restrict to printable ASCII.
_ASCII_TEXT = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),  # printable ASCII (no space)
    min_size=1,
    max_size=64,
)


def _settings(api_key: str) -> Settings:
    """Create a Settings instance with a specific api_key value."""
    return Settings(api_key=api_key)


def _call(api_key, configured_key: str):
    """Invoke require_api_key directly (bypassing FastAPI DI)."""
    require_api_key(api_key=api_key, settings=_settings(configured_key))


# ---------------------------------------------------------------------------
# Valid-key invariants
# ---------------------------------------------------------------------------

@given(key=_ASCII_TEXT)
@settings(max_examples=50)
def test_matching_key_does_not_raise(key):
    """When api_key == configured_key, require_api_key must not raise."""
    _call(api_key=key, configured_key=key)  # should complete silently


# ---------------------------------------------------------------------------
# Missing-key invariants
# ---------------------------------------------------------------------------

@given(configured_key=_ASCII_TEXT)
@settings(max_examples=30)
def test_missing_key_raises_401(configured_key):
    """None api_key always raises HTTP 401 regardless of configured key."""
    with pytest.raises(HTTPException) as exc_info:
        _call(api_key=None, configured_key=configured_key)
    assert exc_info.value.status_code == 401


@given(configured_key=_ASCII_TEXT)
@settings(max_examples=30)
def test_empty_string_key_raises_401(configured_key):
    """Empty string api_key always raises HTTP 401 (treated as missing)."""
    with pytest.raises(HTTPException) as exc_info:
        _call(api_key="", configured_key=configured_key)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Wrong-key invariants
# ---------------------------------------------------------------------------

@given(
    api_key=_ASCII_TEXT,
    configured_key=_ASCII_TEXT,
)
@settings(max_examples=50)
def test_wrong_key_raises_403(api_key, configured_key):
    """When api_key != configured_key, require_api_key raises HTTP 403."""
    if api_key == configured_key:
        return  # skip matching pairs — they are valid
    with pytest.raises(HTTPException) as exc_info:
        _call(api_key=api_key, configured_key=configured_key)
    assert exc_info.value.status_code == 403


@given(api_key=_ASCII_TEXT, configured_key=_ASCII_TEXT)
@settings(max_examples=30)
def test_wrong_key_never_raises_401(api_key, configured_key):
    """A non-empty, wrong api_key must raise 403, never 401."""
    if api_key == configured_key:
        return  # skip valid pairs
    try:
        _call(api_key=api_key, configured_key=configured_key)
    except HTTPException as exc:
        assert exc.status_code != 401, (
            f"Expected 403 for wrong key, got 401. api_key={api_key!r}"
        )
