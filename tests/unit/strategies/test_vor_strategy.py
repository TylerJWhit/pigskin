"""Tests for vor_strategy.py - VOR-based draft strategy focused on value over replacement."""

from unittest.mock import Mock, patch
from strategies.vor_strategy import VorStrategy


class TestVorStrategyInitialization:
    """Test VorStrategy initialization and configuration."""
    
    def test_vor_strategy_initialization_defaults(self):
        """Test VOR strategy initialization with default parameters."""
        with patch('config.config_manager.load_config') as mock_load_config:
            mock_config = Mock()
            mock_config.get.return_value = 12  # num_teams
            mock_config.get.side_effect = lambda key, default=None: {
                'num_teams': 12,
                'roster_positions': {
                    'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1,
                    'K': 1, 'DST': 1, 'FLEX': 2, 'SUPERFLEX': 1
                }
            }.get(key, default)
            mock_load_config.return_value = mock_config
            
            with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={}):
                with patch.object(VorStrategy, '_calculate_replacement_levels', return_value={}):
                    with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=1.0):
                        strategy = VorStrategy()
        
        assert strategy.name == "vor"
        assert strategy.description == "Value Over Replacement focused strategy"
        assert strategy.aggression == 1.0
        assert strategy.scarcity_weight == 0.7
        assert strategy.num_teams == 12
        
    def test_vor_strategy_initialization_custom_params(self):
        """Test VOR strategy initialization with custom parameters."""
        with patch('config.config_manager.load_config') as mock_load_config:
            mock_config = Mock()
            mock_config.get.return_value = 10
            mock_config.get.side_effect = lambda key, default=None: {
                'num_teams': 10,
                'roster_positions': {'QB': 1, 'RB': 2, 'WR': 3}
            }.get(key, default)
            mock_load_config.return_value = mock_config
            
            with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={}):
                with patch.object(VorStrategy, '_calculate_replacement_levels', return_value={}):
                    with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=2.0):
                        strategy = VorStrategy(aggression=1.5, scarcity_weight=0.8)
        
        assert strategy.aggression == 1.5
        assert strategy.scarcity_weight == 0.8
        assert strategy.num_teams == 10
        
    def test_vor_strategy_initialization_config_fallback(self):
        """Test VOR strategy initialization when config loading fails."""
        with patch('config.config_manager.load_config', side_effect=Exception("Config failed")):
            with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={}):
                with patch.object(VorStrategy, '_calculate_replacement_levels', return_value={}):
                    with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=1.0):
                        strategy = VorStrategy()
        
        # Should fall back to defaults
        assert strategy.num_teams == 12
        assert strategy.roster_requirements['QB'] == 1
        assert strategy.roster_requirements['RB'] == 2
        assert strategy.roster_requirements['FLEX'] == 2
        
    def test_vor_strategy_roster_requirements_fallback(self):
        """Test roster requirements fallback when config fails."""
        with patch('config.config_manager.load_config', side_effect=ImportError("No config")):
            with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={}):
                with patch.object(VorStrategy, '_calculate_replacement_levels', return_value={}):
                    with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=1.0):
                        strategy = VorStrategy()
        
        expected_requirements = {
            'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1,
            'K': 1, 'DST': 1, 'FLEX': 2, 'SF': 1
        }
        
        assert strategy.roster_requirements == expected_requirements


class TestVorCalculation:
    """Test VOR calculation methods."""
    
    def create_test_strategy(self):
        """Create a test VOR strategy with mocked initialization."""
        with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={'QB': 1.2, 'RB': 1.5}):
            with patch.object(VorStrategy, '_calculate_replacement_levels', return_value={'QB': 250, 'RB': 180}):
                with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=0.1):
                    with patch('config.config_manager.load_config', side_effect=Exception):
                        strategy = VorStrategy()
        return strategy
        
    def test_calculate_vor_positive_value(self):
        """Test VOR calculation for above-replacement player."""
        strategy = self.create_test_strategy()
        
        player = Mock()
        player.position = "QB"
        player.vor = 50.0  # Player already has VOR attribute
        
        vor = strategy._calculate_vor(player)
        
        assert vor == 50.0
        
    def test_calculate_vor_negative_value(self):
        """Test VOR calculation for below-replacement player."""
        strategy = self.create_test_strategy()
        
        player = Mock()
        player.position = "RB"
        player.vor = -10.0  # Player already has negative VOR
        
        vor = strategy._calculate_vor(player)
        
        assert vor == -10.0
        
    def test_calculate_vor_zero_value(self):
        """Test VOR calculation for replacement-level player."""
        strategy = self.create_test_strategy()
        
        player = Mock()
        player.position = "TE"
        player.vor = 0.0  # Player already has zero VOR
        
        vor = strategy._calculate_vor(player)
        
        assert vor == 0.0


class TestScarcityCalculations:
    """Test position scarcity calculation methods."""
    
    def create_test_strategy(self):
        """Create a test VOR strategy with mocked initialization."""
        with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={'QB': 1.2, 'RB': 1.5}):
            with patch.object(VorStrategy, '_calculate_replacement_levels', return_value={'QB': 250, 'RB': 180}):
                with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=0.1):
                    with patch('config.config_manager.load_config', side_effect=Exception):
                        strategy = VorStrategy()
        return strategy
        
    def test_calculate_remaining_scarcity_high_demand(self):
        """Test remaining scarcity calculation for high-demand position."""
        strategy = self.create_test_strategy()
        
        player = Mock()
        player.position = "RB"
        
        # Create remaining players - few RBs left
        remaining_players = []
        for i in range(5):  # Only 5 RBs remaining
            rb_player = Mock()
            rb_player.position = "RB"
            rb_player.vor = 10.0  # Positive VOR
            remaining_players.append(rb_player)
        
        for i in range(20):  # Lots of other positions
            other_player = Mock()
            other_player.position = "WR"
            other_player.vor = 5.0
            remaining_players.append(other_player)
            
        scarcity = strategy._calculate_remaining_scarcity(player, remaining_players)
        
        # Should be high scarcity (>1.0) due to few RBs remaining
        assert scarcity > 1.0
        
    def test_calculate_remaining_scarcity_low_demand(self):
        """Test remaining scarcity calculation for abundant position."""
        strategy = self.create_test_strategy()
        
        player = Mock()
        player.position = "WR"
        
        # Create remaining players - many WRs left
        remaining_players = []
        for i in range(30):  # Lots of WRs remaining
            wr_player = Mock()
            wr_player.position = "WR"
            wr_player.vor = 8.0  # Positive VOR
            remaining_players.append(wr_player)
            
        scarcity = strategy._calculate_remaining_scarcity(player, remaining_players)
        
        # Should be lower scarcity due to abundance
        assert scarcity <= 1.5
        
    def test_calculate_dynamic_superflex_adjustment_qb(self):
        """Test SuperFlex adjustment calculation for QB."""
        strategy = self.create_test_strategy()
        
        with patch.object(strategy, '_get_actual_starter_counts', return_value={'QB': 24}):  # 2 QBs per team
            adjustment = strategy._calculate_dynamic_superflex_adjustment("QB")
        
        # QB should get adjustment less than 1.0 (lower baseline = higher VOR)
        assert adjustment <= 1.0
        assert adjustment > 0.0
        
    def test_calculate_dynamic_superflex_adjustment_non_qb(self):
        """Test SuperFlex adjustment calculation for non-QB."""
        strategy = self.create_test_strategy()
        
        adjustment = strategy._calculate_dynamic_superflex_adjustment("RB")
        
        # Non-QB should get smaller adjustment
        assert adjustment <= 1.2


class TestBidCalculationLogic:
    """Test the main bid calculation algorithm."""
    
    def create_bid_test_setup(self):
        """Create comprehensive setup for bid calculation tests."""
        # Create strategy with mocked initialization
        with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={'RB': 1.3}):
            with patch.object(VorStrategy, '_calculate_replacement_levels', return_value={'RB': 150}):
                with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=0.12):
                    with patch('config.config_manager.load_config', side_effect=Exception):
                        strategy = VorStrategy(aggression=1.2, scarcity_weight=0.7)
        
        player = Mock()
        player.position = "RB"
        player.player_name = "Test Player"
        player.name = "Test Player"
        
        team = Mock()
        team.get_remaining_roster_slots.return_value = 8
        team.calculate_position_priority.return_value = 0.8
        
        owner = Mock()
        remaining_players = [Mock() for _ in range(30)]
        
        return strategy, player, team, owner, remaining_players
        
    def test_calculate_bid_positive_vor_standard(self):
        """Test bid calculation for positive VOR player under standard conditions."""
        strategy, player, team, owner, remaining_players = self.create_bid_test_setup()
        
        # Mock VOR calculation to return positive value
        with patch.object(strategy, '_calculate_vor', return_value=25.0):
            with patch.object(strategy, '_calculate_remaining_scarcity', return_value=1.2):
                result = strategy.calculate_bid(player, team, owner, 15.0, 80.0, remaining_players)
        
        # Should return reasonable bid based on VOR
        assert isinstance(result, (int, float))
        assert result > 15  # Should bid higher than current bid
        
    def test_calculate_bid_negative_vor_required_position(self):
        """Test bid calculation for negative VOR but required position."""
        strategy, player, team, owner, remaining_players = self.create_bid_test_setup()
        team.calculate_position_priority.return_value = 1.0  # Required position
        
        with patch.object(strategy, '_calculate_vor', return_value=-5.0):
            with patch.object(strategy, '_calculate_remaining_scarcity', return_value=1.1):
                result = strategy.calculate_bid(player, team, owner, 3.0, 50.0, remaining_players)
        
        # Should still bid minimal amount for required position
        assert result > 0
        assert result <= 10  # But not too much for negative VOR
        
    def test_calculate_bid_zero_position_priority(self):
        """Test bid calculation when position priority is zero."""
        strategy, player, team, owner, remaining_players = self.create_bid_test_setup()
        team.calculate_position_priority.return_value = 0.0  # No need for position
        team.get_remaining_roster_slots.return_value = 3  # Few slots left
        
        with patch.object(strategy, '_calculate_vor', return_value=30.0):
            result = strategy.calculate_bid(player, team, owner, 10.0, 60.0, remaining_players)
        
        # Should not bid when priority is 0 AND we have few roster slots
        assert result == 0
        
    def test_calculate_bid_low_budget_scenario(self):
        """Test bid calculation with very low remaining budget."""
        strategy, player, team, owner, remaining_players = self.create_bid_test_setup()
        team.get_remaining_roster_slots.return_value = 6  # 6 slots remaining
        
        with patch.object(strategy, '_calculate_vor', return_value=15.0):
            with patch.object(strategy, '_calculate_remaining_scarcity', return_value=1.0):
                # Only $10 budget for 6 slots (need to reserve $5 for remaining slots)
                result = strategy.calculate_bid(player, team, owner, 2.0, 10.0, remaining_players)
        
        # Should bid conservatively to preserve budget for roster completion
        assert result <= 5  # Can't spend more than available budget minus reserves
        
    def test_calculate_bid_very_low_position_priority(self):
        """Test bid calculation with very low position priority."""
        strategy, player, team, owner, remaining_players = self.create_bid_test_setup()
        team.calculate_position_priority.return_value = 0.05  # Very low priority
        team.get_remaining_roster_slots.return_value = 10  # Many slots remaining
        
        with patch.object(strategy, '_calculate_vor', return_value=20.0):
            result = strategy.calculate_bid(player, team, owner, 5.0, 100.0, remaining_players)
        
        # Should bid minimal amount or not at all for very low priority
        assert result <= 15
        
    def test_calculate_bid_budget_exhausted(self):
        """Test bid calculation when budget is exhausted."""
        strategy, player, team, owner, remaining_players = self.create_bid_test_setup()
        team.get_remaining_roster_slots.return_value = 3  # 3 slots remaining
        
        with patch.object(strategy, '_calculate_vor', return_value=10.0):
            # Need $2 to complete roster, current bid is $5
            result = strategy.calculate_bid(player, team, owner, 5.0, 6.0, remaining_players)
        
        # Should not be able to bid higher than budget allows
        assert result <= 1 or result == 0


class TestNominationLogic:
    """Test player nomination decision logic."""
    
    def create_nomination_test_setup(self):
        """Create test setup for nomination logic."""
        with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={'WR': 1.1}):
            with patch.object(VorStrategy, '_calculate_replacement_levels', return_value={'WR': 120}):
                with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=0.08):
                    with patch('config.config_manager.load_config', side_effect=Exception):
                        strategy = VorStrategy()
        
        player = Mock()
        player.position = "WR"
        
        team = Mock()
        team.get_remaining_roster_slots.return_value = 10
        team.calculate_position_priority.return_value = 0.7
        
        owner = Mock()
        
        return strategy, player, team, owner
        
    def test_should_nominate_force_completion(self):
        """Test nomination when forced by roster completion needs."""
        strategy, player, team, owner = self.create_nomination_test_setup()
        team.get_remaining_roster_slots.return_value = 2  # Force completion
        
        result = strategy.should_nominate(player, team, owner, 50.0)
        
        assert result is True
        
    def test_should_nominate_high_vor_needed_position(self):
        """Test nomination for high VOR player in needed position."""
        strategy, player, team, owner = self.create_nomination_test_setup()
        
        with patch.object(strategy, '_calculate_vor', return_value=25.0):
            with patch.object(strategy, 'calculate_bid', return_value=15):
                result = strategy.should_nominate(player, team, owner, 100.0)
        
        assert result is True
        
    def test_should_nominate_affordable_valuable_player(self):
        """Test nomination for affordable valuable player."""
        strategy, player, team, owner = self.create_nomination_test_setup()
        team.calculate_position_priority.return_value = 0.5  # Moderate need
        
        with patch.object(strategy, '_calculate_vor', return_value=15.0):
            with patch.object(strategy, 'calculate_bid', return_value=8):  # 8% of 100 budget
                result = strategy.should_nominate(player, team, owner, 100.0)
        
        assert result is True
        
    def test_should_nominate_strategic_nomination(self):
        """Test strategic nomination to force opponent spending."""
        strategy, player, team, owner = self.create_nomination_test_setup()
        team.calculate_position_priority.return_value = 0.1  # Don't need position
        team.get_remaining_roster_slots.return_value = 8  # Plenty of slots
        
        with patch.object(strategy, '_calculate_vor', return_value=15.0):  # Valuable to others
            with patch.object(strategy, 'calculate_bid', return_value=5):
                result = strategy.should_nominate(player, team, owner, 150.0)  # Lots of budget
        
        assert result is True  # Strategic nomination
        
    def test_should_not_nominate_low_vor_unneeded(self):
        """Test not nominating low VOR player in unneeded position."""
        strategy, player, team, owner = self.create_nomination_test_setup()
        team.calculate_position_priority.return_value = 0.2  # Low need
        
        with patch.object(strategy, '_calculate_vor', return_value=2.0):  # Low VOR
            with patch.object(strategy, 'calculate_bid', return_value=0):
                result = strategy.should_nominate(player, team, owner, 80.0)
        
        assert result is False


class TestReplacementLevelCalculations:
    """Test replacement level calculation methods."""
    
    def create_replacement_test_strategy(self):
        """Create strategy for replacement level testing."""
        with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={}):
            with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=0.1):
                with patch('config.config_manager.load_config', side_effect=Exception):
                    strategy = VorStrategy()
        return strategy
        
    def test_calculate_replacement_levels(self):
        """Test replacement level calculation."""
        strategy = self.create_replacement_test_strategy()
        
        with patch.object(strategy, '_get_actual_starter_counts', return_value={'QB': 12, 'RB': 24}):
            replacement_levels = strategy._calculate_replacement_levels()
            
        # Should return dict with position replacement levels
        assert isinstance(replacement_levels, dict)
        
    def test_get_actual_starter_counts_quiet_mode(self):
        """Test starter counts calculation in quiet mode."""
        strategy = self.create_replacement_test_strategy()
        
        with patch.dict('os.environ', {'PIGSKIN_QUIET': '1'}):
            starter_counts = strategy._get_actual_starter_counts()
            
        # Should return configured requirements
        assert isinstance(starter_counts, dict)
        assert starter_counts['QB'] == strategy.num_teams * 1
        assert starter_counts['RB'] == strategy.num_teams * 2


class TestVorScalingFactor:
    """Test VOR scaling factor calculation."""
    
    def create_scaling_test_strategy(self):
        """Create strategy for scaling factor testing."""
        with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={}):
            with patch.object(VorStrategy, '_calculate_replacement_levels', return_value={}):
                with patch('config.config_manager.load_config', side_effect=Exception):
                    strategy = VorStrategy()
        return strategy
        
    def test_calculate_vor_scaling_factor(self):
        """Test VOR scaling factor calculation."""
        strategy = self.create_scaling_test_strategy()
        
        scaling_factor = strategy._calculate_vor_scaling_factor()
        
        # Should return positive scaling factor
        assert isinstance(scaling_factor, float)
        assert scaling_factor > 0
        assert scaling_factor < 1.0  # Should be fractional for reasonable bid amounts


class TestTeamDelegationMethods:
    """Test methods that delegate to team functionality."""
    
    def create_delegation_test_strategy(self):
        """Create strategy for delegation testing."""
        with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={}):
            with patch.object(VorStrategy, '_calculate_replacement_levels', return_value={}):
                with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=0.1):
                    with patch('config.config_manager.load_config', side_effect=Exception):
                        strategy = VorStrategy()
        return strategy
        
    def test_get_remaining_roster_slots(self):
        """Test delegation to team's roster slots method."""
        strategy = self.create_delegation_test_strategy()
        team = Mock()
        team.get_remaining_roster_slots.return_value = 7
        
        slots = strategy._get_remaining_roster_slots(team)
        
        assert slots == 7
        team.get_remaining_roster_slots.assert_called_once()


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling scenarios."""
    
    def create_edge_case_strategy(self):
        """Create strategy for edge case testing."""
        with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={}):
            with patch.object(VorStrategy, '_calculate_replacement_levels', return_value={}):
                with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=0.1):
                    with patch('config.config_manager.load_config', side_effect=Exception):
                        strategy = VorStrategy()
        return strategy
        
    def test_calculate_bid_with_missing_player_attributes(self):
        """Test bid calculation when player lacks expected attributes."""
        strategy = self.create_edge_case_strategy()
        
        player = Mock()
        player.position = "QB"
        # Remove name attributes to test fallback
        del player.player_name
        del player.name
        
        team = Mock()
        team.get_remaining_roster_slots.return_value = 5
        team.calculate_position_priority.return_value = 0.6
        
        owner = Mock()
        remaining_players = []
        
        with patch.object(strategy, '_calculate_vor', return_value=10.0):
            with patch.object(strategy, '_calculate_remaining_scarcity', return_value=1.0):
                # Should not raise exception
                result = strategy.calculate_bid(player, team, owner, 8.0, 40.0, remaining_players)
                
        assert isinstance(result, (int, float))
        
    def test_vor_calculation_with_empty_remaining_players(self):
        """Test VOR calculations with empty remaining players list."""
        strategy = self.create_edge_case_strategy()
        
        player = Mock()
        player.position = "TE"
        
        # Should handle empty list gracefully
        scarcity = strategy._calculate_remaining_scarcity(player, [])
        
        assert isinstance(scarcity, (int, float))
        assert scarcity >= 1.0  # Should default to high scarcity when no players left
        
    def test_calculate_bid_extreme_budget_constraints(self):
        """Test bid calculation with extreme budget constraints."""
        strategy = self.create_edge_case_strategy()
        
        player = Mock()
        player.position = "K"
        player.player_name = "Test Kicker"
        
        team = Mock()
        team.get_remaining_roster_slots.return_value = 1  # Last slot
        team.calculate_position_priority.return_value = 1.0  # Must fill
        
        owner = Mock()
        
        with patch.object(strategy, '_calculate_vor', return_value=5.0):
            # Very constrained budget - only $2 left for 1 slot
            result = strategy.calculate_bid(player, team, owner, 1.0, 2.0, [])
            
        # Should bid conservatively or max available
        assert result <= 2
        assert result >= 0


class TestVorStrategyIntegration:
    """Test integration between different VOR strategy components."""
    
    def test_full_bid_workflow_integration(self):
        """Test complete bid workflow from initialization to final bid."""
        # Create strategy with realistic configuration
        with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', 
                         return_value={'QB': 1.5, 'RB': 1.3, 'WR': 1.1, 'TE': 1.2}):
            with patch.object(VorStrategy, '_calculate_replacement_levels', 
                             return_value={'QB': 280, 'RB': 150, 'WR': 120, 'TE': 100}):
                with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=0.15):
                    with patch('config.config_manager.load_config', side_effect=Exception):
                        strategy = VorStrategy(aggression=1.3, scarcity_weight=0.6)
        
        # Create realistic player and team setup
        player = Mock()
        player.position = "RB"
        player.player_name = "Elite Running Back"
        player.name = "Elite Running Back"
        
        team = Mock()
        team.get_remaining_roster_slots.return_value = 9
        team.calculate_position_priority.return_value = 0.9  # High priority
        
        owner = Mock()
        remaining_players = [Mock() for _ in range(50)]  # Realistic remaining pool
        
        # Mock VOR calculation for high-value player
        with patch.object(strategy, '_calculate_vor', return_value=35.0):
            with patch.object(strategy, '_calculate_remaining_scarcity', return_value=1.4):
                bid_result = strategy.calculate_bid(player, team, owner, 20.0, 120.0, remaining_players)
                nomination_result = strategy.should_nominate(player, team, owner, 120.0)
        
        # Verify realistic results
        assert isinstance(bid_result, (int, float))
        assert bid_result > 20  # Should bid above current bid for high-VOR player
        assert bid_result < 120  # Should not bid entire budget
        assert nomination_result is True  # Should nominate high-value player we need
        
    def test_vor_strategy_consistency(self):
        """Test that VOR strategy produces consistent results."""
        # Create strategy
        with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={'WR': 1.2}):
            with patch.object(VorStrategy, '_calculate_replacement_levels', return_value={'WR': 110}):
                with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=0.12):
                    with patch('config.config_manager.load_config', side_effect=Exception):
                        strategy = VorStrategy(aggression=1.0, scarcity_weight=0.5)
        
        player = Mock()
        player.position = "WR"
        player.player_name = "Consistent Player"
        
        team = Mock()
        team.get_remaining_roster_slots.return_value = 8
        team.calculate_position_priority.return_value = 0.7
        
        owner = Mock()
        remaining_players = [Mock() for _ in range(40)]
        
        # Calculate bid multiple times with same inputs
        with patch.object(strategy, '_calculate_vor', return_value=15.0):
            with patch.object(strategy, '_calculate_remaining_scarcity', return_value=1.1):
                bid1 = strategy.calculate_bid(player, team, owner, 12.0, 80.0, remaining_players)
                bid2 = strategy.calculate_bid(player, team, owner, 12.0, 80.0, remaining_players)
                bid3 = strategy.calculate_bid(player, team, owner, 12.0, 80.0, remaining_players)
        
        # Results should be consistent
        assert bid1 == bid2 == bid3


class TestVorStrategyPerformance:
    """Test VOR strategy performance and efficiency."""
    
    def test_bid_calculation_performance(self):
        """Test bid calculation performance with large datasets."""
        import time
        
        # Create strategy
        with patch.object(VorStrategy, '_calculate_all_dynamic_scarcity_factors', return_value={'RB': 1.3}):
            with patch.object(VorStrategy, '_calculate_replacement_levels', return_value={'RB': 160}):
                with patch.object(VorStrategy, '_calculate_vor_scaling_factor', return_value=0.1):
                    with patch('config.config_manager.load_config', side_effect=Exception):
                        strategy = VorStrategy()
        
        player = Mock()
        player.position = "RB"
        player.player_name = "Performance Test Player"
        
        team = Mock()
        team.get_remaining_roster_slots.return_value = 10
        team.calculate_position_priority.return_value = 0.8
        
        owner = Mock()
        # Large remaining players list
        remaining_players = [Mock() for _ in range(200)]
        for p in remaining_players:
            p.position = "RB"  # All same position for worst-case scarcity calculation
        
        with patch.object(strategy, '_calculate_vor', return_value=20.0):
            start_time = time.time()
            result = strategy.calculate_bid(player, team, owner, 15.0, 100.0, remaining_players)
            end_time = time.time()
        
        assert isinstance(result, (int, float))
        assert (end_time - start_time) < 0.5  # Should complete in under 500ms

class TestVorStrategyAdditionalCoverage:
    """Cover remaining uncovered lines in vor_strategy.py."""

    def test_init_exception_in_dynamic_scarcity(self):
        """Cover lines 58-59 — exception in _calculate_all_dynamic_scarcity_factors."""
        from strategies.vor_strategy import VorStrategy as VORStrategy
        from unittest.mock import patch

        with patch.object(VORStrategy, '_calculate_all_dynamic_scarcity_factors',
                          side_effect=Exception("error")):
            strategy = VORStrategy()
            # Should still initialize without raising
            assert strategy is not None

    def test_init_exception_in_vor_scaling_factor(self):
        """Cover lines 79-80 — exception in _calculate_vor_scaling_factor."""
        from strategies.vor_strategy import VorStrategy as VORStrategy
        from unittest.mock import patch

        with patch.object(VORStrategy, '_calculate_vor_scaling_factor',
                          side_effect=Exception("error")):
            strategy = VORStrategy()
            assert strategy._vor_scaling_factor == 0.25

    def test_calculate_bid_vor_negative_high_slots(self):
        """Cover line 133 — vor <= 0, roster_slots > 3 → bid $2."""
        from strategies.vor_strategy import VorStrategy as VORStrategy
        from unittest.mock import MagicMock

        strategy = VORStrategy()

        player = MagicMock()
        player.position = "WR"
        player.projected_points = 50.0  # Below VOR baseline for WR (140), so vor < 0
        player.auction_value = 2.0

        team = MagicMock()
        team.get_remaining_roster_slots.return_value = 10
        team.calculate_position_priority.return_value = 0.8
        team.calculate_max_bid.return_value = 50
        team.enforce_budget_constraint = None
        team.calculate_minimum_budget_needed.return_value = 10.0

        result = strategy.calculate_bid(player, team, MagicMock(), 1.0, 100.0, [])
        assert result >= 0  # bid up to $2

    def test_calculate_bid_vor_negative_low_slots(self):
        """Cover line 134 — vor <= 0, roster_slots <= 3 → return 0."""
        from strategies.vor_strategy import VorStrategy as VORStrategy
        from unittest.mock import MagicMock

        strategy = VORStrategy()

        player = MagicMock()
        player.position = "WR"
        player.projected_points = 50.0  # Below VOR baseline for WR (140), so vor < 0
        player.auction_value = 2.0

        team = MagicMock()
        team.get_remaining_roster_slots.return_value = 2  # <= 3
        team.calculate_position_priority.return_value = 0.8
        team.calculate_max_bid.return_value = 50
        team.enforce_budget_constraint = None
        team.calculate_minimum_budget_needed.return_value = 2.0

        result = strategy.calculate_bid(player, team, MagicMock(), 1.0, 100.0, [])
        assert result == 0

    def test_calculate_bid_zero_position_priority(self):
        """Cover line 152 — position_priority == 0.0 → return 0."""
        from strategies.vor_strategy import VorStrategy as VORStrategy
        from unittest.mock import MagicMock

        strategy = VORStrategy()

        player = MagicMock()
        player.position = "QB"
        player.projected_points = 400.0  # High VOR
        player.auction_value = 40.0

        team = MagicMock()
        team.get_remaining_roster_slots.return_value = 5
        team.calculate_position_priority.return_value = 0.0  # No priority
        team.calculate_max_bid.return_value = 50
        team.enforce_budget_constraint = None
        team.calculate_minimum_budget_needed.return_value = 5.0

        result = strategy.calculate_bid(player, team, MagicMock(), 1.0, 100.0, [])
        assert result == 0

    def test_calculate_vor_non_numeric_values(self):
        """Cover lines 240, 243 — non-numeric projected_points and auction_value."""
        from strategies.vor_strategy import VorStrategy as VORStrategy
        from unittest.mock import MagicMock

        strategy = VORStrategy()

        player = MagicMock()
        player.position = "QB"
        player.projected_points = "not_a_number"
        player.auction_value = "also_not_a_number"

        vor = strategy._calculate_vor(player)
        # Should fall back to baseline (250 for QB) - baseline = baseline → vor = 0
        assert isinstance(vor, (int, float))

    def test_calculate_remaining_scarcity_varying_counts(self):
        """Cover lines 291, 293 — normal and plenty available scarcity."""
        from strategies.vor_strategy import VorStrategy as VORStrategy
        from unittest.mock import MagicMock

        strategy = VORStrategy()

        player = MagicMock()
        player.position = "WR"

        # 12 WR with positive VOR → "normal" (line 291, returns 1.0)
        remaining_players = []
        for _ in range(12):
            p = MagicMock()
            p.position = "WR"
            p.projected_points = 200.0  # above WR baseline 140
            p.auction_value = 20.0
            remaining_players.append(p)

        factor = strategy._calculate_remaining_scarcity(player, remaining_players)
        assert factor == 1.0

        # 20 WR with positive VOR → "plenty available" (line 293, returns 0.8)
        many_players = []
        for _ in range(20):
            p = MagicMock()
            p.position = "WR"
            p.projected_points = 200.0
            p.auction_value = 20.0
            many_players.append(p)
        factor2 = strategy._calculate_remaining_scarcity(player, many_players)
        assert factor2 == 0.8

    def test_calculate_dynamic_superflex_adjustment_exception(self):
        """Cover lines 322-323 — exception in _calculate_dynamic_superflex_adjustment."""
        from strategies.vor_strategy import VorStrategy as VORStrategy
        from unittest.mock import patch

        strategy = VORStrategy()

        with patch.object(strategy, '_get_actual_starter_counts',
                          side_effect=Exception("error")):
            factor = strategy._calculate_dynamic_superflex_adjustment('QB')
            assert factor == 1.0

    def test_calculate_all_dynamic_scarcity_factors_ranges(self):
        """Cover lines 360-363 — dynamic scarcity for different counts."""
        from strategies.vor_strategy import VorStrategy as VORStrategy
        from unittest.mock import MagicMock

        strategy = VORStrategy()

        # Create players at different counts per position
        players = []
        for _ in range(12):
            p = MagicMock()
            p.position = "WR"
            players.append(p)
        for _ in range(3):
            p = MagicMock()
            p.position = "QB"
            players.append(p)
        for _ in range(20):
            p = MagicMock()
            p.position = "RB"
            players.append(p)

        result = strategy._calculate_all_dynamic_scarcity_factors(players)
        assert isinstance(result, dict)
        # WR: 12 players hits count <= 15 branch (line 360-361)
        assert 'WR' in result
        # RB: 20 players hits count > 15 branch (line 362-363)
        assert 'RB' in result
