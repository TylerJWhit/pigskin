"""Test cases for data loading and API functionality."""

import unittest
import sys
import os
from unittest.mock import Mock, patch, mock_open

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from test_base import BaseTestCase


class TestFantasyProsLoader(BaseTestCase):
    """Test FantasyPros data loading functionality."""
    
    def setUp(self):
        super().setUp()
        # Sample CSV data for testing
        self.sample_csv_data = """player_name,team,position,projected_points,auction_value
Josh Allen,BUF,QB,325.5,28
Jonathan Taylor,IND,RB,245.2,35
Cooper Kupp,LAR,WR,220.8,32
Travis Kelce,KC,TE,185.4,22
Justin Tucker,BAL,K,145.2,8
Buffalo Bills,BUF,DST,155.8,12"""
        
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    @patch('os.listdir')
    def test_load_fantasypros_players_success(self, mock_listdir, mock_exists, mock_file):
        """Test successful loading of FantasyPros data."""
        from data.fantasypros_loader import load_fantasypros_players
        
        # Mock file system
        mock_exists.return_value = True
        mock_listdir.return_value = ['QB.csv', 'RB.csv', 'WR.csv', 'TE.csv', 'K.csv', 'DST.csv']
        mock_file.return_value.read.return_value = self.sample_csv_data
        
        # Test loading
        players = load_fantasypros_players('test/path')
        
        # Should return a list of players
        self.assertIsInstance(players, list)
        
    @patch('os.path.exists')
    def test_load_fantasypros_players_invalid_path(self, mock_exists):
        """Test loading with invalid path."""
        from data.fantasypros_loader import load_fantasypros_players
        
        mock_exists.return_value = False
        
        players = load_fantasypros_players('invalid/path')
        self.assertEqual(players, [])
        
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    @patch('os.listdir')
    def test_load_fantasypros_players_with_filters(self, mock_listdir, mock_exists, mock_file):
        """Test loading with minimum points filter."""
        from data.fantasypros_loader import load_fantasypros_players
        
        # Mock file system
        mock_exists.return_value = True
        mock_listdir.return_value = ['QB.csv']
        mock_file.return_value.read.return_value = self.sample_csv_data
        
        # Test with high minimum points (should filter out most players)
        players = load_fantasypros_players('test/path', min_projected_points=300.0)
        
        self.assertIsInstance(players, list)
        
    def test_csv_parsing_edge_cases(self):
        """Test CSV parsing with edge cases."""
        from data.fantasypros_loader import _parse_csv_file
        
        # Test empty CSV
        empty_csv = "player_name,team,position,projected_points,auction_value\n"
        players = _parse_csv_file(empty_csv, 'QB')
        self.assertEqual(len(players), 0)
        
        # Test CSV with invalid data
        invalid_csv = """player_name,team,position,projected_points,auction_value
Invalid Player,TEAM,QB,invalid,invalid"""
        players = _parse_csv_file(invalid_csv, 'QB')
        self.assertEqual(len(players), 0)


class TestSleeperAPI(BaseTestCase):
    """Test Sleeper API functionality."""
    
    def setUp(self):
        super().setUp()
        
    @patch('requests.get')
    def test_get_nfl_players_success(self, mock_get):
        """Test successful NFL players retrieval."""
        from api.sleeper_api import SleeperAPI
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            '1': {
                'player_id': '1',
                'full_name': 'Test Player',
                'position': 'QB',
                'team': 'TEST'
            }
        }
        mock_get.return_value = mock_response
        
        api = SleeperAPI()
        players = api.get_nfl_players()
        
        self.assertIsInstance(players, dict)
        self.assertIn('1', players)
        
    @patch('requests.get')
    def test_get_nfl_players_failure(self, mock_get):
        """Test NFL players retrieval failure."""
        from api.sleeper_api import SleeperAPI
        
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        api = SleeperAPI()
        players = api.get_nfl_players()
        
        self.assertEqual(players, {})
        
    @patch('requests.get')
    def test_get_user_success(self, mock_get):
        """Test successful user retrieval."""
        from api.sleeper_api import SleeperAPI
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'user_id': 'test_user',
            'username': 'test_username'
        }
        mock_get.return_value = mock_response
        
        api = SleeperAPI()
        user = api.get_user('test_username')
        
        self.assertIsInstance(user, dict)
        self.assertEqual(user['user_id'], 'test_user')
        
    @patch('requests.get')
    def test_get_user_not_found(self, mock_get):
        """Test user not found."""
        from api.sleeper_api import SleeperAPI
        
        # Mock not found response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        api = SleeperAPI()
        user = api.get_user('nonexistent_user')
        
        self.assertIsNone(user)
        
    @patch('requests.get')
    def test_get_leagues_success(self, mock_get):
        """Test successful leagues retrieval."""
        from api.sleeper_api import SleeperAPI
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'league_id': 'league_1',
                'name': 'Test League'
            }
        ]
        mock_get.return_value = mock_response
        
        api = SleeperAPI()
        leagues = api.get_user_leagues('test_user', 2023)
        
        self.assertIsInstance(leagues, list)
        self.assertEqual(len(leagues), 1)
        
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        from api.sleeper_api import SleeperAPI
        
        api = SleeperAPI()
        
        # Test that rate limiting attributes exist
        self.assertTrue(hasattr(api, 'last_request_time'))
        self.assertTrue(hasattr(api, 'min_request_interval'))
        
    @patch('time.sleep')
    @patch('requests.get')
    def test_rate_limiting_delay(self, mock_get, mock_sleep):
        """Test that rate limiting adds appropriate delays."""
        from api.sleeper_api import SleeperAPI
        import time
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response
        
        api = SleeperAPI()
        
        # Simulate rapid requests
        api.last_request_time = time.time()  # Recent request
        api.get_nfl_players()
        
        # Should have called sleep to enforce rate limit
        mock_sleep.assert_called()


class TestConfigManager(BaseTestCase):
    """Test configuration management functionality."""
    
    def setUp(self):
        super().setUp()
        self.test_config_data = {
            'budget': 200,
            'num_teams': 10,
            'roster_positions': {
                'QB': 1,
                'RB': 2,
                'WR': 3
            },
            'strategy_type': 'value',
            'data_source': 'fantasypros',
            'data_path': 'test/path',
            'min_projected_points': 5.0
        }
        
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_load_config_success(self, mock_exists, mock_file):
        """Test successful config loading."""
        from config.config_manager import ConfigManager
        import json
        
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.test_config_data)
        
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        self.assertEqual(config.budget, 200)
        self.assertIn('QB', config.roster_positions)
        self.assertEqual(config.num_teams, 10)
        
    @patch('os.path.exists')
    def test_load_config_missing_file(self, mock_exists):
        """Test config loading with missing file."""
        from config.config_manager import ConfigManager
        
        mock_exists.return_value = False
        
        config_manager = ConfigManager()
        
        # Should create default config when file doesn't exist
        with patch.object(config_manager, 'create_default_config') as mock_create:
            config_manager.load_config()
            mock_create.assert_called_once()
            
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_save_config(self, mock_exists, mock_file):
        """Test config saving."""
        from config.config_manager import ConfigManager
        
        mock_exists.return_value = True
        
        config_manager = ConfigManager()
        
        # Test saving
        config_manager.save_config(self.test_config_data)
        
        # Should have written to file
        mock_file.assert_called()
        
    def test_validate_config(self):
        """Test config validation."""
        from config.config_manager import ConfigManager
        
        config_manager = ConfigManager()
        
        # Test valid config
        is_valid, errors = config_manager.validate_config(self.test_config_data)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Test invalid config (missing budget)
        invalid_config = self.test_config_data.copy()
        del invalid_config['budget']
        
        is_valid, errors = config_manager.validate_config(invalid_config)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)


if __name__ == '__main__':
    unittest.main()
