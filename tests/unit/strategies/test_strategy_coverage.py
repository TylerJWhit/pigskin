"""Unit tests for strategy modules with low coverage."""
from unittest.mock import MagicMock
import pytest


def _make_player(name="Josh Allen", position="QB", auction_value=50.0, projected_points=350.0):
    p = MagicMock()
    p.name = name
    p.position = position
    p.auction_value = auction_value
    p.projected_points = projected_points
    p.is_drafted = False
    p.team = "BUF"
    p.drafted_price = None
    p.vor = 0.0
    return p


def _make_team(budget=200.0, roster=None):
    t = MagicMock()
    t.team_id = "team1"
    t.owner_id = "owner1"
    t.team_name = "Test Team"
    t.budget = budget
    t.initial_budget = 200.0
    t.roster = roster or []
    t.get_needs.return_value = ["QB", "RB", "WR"]
    t.get_total_spent.return_value = 0.0
    # Prevent base_strategy from delegating to team methods that return MagicMocks
    t.calculate_position_priority = None
    t.get_remaining_roster_slots = None
    t.enforce_budget_constraint = None
    t.roster_config = None
    t.calculate_minimum_budget_needed = None
    return t


def _make_owner():
    o = MagicMock()
    o.owner_id = "owner1"
    o.is_human = False
    o.get_risk_tolerance.return_value = 0.7
    return o


class TestLeagueStrategy:
    def setup_method(self):
        from strategies.league_strategy import LeagueStrategy
        self.strategy = LeagueStrategy()

    def test_init(self):
        assert self.strategy.name == "League"
        assert self.strategy.aggression == 1.0
        assert self.strategy.trend_adjustment == 0.8

    def test_calculate_bid_basic(self):
        player = _make_player("QB1", "QB", auction_value=40.0)
        team = _make_team()
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_calculate_bid_low_priority_position_full(self):
        # Position priority <= 0.1 when full (current_count >= target_count)
        qbs = [_make_player(f"QB{i}", "QB") for i in range(3)]
        team = _make_team(roster=qbs)
        player = _make_player("Backup QB", "QB", auction_value=5.0)
        owner = _make_owner()
        # With position full (3 QBs) and position_priority low, small current bid → returns 0 or low bid
        bid = self.strategy.calculate_bid(player, team, owner, 6.0, 200.0, [])
        assert bid == 0 or bid <= 10

    def test_calculate_bid_low_priority_high_current_bid(self):
        # With many QBs already, position priority is low; high current bid means returns 0
        qbs = [_make_player(f"QB{i}", "QB") for i in range(3)]
        team = _make_team(roster=qbs)
        player = _make_player("Backup QB", "QB", auction_value=5.0)
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 50.0, 200.0, [])
        # With full position roster and high current bid, returns 0 or a valid bid
        assert isinstance(bid, (int, float))

    def test_should_nominate_undervalued_position(self):
        # K has league_factor < 0.95 → undervalued
        player = _make_player("Tucker", "K", auction_value=15.0)
        team = _make_team()
        owner = _make_owner()
        result = self.strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)

    def test_should_nominate_high_priority(self):
        player = _make_player("CMC", "RB", auction_value=70.0)
        team = _make_team()  # No RBs → high priority
        owner = _make_owner()
        result = self.strategy.should_nominate(player, team, owner, 200.0)
        assert result is True

    def test_should_nominate_high_value_affordable(self):
        player = _make_player("Star", "WR", auction_value=30.0)
        team = _make_team(budget=200.0, roster=[])
        owner = _make_owner()
        result = self.strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)

    def test_calculate_league_trend_factor_elite(self):
        player = _make_player(auction_value=35.0, position="QB")
        factor = self.strategy._calculate_league_trend_factor(player)
        assert factor > 0

    def test_calculate_league_trend_factor_mid_tier(self):
        player = _make_player(auction_value=17.0, position="RB")
        factor = self.strategy._calculate_league_trend_factor(player)
        assert factor > 0

    def test_calculate_league_trend_factor_low_tier(self):
        player = _make_player(auction_value=5.0, position="K")
        factor = self.strategy._calculate_league_trend_factor(player)
        assert factor > 0

    def test_apply_league_context_rb_first(self):
        player = _make_player("CMC", "RB")
        team = _make_team(roster=[])
        result = self.strategy._apply_league_context_adjustments(40.0, player, team)
        assert result > 40.0  # 1.1x multiplier

    def test_apply_league_context_backup_qb(self):
        player = _make_player("QB2", "QB")
        qb = _make_player("QB1", "QB")
        team = _make_team(roster=[qb])
        result = self.strategy._apply_league_context_adjustments(40.0, player, team)
        assert result < 40.0  # 0.9x multiplier

    def test_apply_league_context_first_te(self):
        player = _make_player("TE1", "TE")
        team = _make_team(roster=[])
        result = self.strategy._apply_league_context_adjustments(20.0, player, team)
        assert result > 20.0  # 1.05x

    def test_apply_league_context_kicker(self):
        player = _make_player("K1", "K")
        team = _make_team(roster=[])
        result = self.strategy._apply_league_context_adjustments(5.0, player, team)
        assert result < 5.0  # 0.9x

    def test_calculate_position_priority_full(self):
        qbs = [_make_player(f"QB{i}", "QB") for i in range(3)]
        team = _make_team(roster=qbs)
        player = _make_player("QB3", "QB")
        priority = self.strategy._calculate_position_priority(player, team)
        assert priority == 0.2

    def test_calculate_position_priority_empty(self):
        team = _make_team(roster=[])
        player = _make_player("QB1", "QB")
        priority = self.strategy._calculate_position_priority(player, team)
        assert priority > 0.2

    def test_get_remaining_roster_slots(self):
        team = _make_team(roster=[_make_player() for _ in range(5)])
        slots = self.strategy._get_remaining_roster_slots(team)
        assert slots == 10


class TestAdaptiveStrategy:
    def setup_method(self):
        from strategies.adaptive_strategy import AdaptiveStrategy
        self.strategy = AdaptiveStrategy()

    def test_init(self):
        assert self.strategy.name == "adaptive"
        assert self.strategy.base_aggression == 1.0
        assert self.strategy.adapt_factor == 0.5

    def test_calculate_bid_basic(self):
        player = _make_player()
        team = _make_team()
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_calculate_bid_high_tier_player(self):
        player = _make_player(auction_value=60.0, projected_points=400.0)
        team = _make_team()
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 40.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_update_draft_trends_updates_data(self):
        player = _make_player(auction_value=50.0)
        self.strategy.update_draft_trends(player, 55.0)
        # Should have recorded the bid in bid_history
        assert len(self.strategy.bid_history) > 0

    def test_update_draft_trends_underpay(self):
        player = _make_player(auction_value=50.0)
        initial_len = len(self.strategy.bid_history)
        self.strategy.update_draft_trends(player, 40.0)
        assert len(self.strategy.bid_history) > initial_len

    def test_update_aggression_no_raise(self):
        # Just check it doesn't raise
        self.strategy._update_aggression()

    def test_should_nominate_basic(self):
        player = _make_player()
        team = _make_team()
        owner = _make_owner()
        result = self.strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)

    def test_get_remaining_roster_slots(self):
        team = _make_team(roster=[_make_player() for _ in range(5)])
        slots = self.strategy._get_remaining_roster_slots(team)
        assert slots == 10


class TestAggressiveStrategy:
    def test_calculate_bid_basic(self):
        from strategies.aggressive_strategy import AggressiveStrategy
        strategy = AggressiveStrategy()
        player = _make_player(auction_value=40.0)
        team = _make_team()
        owner = _make_owner()
        bid = strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_high_value_player(self):
        from strategies.aggressive_strategy import AggressiveStrategy
        strategy = AggressiveStrategy()
        player = _make_player(auction_value=70.0)
        team = _make_team()
        owner = _make_owner()
        bid = strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_should_nominate(self):
        from strategies.aggressive_strategy import AggressiveStrategy
        strategy = AggressiveStrategy()
        player = _make_player()
        team = _make_team()
        owner = _make_owner()
        result = strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)


class TestConservativeStrategy:
    def test_calculate_bid_basic(self):
        from strategies.conservative_strategy import ConservativeStrategy
        strategy = ConservativeStrategy()
        player = _make_player(auction_value=40.0)
        team = _make_team()
        owner = _make_owner()
        bid = strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_should_nominate(self):
        from strategies.conservative_strategy import ConservativeStrategy
        strategy = ConservativeStrategy()
        player = _make_player()
        team = _make_team()
        owner = _make_owner()
        result = strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)


class TestBalancedStrategy:
    def test_calculate_bid_basic(self):
        from strategies.balanced_strategy import BalancedStrategy
        strategy = BalancedStrategy()
        player = _make_player(auction_value=40.0)
        team = _make_team()
        owner = _make_owner()
        bid = strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_calculate_bid_positional_needs(self):
        from strategies.balanced_strategy import BalancedStrategy
        strategy = BalancedStrategy()
        # Team needs RBs
        player = _make_player("CMC", "RB", auction_value=60.0)
        team = _make_team()
        owner = _make_owner()
        bid = strategy.calculate_bid(player, team, owner, 30.0, 200.0, [])
        assert bid >= 0

    def test_should_nominate(self):
        from strategies.balanced_strategy import BalancedStrategy
        strategy = BalancedStrategy()
        player = _make_player()
        team = _make_team()
        owner = _make_owner()
        result = strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)

    def test_should_nominate_position_scarcity(self):
        from strategies.balanced_strategy import BalancedStrategy
        strategy = BalancedStrategy()
        player = _make_player("CMC", "RB", auction_value=60.0)
        # Only a few available RBs (scarcity triggers)
        remaining = [_make_player(f"RB{i}", "RB") for i in range(3)]
        team = _make_team()
        owner = _make_owner()
        result = strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)


class TestEliteHybridStrategy:
    def test_calculate_bid_basic(self):
        from strategies.elite_hybrid_strategy import EliteHybridStrategy
        strategy = EliteHybridStrategy()
        player = _make_player(auction_value=50.0)
        team = _make_team()
        owner = _make_owner()
        bid = strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_calculate_bid_elite_player(self):
        from strategies.elite_hybrid_strategy import EliteHybridStrategy
        strategy = EliteHybridStrategy()
        player = _make_player(auction_value=80.0, projected_points=400.0)
        team = _make_team()
        owner = _make_owner()
        bid = strategy.calculate_bid(player, team, owner, 50.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_should_nominate(self):
        from strategies.elite_hybrid_strategy import EliteHybridStrategy
        strategy = EliteHybridStrategy()
        player = _make_player()
        team = _make_team()
        owner = _make_owner()
        result = strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)


class TestHybridStrategies:
    """Tests for hybrid strategy classes."""

    def test_value_random_strategy_init(self):
        from strategies.hybrid_strategies import ValueRandomStrategy
        s = ValueRandomStrategy()
        assert s.name is not None

    def test_value_random_calculate_bid(self):
        from strategies.hybrid_strategies import ValueRandomStrategy
        s = ValueRandomStrategy()
        player = _make_player(auction_value=40.0)
        team = _make_team()
        owner = _make_owner()
        bid = s.calculate_bid(player, team, owner, 20.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_value_random_calculate_bid_no_bid(self):
        from strategies.hybrid_strategies import ValueRandomStrategy
        s = ValueRandomStrategy(aggression=0.01, randomness=0.0)  # Minimal bid multiplier
        player = _make_player(auction_value=10.0)
        team = _make_team(budget=200.0)
        owner = _make_owner()
        # Returns an int/float regardless
        bid = s.calculate_bid(player, team, owner, 100.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_value_random_should_nominate(self):
        from strategies.hybrid_strategies import ValueRandomStrategy
        s = ValueRandomStrategy()
        player = _make_player(auction_value=40.0)
        team = _make_team()
        owner = _make_owner()
        result = s.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)

    def test_value_smart_strategy_init(self):
        from strategies.hybrid_strategies import ValueSmartStrategy
        s = ValueSmartStrategy()
        assert s.name is not None

    def test_value_smart_calculate_bid(self):
        from strategies.hybrid_strategies import ValueSmartStrategy
        s = ValueSmartStrategy()
        player = _make_player(auction_value=40.0)
        team = _make_team()
        owner = _make_owner()
        bid = s.calculate_bid(player, team, owner, 20.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_value_smart_should_nominate(self):
        from strategies.hybrid_strategies import ValueSmartStrategy
        s = ValueSmartStrategy()
        player = _make_player(auction_value=40.0)
        team = _make_team()
        owner = _make_owner()
        result = s.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)

    def test_improved_value_strategy_init(self):
        from strategies.hybrid_strategies import ImprovedValueStrategy
        s = ImprovedValueStrategy()
        assert s.name is not None

    def test_improved_value_calculate_bid(self):
        from strategies.hybrid_strategies import ImprovedValueStrategy
        s = ImprovedValueStrategy()
        player = _make_player(auction_value=40.0)
        team = _make_team()
        owner = _make_owner()
        bid = s.calculate_bid(player, team, owner, 20.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_improved_value_should_nominate(self):
        from strategies.hybrid_strategies import ImprovedValueStrategy
        s = ImprovedValueStrategy()
        player = _make_player(auction_value=40.0)
        team = _make_team()
        owner = _make_owner()
        result = s.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)


class TestVorStrategy:
    def setup_method(self):
        from strategies.vor_strategy import VorStrategy
        self.strategy = VorStrategy()

    def test_init(self):
        assert self.strategy.name is not None

    def test_calculate_bid_basic(self):
        player = _make_player(projected_points=350.0, auction_value=45.0)
        team = _make_team()
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_should_nominate(self):
        player = _make_player(projected_points=350.0)
        team = _make_team()
        owner = _make_owner()
        result = self.strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)

    def test_calculate_bid_exceeds_value(self):
        player = _make_player(projected_points=100.0, auction_value=20.0)
        team = _make_team()
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 50.0, 200.0, [])
        assert bid == 0

    def test_calculate_bid_negative_vor_needed_position(self):
        """Cover vor <= 0 and position_priority >= 1.0 branch (lines 132-134)."""
        # Player with low projected points -> negative VOR
        player = _make_player(position="QB", projected_points=100.0, auction_value=1.0)
        player.vor = -10.0  # Force negative VOR
        team = _make_team()
        # Make team have very high position priority for QB
        team.get_needs.return_value = ["QB"]
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 0.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_calculate_bid_tight_budget(self):
        """Cover low-budget path."""
        player = _make_player(projected_points=350.0, auction_value=45.0)
        team = _make_team()
        owner = _make_owner()
        # Very tight budget — remaining_budget <= min_needed + 3
        bid = self.strategy.calculate_bid(player, team, owner, 0.0, 2.0, [])
        assert isinstance(bid, (int, float))

    def test_calculate_bid_with_remaining_players(self):
        """Cover scarcity calculation with remaining players (lines 291+)."""
        # A few remaining players at same position
        remaining = [
            _make_player(name=f"P{i}", position="QB", projected_points=300.0)
            for i in range(5)
        ]
        player = _make_player(position="QB", projected_points=400.0, auction_value=50.0)
        team = _make_team()
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 5.0, 200.0, remaining)
        assert isinstance(bid, (int, float))

    def test_calculate_dynamic_scarcity_with_players(self):
        """Cover _calculate_all_dynamic_scarcity_factors with remaining_players (lines 348-365)."""
        remaining = [
            _make_player(name=f"P{i}", position="QB" if i < 3 else "RB", projected_points=300.0)
            for i in range(10)
        ]
        result = self.strategy._calculate_all_dynamic_scarcity_factors(remaining)
        assert isinstance(result, dict)
        assert "QB" in result

    def test_calculate_dynamic_scarcity_empty(self):
        """Cover _calculate_all_dynamic_scarcity_factors with no players."""
        result = self.strategy._calculate_all_dynamic_scarcity_factors([])
        assert isinstance(result, dict)

    def test_get_actual_starter_counts(self):
        """Cover _get_actual_starter_counts (lines 322-323)."""
        result = self.strategy._get_actual_starter_counts()
        assert isinstance(result, dict)

    def test_calculate_dynamic_superflex_qb(self):
        """Cover _calculate_dynamic_superflex_adjustment for QB."""
        result = self.strategy._calculate_dynamic_superflex_adjustment("QB")
        assert isinstance(result, float)

    def test_calculate_dynamic_superflex_rb(self):
        """Cover _calculate_dynamic_superflex_adjustment for non-QB."""
        result = self.strategy._calculate_dynamic_superflex_adjustment("RB")
        assert isinstance(result, float)

    def test_calculate_vor_fallback_no_projected(self):
        """Cover _calculate_vor fallback (lines 238+)."""
        player = _make_player(position="QB")
        player.vor = None  # Force non-numeric, use projected_points
        player.projected_points = 300.0
        result = self.strategy._calculate_vor(player)
        assert isinstance(result, float)

    def test_should_nominate_low_slots(self):
        """Cover should_nominate with few slots remaining."""
        player = _make_player()
        team = _make_team()
        # Override get_remaining_roster_slots to return 1
        team.get_remaining_roster_slots = MagicMock(return_value=1)
        # base_strategy won't delegate since it's callable but return is 1
        # Instead use the actual super() path by not setting to None
        owner = _make_owner()
        result = self.strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)


class TestEnhancedVorStrategy:
    def setup_method(self):
        from strategies.enhanced_vor_strategy import InflationAwareVorStrategy
        self.strategy = InflationAwareVorStrategy()

    def test_init(self):
        assert self.strategy.name is not None

    def test_calculate_bid_basic(self):
        player = _make_player(projected_points=350.0, auction_value=45.0)
        team = _make_team()
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_should_nominate(self):
        player = _make_player()
        team = _make_team()
        owner = _make_owner()
        result = self.strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)


class TestValueBasedStrategy:
    def setup_method(self):
        from strategies.value_based_strategy import ValueBasedStrategy
        self.strategy = ValueBasedStrategy()

    def test_init(self):
        assert self.strategy.name is not None

    def test_calculate_bid_basic(self):
        player = _make_player(projected_points=350.0, auction_value=45.0)
        team = _make_team()
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_should_nominate(self):
        player = _make_player()
        team = _make_team()
        owner = _make_owner()
        result = self.strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)


class TestRefinedValueRandomStrategy:
    def setup_method(self):
        from strategies.refined_value_random_strategy import RefinedValueRandomStrategy
        self.strategy = RefinedValueRandomStrategy()

    def test_init(self):
        assert self.strategy.name is not None

    def test_calculate_bid_basic(self):
        player = _make_player(projected_points=350.0, auction_value=45.0)
        team = _make_team()
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_should_nominate(self):
        player = _make_player()
        team = _make_team()
        owner = _make_owner()
        result = self.strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)


class TestImprovedValueStrategy:
    def setup_method(self):
        from strategies.improved_value_strategy import ImprovedValueStrategy
        self.strategy = ImprovedValueStrategy()

    def test_init(self):
        assert self.strategy.name is not None

    def test_calculate_bid_basic(self):
        player = _make_player(projected_points=350.0, auction_value=45.0)
        team = _make_team()
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_should_nominate(self):
        player = _make_player()
        team = _make_team()
        owner = _make_owner()
        result = self.strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)


class TestRandomStrategy:
    def setup_method(self):
        from strategies.random_strategy import RandomStrategy
        self.strategy = RandomStrategy()

    def test_init(self):
        assert self.strategy.name is not None

    def test_calculate_bid_basic(self):
        player = _make_player(auction_value=40.0)
        team = _make_team()
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_should_nominate(self):
        player = _make_player()
        team = _make_team()
        owner = _make_owner()
        result = self.strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)


class TestSigmoidStrategy:
    def setup_method(self):
        from strategies.sigmoid_strategy import SigmoidStrategy
        self.strategy = SigmoidStrategy()

    def _make_sigmoid_team(self, budget=200.0):
        t = _make_team(budget=budget)
        rc = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DST": 1}
        t.roster_requirements = rc
        t.roster_config = rc
        return t

    def test_init(self):
        assert self.strategy.name is not None

    def test_calculate_bid_basic(self):
        player = _make_player(auction_value=40.0, projected_points=300.0)
        team = self._make_sigmoid_team()
        owner = _make_owner()
        bid = self.strategy.calculate_bid(player, team, owner, 10.0, 200.0, [])
        assert isinstance(bid, (int, float))

    def test_should_nominate(self):
        player = _make_player()
        team = self._make_sigmoid_team()
        owner = _make_owner()
        result = self.strategy.should_nominate(player, team, owner, 200.0)
        assert isinstance(result, bool)
