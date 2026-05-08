"""Sprint 9 QA tests — Issue #170: _get_cache_metadata reads disk on every call.

Expected outcome:
  - FAILS before fix  (_get_cache_metadata opens meta_file N times for N calls)
  - PASSES after fix  (result is cached in-memory; open() called exactly once)
"""

import json
import pytest
from unittest.mock import patch
from pathlib import Path


# ── helpers / fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def cache_instance(tmp_path):
    """Return a SleeperPlayerCache with all heavy I/O dependencies mocked out."""
    with (
        patch("utils.sleeper_cache.SleeperAPI"),
        patch("utils.sleeper_cache.get_data_dir", return_value=tmp_path),
        patch("utils.sleeper_cache.ensure_dir_exists"),
    ):
        from utils.sleeper_cache import SleeperPlayerCache

        cache = SleeperPlayerCache()
    return cache, tmp_path


def _write_meta(meta_dir: Path, data: dict | None = None) -> Path:
    """Write a meta JSON file and return its path."""
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta_file = meta_dir / "sleeper_players_meta.json"
    payload = data or {"last_updated": None, "player_count": 0, "cache_version": "1.0"}
    meta_file.write_text(json.dumps(payload))
    return meta_file


# ── Issue #170 tests ──────────────────────────────────────────────────────────


class TestGetCacheMetadataDiskReads:
    """Issue #170: _get_cache_metadata must not open the file on every invocation."""

    def test_get_cache_metadata_opens_file_only_once_across_multiple_calls(
        self, cache_instance
    ):
        """_get_cache_metadata() called 5× must open the meta file exactly 1 time.

        Currently FAILS: open() is called once per invocation (5 times total).
        After fix (add in-memory cache / lru_cache): open() called exactly once.
        """
        cache, tmp_path = cache_instance
        meta_file = _write_meta(tmp_path / "cache")

        open_calls: list[str] = []
        real_open = open

        def counting_open(path, *args, **kwargs):
            if str(path) == str(meta_file):
                open_calls.append(str(path))
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=counting_open):
            for _ in range(5):
                cache._get_cache_metadata()

        assert len(open_calls) == 1, (
            f"_get_cache_metadata() opened the meta file {len(open_calls)} time(s); "
            "expected exactly 1 — the result must be cached in-memory (Issue #170)."
        )

    def test_get_cache_metadata_returns_consistent_result_across_calls(
        self, cache_instance
    ):
        """Repeated calls must return identical results without re-parsing disk.

        Currently PASSES (the return value is consistent because the file is unchanged),
        but included as a regression guard: after adding caching, the results must
        still be consistent.
        """
        cache, tmp_path = cache_instance
        _write_meta(tmp_path / "cache", {"last_updated": "2026-01-01T00:00:00", "player_count": 42, "cache_version": "1.0"})

        results = [cache._get_cache_metadata() for _ in range(3)]
        assert all(r == results[0] for r in results), (
            "_get_cache_metadata() returned inconsistent results across calls."
        )

    def test_get_cache_metadata_n_rapid_calls_single_io(self, cache_instance):
        """10 rapid successive calls → exactly 1 disk read (not 10).

        Currently FAILS: each call hits disk.
        After fix: cached after first read.
        """
        cache, tmp_path = cache_instance
        meta_file = _write_meta(tmp_path / "cache")

        read_count = [0]
        real_open = open

        def tracking_open(path, *args, **kwargs):
            if Path(path) == meta_file:
                read_count[0] += 1
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=tracking_open):
            for _ in range(10):
                cache._get_cache_metadata()

        assert read_count[0] == 1, (
            f"Expected 1 disk read for 10 calls to _get_cache_metadata(); "
            f"got {read_count[0]}.  Add in-memory caching to fix Issue #170."
        )

    def test_get_cache_metadata_returns_default_when_file_missing(self, cache_instance):
        """When meta file does not exist, _get_cache_metadata returns default dict.

        Sanity test that must continue to pass before and after the fix.
        """
        cache, tmp_path = cache_instance
        # Do NOT create the meta file
        result = cache._get_cache_metadata()
        assert result["last_updated"] is None
        assert "player_count" in result
