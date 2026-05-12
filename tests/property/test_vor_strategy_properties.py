"""Property tests for strategies/vor_strategy.py — VOR invariants (#333).

Tests:
- aggression and scarcity_weight are stored exactly as given
- scarcity_factors values are all in [0.0, 1.0]
- position_baselines values are all > 0
- _vor_scaling_factor is positive
- calculate_bid always returns a numeric (int/float) value
- calculate_bid never exceeds remaining_budget
- should_nominate always returns a bool
"""
from __future__ import annotations

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.property.conftest import draft_player
from strategies.vor_strategy import VorStrategy


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------

def _make_team(remaining_slots: int = 5, remaining_budget: float = 100.0) -> MagicMock:
    """Minimal team mock with delegation methods VorStrategy relies on."""
    team = MagicMock()
    team.get_remaining_roster_slots.return_value = remaining_slots
    team.calculate_position_priority.return_value = 0.8
    # Clamp bid to remaining_budget, matching real enforce_budget_constraint semantics
    team.enforce_budget_constraint.side_effect = lambda bid, budget: min(bid, budget)
    team.calculate_minimum_budget_needed.return_value = 0.0
    team.budget = int(remaining_budget)
    team.initial_budget = int(remaining_budget)
    team.roster = []
    return team


def _make_owner() -> MagicMock:
    owner = MagicMock()
    owner.get_risk_tolerance.return_value = 0.7
    owner.is_target_player.return_value = False
    return owner


# ---------------------------------------------------------------------------
# Tests — constructor parameter storage
# ---------------------------------------------------------------------------

@given(
    aggression=st.floats(min_value=0.1, max_value=1.5, allow_nan=False, allow_infinity=False),
    scarcity_weight=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=20, deadline=None)
def test_params_stored_correctly(aggression, scarcity_weight):
    """aggression and scarcity_weight are stored exactly as provided."""
    s = VorStrategy(aggression=aggression, scarcity_weight=scarcity_weight)
    assert s.aggression == aggression
    assert s.scarcity_weight == scarcity_weight


# ---------------------------------------------------------------------------
# Tests — internal table invariants
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=5, deadline=None)
def test_scarcity_factors_all_in_range(_):
    """All static scarcity_factors values are in [0.0, 1.0]."""
    s = VorStrategy()
    for pos, factor in s.scarcity_factors.items():
        assert 0.0 <= factor <= 1.0, f"scarcity_factors[{pos!r}] = {factor} out of [0,1]"


@given(st.just(None))
@settings(max_examples=5, deadline=None)
def test_position_baselines_all_positive(_):
    """All position_baselines replacement-level values are strictly positive."""
    s = VorStrategy()
    for pos, baseline in s.position_baselines.items():
        assert baseline > 0, f"position_baselines[{pos!r}] = {baseline} not positive"


@given(st.just(None))
@settings(max_examples=5, deadline=None)
def test_vor_scaling_factor_is_positive(_):
    """_vor_scaling_factor must be positive for meaningful VOR bids."""
    s = VorStrategy()
    assert s._vor_scaling_factor > 0


# ---------------------------------------------------------------------------
# Tests — calculate_bid
# ---------------------------------------------------------------------------

@given(
    player=draft_player(),
    remaining_budget=st.floats(min_value=10.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    current_bid=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50, deadline=None)
def test_calculate_bid_returns_numeric(player, remaining_budget, current_bid):
    """calculate_bid always returns an int or float (never raises, never NaN)."""
    s = VorStrategy()
    team = _make_team(remaining_budget=remaining_budget)
    result = s.calculate_bid(
        player=player,
        team=team,
        owner=_make_owner(),
        current_bid=current_bid,
        remaining_budget=remaining_budget,
        remaining_players=[],
    )
    assert isinstance(result, (int, float))
    assert result == result  # NaN check


@given(
    player=draft_player(),
    remaining_budget=st.floats(min_value=10.0, max_value=500.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50, deadline=None)
def test_calculate_bid_never_exceeds_remaining_budget(player, remaining_budget):
    """calculate_bid never returns more than remaining_budget."""
    s = VorStrategy()
    team = _make_team(remaining_budget=remaining_budget)
    result = s.calculate_bid(
        player=player,
        team=team,
        owner=_make_owner(),
        current_bid=0.0,
        remaining_budget=remaining_budget,
        remaining_players=[],
    )
    assert result <= remaining_budget


# ---------------------------------------------------------------------------
# Tests — should_nominate
# ---------------------------------------------------------------------------

@given(player=draft_player())
@settings(max_examples=50, deadline=None)
def test_should_nominate_returns_bool(player):
    """should_nominate always returns a bool (True or False, never raises)."""
    s = VorStrategy()
    team = _make_team()
    result = s.should_nominate(
        player=player,
        team=team,
        owner=_make_owner(),
        remaining_budget=100.0,
    )
    assert isinstance(result, bool)
