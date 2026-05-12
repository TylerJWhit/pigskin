"""Property tests for utils/cheatsheet_parser.py — stub interface invariants (#342).

Tests:
- get_cheatsheet_parser() always returns a CheatsheetParser instance
- find_undervalued_players_simple(threshold) raises NotImplementedError for any threshold
- find_undervalued_players(threshold) raises NotImplementedError for any threshold
- get_all_players() raises NotImplementedError
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from utils.cheatsheet_parser import CheatsheetParser, get_cheatsheet_parser


# ---------------------------------------------------------------------------
# Factory invariants
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=5)
def test_factory_returns_cheatsheet_parser(_):
    """get_cheatsheet_parser() always returns a CheatsheetParser instance."""
    parser = get_cheatsheet_parser()
    assert isinstance(parser, CheatsheetParser)


@given(st.just(None))
@settings(max_examples=3)
def test_factory_returns_new_instance_each_call(_):
    """Each get_cheatsheet_parser() call returns a distinct object."""
    p1 = get_cheatsheet_parser()
    p2 = get_cheatsheet_parser()
    assert p1 is not p2


# ---------------------------------------------------------------------------
# Stub method invariants — all public methods raise NotImplementedError
# ---------------------------------------------------------------------------

@given(
    threshold=st.floats(
        min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
    )
)
@settings(max_examples=30)
def test_find_undervalued_players_simple_not_implemented(threshold):
    """find_undervalued_players_simple() raises NotImplementedError for any threshold."""
    parser = get_cheatsheet_parser()
    with pytest.raises(NotImplementedError):
        parser.find_undervalued_players_simple(threshold)


@given(
    threshold=st.floats(
        min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
    )
)
@settings(max_examples=30)
def test_find_undervalued_players_not_implemented(threshold):
    """find_undervalued_players() raises NotImplementedError for any threshold."""
    parser = get_cheatsheet_parser()
    with pytest.raises(NotImplementedError):
        parser.find_undervalued_players(threshold)


@given(st.just(None))
@settings(max_examples=5)
def test_get_all_players_not_implemented(_):
    """get_all_players() raises NotImplementedError."""
    parser = get_cheatsheet_parser()
    with pytest.raises(NotImplementedError):
        parser.get_all_players()
