"""Property tests for strategies/base_strategy.py — Strategy ABC (#331).

Tests:
- set_parameter / get_parameter round-trip
- get_parameter returns default when key absent
- __init_subclass__ wrapping: calculate_bid returns 0 when raw <= current_bid
- __init_subclass__ wrapping: calculate_bid returns positive when raw beats bid
- __init_subclass__ wrapping: should_nominate blocks when slots<=2 & priority<0.3
- _calculate_safe_bid_limit always returns a positive integer
- str(strategy) contains strategy name
"""
from __future__ import annotations

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from strategies.base_strategy import Strategy


# ---------------------------------------------------------------------------
# Minimal concrete subclasses — defined at module level so __init_subclass__
# fires once at class-definition time (not per test invocation).
# ---------------------------------------------------------------------------

class _HighBidStrategy(Strategy):
    """Always returns a very high raw bid (999.0), used to test clamping."""

    def __init__(self, raw_bid: float = 999.0):
        super().__init__("test-high", "test strategy high bid")
        self._raw_bid = raw_bid

    def calculate_bid(self, player, team, owner, current_bid, remaining_budget, remaining_players):  # noqa: D102
        return self._raw_bid

    def should_nominate(self, player, team, owner, remaining_budget):  # noqa: D102
        return True


class _ZeroBidStrategy(Strategy):
    """Always returns 0 as the raw bid — wrapper must short-circuit to 0."""

    def __init__(self):
        super().__init__("test-zero", "test strategy zero bid")

    def calculate_bid(self, player, team, owner, current_bid, remaining_budget, remaining_players):  # noqa: D102
        return 0

    def should_nominate(self, player, team, owner, remaining_budget):  # noqa: D102
        return True


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_team(remaining_slots: int = 10, priority: float = 0.8) -> MagicMock:
    """Return a minimal MagicMock team with the delegation methods configured."""
    team = MagicMock()
    team.get_remaining_roster_slots.return_value = remaining_slots
    team.calculate_position_priority.return_value = priority
    # enforce_budget_constraint: clamp bid to remaining_budget
    team.enforce_budget_constraint.side_effect = lambda bid, budget: min(bid, budget)
    # calculate_minimum_budget_needed: no reservation by default
    team.calculate_minimum_budget_needed.return_value = 0.0
    team.budget = 200
    team.initial_budget = 200
    team.roster = []
    return team


# ---------------------------------------------------------------------------
# Tests — parameter persistence
# ---------------------------------------------------------------------------

@given(
    key=st.text(min_size=1, max_size=30),
    value=st.one_of(
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(),
    ),
)
@settings(max_examples=50)
def test_set_get_parameter_round_trip(key, value):
    """set_parameter(k, v) → get_parameter(k) returns v unchanged."""
    s = _HighBidStrategy()
    s.set_parameter(key, value)
    assert s.get_parameter(key) == value


@given(
    key=st.text(min_size=1, max_size=30),
    default=st.one_of(st.none(), st.integers(), st.text()),
)
@settings(max_examples=30)
def test_get_missing_parameter_returns_default(key, default):
    """get_parameter on an absent key returns the supplied default."""
    s = _HighBidStrategy()
    s.parameters = {}
    assert s.get_parameter(key, default) == default


# ---------------------------------------------------------------------------
# Tests — __init_subclass__ calculate_bid wrapping
# ---------------------------------------------------------------------------

@given(
    current_bid=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50)
def test_wrapped_calculate_bid_returns_zero_when_raw_is_zero(current_bid):
    """When raw bid is 0 (<= any current_bid), the wrapped result is 0."""
    s = _ZeroBidStrategy()
    team = _make_team()
    result = s.calculate_bid(
        player=MagicMock(position="QB"),
        team=team,
        owner=MagicMock(),
        current_bid=current_bid,
        remaining_budget=200.0,
        remaining_players=[],
    )
    assert result == 0


@given(
    current_bid=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50)
def test_wrapped_calculate_bid_returns_positive_when_raw_beats_current(current_bid):
    """When raw bid (999) > current_bid, the wrapped result is > 0."""
    s = _HighBidStrategy(raw_bid=999.0)
    team = _make_team()
    result = s.calculate_bid(
        player=MagicMock(position="RB"),
        team=team,
        owner=MagicMock(),
        current_bid=current_bid,
        remaining_budget=200.0,
        remaining_players=[],
    )
    assert result > 0


# ---------------------------------------------------------------------------
# Tests — __init_subclass__ should_nominate wrapping
# ---------------------------------------------------------------------------

@given(
    slots=st.integers(min_value=0, max_value=2),
    priority=st.floats(min_value=0.0, max_value=0.29, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=30)
def test_wrapped_should_nominate_blocks_when_few_slots_low_priority(slots, priority):
    """slots<=2 AND priority<0.3 → should_nominate returns False via wrapper."""
    s = _HighBidStrategy()
    team = _make_team(remaining_slots=slots, priority=priority)
    result = s.should_nominate(
        player=MagicMock(position="K"),
        team=team,
        owner=MagicMock(),
        remaining_budget=50.0,
    )
    assert result is False


@given(
    slots=st.integers(min_value=3, max_value=15),
    priority=st.floats(min_value=0.3, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=30)
def test_wrapped_should_nominate_delegates_when_slots_ok(slots, priority):
    """When slots>2 or priority>=0.3, should_nominate delegates to the original (True)."""
    s = _HighBidStrategy()
    team = _make_team(remaining_slots=slots, priority=priority)
    result = s.should_nominate(
        player=MagicMock(position="WR"),
        team=team,
        owner=MagicMock(),
        remaining_budget=100.0,
    )
    # The original always returns True, so wrapped result should also be True
    assert result is True


# ---------------------------------------------------------------------------
# Tests — _calculate_safe_bid_limit
# ---------------------------------------------------------------------------

@given(
    remaining_budget=st.floats(min_value=10.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    max_pct=st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50)
def test_calculate_safe_bid_limit_is_positive_integer(remaining_budget, max_pct):
    """_calculate_safe_bid_limit always returns an int >= 1."""
    s = _HighBidStrategy()
    team = _make_team()
    result = s._calculate_safe_bid_limit(team, remaining_budget, max_pct)
    assert isinstance(result, int)
    assert result >= 1


# ---------------------------------------------------------------------------
# Tests — str representation
# ---------------------------------------------------------------------------

@given(name=st.text(min_size=1, max_size=30))
@settings(max_examples=20)
def test_str_representation_contains_name(name):
    """str(strategy) contains the strategy name."""
    s = _HighBidStrategy()
    s.name = name
    assert name in str(s)
