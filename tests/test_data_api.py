"""Test cases for data loading and API functionality."""

import unittest
from unittest.mock import Mock, patch, mock_open

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
        
    @patch('requests.Session.get')
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
        
    @patch('requests.Session.get')
    def test_get_nfl_players_failure(self, mock_get):
        """Test NFL players retrieval failure."""
        from api.sleeper_api import SleeperAPI

        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 500
        import requests as _requests
        mock_response.raise_for_status.side_effect = _requests.exceptions.HTTPError("500 Server Error")
        mock_get.return_value = mock_response
        
        api = SleeperAPI()
        players = api.get_nfl_players()
        
        self.assertEqual(players, {})
        
    @patch('requests.Session.get')
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
        
    @patch('requests.Session.get')
    def test_get_user_not_found(self, mock_get):
        """Test user not found."""
        from api.sleeper_api import SleeperAPI

        # Mock not found response
        mock_response = Mock()
        mock_response.status_code = 404
        import requests as _requests
        mock_response.raise_for_status.side_effect = _requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        api = SleeperAPI()
        user = api.get_user('nonexistent_user')
        
        self.assertIsNone(user)
        
    @patch('requests.Session.get')
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
        
    @patch('api.sleeper_api.time')
    @patch('requests.Session.get')
    def test_rate_limiting_delay(self, mock_get, mock_time):
        """Test that rate limiting adds appropriate delays."""
        from api.sleeper_api import SleeperAPI

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        # Make time.time() report a very recent last_request so the rate limit fires
        mock_time.time.return_value = 1000.0

        api = SleeperAPI(rate_limit_delay=1.0)
        api.last_request_time = 999.95  # 0.05s ago → under 1.0s limit

        api.get_nfl_players()

        # sleep must have been called to enforce rate limit
        mock_time.sleep.assert_called()


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
        with patch.object(config_manager, 'create_default_config') as mock_create, \
             patch.object(config_manager, 'save_config'):
            config_manager.load_config()
            mock_create.assert_called_once()
            
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_save_config(self, mock_exists, mock_file):
        """Test config saving."""
        from config.config_manager import ConfigManager, DraftConfig
        
        mock_exists.return_value = True
        
        config_manager = ConfigManager()
        
        # Test saving with a proper DraftConfig object
        draft_config = DraftConfig.from_dict(self.test_config_data)
        config_manager.save_config(draft_config)
        
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


class TestSleeperAPIPathEncoding(BaseTestCase):
    """Regression tests for #97 — URL path segments must be encoded to prevent SSRF."""

    def test_safe_path_encodes_slash(self):
        """_safe_path must URL-encode forward slashes (the traversal vector)."""
        from api.sleeper_api import _safe_path
        encoded = _safe_path("../../admin")
        # Slashes must be percent-encoded; the segment cannot escape its path position
        self.assertNotIn("/", encoded,
            msg=f"Unencoded slash survived: {encoded}")
        self.assertIn("%2F", encoded.upper(),
            msg=f"Expected %2F encoding of slashes in: {encoded}")

    def test_safe_path_plain_value_unchanged(self):
        """_safe_path must not corrupt normal alphanumeric IDs."""
        from api.sleeper_api import _safe_path
        self.assertEqual(_safe_path("abc123"), "abc123")

    def test_get_user_encodes_slashes_in_path(self):
        """get_user must URL-encode the username so slashes cannot escape the path segment."""
        from api.sleeper_api import SleeperAPI
        from unittest.mock import patch
        api = SleeperAPI()
        with patch.object(api, '_make_request') as mock_req:
            mock_req.return_value = {}
            api.get_user("../../admin")
            called_path = mock_req.call_args[0][0]
            # The final URL segment must not contain a literal unencoded slash
            # i.e. the attacker cannot inject "/admin" as a new path component
            self.assertNotIn("/../", called_path,
                msg=f"Traversal sequence survived URL construction: {called_path}")

    def test_get_league_encodes_slashes_in_league_id(self):
        """get_league must URL-encode the league_id."""
        from api.sleeper_api import SleeperAPI
        from unittest.mock import patch
        api = SleeperAPI()
        with patch.object(api, '_make_request') as mock_req:
            mock_req.return_value = {}
            api.get_league("../secret")
            called_path = mock_req.call_args[0][0]
            self.assertNotIn("/../", called_path)


class TestPathUtilsTraversalGuard(BaseTestCase):
    """Regression tests for #160 — path traversal must raise ValueError."""

    def test_get_data_file_traversal_raises(self):
        """get_data_file must raise ValueError for traversal sequences."""
        from utils.path_utils import get_data_file
        with self.assertRaises(ValueError):
            get_data_file("../../../etc/passwd")

    def test_get_data_file_double_dot_raises(self):
        """get_data_file must raise ValueError for relative traversal."""
        from utils.path_utils import get_data_file
        with self.assertRaises(ValueError):
            get_data_file("../config.json")

    def test_safe_file_path_outside_root_raises(self):
        """safe_file_path must raise ValueError for absolute paths outside the project."""
        from utils.path_utils import safe_file_path
        with self.assertRaises(ValueError):
            safe_file_path("/etc/passwd")

    def test_get_data_file_normal_path_ok(self):
        """get_data_file must not raise for a benign filename."""
        from utils.path_utils import get_data_file
        result = get_data_file("players.csv")
        self.assertIn("players.csv", str(result))

    def test_safe_file_path_within_project_ok(self):
        """safe_file_path must not raise for a path inside the project root."""
        from utils.path_utils import safe_file_path, get_project_root
        result = safe_file_path(get_project_root() / "data" / "sample.json")
        self.assertIsNotNone(result)


class TestSleeperAPIExponentialBackoff(BaseTestCase):
    """Tests for #91 — exponential backoff on 429 responses."""

    @patch('time.sleep')
    @patch('requests.Session.get')
    def test_429_retries_with_backoff(self, mock_get, mock_sleep):
        """_make_request must retry on 429 with exponential backoff."""
        from api.sleeper_api import SleeperAPI

        rate_429 = Mock()
        rate_429.status_code = 429

        ok_resp = Mock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"user_id": "abc"}

        mock_get.side_effect = [rate_429, ok_resp]

        api = SleeperAPI(rate_limit_delay=0, max_retries=5)
        result = api._make_request("/user/testuser")

        self.assertEqual(result, {"user_id": "abc"})
        # sleep must have been called at least once for the backoff
        mock_sleep.assert_called()

    @patch('time.sleep')
    @patch('requests.Session.get')
    def test_429_exhausts_retries_raises(self, mock_get, mock_sleep):
        """_make_request must raise SleeperAPIError after exhausting all retries."""
        from api.sleeper_api import SleeperAPI, SleeperAPIError

        rate_429 = Mock()
        rate_429.status_code = 429

        api = SleeperAPI(rate_limit_delay=0, max_retries=2)
        mock_get.return_value = rate_429

        with self.assertRaises(SleeperAPIError):
            api._make_request("/user/testuser")

        # We called sleep for each retry (max_retries=2 means 2 backoff sleeps)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('time.sleep')
    @patch('requests.Session.get')
    def test_backoff_delay_increases(self, mock_get, mock_sleep):
        """Each retry backoff delay must be larger than the previous one (without jitter)."""
        from api.sleeper_api import SleeperAPI, SleeperAPIError

        rate_429 = Mock()
        rate_429.status_code = 429

        api = SleeperAPI(rate_limit_delay=0, max_retries=3, backoff_jitter=0)
        mock_get.return_value = rate_429

        with self.assertRaises(SleeperAPIError):
            api._make_request("/user/testuser")

        # Extract sleep durations (ignoring sub-second rate-limiting sleeps)
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        backoff_delays = [d for d in delays if d >= 1.0]
        # Each backoff delay should be >= the previous one
        for i in range(1, len(backoff_delays)):
            self.assertGreaterEqual(backoff_delays[i], backoff_delays[i - 1],
                msg=f"Backoff delay did not increase: {backoff_delays}")

    def test_default_max_retries(self):
        """SleeperAPI default max_retries should be 5."""
        from api.sleeper_api import SleeperAPI
        api = SleeperAPI()
        self.assertEqual(api.max_retries, 5)


if __name__ == '__main__':
    unittest.main()
