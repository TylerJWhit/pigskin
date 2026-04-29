"""Tests for GridironSageStrategy — MCTS + dual-head neural network bidding strategy.

Covers:
  - Strategy interface compliance (calculate_bid returns int >= 0)
  - Should-nominate logic (position need, budget headroom, VOR threshold)
  - MCTS-off mode (VOR heuristic fallback)
  - Neural network fallback when checkpoint is unavailable
  - Feature extraction dimensions
  - Budget guard (never over-spends to complete roster)
  - Strategy string representation
"""

import math
import pytest

from classes.player import Player
from classes.team import Team
from classes.owner import Owner
from strategies.gridiron_sage_strategy import (
    GridironSageStrategy,
    _extract_features,
    _softmax,
    _vor_heuristic_bid,
    FEATURE_DIM,
    TOURNAMENT_MCTS_ITERATIONS,
    TRAINING_MCTS_ITERATIONS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def player_rb():
    return Player("rb1", "Star RB", "RB", "SF", projected_points=300.0, auction_value=55.0)


@pytest.fixture
def player_te():
    return Player("te1", "Elite TE", "TE", "KC", projected_points=200.0, auction_value=35.0)


@pytest.fixture
def player_cheap():
    return Player("k1", "Kicker", "K", "BAL", projected_points=130.0, auction_value=3.0)


@pytest.fixture
def remaining_players():
    return [
        Player(f"p{i}", f"Player {i}", "RB", "XX", projected_points=float(200 - i * 2), auction_value=float(50 - i))
        for i in range(30)
    ]


@pytest.fixture
def team():
    return Team("t1", "o1", "Test Team", 200)


@pytest.fixture
def owner():
    return Owner("o1", "Test Owner")


@pytest.fixture
def strategy_mcts():
    return GridironSageStrategy(mcts_iterations=5, use_mcts=True)


@pytest.fixture
def strategy_no_mcts():
    return GridironSageStrategy(use_mcts=False)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_tournament_mcts_iterations_is_50():
    assert TOURNAMENT_MCTS_ITERATIONS == 50


def test_training_mcts_iterations_is_800():
    assert TRAINING_MCTS_ITERATIONS == 800


def test_feature_dim_is_20():
    assert FEATURE_DIM == 20


# ---------------------------------------------------------------------------
# Strategy interface compliance
# ---------------------------------------------------------------------------


class TestCalculateBidInterface:
    def test_returns_int(self, strategy_mcts, player_rb, team, owner, remaining_players):
        bid = strategy_mcts.calculate_bid(player_rb, team, owner, 0, 200.0, remaining_players)
        assert isinstance(bid, int)

    def test_returns_non_negative(self, strategy_mcts, player_rb, team, owner, remaining_players):
        bid = strategy_mcts.calculate_bid(player_rb, team, owner, 0, 200.0, remaining_players)
        assert bid >= 0

    def test_does_not_raise(self, strategy_mcts, player_rb, team, owner, remaining_players):
        # Should never raise, even with edge-case inputs
        bid = strategy_mcts.calculate_bid(player_rb, team, owner, 100, 105.0, remaining_players)
        assert isinstance(bid, int)

    def test_pass_when_budget_exhausted(self, strategy_mcts, player_rb, team, owner, remaining_players):
        # Remaining budget exactly equals remaining slots → must pass (return 0)
        bid = strategy_mcts.calculate_bid(player_rb, team, owner, 1, 1.0, remaining_players)
        assert bid == 0

    def test_no_mcts_returns_int(self, strategy_no_mcts, player_rb, team, owner, remaining_players):
        bid = strategy_no_mcts.calculate_bid(player_rb, team, owner, 0, 200.0, remaining_players)
        assert isinstance(bid, int)
        assert bid >= 0

    def test_aggression_scales_bid(self, player_rb, team, owner, remaining_players):
        low = GridironSageStrategy(use_mcts=False, aggression=0.5)
        high = GridironSageStrategy(use_mcts=False, aggression=2.0)
        bid_low = low.calculate_bid(player_rb, team, owner, 0, 200.0, remaining_players)
        bid_high = high.calculate_bid(player_rb, team, owner, 0, 200.0, remaining_players)
        # Higher aggression should produce equal-or-higher bid (or both 0 on pass)
        assert bid_high >= bid_low


class TestShouldNominate:
    def test_nominates_elite_player(self, strategy_mcts, player_rb, team, owner):
        # player_rb has auction_value=55 which is > 30 (elite threshold)
        result = strategy_mcts.should_nominate(player_rb, team, owner, 200.0)
        assert result is True

    def test_nominates_mid_tier_player_with_vor(self, strategy_mcts, team, owner):
        mid = Player("mid1", "Mid WR", "WR", "GB", projected_points=150.0, auction_value=15.0)
        mid.vor = 20.0
        result = strategy_mcts.should_nominate(mid, team, owner, 200.0)
        assert result is True

    def test_does_not_nominate_kicker_cheap(self, strategy_mcts, player_cheap, team, owner):
        # Kicker with low value and no VOR — should not nominate
        player_cheap.vor = 0.0
        result = strategy_mcts.should_nominate(player_cheap, team, owner, 200.0)
        assert result is False

    def test_does_not_nominate_when_budget_critically_low(self, strategy_mcts, player_rb, team, owner):
        # Only $3 left — should not nominate
        result = strategy_mcts.should_nominate(player_rb, team, owner, 3.0)
        assert result is False

    def test_returns_bool(self, strategy_mcts, player_rb, team, owner):
        result = strategy_mcts.should_nominate(player_rb, team, owner, 200.0)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------


class TestExtractFeatures:
    def test_returns_correct_length(self, player_rb, team, remaining_players):
        features = _extract_features(player_rb, team, 10.0, 180.0, remaining_players)
        assert len(features) == FEATURE_DIM

    def test_all_finite(self, player_rb, team, remaining_players):
        features = _extract_features(player_rb, team, 10.0, 180.0, remaining_players)
        assert all(math.isfinite(f) for f in features)

    def test_all_bounded(self, player_rb, team, remaining_players):
        features = _extract_features(player_rb, team, 10.0, 180.0, remaining_players)
        # All values must be in a reasonable range (no runaway values)
        assert all(-10.0 <= f <= 10.0 for f in features)

    def test_bias_term_is_one(self, player_rb, team, remaining_players):
        features = _extract_features(player_rb, team, 10.0, 180.0, remaining_players)
        assert features[19] == 1.0

    def test_empty_remaining_players(self, player_rb, team):
        features = _extract_features(player_rb, team, 0.0, 200.0, [])
        assert len(features) == FEATURE_DIM
        assert all(math.isfinite(f) for f in features)


# ---------------------------------------------------------------------------
# VOR heuristic
# ---------------------------------------------------------------------------


class TestVorHeuristic:
    def test_returns_float(self, player_rb, remaining_players):
        bid = _vor_heuristic_bid(player_rb, 0.0, 200.0, remaining_players)
        assert isinstance(bid, (int, float))

    def test_bid_exceeds_current_bid(self, player_rb, remaining_players):
        bid = _vor_heuristic_bid(player_rb, 5.0, 200.0, remaining_players)
        assert bid > 5.0

    def test_bid_within_budget(self, player_rb, remaining_players):
        remaining = 100.0
        bid = _vor_heuristic_bid(player_rb, 0.0, remaining, remaining_players)
        assert bid <= remaining

    def test_zero_budget_does_not_crash(self, player_rb, remaining_players):
        # Edge case: zero remaining budget
        bid = _vor_heuristic_bid(player_rb, 0.0, 0.0, remaining_players)
        assert isinstance(bid, (int, float))


# ---------------------------------------------------------------------------
# Softmax helper
# ---------------------------------------------------------------------------


class TestSoftmax:
    def test_sums_to_one(self):
        logits = [1.0, 2.0, 3.0, 4.0]
        probs = _softmax(logits)
        assert abs(sum(probs) - 1.0) < 1e-6

    def test_all_positive(self):
        logits = [-10.0, 0.0, 10.0]
        probs = _softmax(logits)
        assert all(p > 0 for p in probs)

    def test_uniform_for_equal_logits(self):
        logits = [0.0, 0.0, 0.0, 0.0]
        probs = _softmax(logits)
        assert all(abs(p - 0.25) < 1e-6 for p in probs)

    def test_empty_list(self):
        probs = _softmax([])
        assert probs == []


# ---------------------------------------------------------------------------
# Strategy metadata
# ---------------------------------------------------------------------------


class TestStrategyMetadata:
    def test_name(self, strategy_mcts):
        assert strategy_mcts.name == "GridironSage"

    def test_description_contains_iterations(self):
        s = GridironSageStrategy(mcts_iterations=5)
        assert "5" in s.description

    def test_str_representation(self, strategy_mcts):
        rep = str(strategy_mcts)
        assert "GridironSage" in rep

    def test_checkpoint_loaded_false_without_model(self, strategy_mcts):
        # No model file present in test environment → should be False
        assert strategy_mcts.checkpoint_loaded is False


# ---------------------------------------------------------------------------
# Neural network fallback
# ---------------------------------------------------------------------------


class TestNetworkFallback:
    def test_forward_returns_correct_shapes(self, strategy_mcts):
        features = [0.5] * FEATURE_DIM
        logits, value = strategy_mcts._network.forward(features)
        assert len(logits) > 0
        assert isinstance(value, float)

    def test_value_in_unit_interval(self, strategy_mcts):
        features = [0.5] * FEATURE_DIM
        _, value = strategy_mcts._network.forward(features)
        assert 0.0 <= value <= 1.0

    def test_mcts_off_still_produces_bid(self, strategy_no_mcts, player_rb, team, owner, remaining_players):
        bid = strategy_no_mcts.calculate_bid(player_rb, team, owner, 0, 200.0, remaining_players)
        assert isinstance(bid, int)
        assert bid >= 0
