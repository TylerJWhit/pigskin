"""Property tests for strategies/strategy_registry.py — security & config (#332).

Tests:
- create() with any valid key returns a Strategy instance
- create() with any unknown key raises ValueError (fuzz arbitrary strings)
- list_available() is sorted
- list_available() is stable across repeated calls
- from_dict() with any base_class not in the hardcoded allowlist raises ValueError
- Arbitrary non-identifier strings as base_class are always rejected (security)
- from_dict() with a valid allowlisted base_class returns the correct Strategy type
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from strategies import AVAILABLE_STRATEGIES
from strategies.base_strategy import Strategy
from strategies.strategy_registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Known allowlisted base class names (kept in sync with StrategyRegistry source)
# ---------------------------------------------------------------------------
_ALLOWLISTED_BASE_CLASSES = frozenset({
    "VorStrategy",
    "SigmoidStrategy",
    "AggressiveStrategy",
    "ConservativeStrategy",
    "ValueBasedStrategy",
    "ImprovedValueStrategy",
    "AdaptiveStrategy",
    "RandomStrategy",
    "SmartStrategy",
    "BalancedStrategy",
    "BasicStrategy",
    "EliteHybridStrategy",
    "InflationAwareVorStrategy",
    "ValueRandomStrategy",
    "ValueSmartStrategy",
    "LeagueStrategy",
    "RefinedValueRandomStrategy",
})

_VALID_KEYS = sorted(AVAILABLE_STRATEGIES.keys())

_MINIMAL_CONFIG_BASE: dict = {
    "name": "test",
    "display_name": "Test Strategy",
    "description": "A test strategy for property testing.",
}


# ---------------------------------------------------------------------------
# Tests — create() by key
# ---------------------------------------------------------------------------

@given(key=st.sampled_from(_VALID_KEYS))
@settings(max_examples=len(_VALID_KEYS))
def test_create_valid_key_returns_strategy(key):
    """StrategyRegistry.create() with any valid key returns a Strategy instance."""
    result = StrategyRegistry.create(key)
    assert isinstance(result, Strategy)


@given(
    key=st.text(min_size=1, max_size=50).filter(lambda k: k not in AVAILABLE_STRATEGIES)
)
@settings(max_examples=50)
def test_create_unknown_key_raises_value_error(key):
    """create() with any key not in AVAILABLE_STRATEGIES always raises ValueError."""
    with pytest.raises(ValueError):
        StrategyRegistry.create(key)


# ---------------------------------------------------------------------------
# Tests — list_available()
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=1)
def test_list_available_is_sorted(_):
    """list_available() returns keys in sorted (alphabetical) order."""
    available = StrategyRegistry.list_available()
    assert available == sorted(available)


@given(st.just(None))
@settings(max_examples=5)
def test_list_available_is_stable_across_calls(_):
    """Calling list_available() twice returns identical results."""
    first = StrategyRegistry.list_available()
    second = StrategyRegistry.list_available()
    assert first == second


# ---------------------------------------------------------------------------
# Tests — from_dict() base_class allowlist security
# ---------------------------------------------------------------------------

@given(
    base_class=st.text(min_size=1, max_size=100).filter(
        lambda b: b not in _ALLOWLISTED_BASE_CLASSES
    )
)
@settings(max_examples=50)
def test_from_dict_unlisted_base_class_raises(base_class):
    """Any base_class not in the hardcoded allowlist must raise ValueError."""
    config = {**_MINIMAL_CONFIG_BASE, "base_class": base_class}
    with pytest.raises(ValueError):
        StrategyRegistry.from_dict(config)


@given(
    base_class=st.text(
        alphabet=st.characters(
            whitelist_categories=["P", "S", "Z", "C"],  # punctuation, symbols, spaces, control
        ),
        min_size=1,
        max_size=50,
    )
)
@settings(max_examples=50)
def test_arbitrary_non_identifier_base_class_rejected(base_class):
    """Non-identifier unicode strings as base_class are always rejected."""
    config = {**_MINIMAL_CONFIG_BASE, "base_class": base_class}
    with pytest.raises(Exception):  # ValueError from allowlist check or Pydantic validation
        StrategyRegistry.from_dict(config)


# ---------------------------------------------------------------------------
# Tests — from_dict() valid path
# ---------------------------------------------------------------------------

@given(base_class=st.sampled_from(sorted(_ALLOWLISTED_BASE_CLASSES)))
@settings(max_examples=len(_ALLOWLISTED_BASE_CLASSES))
def test_from_dict_valid_base_class_returns_strategy(base_class):
    """from_dict() with any allowlisted base_class returns a Strategy instance."""
    config = {**_MINIMAL_CONFIG_BASE, "base_class": base_class}
    result = StrategyRegistry.from_dict(config)
    assert isinstance(result, Strategy)
