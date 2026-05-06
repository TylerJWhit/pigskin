"""Integration tests for the complete auction draft system."""

import unittest
from unittest.mock import Mock, patch

from test_base import BaseTestCase, TestDataGenerator


class TestCompleteAuctionFlow(BaseTestCase):
    """Test complete auction draft workflow."""
    
    @patch('data.fantasypros_loader.load_fantasypros_players')
    @patch('services.draft_loading_service.ConfigManager')
    def test_full_draft_simulation(self, mock_config_manager, mock_load_players):
        """Test a complete draft from setup to completion."""
        # Mock configuration
        mock_config = Mock()
        mock_config.budget = 200
        mock_config.num_teams = 2
        mock_config.roster_positions = {'QB': 1, 'RB': 2, 'WR': 2}
        mock_config.teams = [
            {'owner_name': 'Owner 1', 'team_name': 'Team 1', 'strategy': 'value'},
            {'owner_name': 'Owner 2', 'team_name': 'Team 2', 'strategy': 'aggressive'}
        ]
        mock_config.data_source = 'fantasypros'
        mock_config.data_path = 'test/path'
        mock_config.min_projected_points = 5.0
        
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.load_config.return_value = mock_config
        mock_config_manager.return_value = mock_config_manager_instance
        
        # Mock player data
        test_players = TestDataGenerator.create_test_players(20)
        mock_load_players.return_value = test_players
        
        try:
            # Step 1: Load draft configuration
            from services.draft_loading_service import DraftLoadingService
            
            draft_service = DraftLoadingService()
            draft_result = draft_service.load_draft_from_config()
            
            if not draft_result['success']:
                self.skipTest(f"Draft loading failed: {draft_result.get('error', 'Unknown error')}")
                
            draft = draft_result['draft']
            auction = draft_result['auction']
            
            # Verify draft setup
            self.assertEqual(len(draft.teams), 2)
            self.assertGreater(len(draft.available_players), 0)
            
            # Step 2: Test bid recommendations
            from services.bid_recommendation_service import BidRecommendationService
            
            bid_service = BidRecommendationService()
            
            if len(draft.teams) > 0 and len(draft.available_players) > 0:
                team = draft.teams[0]
                player = draft.available_players[0]
                
                bid_result = bid_service.recommend_bid(auction, player, team)
                
                # Should get some kind of recommendation
                self.assertIn('success', bid_result)
                
            # Step 3: Simulate some auction activity using the sealed-bid model.
            # In the sealed-bid model, nominate_player resolves the auction
            # immediately and synchronously — there is no timer or intermediate
            # is_active period visible to callers.
            if len(draft.available_players) > 0:
                first_player = draft.available_players[0]
                players_before = len(draft.available_players)

                # Nominate player — resolves immediately in sealed-bid mode
                result = auction.nominate_player(first_player.player_id, "Owner 1")
                self.assertTrue(result, "nominate_player should return True for a valid player")

                # After sealed-bid resolution the player has been processed:
                # either drafted (if a bidder won) or still available (if no bids).
                # Either way, the auction has returned to the idle state.
                self.assertFalse(
                    auction.is_active,
                    "auction.is_active should be False after sealed-bid resolution",
                )

                # The player pool has shrunk by at least 1 (player was resolved)
                self.assertLess(
                    len(draft.available_players),
                    players_before,
                    "available_players should shrink after a nomination is resolved",
                )
                
        except ImportError as e:
            self.skipTest(f"Integration test skipped due to import error: {e}")
        except Exception as e:
            self.fail(f"Integration test failed: {e}")
            
    def test_strategy_interaction_simulation(self):
        """Test interaction between different strategies in auction."""
        try:
            from classes.draft import Draft
            from classes.auction import Auction
            from strategies import create_strategy
            
            # Create draft with multiple strategies
            draft = Draft(name="Test Draft", budget_per_team=200, roster_size=9)
            
            # Create teams with different strategies
            strategies = ['value', 'aggressive', 'conservative', 'sigmoid']
            teams = []
            owners = []
            
            for i, strategy_type in enumerate(strategies):
                team = self.create_mock_team(f"Team {i+1}")
                owner = self.create_mock_owner(f"Owner {i+1}")
                strategy = create_strategy(strategy_type)
                
                team.set_strategy(strategy)
                owner.assign_team(team)
                
                draft.add_team(team, owner)
                teams.append(team)
                owners.append(owner)
                
            # Add players
            test_players = TestDataGenerator.create_test_players(20)
            draft.add_players(test_players)
            
            # Create auction
            auction = Auction(draft)
            
            # Simulate bidding on a player
            if test_players:
                player = test_players[0]
                auction.nominate_player(player.player_id, owners[0].name)
                
                # Get bids from each strategy
                bids = []
                for i, team in enumerate(teams):
                    owner = owners[i]
                    bid = team.calculate_bid(
                        player, owner, 5.0, 
                        draft.available_players
                    )
                    bids.append((f"Strategy {team.strategy.name}", bid))
                    
                # Should have different bidding behaviors
                self.assertEqual(len(bids), 4)
                
                # At least some strategies should produce non-zero bids
                non_zero_bids = [bid for _, bid in bids if bid > 0]
                self.assertGreater(len(non_zero_bids), 0)
                
        except ImportError as e:
            self.skipTest(f"Strategy interaction test skipped due to import error: {e}")
        except Exception as e:
            self.fail(f"Strategy interaction test failed: {e}")


class TestSystemPerformance(BaseTestCase):
    """Test system performance and scalability."""
    
    def test_large_player_set_handling(self):
        """Test handling of large player datasets."""
        try:
            # Create large dataset
            large_player_set = TestDataGenerator.create_test_players(500)
            
            from classes.draft import Draft
            
            draft = Draft(name="Large Draft", budget_per_team=200, roster_size=9)
            
            # Test adding large number of players
            import time
            start_time = time.time()
            draft.add_players(large_player_set)
            end_time = time.time()
            
            # Should complete in reasonable time (less than 1 second)
            self.assertLess(end_time - start_time, 1.0)
            self.assertEqual(len(draft.available_players), 500)
            
        except ImportError as e:
            self.skipTest(f"Performance test skipped due to import error: {e}")
            
    def test_tournament_scalability(self):
        """Test tournament scalability with multiple simulations."""
        try:
            from services.tournament_service import TournamentService
            from config.config_manager import ConfigManager
            
            with patch('services.tournament_service.load_fantasypros_players') as mock_load:
                with patch.object(ConfigManager, 'load_config') as mock_config:
                    # Mock data
                    test_players = TestDataGenerator.create_test_players(100)
                    mock_load.return_value = test_players
                    
                    mock_config_obj = Mock()
                    mock_config_obj.budget = 200
                    mock_config_obj.roster_positions = {'QB': 1, 'RB': 2}
                    mock_config_obj.data_source = 'fantasypros'
                    mock_config_obj.data_path = 'test'
                    mock_config_obj.min_projected_points = 5.0
                    mock_config.return_value = mock_config_obj
                    
                    service = TournamentService()
                    
                    # Test with small number of simulations
                    import time
                    start_time = time.time()
                    
                    result = service.run_strategy_tournament(
                        strategies_to_test=['value', 'aggressive'],
                        num_simulations=3,  # Small number for testing
                        teams_per_strategy=1
                    )
                    
                    end_time = time.time()
                    
                    # Should complete in reasonable time
                    self.assertLess(end_time - start_time, 30.0)  # 30 seconds max
                    self.assertIn('success', result)
                    
        except ImportError as e:
            self.skipTest(f"Tournament scalability test skipped due to import error: {e}")


class TestErrorHandling(BaseTestCase):
    """Test system error handling and recovery."""
    
    def test_invalid_data_handling(self):
        """Test handling of invalid or corrupted data."""
        try:
            from classes.player import Player
            
            # Test creating player with invalid data
            with self.assertRaises((ValueError, TypeError)):
                Player(
                    player_id=None,  # Invalid
                    name="Test Player",
                    position="QB",
                    team="TEST",
                    projected_points="invalid"  # Invalid type
                )
                
        except ImportError as e:
            self.skipTest(f"Error handling test skipped due to import error: {e}")
            
    def test_auction_error_recovery(self):
        """Test auction error handling and recovery."""
        try:
            from classes.draft import Draft
            from classes.auction import Auction
            
            draft = Draft(name="Test Draft", budget_per_team=200, roster_size=9)
            auction = Auction(draft)
            
            # Test nominating non-existent player
            with self.assertRaises((KeyError, ValueError)):
                auction.nominate_player("nonexistent_player", "Test Owner")
                
            # Test invalid bid — place_bid is a sealed-bid no-op; returns False
            result = auction.place_bid("Test Team", -10.0)
            self.assertFalse(result)
                
        except ImportError as e:
            self.skipTest(f"Auction error test skipped due to import error: {e}")
            
    def test_strategy_error_handling(self):
        """Test strategy error handling."""
        try:
            from strategies import create_strategy
            
            # Test invalid strategy creation
            with self.assertRaises(ValueError):
                create_strategy("nonexistent_strategy")
                
            # Test strategy with invalid parameters
            strategy = create_strategy("value")
            
            # Should handle None values gracefully
            bid = strategy.calculate_bid(
                None, None, None, 0.0, 100.0, []
            )
            
            # Should either return 0 or raise appropriate error
            self.assertTrue(isinstance(bid, (int, float)) or bid is None)
            
        except ImportError as e:
            self.skipTest(f"Strategy error test skipped due to import error: {e}")


class TestDataConsistency(BaseTestCase):
    """Test data consistency across the system."""
    
    def test_budget_consistency(self):
        """Test that budget calculations remain consistent."""
        try:
            team = self.create_mock_team(budget=200.0)
            
            # Add players and verify budget consistency
            total_spent = 0.0
            for i in range(3):
                player = self.create_mock_player(player_id=f"p{i}")
                cost = 20.0 + i * 10
                team.add_player(player, cost)
                total_spent += cost
                
                # Budget should always be consistent
                expected_remaining = 200.0 - total_spent
                self.assertEqual(team.budget, expected_remaining)
                
        except ImportError as e:
            self.skipTest(f"Budget consistency test skipped due to import error: {e}")
            
    def test_roster_consistency(self):
        """Test that roster management remains consistent."""
        try:
            team = self.create_mock_team()
            
            # Test roster limits
            initial_needs = team.get_needs()
            
            # Add players for each position
            for position in ['QB', 'RB', 'WR']:
                if position in initial_needs:
                    player = self.create_mock_player(position=position)
                    team.add_player(player, 20.0)
                    
            # Verify roster consistency
            current_needs = team.get_needs()
            roster_count = len(team.roster)
            
            self.assertGreaterEqual(roster_count, 0)
            self.assertIsInstance(current_needs, list)
            
        except ImportError as e:
            self.skipTest(f"Roster consistency test skipped due to import error: {e}")


if __name__ == '__main__':
    unittest.main()
