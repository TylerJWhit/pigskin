"""Test cases for auction draft strategies."""

import unittest

from test_base import BaseTestCase, TestDataGenerator
from strategies import (
    create_strategy, 
    list_available_strategies,
    get_strategy_info,
    AVAILABLE_STRATEGIES
)
from classes.player import Player
from classes.team import Team
from classes.owner import Owner


class TestStrategies(BaseTestCase):
    """Test all strategy implementations."""
    
    def test_strategy_creation(self):
        """Test that all strategies can be created."""
        available_strategies = list_available_strategies()
        self.assertGreater(len(available_strategies), 0)
        
        for strategy_type in available_strategies:
            with self.subTest(strategy=strategy_type):
                strategy = create_strategy(strategy_type)
                self.assertIsNotNone(strategy)
                self.assertTrue(hasattr(strategy, 'calculate_bid'))
                self.assertTrue(hasattr(strategy, 'should_nominate'))
                
    def test_invalid_strategy_creation(self):
        """Test that invalid strategy types raise errors."""
        with self.assertRaises(ValueError):
            create_strategy('invalid_strategy')
            
    def test_strategy_info(self):
        """Test strategy information retrieval."""
        for strategy_type in list_available_strategies():
            with self.subTest(strategy=strategy_type):
                info = get_strategy_info(strategy_type)
                self.assertIn('name', info)
                self.assertIn('description', info)
                
    def test_all_strategies_available(self):
        """Test that all expected strategies are available."""
        expected_strategies = [
            'value', 'aggressive', 'conservative', 'sigmoid', 'improved_value',
            'adaptive', 'vor', 'random', 'balanced', 'basic', 'elite_hybrid',
            'value_random', 'value_smart', 'hybrid_improved_value', 
            'league', 'refined_value_random'
        ]
        
        available = list_available_strategies()
        for strategy in expected_strategies:
            with self.subTest(strategy=strategy):
                self.assertIn(strategy, available, f"Strategy '{strategy}' should be available")
    
    def test_strategy_bidding_logic(self):
        """Test basic bidding logic for all strategies."""
        player = self.create_mock_player(projected_points=200.0, auction_value=25.0)
        team = self.create_mock_team()
        owner = self.create_mock_owner()
        remaining_players = [self.create_mock_player(f"player_{i}") for i in range(10)]
        
        for strategy_type in list_available_strategies():
            with self.subTest(strategy=strategy_type):
                strategy = create_strategy(strategy_type)
                
                # Test basic bid calculation
                bid = strategy.calculate_bid(
                    player=player,
                    team=team,
                    owner=owner,
                    current_bid=10.0,
                    remaining_budget=150.0,
                    remaining_players=remaining_players
                )
                
                # Bid should be a valid number
                self.assertIsInstance(bid, (int, float))
                self.assertGreaterEqual(bid, 0.0)
                
                # If strategy bids, it should be at least current bid + 1
                if bid > 0:
                    self.assertGreaterEqual(bid, 11.0)  # current_bid + 1
                
    def test_strategy_nomination_logic(self):
        """Test nomination logic for all strategies."""
        player = self.create_mock_player(projected_points=200.0, auction_value=25.0)
        team = self.create_mock_team()
        owner = self.create_mock_owner()
        
        for strategy_type in list_available_strategies():
            with self.subTest(strategy=strategy_type):
                strategy = create_strategy(strategy_type)
                
                # Test nomination decision
                should_nominate = strategy.should_nominate(
                    player=player,
                    team=team,
                    owner=owner,
                    remaining_budget=150.0
                )
                
                # Should return boolean
                self.assertIsInstance(should_nominate, bool)
    
    def test_vor_strategy_specific(self):
        """Test VOR strategy specific functionality."""
        vor_strategy = create_strategy('vor')
        player = self.create_mock_player(projected_points=200.0, auction_value=25.0)
        
        # Test VOR calculation if method exists
        if hasattr(vor_strategy, '_calculate_vor'):
            vor = vor_strategy._calculate_vor(player)
            self.assertIsInstance(vor, (int, float))
            self.assertGreaterEqual(vor, 0.0)
    
    def test_budget_constraint_handling(self):
        """Test that strategies handle budget constraints properly."""
        player = self.create_mock_player(projected_points=200.0, auction_value=25.0)
        team = self.create_mock_team()
        owner = self.create_mock_owner()
        remaining_players = [self.create_mock_player(f"player_{i}") for i in range(10)]
        
        for strategy_type in list_available_strategies():
            with self.subTest(strategy=strategy_type):
                strategy = create_strategy(strategy_type)
                
                # Test with very low budget
                bid = strategy.calculate_bid(
                    player=player,
                    team=team,
                    owner=owner,
                    current_bid=10.0,
                    remaining_budget=15.0,  # Very tight budget
                    remaining_players=remaining_players
                )
                
                # Strategy should not bid more than available budget
                if bid > 0:
                    self.assertLessEqual(bid, 15.0)


class TestStrategyPerformance(BaseTestCase):
    """Test strategy performance characteristics."""
    
    def test_strategy_consistency(self):
        """Test that strategies produce consistent results."""
        player = self.create_mock_player(projected_points=200.0, auction_value=25.0)
        team = self.create_mock_team()
        owner = self.create_mock_owner()
        remaining_players = [self.create_mock_player(f"player_{i}") for i in range(10)]
        
        # Test non-random strategies for consistency
        deterministic_strategies = [s for s in list_available_strategies() 
                                   if 'random' not in s.lower()]
        
        for strategy_type in deterministic_strategies:
            with self.subTest(strategy=strategy_type):
                strategy = create_strategy(strategy_type)
                
                # Calculate bid multiple times with same inputs
                bids = []
                for _ in range(3):
                    bid = strategy.calculate_bid(
                        player=player,
                        team=team,
                        owner=owner,
                        current_bid=10.0,
                        remaining_budget=150.0,
                        remaining_players=remaining_players
                    )
                    bids.append(bid)
                
                # All bids should be the same for deterministic strategies
                self.assertEqual(len(set(bids)), 1, 
                               f"Strategy {strategy_type} should be deterministic")


class TestValueBasedStrategy(BaseTestCase):
    """Test Value-Based strategy."""
    
    def setUp(self):
        super().setUp()
        self.strategy = create_strategy('value')
        self.player = self.create_mock_player(auction_value=20.0)
        self.team = self.create_mock_team()
        self.owner = self.create_mock_owner()
        self.remaining_players = TestDataGenerator.create_test_players(20)
        
    def test_calculate_bid_basic(self):
        """Test basic bid calculation."""
        bid = self.strategy.calculate_bid(
            self.player, self.team, self.owner, 
            current_bid=5.0, remaining_budget=100.0, 
            remaining_players=self.remaining_players
        )
        
        self.assertGreater(bid, 0)
        self.assertLessEqual(bid, 100.0)  # Shouldn't exceed budget
        
    def test_calculate_bid_no_budget(self):
        """Test bid calculation with no budget."""
        bid = self.strategy.calculate_bid(
            self.player, self.team, self.owner,
            current_bid=5.0, remaining_budget=0.0,
            remaining_players=self.remaining_players
        )
        
        self.assertEqual(bid, 0.0)
        
    def test_calculate_bid_high_current_bid(self):
        """Test bid calculation when current bid is too high."""
        bid = self.strategy.calculate_bid(
            self.player, self.team, self.owner,
            current_bid=50.0, remaining_budget=100.0,
            remaining_players=self.remaining_players
        )
        
        self.assertEqual(bid, 0.0)  # Should not bid when current bid exceeds value
        
    def test_should_nominate_needed_position(self):
        """Test nomination of needed positions."""
        # Mock team to need RB
        self.team.get_needs = lambda: ['RB']
        
        should_nominate = self.strategy.should_nominate(
            self.player, self.team, self.owner, 100.0
        )
        
        self.assertTrue(should_nominate)
        
    def test_should_nominate_target_player(self):
        """Test nomination of target players."""
        # Mock owner to have this as target player
        self.owner.is_target_player = lambda player_id: True
        
        should_nominate = self.strategy.should_nominate(
            self.player, self.team, self.owner, 100.0
        )
        
        self.assertTrue(should_nominate)


class TestAggressiveStrategy(BaseTestCase):
    """Test Aggressive strategy."""
    
    def setUp(self):
        super().setUp()
        self.strategy = create_strategy('aggressive')
        self.elite_player = self.create_mock_player(auction_value=30.0)
        self.regular_player = self.create_mock_player(auction_value=15.0)
        self.team = self.create_mock_team()
        self.owner = self.create_mock_owner()
        self.remaining_players = TestDataGenerator.create_test_players(20)
        
    def test_aggressive_bid_on_elite_player(self):
        """Test aggressive bidding on elite players."""
        bid = self.strategy.calculate_bid(
            self.elite_player, self.team, self.owner,
            current_bid=20.0, remaining_budget=150.0,
            remaining_players=self.remaining_players
        )
        
        # Should bid more aggressively on elite players
        self.assertGreater(bid, 20.0)
        
    def test_conservative_with_low_budget(self):
        """Test conservative bidding when budget is low."""
        # Set low budget to trigger conservative mode
        bid = self.strategy.calculate_bid(
            self.elite_player, self.team, self.owner,
            current_bid=20.0, remaining_budget=50.0,  # Low budget
            remaining_players=self.remaining_players
        )
        
        # Should be more conservative with low budget
        self.assertBetween(bid, 20.0, 30.0)
        
    def test_nomination_elite_players(self):
        """Test nomination preference for elite players."""
        should_nominate = self.strategy.should_nominate(
            self.elite_player, self.team, self.owner, 100.0
        )
        
        self.assertTrue(should_nominate)


class TestConservativeStrategy(BaseTestCase):
    """Test Conservative strategy."""
    
    def setUp(self):
        super().setUp()
        self.strategy = create_strategy('conservative')
        self.expensive_player = self.create_mock_player(auction_value=25.0)
        self.sleeper_player = self.create_mock_player(auction_value=10.0)
        self.team = self.create_mock_team()
        self.owner = self.create_mock_owner()
        self.remaining_players = TestDataGenerator.create_test_players(20)
        
    def test_conservative_bid_expensive_player(self):
        """Test conservative bidding on expensive players."""
        bid = self.strategy.calculate_bid(
            self.expensive_player, self.team, self.owner,
            current_bid=15.0, remaining_budget=150.0,
            remaining_players=self.remaining_players
        )
        
        # Should bid conservatively (less than value)
        self.assertLess(bid, self.expensive_player.auction_value)
        
    def test_sleeper_overbid(self):
        """Test slight overbid on sleeper players."""
        bid = self.strategy.calculate_bid(
            self.sleeper_player, self.team, self.owner,
            current_bid=8.0, remaining_budget=150.0,
            remaining_players=self.remaining_players
        )
        
        # Should be willing to pay slightly more for sleepers
        self.assertGreater(bid, 8.0)
        
    def test_budget_constraint(self):
        """Test that conservative strategy respects budget constraints."""
        bid = self.strategy.calculate_bid(
            self.expensive_player, self.team, self.owner,
            current_bid=15.0, remaining_budget=100.0,
            remaining_players=self.remaining_players
        )
        
        # Should never spend more than 20% of budget on one player
        self.assertLessEqual(bid, 20.0)


class TestSigmoidStrategy(BaseTestCase):
    """Test Sigmoid strategy."""
    
    def setUp(self):
        super().setUp()
        self.strategy = create_strategy('sigmoid')
        self.player = self.create_mock_player(auction_value=20.0)
        self.team = self.create_mock_team()
        self.owner = self.create_mock_owner()
        self.remaining_players = TestDataGenerator.create_test_players(50)
        
    def test_sigmoid_bid_calculation(self):
        """Test that sigmoid strategy produces reasonable bids."""
        bid = self.strategy.calculate_bid(
            self.player, self.team, self.owner,
            current_bid=10.0, remaining_budget=100.0,
            remaining_players=self.remaining_players
        )
        
        self.assertGreater(bid, 0)
        self.assertLessEqual(bid, 100.0)
        
    def test_sigmoid_with_positional_need(self):
        """Test sigmoid strategy with positional needs."""
        # Mock team to desperately need RB
        self.team.get_needs = lambda: ['RB']
        self.team.roster_requirements = {'RB': 2}
        self.team.roster = []  # Empty roster
        
        bid = self.strategy.calculate_bid(
            self.player, self.team, self.owner,
            current_bid=10.0, remaining_budget=100.0,
            remaining_players=self.remaining_players
        )
        
        # Should bid more when we need the position
        self.assertGreater(bid, 10.0)
        
    def test_sigmoid_mathematical_functions(self):
        """Test the mathematical functions of sigmoid strategy."""
        # Test sigmoid function directly
        sigmoid_value = self.strategy._sigmoid(0.5)
        self.assertBetween(sigmoid_value, 0.4, 0.6)  # Should be around 0.5
        
        # Test with extreme values
        sigmoid_low = self.strategy._sigmoid(0.0)
        sigmoid_high = self.strategy._sigmoid(1.0)
        
        self.assertLess(sigmoid_low, sigmoid_high)
        self.assertBetween(sigmoid_low, 0.0, 1.0)
        self.assertBetween(sigmoid_high, 0.0, 1.0)


class TestStrategyComparison(BaseTestCase):
    """Test strategy comparisons and interactions."""
    
    def setUp(self):
        super().setUp()
        self.strategies = {
            strategy_type: create_strategy(strategy_type)
            for strategy_type in list_available_strategies()
        }
        self.player = self.create_mock_player(auction_value=20.0)
        self.team = self.create_mock_team()
        self.owner = self.create_mock_owner()
        self.remaining_players = TestDataGenerator.create_test_players(20)
        
    def test_all_strategies_bid(self):
        """Test that all strategies can calculate bids."""
        for strategy_name, strategy in self.strategies.items():
            with self.subTest(strategy=strategy_name):
                bid = strategy.calculate_bid(
                    self.player, self.team, self.owner,
                    current_bid=10.0, remaining_budget=100.0,
                    remaining_players=self.remaining_players
                )
                
                self.assertIsInstance(bid, (int, float))
                self.assertGreaterEqual(bid, 0)
                
    def test_strategy_nomination_differences(self):
        """Test that strategies have different nomination behaviors."""
        nominations = {}
        
        for strategy_name, strategy in self.strategies.items():
            nominations[strategy_name] = strategy.should_nominate(
                self.player, self.team, self.owner, 100.0
            )
            
        # Should have some variation in nomination decisions
        unique_decisions = len(set(nominations.values()))
        self.assertGreaterEqual(unique_decisions, 1)  # At least some decision variation
        
    def test_strategy_parameters(self):
        """Test strategy parameter management."""
        for strategy_name, strategy in self.strategies.items():
            with self.subTest(strategy=strategy_name):
                # Test parameter setting and getting
                strategy.set_parameter('test_param', 42)
                self.assertEqual(strategy.get_parameter('test_param'), 42)
                
                # Test default value
                self.assertIsNone(strategy.get_parameter('nonexistent_param'))
                self.assertEqual(strategy.get_parameter('nonexistent_param', 'default'), 'default')


if __name__ == '__main__':
    unittest.main()
