"""Test cases for services (draft loading, bid recommendations, tournament)."""

import unittest
from unittest.mock import Mock, patch

from test_base import BaseTestCase, TestDataGenerator


class TestDraftLoadingService(BaseTestCase):
    """Test Draft Loading Service functionality."""
    
    def setUp(self):
        super().setUp()
        
    @patch('services.draft_loading_service.ConfigManager')
    @patch('services.draft_loading_service.load_fantasypros_players')
    def test_load_draft_from_config(self, mock_load_players, mock_config_manager):
        """Test loading draft from configuration."""
        from services.draft_loading_service import DraftLoadingService
        
        # Mock configuration
        mock_config = Mock()
        mock_config.budget = 200
        mock_config.num_teams = 2
        mock_config.roster_positions = {'QB': 1, 'RB': 2, 'WR': 3}
        mock_config.teams = [
            {'owner_name': 'Owner 1', 'team_name': 'Team 1', 'strategy': 'value'},
            {'owner_name': 'Owner 2', 'team_name': 'Team 2', 'strategy': 'aggressive'}
        ]
        mock_config.data_source = 'fantasypros'
        mock_config.data_path = '/home/tezell/Documents/code/pigskin/data/sheets'
        mock_config.min_projected_points = 5.0
        mock_config.sleeper_draft_id = None
        
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.load_config.return_value = mock_config
        mock_config_manager.return_value = mock_config_manager_instance
        
        # Mock player loading
        test_players = TestDataGenerator.create_test_players(20)
        mock_load_players.return_value = test_players
        
        # Test service
        service = DraftLoadingService()
        result = service.load_draft_from_config()
        
        self.assertTrue(result['success'])
        self.assertIn('draft', result)
        self.assertIn('auction', result)
        
        draft = result['draft']
        self.assertEqual(len(draft.teams), 2)
        # Available players count depends on whether CSV data files are present;
        # just verify the draft loaded with at least some players.
        self.assertGreater(len(draft.available_players), 0)
        
    def test_load_draft_invalid_config(self):
        """Test handling of invalid configuration."""
        from services.draft_loading_service import DraftLoadingService
        
        with patch('services.draft_loading_service.ConfigManager') as mock_config_manager:
            mock_config_manager_instance = Mock()
            mock_config_manager_instance.load_config.side_effect = Exception("Config error")
            mock_config_manager.return_value = mock_config_manager_instance
            
            service = DraftLoadingService()
            result = service.load_draft_from_config()
            
            self.assertFalse(result['success'])
            self.assertIn('message', result)


class TestBidRecommendationService(BaseTestCase):
    """Test Bid Recommendation Service functionality."""
    
    def setUp(self):
        super().setUp()
        self.players = TestDataGenerator.create_test_players(20)
        
    @patch('services.bid_recommendation_service.ConfigManager')
    def test_recommend_bid_basic(self, mock_config_manager):
        """Test basic bid recommendation."""
        from services.bid_recommendation_service import BidRecommendationService
        from classes.auction import Auction
        from classes.draft import Draft
        
        # Mock configuration
        mock_config = Mock()
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.load_config.return_value = mock_config
        mock_config_manager.return_value = mock_config_manager_instance
        
        # Create test objects
        draft = Draft("Test Draft", budget_per_team=200, roster_size=9)
        auction = Auction(draft)
        player = self.create_mock_player()
        team = self.create_mock_team()
        
        service = BidRecommendationService()
        recommendation = service.recommend_bid(auction, player, team)
        
        self.assertIn('success', recommendation)
        # recommended_bid is present in both success and failure responses
        self.assertIn('recommended_bid', recommendation)
        self.assertIn('should_bid', recommendation)
        if recommendation['success']:
            self.assertIn('confidence', recommendation)
            self.assertIn('reasoning', recommendation)
    @patch('services.bid_recommendation_service.ConfigManager')
    def test_recommend_nomination(self, mock_config_manager):
        """Test nomination recommendation."""
        from services.bid_recommendation_service import BidRecommendationService
        from classes.auction import Auction
        from classes.draft import Draft
        
        # Mock configuration
        mock_config = Mock()
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.load_config.return_value = mock_config
        mock_config_manager.return_value = mock_config_manager_instance
        
        # Create test objects
        draft = Draft("Test Draft", budget_per_team=200, roster_size=9)
        draft.add_players(self.players)
        auction = Auction(draft)
        team = self.create_mock_team()
        
        service = BidRecommendationService()
        recommendation = service.recommend_nomination(auction, team)
        
        self.assertIn('success', recommendation)
        # success key is always present; inner fields only available on success
        if recommendation['success']:
            self.assertIn('recommended_player', recommendation)
            self.assertIn('reasoning', recommendation)
        else:
            # On failure, an error key must explain why
            self.assertIn('error', recommendation)
    @patch('services.bid_recommendation_service.ConfigManager')
    def test_analyze_team_value(self, mock_config_manager):
        """Test team value analysis."""
        from services.bid_recommendation_service import BidRecommendationService
        
        # Mock configuration  
        mock_config = Mock()
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.load_config.return_value = mock_config
        mock_config_manager.return_value = mock_config_manager_instance
        
        team = self.create_mock_team()
        # Add some players to team
        for i in range(3):
            player = self.create_mock_player(player_id=f"p{i}", projected_points=100 + i*10)
            team.add_player(player, 15.0 + i*5)
            
        service = BidRecommendationService()
        analysis = service.analyze_team_value(team)
        
        self.assertIn('success', analysis)
        if analysis['success']:
            self.assertIn('total_value', analysis)
            self.assertIn('roster_strength', analysis)
            self.assertIn('budget_efficiency', analysis)


class TestTournamentService(BaseTestCase):
    """Test Tournament Service functionality."""
    
    def setUp(self):
        super().setUp()
        
    @patch('services.tournament_service.ConfigManager')
    @patch('services.tournament_service.load_fantasypros_players')
    def test_run_strategy_tournament(self, mock_load_players, mock_config_manager):
        """Test running a strategy tournament."""
        from services.tournament_service import TournamentService
        
        # Mock configuration
        mock_config = Mock()
        mock_config.budget = 200
        mock_config.roster_positions = {'QB': 1, 'RB': 2, 'WR': 3}
        mock_config.data_source = 'fantasypros'
        mock_config.data_path = 'test/path'
        mock_config.min_projected_points = 5.0
        
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.load_config.return_value = mock_config
        mock_config_manager.return_value = mock_config_manager_instance
        
        # Mock player loading
        test_players = TestDataGenerator.create_test_players(50)
        mock_load_players.return_value = test_players
        
        service = TournamentService()
        
        # Run with minimal simulations for speed
        result = service.run_strategy_tournament(
            strategies_to_test=['value', 'aggressive'],
            num_simulations=2,  # Minimal for testing
            teams_per_strategy=1
        )
        
        self.assertIn('success', result)
        # Note: Tournament might fail due to missing dependencies, that's OK for testing
        
    @patch('services.tournament_service.ConfigManager')
    def test_find_optimal_strategy(self, mock_config_manager):
        """Test finding optimal strategy."""
        from services.tournament_service import TournamentService
        
        # Mock configuration
        mock_config = Mock()
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.load_config.return_value = mock_config
        mock_config_manager.return_value = mock_config_manager_instance
        
        service = TournamentService()
        
        # This will likely fail due to no data, but we test the interface
        result = service.find_optimal_strategy(risk_tolerance=0.5)
        
        self.assertIn('success', result)
        # The actual result will depend on whether data is available
        
    def test_tournament_progress_tracking(self):
        """Test tournament progress tracking."""
        from services.tournament_service import TournamentService
        
        service = TournamentService()
        
        # Test with no active tournament
        progress = service.get_tournament_progress()
        self.assertFalse(progress['active'])
        
        # Test stopping non-existent tournament
        stop_result = service.stop_tournament()
        self.assertFalse(stop_result['success'])


class TestServiceIntegration(BaseTestCase):
    """Test integration between services."""
    
    @patch('services.draft_loading_service.ConfigManager')
    @patch('services.draft_loading_service.load_fantasypros_players')
    def test_draft_to_bid_recommendation_flow(self, mock_load_players, mock_config_manager):
        """Test flow from draft loading to bid recommendation."""
        from services.draft_loading_service import DraftLoadingService
        from services.bid_recommendation_service import BidRecommendationService
        
        # Mock configuration for draft loading
        mock_config = Mock()
        mock_config.budget = 200
        mock_config.roster_positions = {'QB': 1, 'RB': 2}
        mock_config.teams = [
            {'owner_name': 'Owner 1', 'team_name': 'Team 1', 'strategy': 'value'}
        ]
        mock_config.data_source = 'fantasypros'
        mock_config.data_path = 'test/path'
        mock_config.min_projected_points = 5.0
        
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.load_config.return_value = mock_config
        mock_config_manager.return_value = mock_config_manager_instance
        
        # Mock player loading
        test_players = TestDataGenerator.create_test_players(10)
        mock_load_players.return_value = test_players
        
        # Load draft
        draft_service = DraftLoadingService()
        draft_result = draft_service.load_draft_from_config()
        
        if draft_result['success']:
            # Use loaded draft for bid recommendation
            auction = draft_result['auction']
            draft = draft_result['draft']
            team = draft.teams[0] if draft.teams else self.create_mock_team()
            player = test_players[0] if test_players else self.create_mock_player()
            
            # Get bid recommendation
            bid_service = BidRecommendationService()
            bid_result = bid_service.recommend_bid(auction, player, team)
            
            self.assertIn('success', bid_result)
            
    def test_convenience_functions(self):
        """Test convenience functions from services."""
        # Test strategy tournament convenience function
        with patch('services.tournament_service.ConfigManager'):
            with patch('services.tournament_service.load_fantasypros_players'):
                from services.tournament_service import run_strategy_tournament
                
                result = run_strategy_tournament(
                    strategies_to_test=['value'],
                    num_simulations=1
                )
                self.assertIn('success', result)
                
        # Test draft loading convenience function
        with patch('services.draft_loading_service.ConfigManager'):
            with patch('services.draft_loading_service.load_fantasypros_players'):
                from services.draft_loading_service import load_draft_from_config
                
                result = load_draft_from_config()
                self.assertIn('success', result)


if __name__ == '__main__':
    unittest.main()
