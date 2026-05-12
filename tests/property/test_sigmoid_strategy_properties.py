"""Property tests for strategies/sigmoid_strategy.py — output bounds (#334).

Tests:
- _sigmoid(x) always returns a value in [0.0, 1.0]
- _sigmoid is monotone increasing (larger x → larger output)
- _calculate_draft_progress always returns a float in [0.0, 1.0]
- _calculate_budget_pressure always returns a float in [0.0, 1.0]
- All default parameters are positive
- calculate_bid always returns a numeric value
- should_nominate always returns a bool
"""
from __future__ import annotations

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.property.conftest import draft_player
from strategies.sigmoid_strategy import SigmoidStrategy

_ROSTER_CONFIG = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------

def _make_team(remaining_budget: float = 100.0) -> MagicMock:
    """Minimal team mock for SigmoidStrategy calls."""
    team = MagicMock()
    # Must be real dicts so sum() / .get() work correctly
    team.roster_config = dict(_ROSTER_CONFIG)
    team.roster_requirements = dict(_ROSTER_CONFIG)
    team.roster = []
    team.initial_budget = max(1, int(remaining_budget))
    team.budget = max(1, int(remaining_budget))
    team.get_needs.return_value = {"QB": 1, "RB": 2}
    team.enforce_budget_constraint.side_effect = lambda bid, budget: min(bid, budget)
    team.calculate_minimum_budget_needed.return_value = 0.0
    team.get_remaining_roster_slots.return_value = 8
    team.calculate_position_priority.return_value = 0.8
    return team


def _make_owner() -> MagicMock:
    owner = MagicMock()
    owner.get_risk_tolerance.return_value = 0.7
    owner.is_target_player.return_value = False
    return owner


# ---------------------------------------------------------------------------
# Tests — _sigmoid output bounds
# ---------------------------------------------------------------------------

@given(
    x=st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_sigmoid_output_in_unit_interval(x):
    """_sigmoid(x) always returns a value in [0.0, 1.0]."""
    s = SigmoidStrategy()
    result = s._sigmoid(x)
    assert 0.0 <= result <= 1.0


@given(
    x1=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    delta=st.floats(min_value=0.01, max_value=5.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_sigmoid_is_monotone_increasing(x1, delta):
    """_sigmoid(x1 + delta) >= _sigmoid(x1) for any positive delta (monotone)."""
    s = SigmoidStrategy()
    x2 = x1 + delta
    assert s._sigmoid(x2) >= s._sigmoid(x1)


# ---------------------------------------------------------------------------
# Tests — _calculate_draft_progress bounds
# ---------------------------------------------------------------------------

@given(
    n_players=st.integers(min_value=0, max_value=200),
    high_value_count=st.integers(min_value=0, max_value=50),
)
@settings(max_examples=50)
def test_calculate_draft_progress_in_unit_interval(n_players, high_value_count):
    """_calculate_draft_progress always returns a float in [0.0, 1.0]."""
    s = SigmoidStrategy()
    # Build a simple list of mock players, some with auction_value > 15
    players = []
    for i in range(n_players):
        p = MagicMock()
        p.auction_value = 20.0 if i < high_value_count else 5.0
        players.append(p)
    result = s._calculate_draft_progress(players)
    assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# Tests — _calculate_budget_pressure bounds
# ---------------------------------------------------------------------------

@given(
    remaining_budget=st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50)
def test_calculate_budget_pressure_in_unit_interval(remaining_budget):
    """_calculate_budget_pressure always returns a float in [0.0, 1.0]."""
    s = SigmoidStrategy()
    team = _make_team(remaining_budget=max(remaining_budget, 1.0))
    result = s._calculate_budget_pressure(remaining_budget, team)
    assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# Tests — default parameters
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=1)
def test_default_parameters_all_positive(_):
    """All default parameters in SigmoidStrategy are strictly positive."""
    s = SigmoidStrategy()
    for name, value in s.parameters.items():
        assert value > 0, f"parameters[{name!r}] = {value} is not positive"


# ---------------------------------------------------------------------------
# Tests — calculate_bid and should_nominate
# ---------------------------------------------------------------------------

@given(
    player=draft_player(),
    remaining_budget=st.floats(min_value=20.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    current_bid=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50, deadline=None)
def test_calculate_bid_returns_numeric(player, remaining_budget, current_bid):
    """calculate_bid always returns an int or float (never raises, never NaN)."""
    s = SigmoidStrategy()
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


@given(player=draft_player())
@settings(max_examples=50, deadline=None)
def test_should_nominate_returns_bool(player):
    """should_nominate always returns a bool (True or False, never raises)."""
    s = SigmoidStrategy()
    team = _make_team()
    result = s.should_nominate(
        player=player,
        team=team,
        owner=_make_owner(),
        remaining_budget=100.0,
    )
    assert isinstance(result, bool)
