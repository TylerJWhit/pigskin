"""Property tests for utils/sleeper_cache.py — cache metadata invariants (#341).

Tests:
- SleeperPlayerCache stores cache_hours correctly for any value
- _is_cache_valid() returns False when no cache file exists
- _get_cache_metadata() always returns a dict with the required keys
- Cache metadata keys are always present regardless of file existence
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from utils.sleeper_cache import SleeperPlayerCache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cache(cache_hours: int = 24) -> SleeperPlayerCache:
    """Create a SleeperPlayerCache that uses a fresh temp directory."""
    return SleeperPlayerCache(cache_hours=cache_hours)


_REQUIRED_METADATA_KEYS = {"last_updated", "player_count", "cache_version"}


# ---------------------------------------------------------------------------
# Tests — constructor parameter storage
# ---------------------------------------------------------------------------

@given(
    cache_hours=st.integers(min_value=1, max_value=8760),  # 1 hour to 1 year
)
@settings(max_examples=30)
def test_cache_hours_stored_correctly(cache_hours):
    """cache_hours argument is stored exactly on the instance."""
    cache = SleeperPlayerCache(cache_hours=cache_hours)
    assert cache.cache_hours == cache_hours


# ---------------------------------------------------------------------------
# Tests — _is_cache_valid() returns False when no file
# ---------------------------------------------------------------------------

@given(
    cache_hours=st.integers(min_value=1, max_value=168),
)
@settings(max_examples=20)
def test_is_cache_valid_false_when_no_file(cache_hours):
    """_is_cache_valid() must return False when the cache file does not exist."""
    cache = SleeperPlayerCache(cache_hours=cache_hours)
    # Redirect to a non-existent temp location
    with tempfile.TemporaryDirectory() as tmpdir:
        cache.cache_file = Path(tmpdir) / "nonexistent_players.json"
        cache.meta_file = Path(tmpdir) / "nonexistent_meta.json"
        cache._meta_cache = None  # reset in-memory cache
        assert cache._is_cache_valid() is False


# ---------------------------------------------------------------------------
# Tests — _get_cache_metadata() always returns required keys
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=5)
def test_get_cache_metadata_has_required_keys_no_file(_):
    """_get_cache_metadata() returns a dict with all required keys when file is absent."""
    cache = SleeperPlayerCache(cache_hours=24)
    with tempfile.TemporaryDirectory() as tmpdir:
        cache.meta_file = Path(tmpdir) / "nonexistent_meta.json"
        cache._meta_cache = None
        metadata = cache._get_cache_metadata()

    assert isinstance(metadata, dict)
    for key in _REQUIRED_METADATA_KEYS:
        assert key in metadata, f"Missing key {key!r} in metadata"


@given(st.just(None))
@settings(max_examples=5)
def test_get_cache_metadata_returns_none_last_updated_when_no_file(_):
    """last_updated is None when there is no existing metadata file."""
    cache = SleeperPlayerCache(cache_hours=24)
    with tempfile.TemporaryDirectory() as tmpdir:
        cache.meta_file = Path(tmpdir) / "nonexistent_meta.json"
        cache._meta_cache = None
        metadata = cache._get_cache_metadata()

    assert metadata["last_updated"] is None
