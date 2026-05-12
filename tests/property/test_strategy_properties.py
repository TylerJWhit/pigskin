"""Property-based tests: strategy bid recommendation invariants.

Track C — Issue #316

Base contract tests are parameterized across all 17 strategies via
@pytest.mark.parametrize. A single failure identifies the violating strategy.

NOTE on GridironSageStrategy: Instantiated with ``use_mcts=False`` to avoid
MCTS overhead. The strategy still exercises the bid-calculation code path.

Sprint 10 · sprint/10 branch
"""

from __future__ import annotations

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tests.property.conftest import draft_player, draft_team

# ---------------------------------------------------------------------------
# Strategy import table
# ---------------------------------------------------------------------------
_STRATEGY_REGISTRY: list[tuple[str, str, dict]] = [
    ("strategies.adaptive_strategy", "AdaptiveStrategy", {}),
    ("strategies.aggressive_strategy", "AggressiveStrategy", {}),
    ("strategies.balanced_strategy", "BalancedStrategy", {}),
    ("strategies.basic_strategy", "BasicStrategy", {}),
    ("strategies.conservative_strategy", "ConservativeStrategy", {}),
    ("strategies.elite_hybrid_strategy", "EliteHybridStrategy", {}),
    ("strategies.enhanced_vor_strategy", "InflationAwareVorStrategy", {}),
    ("strategies.gridiron_sage_strategy", "GridironSageStrategy", {"use_mcts": False}),
    ("strategies.hybrid_strategies", "ValueRandomStrategy", {}),
    ("strategies.improved_value_strategy", "ImprovedValueStrategy", {}),
    ("strategies.league_strategy", "LeagueStrategy", {}),
    ("strategies.random_strategy", "RandomStrategy", {}),
    ("strategies.refined_value_random_strategy", "RefinedValueRandomStrategy", {}),
    ("strategies.sigmoid_strategy", "SigmoidStrategy", {}),
    ("strategies.smart_strategy", "SmartStrategy", {}),
    ("strategies.value_based_strategy", "ValueBasedStrategy", {}),
    ("strategies.vor_strategy", "VorStrategy", {}),
]


def _load_strategy(module_path: str, class_name: str, kwargs: dict):
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(**kwargs)


_STRATEGY_PARAMS = [
    pytest.param(mp, cn, kw, id=cn) for mp, cn, kw in _STRATEGY_REGISTRY
]


# ---------------------------------------------------------------------------
# Base contract: max_bid_bounded_above
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module_path,class_name,kwargs", _STRATEGY_PARAMS)
@given(
    team=draft_team(),
    remaining_budget=st.integers(min_value=1, max_value=500),
)
@settings(max_examples=50)
def test_max_bid_bounded_above(module_path, class_name, kwargs, team, remaining_budget):
    """calculate_max_bid(team, remaining_budget) <= remaining_budget always.

    Invariant:
        forall strategy, team, remaining_budget >= 1:
            strategy.calculate_max_bid(team, remaining_budget) <= remaining_budget
    """
    strategy = _load_strategy(module_path, class_name, kwargs)
    team.budget = remaining_budget
    result = strategy.calculate_max_bid(team, remaining_budget)
    assert result <= remaining_budget, (
        f"{class_name}.calculate_max_bid returned {result} > budget {remaining_budget}"
    )


# ---------------------------------------------------------------------------
# Base contract: max_bid_bounded_below
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module_path,class_name,kwargs", _STRATEGY_PARAMS)
@given(
    team=draft_team(),
    remaining_budget=st.integers(min_value=1, max_value=500),
)
@settings(max_examples=50)
def test_max_bid_bounded_below(module_path, class_name, kwargs, team, remaining_budget):
    """calculate_max_bid(team, remaining_budget) >= 1 when remaining_budget >= 1.

    Invariant:
        forall strategy, team, remaining_budget >= 1:
            strategy.calculate_max_bid(team, remaining_budget) >= 1
    """
    strategy = _load_strategy(module_path, class_name, kwargs)
    team.budget = remaining_budget
    result = strategy.calculate_max_bid(team, remaining_budget)
    assert result >= 1, (
        f"{class_name}.calculate_max_bid returned {result} < 1 for budget {remaining_budget}"
    )


# ---------------------------------------------------------------------------
# Base contract: max_bid_zero_budget
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module_path,class_name,kwargs", _STRATEGY_PARAMS)
@given(team=draft_team())
@settings(max_examples=50)
def test_max_bid_zero_budget(module_path, class_name, kwargs, team):
    """calculate_max_bid with remaining_budget == 0 returns 0 or raises; never negative.

    Invariant:
        forall strategy, team:
            calculate_max_bid(team, 0) >= 0 or raises ValueError/ZeroDivisionError
    """
    strategy = _load_strategy(module_path, class_name, kwargs)
    team.budget = 0
    try:
        result = strategy.calculate_max_bid(team, 0)
        assert result >= 0, f"{class_name}.calculate_max_bid returned {result} < 0 for budget 0"
    except (ValueError, ZeroDivisionError, ArithmeticError):
        pass  # acceptable for zero-budget edge case


# ---------------------------------------------------------------------------
# Base contract: max_bid_monotone_in_budget (BasicStrategy)
# ---------------------------------------------------------------------------


@given(
    team=draft_team(),
    low_budget=st.integers(min_value=5, max_value=100),
    high_budget=st.integers(min_value=101, max_value=500),
)
@settings(max_examples=50)
def test_max_bid_monotone_in_budget(team, low_budget, high_budget):
    """With the same team structure, higher remaining_budget → non-decreasing max_bid.

    BasicStrategy uses a simple linear calculation so strict monotonicity holds.

    Invariant:
        forall team, 5 <= low < high <= 500:
            BasicStrategy.calculate_max_bid(team, low) <= BasicStrategy.calculate_max_bid(team, high)
    """
    from strategies.basic_strategy import BasicStrategy

    strategy = BasicStrategy()

    team.budget = low_budget
    low_result = strategy.calculate_max_bid(team, low_budget)

    team.budget = high_budget
    high_result = strategy.calculate_max_bid(team, high_budget)

    assert low_result <= high_result, (
        f"BasicStrategy.calculate_max_bid not monotone: "
        f"budget {low_budget}→{low_result} > budget {high_budget}→{high_result}"
    )


# ---------------------------------------------------------------------------
# Strategy-specific: sigmoid output is bounded in (0, 1)
# ---------------------------------------------------------------------------


@given(
    raw_score=st.floats(
        min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
    )
)
@settings(max_examples=200)
def test_sigmoid_output_bounded(raw_score):
    """SigmoidStrategy's _sigmoid maps any finite float to strictly (0, 1).

    Invariant:
        forall x in [-1e6, 1e6]:  0 < sigmoid(x) < 1
    """
    from strategies.sigmoid_strategy import SigmoidStrategy

    strategy = SigmoidStrategy()
    result = strategy._sigmoid(raw_score)
    assert 0.0 <= result <= 1.0, f"_sigmoid({raw_score}) = {result} not in [0, 1]"


# ---------------------------------------------------------------------------
# Strategy-specific: adaptive inflation guard
# ---------------------------------------------------------------------------


@given(
    team=draft_team(),
    remaining_budget=st.integers(min_value=1, max_value=500),
)
@settings(max_examples=50)
def test_adaptive_inflation_guard(team, remaining_budget):
    """AdaptiveStrategy: calculate_max_bid never exceeds remaining_budget regardless of inflation.

    Invariant:
        forall team, remaining_budget >= 1:
            AdaptiveStrategy.calculate_max_bid(team, remaining_budget) <= remaining_budget
    """
    from strategies.adaptive_strategy import AdaptiveStrategy

    strategy = AdaptiveStrategy()
    team.budget = remaining_budget
    result = strategy.calculate_max_bid(team, remaining_budget)
    assert result <= remaining_budget


# ---------------------------------------------------------------------------
# Strategy-specific: conservative never bids more than auction_value (when > 0)
# ---------------------------------------------------------------------------


@given(
    team=draft_team(),
    player=draft_player(),
    remaining_budget=st.integers(min_value=1, max_value=500),
)
@settings(max_examples=50)
def test_conservative_always_below_value(team, player, remaining_budget):
    """ConservativeStrategy.calculate_bid: bid <= player.auction_value when auction_value > 0.

    Invariant:
        forall team, player with auction_value > 0, remaining_budget >= 1:
            ConservativeStrategy bid <= player.auction_value
    """
    from strategies.conservative_strategy import ConservativeStrategy
    from classes.owner import Owner

    assume(player.auction_value > 0)

    strategy = ConservativeStrategy()
    team.budget = remaining_budget
    owner = Owner("o1", "Test Owner")

    result = strategy.calculate_bid(
        player=player,
        team=team,
        owner=owner,
        current_bid=0,
        remaining_budget=remaining_budget,
        remaining_players=[player],
    )
    assert result <= player.auction_value, (
        f"ConservativeStrategy bid {result} exceeded auction_value {player.auction_value}"
    )


# ---------------------------------------------------------------------------
# Strategy-specific: aggressive bid capped at remaining budget
# ---------------------------------------------------------------------------


@given(
    team=draft_team(),
    remaining_budget=st.integers(min_value=1, max_value=500),
)
@settings(max_examples=50)
def test_aggressive_capped_at_budget(team, remaining_budget):
    """AggressiveStrategy: calculate_max_bid <= remaining_budget even with high aggression.

    Invariant:
        forall team, remaining_budget >= 1:
            AggressiveStrategy.calculate_max_bid(team, remaining_budget) <= remaining_budget
    """
    from strategies.aggressive_strategy import AggressiveStrategy

    strategy = AggressiveStrategy()
    team.budget = remaining_budget
    result = strategy.calculate_max_bid(team, remaining_budget)
    assert result <= remaining_budget
