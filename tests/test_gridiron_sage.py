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


# ---------------------------------------------------------------------------
# Regression tests — Team.get_remaining_roster_slots() type mismatch (issue #84)
#
# get_remaining_roster_slots() returns int (total remaining slots).
# Previously the strategy called .get() / .values() on that int, which silently
# failed inside try/except blocks, leaving features 9-14 frozen at 0.0 and the
# budget guard / should_nominate reserve check completely inoperative.
# ---------------------------------------------------------------------------


class TestRosterSlotsTypeMismatch:
    """Regression tests for the get_remaining_roster_slots() int vs dict bug."""

    def test_position_need_features_nonzero_for_empty_roster(self, player_rb, remaining_players):
        """Features 9-12 must be > 0 for an empty team that needs all positions.

        Before the fix these were always 0.0 because slots.get() was called on an int.
        """
        team = Team("t_reg", "o1", "Regression Team", 200)
        features = _extract_features(player_rb, team, 10.0, 190.0, remaining_players)
        # RB need (feature 10) must be > 0 since the roster is empty
        assert features[10] > 0.0, (
            "Feature 10 (RB need fraction) should be non-zero for an empty team; "
            "likely still calling .get() on an int return from get_remaining_roster_slots()"
        )

    def test_position_need_features_zero_when_position_full(self, remaining_players):
        """Feature for a filled position must be 0.0."""
        team = Team("t_full", "o1", "Full QB Team", 200)
        # Fill both QB slots
        for i in range(2):
            qb = Player(f"qb{i}", f"QB {i}", "QB", "NE", projected_points=250.0, auction_value=20.0)
            team.add_player(qb, 10)
        features = _extract_features(
            Player("rb_test", "Test RB", "RB", "KC", projected_points=200.0, auction_value=30.0),
            team,
            0.0,
            180.0,
            remaining_players,
        )
        # QB need (feature 9) must be 0 since QB slots are full
        assert features[9] == 0.0, (
            "Feature 9 (QB need fraction) should be 0.0 when all QB slots are filled"
        )

    def test_feature_14_nonzero_for_incomplete_roster(self, player_rb, remaining_players):
        """Feature 14 (min budget to fill / remaining budget) must be > 0 for an empty team."""
        team = Team("t_f14", "o1", "Budget Test Team", 200)
        features = _extract_features(player_rb, team, 0.0, 200.0, remaining_players)
        assert features[14] > 0.0, (
            "Feature 14 (budget headroom ratio) should be > 0 for an empty roster; "
            "likely still calling .values() on the int returned by get_remaining_roster_slots()"
        )

    def test_budget_guard_passes_when_budget_just_enough(self, player_rb, owner, remaining_players):
        """calculate_bid must return 0 (pass) when remaining budget == remaining roster slots.

        This exercises the budget guard that previously silently failed due to the
        type mismatch — the guard was never applied so the team could overbid.
        """
        strategy = GridironSageStrategy(use_mcts=False)
        team = Team("t_guard", "o1", "Guard Test Team", 200)
        # Default roster_config has 18 total slots (QB:2, RB:6, WR:6, TE:2, K:1, DST:1)
        total_slots = sum(team.roster_config.values())
        # Remaining budget == total slots means every dollar is reserved → must pass
        bid = strategy.calculate_bid(player_rb, team, owner, 1, float(total_slots), remaining_players)
        assert bid == 0, (
            "calculate_bid should return 0 when remaining_budget equals remaining roster slots; "
            "budget guard was previously inoperative due to the type mismatch bug"
        )

    def test_min_budget_reserve_uses_integer_return(self):
        """_min_budget_reserve must return the total slot count, not 1.0 (the fallback).

        Before the fix, sum(get_slots().values()) raised AttributeError (int has no
        .values()), which was silently caught, and the method returned the hardcoded
        fallback of 1.0 instead of the actual slot count.
        """
        from strategies.gridiron_sage_strategy import _GridironSageMCTS, _GridironSageNetwork
        team = Team("t_reserve", "o1", "Reserve Test Team", 200)
        network = _GridironSageNetwork()
        mcts = _GridironSageMCTS(network, iterations=5)
        reserve = mcts._min_budget_reserve(team)
        total_slots = sum(team.roster_config.values())
        assert reserve == float(total_slots), (
            f"_min_budget_reserve should return {total_slots} (total roster slots) "
            f"but returned {reserve}; likely still calling .values() on an int"
        )

    def test_should_nominate_respects_budget_reserve(self, player_rb, owner):
        """should_nominate must decline when remaining_budget <= remaining_slots + 2.

        Before the fix the budget headroom check was silently skipped, so the
        strategy would nominate even with a dangerously low budget.
        """
        strategy = GridironSageStrategy(use_mcts=False)
        team = Team("t_nom", "o1", "Nominate Test Team", 200)
        total_slots = sum(team.roster_config.values())
        # Budget == slots + 1 is within the reserve window → should NOT nominate
        result = strategy.should_nominate(player_rb, team, owner, float(total_slots) + 1)
        assert result is False, (
            "should_nominate should return False when budget is within the slot reserve; "
            "budget headroom check was previously inoperative due to the type mismatch bug"
        )

    def test_get_remaining_roster_slots_by_position_returns_dict(self):
        """Team.get_remaining_roster_slots_by_position() must return Dict[str, int]."""
        team = Team("t_dict", "o1", "Dict Test Team", 200)
        result = team.get_remaining_roster_slots_by_position()
        assert isinstance(result, dict), "Expected dict return from get_remaining_roster_slots_by_position"
        assert all(isinstance(v, int) for v in result.values()), "All slot counts must be int"

    def test_get_remaining_roster_slots_by_position_decrements_on_add(self):
        """Slot count for a position must decrease when a player is added."""
        team = Team("t_decr", "o1", "Decrement Test Team", 200)
        before = team.get_remaining_roster_slots_by_position().get("RB", 0)
        rb = Player("rb_test", "Test RB", "RB", "KC", projected_points=200.0, auction_value=30.0)
        team.add_player(rb, 10)
        after = team.get_remaining_roster_slots_by_position().get("RB", 0)
        assert after == before - 1, (
            f"RB slot count should decrease by 1 after adding an RB: got before={before}, after={after}"
        )
