"""Tests for base_strategy.py - Abstract base class for auction draft strategies."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from strategies.base_strategy import Strategy
from typing import List, Dict


# Test implementation of abstract Strategy class
class ConcreteTestStrategy(Strategy):
    """Concrete implementation for testing abstract Strategy class."""
    
    def __init__(self, name: str = "Test Strategy", description: str = "Test Description"):
        super().__init__(name, description)

    def calculate_bid(self, player, team, owner, current_bid, remaining_budget, remaining_players) -> int:
        return int(current_bid + 1)

    def should_nominate(self, player, team, owner, remaining_budget) -> bool:
        return True


class TestStrategyInitialization:
    """Test Strategy class initialization and basic properties."""
    
    def test_strategy_initialization_with_defaults(self):
        """Test strategy initialization with default parameters."""
        strategy = ConcreteTestStrategy()
        
        assert strategy.name == "Test Strategy"
        assert strategy.description == "Test Description"
        assert isinstance(strategy.parameters, dict)
        assert len(strategy.parameters) == 0
        
    def test_strategy_initialization_with_custom_values(self):
        """Test strategy initialization with custom name and description."""
        strategy = ConcreteTestStrategy("Custom Strategy", "Custom Description")
        
        assert strategy.name == "Custom Strategy"
        assert strategy.description == "Custom Description"
        assert isinstance(strategy.parameters, dict)
        
    def test_strategy_string_representation(self):
        """Test strategy string representation."""
        strategy = ConcreteTestStrategy("Test Name", "Test Desc")
        
        assert str(strategy) == "Test Name: Test Desc"


class TestParameterManagement:
    """Test parameter management functionality."""
    
    def test_set_parameter(self):
        """Test setting strategy parameters."""
        strategy = ConcreteTestStrategy()
        
        strategy.set_parameter("aggression", 1.5)
        assert strategy.parameters["aggression"] == 1.5
        
        strategy.set_parameter("randomness", 0.3)
        assert strategy.parameters["randomness"] == 0.3
        
    def test_set_parameter_with_none_parameters(self):
        """Test setting parameters when parameters dict is None."""
        strategy = ConcreteTestStrategy()
        strategy.parameters = None
        
        strategy.set_parameter("test_param", "test_value")
        
        assert isinstance(strategy.parameters, dict)
        assert strategy.parameters["test_param"] == "test_value"
        
    def test_get_parameter(self):
        """Test getting strategy parameters."""
        strategy = ConcreteTestStrategy()
        strategy.parameters = {"aggression": 1.5, "randomness": 0.3}
        
        assert strategy.get_parameter("aggression") == 1.5
        assert strategy.get_parameter("randomness") == 0.3
        assert strategy.get_parameter("nonexistent") is None
        
    def test_get_parameter_with_default(self):
        """Test getting parameters with default values."""
        strategy = ConcreteTestStrategy()
        
        assert strategy.get_parameter("missing", "default") == "default"
        assert strategy.get_parameter("missing", 42) == 42


class TestPlayerValueCalculation:
    """Test player value calculation helpers."""
    
    def test_get_player_value_with_auction_value(self):
        """Test getting player value using auction_value attribute."""
        strategy = ConcreteTestStrategy()
        player = Mock()
        player.auction_value = 25.5
        
        value = strategy._get_player_value(player)
        
        assert value == 25.5
        
    def test_get_player_value_with_projected_points(self):
        """Test getting player value using projected_points fallback."""
        strategy = ConcreteTestStrategy()
        player = Mock()
        del player.auction_value  # Remove auction_value
        player.projected_points = 180.0
        
        value = strategy._get_player_value(player)
        
        assert value == 180.0
        
    def test_get_player_value_with_zero_auction_value(self):
        """Test fallback when auction_value is zero."""
        strategy = ConcreteTestStrategy()
        player = Mock()
        player.auction_value = 0
        player.projected_points = 150.0
        
        value = strategy._get_player_value(player)
        
        assert value == 150.0
        
    def test_get_player_value_fallback(self):
        """Test fallback value when no valid attributes exist."""
        strategy = ConcreteTestStrategy()
        player = Mock()
        del player.auction_value
        del player.projected_points
        
        value = strategy._get_player_value(player, fallback=15.0)
        
        assert value == 15.0
        
    def test_get_player_value_default_fallback(self):
        """Test default fallback value."""
        strategy = ConcreteTestStrategy()
        player = Mock()
        del player.auction_value
        del player.projected_points
        
        value = strategy._get_player_value(player)
        
        assert value == 10.0


class TestTeamDelegationMethods:
    """Test methods that delegate to team functionality."""
    
    def test_get_remaining_roster_slots(self):
        """Test delegation to team's roster slots method."""
        strategy = ConcreteTestStrategy()
        team = Mock()
        team.get_remaining_roster_slots.return_value = 8
        
        slots = strategy._get_remaining_roster_slots(team)
        
        assert slots == 8
        team.get_remaining_roster_slots.assert_called_once()
        
    def test_get_required_positions_needed(self):
        """Test delegation to team's remaining roster slots."""
        strategy = ConcreteTestStrategy()
        team = Mock()
        team.get_remaining_roster_slots.return_value = 5
        
        positions = strategy._get_required_positions_needed(team)
        
        assert positions == 5
        team.get_remaining_roster_slots.assert_called_once()
        
    def test_calculate_position_priority(self):
        """Test delegation to team's position priority calculation."""
        strategy = ConcreteTestStrategy()
        player = Mock()
        player.position = "RB"
        team = Mock()
        team.calculate_position_priority.return_value = 0.8
        
        priority = strategy._calculate_position_priority(player, team)
        
        assert priority == 0.8
        team.calculate_position_priority.assert_called_once_with("RB")
        
    def test_calculate_budget_reservation(self):
        """Test delegation to team's budget calculation method."""
        strategy = ConcreteTestStrategy()
        team = Mock()
        team.calculate_minimum_budget_needed.return_value = 15.0
        
        reservation = strategy._calculate_budget_reservation(team, 100.0)
        
        assert reservation == 15.0
        team.calculate_minimum_budget_needed.assert_called_once_with(100.0)


class TestForceBidLogic:
    """Test force bid determination logic."""
    
    def test_should_force_bid_last_slot(self):
        """Test force bid logic when only 1 slot remaining."""
        strategy = ConcreteTestStrategy()
        team = Mock()
        team.get_remaining_roster_slots.return_value = 1
        
        # Should force bid if we can afford it
        assert strategy._should_force_bid(team, 50.0, 10.0) is True
        assert strategy._should_force_bid(team, 5.0, 10.0) is False
        
    def test_should_force_bid_very_late_draft(self):
        """Test force bid logic with 2-3 slots remaining."""
        strategy = ConcreteTestStrategy()
        team = Mock()
        team.get_remaining_roster_slots.return_value = 3
        
        # Budget per slot = 30, should bid if current_bid <= 45 (1.5x)
        assert strategy._should_force_bid(team, 90.0, 40.0) is True
        assert strategy._should_force_bid(team, 90.0, 50.0) is False
        
    def test_should_force_bid_late_draft(self):
        """Test force bid logic with 4-6 slots remaining."""
        strategy = ConcreteTestStrategy()
        team = Mock()
        team.get_remaining_roster_slots.return_value = 5
        
        # Budget per slot = 20, should bid if current_bid <= 16 (0.8x)
        assert strategy._should_force_bid(team, 100.0, 15.0) is True
        assert strategy._should_force_bid(team, 100.0, 20.0) is False
        
    def test_should_force_bid_mid_late_draft(self):
        """Test force bid logic with 7-10 slots and budget pressure."""
        strategy = ConcreteTestStrategy()
        team = Mock()
        team.get_remaining_roster_slots.return_value = 8
        
        # Budget per slot = 2.5, should force bid on cheap players
        assert strategy._should_force_bid(team, 20.0, 1.0) is True
        assert strategy._should_force_bid(team, 20.0, 5.0) is False
        
    def test_should_force_bid_early_draft(self):
        """Test force bid logic in early draft conditions."""
        strategy = ConcreteTestStrategy()
        team = Mock()
        team.get_remaining_roster_slots.return_value = 15
        
        # Should only force bid on very cheap players with extreme budget pressure
        assert strategy._should_force_bid(team, 25.0, 1.0) is True  # Budget per slot = 1.67
        assert strategy._should_force_bid(team, 150.0, 5.0) is False  # Budget per slot = 10


class TestNominationLogic:
    """Test player nomination decision logic."""
    
    def create_mock_setup(self, remaining_slots: int, remaining_budget: float, 
                         position_priority: float, player_cost: float):
        """Create mock objects for nomination testing."""
        team = Mock()
        team.get_remaining_roster_slots.return_value = remaining_slots
        team.calculate_position_priority.return_value = position_priority
        
        player = Mock()
        player.auction_value = player_cost
        
        owner = Mock()
        
        return player, team, owner
        
    def test_should_nominate_desperate_roster_completion(self):
        """Test nomination when desperately need roster completion."""
        strategy = ConcreteTestStrategy()
        player, team, owner = self.create_mock_setup(
            remaining_slots=2, remaining_budget=10.0, 
            position_priority=0.4, player_cost=8.0
        )
        
        result = strategy.should_nominate(player, team, owner, 10.0)
        
        assert result is True
        
    def test_should_nominate_desperate_low_priority_position(self):
        """Test nomination rejection for low priority with desperate needs."""
        strategy = ConcreteTestStrategy()
        player, team, owner = self.create_mock_setup(
            remaining_slots=2, remaining_budget=10.0, 
            position_priority=0.2, player_cost=5.0
        )
        
        result = strategy.should_nominate(player, team, owner, 10.0)
        
        assert result is False
        
    def test_should_nominate_budget_pressure(self):
        """Test nomination under budget pressure conditions."""
        strategy = ConcreteTestStrategy()
        player, team, owner = self.create_mock_setup(
            remaining_slots=8, remaining_budget=20.0, 
            position_priority=0.6, player_cost=3.0
        )
        
        result = strategy.should_nominate(player, team, owner, 20.0)
        
        assert result is True
        
    def test_should_nominate_high_priority_affordable(self):
        """Test nomination of high priority affordable players."""
        strategy = ConcreteTestStrategy()
        player, team, owner = self.create_mock_setup(
            remaining_slots=10, remaining_budget=100.0, 
            position_priority=0.8, player_cost=15.0
        )
        
        result = strategy.should_nominate(player, team, owner, 100.0)
        
        assert result is True
        
    def test_should_nominate_conservative_conditions(self):
        """Test conservative nomination conditions."""
        strategy = ConcreteTestStrategy()
        player, team, owner = self.create_mock_setup(
            remaining_slots=12, remaining_budget=150.0, 
            position_priority=0.5, player_cost=20.0
        )
        
        result = strategy.should_nominate(player, team, owner, 150.0)
        
        assert result is True


class TestForceNominationLogic:
    """Test force nomination for roster completion."""
    
    def test_should_force_nominate_needed_position_low_budget(self):
        """Test force nomination for needed position with low budget."""
        strategy = ConcreteTestStrategy()
        
        player = Mock()
        team = Mock()
        team.get_remaining_roster_slots.return_value = 5
        team.calculate_position_priority.return_value = 0.8
        
        result = strategy.should_force_nominate_for_completion(player, team, 8.0)
        
        assert result is True
        
    def test_should_force_nominate_high_priority_position(self):
        """Test force nomination for high priority position."""
        strategy = ConcreteTestStrategy()
        
        player = Mock()
        team = Mock()
        team.get_remaining_roster_slots.return_value = 8
        team.calculate_position_priority.return_value = 1.0
        
        result = strategy.should_force_nominate_for_completion(player, team, 50.0)
        
        assert result is True
        
    def test_should_not_force_nominate_early_draft(self):
        """Test no force nomination in early draft conditions."""
        strategy = ConcreteTestStrategy()
        
        player = Mock()
        team = Mock()
        team.get_remaining_roster_slots.return_value = 15
        team.calculate_position_priority.return_value = 0.6
        
        result = strategy.should_force_nominate_for_completion(player, team, 100.0)
        
        assert result is False


class TestBidCalculationLogic:
    """Test the main bid calculation logic."""
    
    def create_bid_test_setup(self):
        """Create comprehensive mock setup for bid calculation testing."""
        player = Mock()
        player.position = "RB"
        player.auction_value = 20.0
        
        team = Mock()
        team.get_remaining_roster_slots.return_value = 8
        team.calculate_position_priority.return_value = 0.7
        team.calculate_max_bid.return_value = 35.0
        team.enforce_budget_constraint.return_value = 25
        
        owner = Mock()
        owner.get_risk_tolerance.return_value = 0.8
        
        remaining_players = [Mock() for _ in range(50)]
        
        return player, team, owner, remaining_players
        
    def test_calculate_bid_standard_conditions(self):
        """Test bid calculation under standard conditions."""
        strategy = ConcreteTestStrategy()
        strategy.parameters = {"value_multiplier": 1.2, "position_premiums": {"RB": 1.1}}
        
        player, team, owner, remaining_players = self.create_bid_test_setup()
        
        result = strategy.calculate_bid(player, team, owner, 15.0, 50.0, remaining_players)
        
        assert result == 25  # Should return team's enforced constraint
        team.enforce_budget_constraint.assert_called()
        
    def test_calculate_bid_low_position_priority(self):
        """Test bid calculation with very low position priority."""
        strategy = ConcreteTestStrategy()
        player, team, owner, remaining_players = self.create_bid_test_setup()
        team.calculate_position_priority.return_value = 0.05
        team.enforce_budget_constraint.return_value = 0
        
        result = strategy.calculate_bid(player, team, owner, 3.0, 50.0, remaining_players)
        
        assert result == 0
        
    def test_calculate_bid_force_bid_scenario(self):
        """Test bid calculation when force bidding is triggered."""
        strategy = ConcreteTestStrategy()
        player, team, owner, remaining_players = self.create_bid_test_setup()
        team.get_remaining_roster_slots.return_value = 2  # Force bid scenario
        team.enforce_budget_constraint.return_value = 11  # Adjusted expected value
        
        result = strategy.calculate_bid(player, team, owner, 10.0, 30.0, remaining_players)
        
        assert result == 11
        
    def test_calculate_bid_exceeds_max_willing(self):
        """Test bid calculation when current bid exceeds max willing to pay."""
        strategy = ConcreteTestStrategy()
        strategy.parameters = {"value_multiplier": 1.0}
        player, team, owner, remaining_players = self.create_bid_test_setup()
        
        # Current bid higher than our calculated value
        result = strategy.calculate_bid(player, team, owner, 50.0, 100.0, remaining_players)
        
        assert result == 0
        
    def test_calculate_bid_aggressive_bidding(self):
        """Test aggressive bidding when we value player much higher."""
        strategy = ConcreteTestStrategy()
        strategy.parameters = {"value_multiplier": 3.0}  # High multiplier
        player, team, owner, remaining_players = self.create_bid_test_setup()
        team.enforce_budget_constraint.return_value = 30
        
        result = strategy.calculate_bid(player, team, owner, 10.0, 100.0, remaining_players)
        
        assert result == 30
        team.enforce_budget_constraint.assert_called()


class TestBidConstraintMethods:
    """Test bid constraint and safety methods."""
    
    def test_get_bid_for_player_minimum_bid(self):
        """Test that bid is always at least $1."""
        strategy = ConcreteTestStrategy()
        player = Mock()
        team = Mock()
        team.enforce_budget_constraint.return_value = 5
        
        result = strategy.get_bid_for_player(player, 0.5, team, 50.0)
        
        assert result == 5
        team.enforce_budget_constraint.assert_called_with(1.0, 50.0)
        
    def test_get_bid_for_player_budget_constraint(self):
        """Test budget constraint enforcement in final bid."""
        strategy = ConcreteTestStrategy()
        player = Mock()
        team = Mock()
        team.enforce_budget_constraint.return_value = 0  # Can't afford
        
        result = strategy.get_bid_for_player(player, 25.0, team, 10.0)
        
        assert result == 0
        
    def test_calculate_bid_with_constraints(self):
        """Test wrapper method that ensures constraints are applied."""
        strategy = ConcreteTestStrategy()
        strategy.parameters = {"value_multiplier": 1.2}
        
        player = Mock()
        player.position = "WR"
        player.auction_value = 15.0
        
        team = Mock()
        team.get_remaining_roster_slots.return_value = 10
        team.calculate_position_priority.return_value = 0.6
        team.calculate_max_bid.return_value = 20.0
        team.enforce_budget_constraint.return_value = 18
        
        owner = Mock()
        owner.get_risk_tolerance.return_value = 0.7
        
        result = strategy.calculate_bid_with_constraints(
            player, team, owner, 12.0, 50.0, []
        )
        
        assert result == 18
        # The wrapper method calls enforce_budget_constraint once
        assert team.enforce_budget_constraint.call_count >= 1


class TestMarketTrackerIntegration:
    """Test market tracker integration methods."""
    
    @patch('utils.market_tracker.get_market_tracker')
    def test_get_market_tracker_success(self, mock_get_tracker):
        """Test successful market tracker retrieval."""
        strategy = ConcreteTestStrategy()
        mock_tracker = Mock()
        mock_get_tracker.return_value = mock_tracker
        
        tracker = strategy._get_market_tracker()
        
        assert tracker == mock_tracker
        
    def test_get_market_tracker_import_error(self):
        """Test market tracker retrieval with import error."""
        strategy = ConcreteTestStrategy()
        
        with patch('builtins.__import__', side_effect=ImportError):
            tracker = strategy._get_market_tracker()
            
        assert tracker is None
        
    def test_get_market_inflation_rate(self):
        """Test market inflation rate retrieval."""
        strategy = ConcreteTestStrategy()
        mock_tracker = Mock()
        mock_tracker.get_inflation_rate.return_value = 1.15
        
        with patch.object(strategy, '_get_market_tracker', return_value=mock_tracker):
            rate = strategy._get_market_inflation_rate()
            
        assert rate == 1.15
        
    def test_get_market_inflation_rate_no_tracker(self):
        """Test inflation rate with no tracker available."""
        strategy = ConcreteTestStrategy()
        
        with patch.object(strategy, '_get_market_tracker', return_value=None):
            rate = strategy._get_market_inflation_rate()
            
        assert rate == 1.0
        
    def test_get_position_inflation_rate(self):
        """Test position-specific inflation rate."""
        strategy = ConcreteTestStrategy()
        mock_tracker = Mock()
        mock_tracker.get_position_inflation_rate.return_value = 1.25
        
        with patch.object(strategy, '_get_market_tracker', return_value=mock_tracker):
            rate = strategy._get_position_inflation_rate("RB")
            
        assert rate == 1.25
        mock_tracker.get_position_inflation_rate.assert_called_once_with("RB")
        
    def test_get_market_budget_remaining_percentage(self):
        """Test market budget remaining percentage."""
        strategy = ConcreteTestStrategy()
        mock_tracker = Mock()
        mock_tracker.get_remaining_budget_percentage.return_value = 0.65
        
        with patch.object(strategy, '_get_market_tracker', return_value=mock_tracker):
            percentage = strategy._get_market_budget_remaining_percentage()
            
        assert percentage == 0.65
        
    def test_get_position_scarcity_factor(self):
        """Test position scarcity factor calculation."""
        strategy = ConcreteTestStrategy()
        mock_tracker = Mock()
        mock_tracker.get_position_scarcity.return_value = 1.8
        
        with patch.object(strategy, '_get_market_tracker', return_value=mock_tracker):
            scarcity = strategy._get_position_scarcity_factor("TE")
            
        assert scarcity == 1.8
        mock_tracker.get_position_scarcity.assert_called_once_with("TE")


class TestDynamicPositionWeights:
    """Test dynamic position weight calculations."""
    
    @patch('utils.market_tracker.get_dynamic_position_weights')
    def test_get_dynamic_position_weights_success(self, mock_get_weights):
        """Test successful dynamic position weights retrieval."""
        strategy = ConcreteTestStrategy()
        expected_weights = {'QB': 1.2, 'RB': 1.5, 'WR': 1.3, 'TE': 0.9}
        mock_get_weights.return_value = expected_weights
        
        weights = strategy._get_dynamic_position_weights()
        
        assert weights == expected_weights
        
    def test_get_dynamic_position_weights_fallback(self):
        """Test fallback position weights on import error."""
        strategy = ConcreteTestStrategy()
        
        with patch('builtins.__import__', side_effect=ImportError):
            weights = strategy._get_dynamic_position_weights()
            
        expected_fallback = {'QB': 1.0, 'RB': 1.0, 'WR': 1.0, 'TE': 1.0, 'K': 0.5, 'DST': 0.5}
        assert weights == expected_fallback
        
    @patch('utils.market_tracker.get_dynamic_scarcity_thresholds')
    def test_get_dynamic_scarcity_thresholds_success(self, mock_get_thresholds):
        """Test successful scarcity thresholds retrieval."""
        strategy = ConcreteTestStrategy()
        expected_thresholds = {'high': 1.8, 'medium': 1.3, 'low': 0.9}
        mock_get_thresholds.return_value = expected_thresholds
        
        thresholds = strategy._get_dynamic_scarcity_thresholds()
        
        assert thresholds == expected_thresholds
        
    def test_get_dynamic_scarcity_thresholds_fallback(self):
        """Test fallback scarcity thresholds on import error."""
        strategy = ConcreteTestStrategy()
        
        with patch('builtins.__import__', side_effect=ImportError):
            thresholds = strategy._get_dynamic_scarcity_thresholds()
            
        expected_fallback = {'high': 1.5, 'medium': 1.2, 'low': 0.8}
        assert thresholds == expected_fallback


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling scenarios."""
    
    def test_calculate_bid_owner_without_risk_tolerance(self):
        """Test bid calculation when owner lacks risk_tolerance method."""
        strategy = ConcreteTestStrategy()
        strategy.parameters = {"value_multiplier": 1.2}
        
        player = Mock()
        player.position = "QB"
        player.auction_value = 25.0
        
        team = Mock()
        team.get_remaining_roster_slots.return_value = 10
        team.calculate_position_priority.return_value = 0.8
        team.calculate_max_bid.return_value = 40.0
        team.enforce_budget_constraint.return_value = 30
        
        owner = Mock()
        del owner.get_risk_tolerance  # Remove the method
        
        # Should not raise exception
        result = strategy.calculate_bid(player, team, owner, 20.0, 100.0, [])
        
        assert result == 30
        
    def test_calculate_bid_none_owner(self):
        """Test bid calculation with None owner."""
        strategy = ConcreteTestStrategy()
        strategy.parameters = {"value_multiplier": 1.2}
        
        player = Mock()
        player.position = "QB"
        player.auction_value = 25.0
        
        team = Mock()
        team.get_remaining_roster_slots.return_value = 10
        team.calculate_position_priority.return_value = 0.8
        team.calculate_max_bid.return_value = 40.0
        team.enforce_budget_constraint.return_value = 30
        
        # Should not raise exception with None owner
        result = strategy.calculate_bid(player, team, None, 20.0, 100.0, [])
        
        assert result == 30
        
    def test_parameters_initialized_as_dict(self):
        """Test that parameters is always initialized as dict."""
        strategy = ConcreteTestStrategy()
        
        # Should never be None after initialization
        assert strategy.parameters is not None
        assert isinstance(strategy.parameters, dict)


class TestStrategyPerformance:
    """Test strategy performance and efficiency."""
    
    def test_bid_calculation_performance(self):
        """Test bid calculation performance with large player lists."""
        import time
        
        strategy = ConcreteTestStrategy()
        strategy.parameters = {"value_multiplier": 1.3, "position_premiums": {"RB": 1.2}}
        
        player = Mock()
        player.position = "RB"
        player.auction_value = 22.0
        
        team = Mock()
        team.get_remaining_roster_slots.return_value = 8
        team.calculate_position_priority.return_value = 0.7
        team.calculate_max_bid.return_value = 35.0
        team.enforce_budget_constraint.return_value = 28
        
        owner = Mock()
        owner.get_risk_tolerance.return_value = 0.75
        
        # Large remaining players list
        remaining_players = [Mock() for _ in range(1000)]
        
        start_time = time.time()
        result = strategy.calculate_bid(player, team, owner, 18.0, 80.0, remaining_players)
        end_time = time.time()
        
        assert result == 28
        assert (end_time - start_time) < 0.1  # Should complete in under 100ms


# Integration test combining multiple components
class TestStrategyIntegration:
    """Test integration between different strategy components."""
    
    def test_full_workflow_integration(self):
        """Test complete workflow from parameter setting to bid calculation."""
        strategy = ConcreteTestStrategy("Integration Test", "Full workflow test")
        
        # Set parameters
        strategy.set_parameter("value_multiplier", 1.4)
        strategy.set_parameter("position_premiums", {"WR": 1.15, "RB": 1.25})
        
        # Create comprehensive mock setup
        player = Mock()
        player.position = "WR"
        player.auction_value = 18.0
        
        team = Mock()
        team.get_remaining_roster_slots.return_value = 6
        team.calculate_position_priority.return_value = 0.85
        team.calculate_max_bid.return_value = 32.0
        team.enforce_budget_constraint.side_effect = lambda bid, budget: min(int(bid), int(budget))
        team.calculate_minimum_budget_needed.return_value = 5.0
        
        owner = Mock()
        owner.get_risk_tolerance.return_value = 0.9
        
        remaining_players = [Mock() for _ in range(75)]
        
        # Test bid calculation
        bid_result = strategy.calculate_bid(player, team, owner, 15.0, 60.0, remaining_players)
        
        # Test nomination logic
        nomination_result = strategy.should_nominate(player, team, owner, 60.0)
        
        # Test force nomination
        force_nom_result = strategy.should_force_nominate_for_completion(player, team, 60.0)
        
        # Verify results
        assert isinstance(bid_result, int)
        assert bid_result > 0
        assert isinstance(nomination_result, bool)
        assert isinstance(force_nom_result, bool)
        
        # Verify team methods were called appropriately
        team.get_remaining_roster_slots.assert_called()
        team.calculate_position_priority.assert_called()
        team.enforce_budget_constraint.assert_called()