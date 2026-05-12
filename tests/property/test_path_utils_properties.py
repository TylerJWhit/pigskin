"""Property tests for utils/path_utils.py — path safety invariants (#343).

Tests:
- get_project_root() returns an existing Path
- get_data_dir(), get_config_dir(), get_results_dir() are all under project root
- get_data_file() raises ValueError for path traversal attempts
- get_data_file() strips a leading 'data/' prefix so result is same as without
- safe_file_path() raises ValueError for paths escaping project root
"""
from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from utils.path_utils import (
    get_project_root,
    get_data_dir,
    get_config_dir,
    get_results_dir,
    get_data_file,
    safe_file_path,
)

_ROOT = get_project_root().resolve()
_DATA = get_data_dir().resolve()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_filename(fname: str) -> bool:
    """Return True if the filename is a simple safe name (no path traversal)."""
    try:
        p = Path(fname)
        parts = p.parts
        if not parts:
            return False
        return not any(part in ("..", ".") or "/" in part or "\\" in part for part in parts)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Tests — project layout invariants
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=1)
def test_project_root_exists(_):
    """get_project_root() returns a Path that exists on disk."""
    root = get_project_root()
    assert isinstance(root, Path)
    assert root.exists()


@given(st.just(None))
@settings(max_examples=1)
def test_data_dir_under_project_root(_):
    """get_data_dir() resolves to a path inside the project root."""
    data = get_data_dir().resolve()
    assert str(data).startswith(str(_ROOT))


@given(st.just(None))
@settings(max_examples=1)
def test_config_dir_under_project_root(_):
    """get_config_dir() resolves to a path inside the project root."""
    cfg = get_config_dir().resolve()
    assert str(cfg).startswith(str(_ROOT))


@given(st.just(None))
@settings(max_examples=1)
def test_results_dir_under_project_root(_):
    """get_results_dir() resolves to a path inside the project root."""
    res = get_results_dir().resolve()
    assert str(res).startswith(str(_ROOT))


# ---------------------------------------------------------------------------
# Tests — get_data_file path traversal protection
# ---------------------------------------------------------------------------

@given(
    prefix=st.sampled_from(["../", "../../", "../etc/", "../../etc/passwd"]),
    suffix=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz_"),
)
@settings(max_examples=30)
def test_get_data_file_traversal_raises_value_error(prefix, suffix):
    """get_data_file() with any '../' traversal component raises ValueError."""
    with pytest.raises(ValueError, match="Path traversal"):
        get_data_file(prefix + suffix)


@given(
    filename=st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz0123456789._"),
)
@settings(max_examples=30)
def test_get_data_file_strips_data_prefix(filename):
    """get_data_file('data/X') and get_data_file('X') resolve to the same path."""
    bare = get_data_file(filename)
    with_prefix = get_data_file("data/" + filename)
    assert bare == with_prefix


# ---------------------------------------------------------------------------
# Tests — safe_file_path traversal protection
# ---------------------------------------------------------------------------

@given(
    escape_path=st.sampled_from([
        "/etc/passwd",
        "/tmp/evil",
        "/root/.ssh/id_rsa",
    ]),
)
@settings(max_examples=3)
def test_safe_file_path_absolute_outside_root_raises(escape_path):
    """safe_file_path() raises ValueError for absolute paths outside project root."""
    with pytest.raises(ValueError, match="Path traversal"):
        safe_file_path(escape_path)
