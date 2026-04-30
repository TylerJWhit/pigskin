"""
Unit tests for Sleeper API wrapper.

This module tests the SleeperAPI class that wraps the Sleeper Fantasy Football API.
Tests validate actual implementation functionality including rate limiting, error handling,
and data conversion methods.
"""

import pytest
from unittest.mock import Mock, patch
import requests
from requests.exceptions import ConnectionError, Timeout

# Import the module under test
from api.sleeper_api import SleeperAPI, SleeperAPIError


class TestSleeperAPIInitialization:
    """Test SleeperAPI initialization and configuration."""
    
    def test_sleeper_api_init_default_values(self):
        """Test SleeperAPI initialization with default values."""
        api = SleeperAPI()
        
        assert api.rate_limit_delay == 0.1
        assert api.BASE_URL == "https://api.sleeper.app/v1"
        assert isinstance(api.session, requests.Session)
        assert api.session.headers['User-Agent'] == 'PigskinAuctionDraft/1.0'
        assert api.last_request_time == 0
    
    def test_sleeper_api_init_custom_rate_limit(self):
        """Test SleeperAPI initialization with custom rate limit."""
        custom_delay = 0.5
        api = SleeperAPI(rate_limit_delay=custom_delay)
        
        assert api.rate_limit_delay == custom_delay
        assert isinstance(api.session, requests.Session)
    
    def test_sleeper_api_session_configuration(self):
        """Test that session is properly configured."""
        api = SleeperAPI()
        
        assert 'User-Agent' in api.session.headers
        assert api.session.headers['User-Agent'] == 'PigskinAuctionDraft/1.0'


class TestSleeperAPIRequestHandling:
    """Test HTTP request handling and rate limiting."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI(rate_limit_delay=0.01)  # Small delay for testing
    
    @patch('requests.Session.get')
    def test_make_request_success(self, mock_get):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'test': 'data'}
        mock_get.return_value = mock_response
        
        result = self.api._make_request('/test')
        
        assert result == {'test': 'data'}
        mock_get.assert_called_once_with(
            'https://api.sleeper.app/v1/test',
            params=None
        )
    
    @patch('requests.Session.get')
    def test_make_request_with_params(self, mock_get):
        """Test API request with parameters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'result': 'success'}
        mock_get.return_value = mock_response
        
        params = {'season': '2024', 'week': 1}
        result = self.api._make_request('/endpoint', params)
        
        assert result == {'result': 'success'}
        mock_get.assert_called_once_with(
            'https://api.sleeper.app/v1/endpoint',
            params=params
        )
    
    @patch('requests.Session.get')
    @patch('time.sleep')
    def test_make_request_rate_limiting(self, mock_sleep, mock_get):
        """Test that rate limiting is properly applied."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': 'test'}
        mock_get.return_value = mock_response
        
        # Make first request
        self.api._make_request('/test1')
        
        # Make second request immediately - should trigger rate limiting
        self.api._make_request('/test2')
        
        # Should have called sleep to enforce rate limit
        mock_sleep.assert_called()
    
    @patch('requests.Session.get')
    @patch('time.sleep')
    def test_make_request_429_retry(self, mock_sleep, mock_get):
        """Test handling of 429 rate limit response with retry."""
        # First response is rate limited
        rate_limited_response = Mock()
        rate_limited_response.status_code = 429
        
        # Second response is successful
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {'retried': 'success'}
        
        mock_get.side_effect = [rate_limited_response, success_response]
        
        result = self.api._make_request('/test')
        
        assert result == {'retried': 'success'}
        assert mock_get.call_count == 2
        # Exponential backoff: first retry delay is backoff_base * 2^0 + jitter
        assert mock_sleep.call_count >= 1
    
    @patch('requests.Session.get')
    def test_make_request_404_error(self, mock_get):
        """Test handling of 404 not found response."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = 'Not found'
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Client Error")
        mock_get.return_value = mock_response
        
        with pytest.raises(SleeperAPIError, match="API request failed"):
            self.api._make_request('/nonexistent')
    
    @patch('requests.Session.get')
    def test_make_request_connection_error(self, mock_get):
        """Test handling of connection errors."""
        mock_get.side_effect = ConnectionError("Connection failed")
        
        with pytest.raises(SleeperAPIError, match="API request failed.*Connection failed"):
            self.api._make_request('/test')
    
    @patch('requests.Session.get')
    def test_make_request_timeout_error(self, mock_get):
        """Test handling of timeout errors."""
        mock_get.side_effect = Timeout("Request timed out")
        
        with pytest.raises(SleeperAPIError, match="API request failed.*Request timed out"):
            self.api._make_request('/test')


class TestSleeperAPIUserMethods:
    """Test user-related API methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    @patch.object(SleeperAPI, '_make_request')
    def test_get_user_success(self, mock_request):
        """Test successful user lookup."""
        mock_request.return_value = {
            'user_id': '12345',
            'username': 'testuser',
            'display_name': 'Test User'
        }
        
        result = self.api.get_user('testuser')
        
        assert result['username'] == 'testuser'
        assert result['user_id'] == '12345'
        mock_request.assert_called_once_with('/user/testuser')
    
    @patch.object(SleeperAPI, '_make_request')
    def test_get_user_not_found(self, mock_request):
        """Test user lookup when user doesn't exist."""
        mock_request.side_effect = SleeperAPIError("HTTP 404")
        
        result = self.api.get_user('nonexistentuser')
        
        assert result is None
    
    @patch.object(SleeperAPI, '_make_request')
    def test_get_user_leagues_success(self, mock_request):
        """Test getting user leagues."""
        mock_request.return_value = [
            {'league_id': 'league1', 'name': 'Test League 1'},
            {'league_id': 'league2', 'name': 'Test League 2'}
        ]
        
        result = self.api.get_user_leagues('user123')
        
        assert len(result) == 2
        assert result[0]['league_id'] == 'league1'
        mock_request.assert_called_once_with('/user/user123/leagues/nfl/2024')
    
    @patch.object(SleeperAPI, '_make_request')
    def test_get_user_leagues_custom_season(self, mock_request):
        """Test getting user leagues for custom season."""
        mock_request.return_value = []
        
        self.api.get_user_leagues('user123', season='2023')
        
        mock_request.assert_called_once_with('/user/user123/leagues/nfl/2023')


class TestSleeperAPILeagueMethods:
    """Test league-related API methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    @patch.object(SleeperAPI, '_make_request')
    def test_get_league_success(self, mock_request):
        """Test successful league lookup."""
        mock_request.return_value = {
            'league_id': 'league123',
            'name': 'Test League',
            'total_rosters': 12,
            'scoring_settings': {'pass_td': 4}
        }
        
        result = self.api.get_league('league123')
        
        assert result['league_id'] == 'league123'
        assert result['total_rosters'] == 12
        mock_request.assert_called_once_with('/league/league123')
    
    @patch.object(SleeperAPI, '_make_request')
    def test_get_league_rosters(self, mock_request):
        """Test getting league rosters."""
        mock_request.return_value = [
            {'roster_id': 1, 'owner_id': 'user1', 'players': ['player1', 'player2']},
            {'roster_id': 2, 'owner_id': 'user2', 'players': ['player3', 'player4']}
        ]
        
        result = self.api.get_league_rosters('league123')
        
        assert len(result) == 2
        assert result[0]['roster_id'] == 1
        mock_request.assert_called_once_with('/league/league123/rosters')
    
    @patch.object(SleeperAPI, '_make_request')
    def test_get_league_users(self, mock_request):
        """Test getting league users."""
        mock_request.return_value = [
            {'user_id': 'user1', 'display_name': 'User One'},
            {'user_id': 'user2', 'display_name': 'User Two'}
        ]
        
        result = self.api.get_league_users('league123')
        
        assert len(result) == 2
        assert result[0]['display_name'] == 'User One'
        mock_request.assert_called_once_with('/league/league123/users')


class TestSleeperAPIDraftMethods:
    """Test draft-related API methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    @patch.object(SleeperAPI, '_make_request')
    def test_get_league_drafts(self, mock_request):
        """Test getting league drafts."""
        mock_request.return_value = [
            {'draft_id': 'draft1', 'type': 'auction', 'status': 'complete'},
            {'draft_id': 'draft2', 'type': 'snake', 'status': 'in_progress'}
        ]
        
        result = self.api.get_league_drafts('league123')
        
        assert len(result) == 2
        assert result[0]['type'] == 'auction'
        mock_request.assert_called_once_with('/league/league123/drafts')
    
    @patch.object(SleeperAPI, '_make_request')
    def test_get_draft(self, mock_request):
        """Test getting specific draft details."""
        mock_request.return_value = {
            'draft_id': 'draft123',
            'type': 'auction',
            'status': 'complete',
            'settings': {'budget': 200}
        }
        
        result = self.api.get_draft('draft123')
        
        assert result['draft_id'] == 'draft123'
        assert result['settings']['budget'] == 200
        mock_request.assert_called_once_with('/draft/draft123')
    
    @patch.object(SleeperAPI, '_make_request')
    def test_get_draft_picks(self, mock_request):
        """Test getting draft picks."""
        mock_request.return_value = [
            {'pick_no': 1, 'player_id': 'player1', 'picked_by': 'user1'},
            {'pick_no': 2, 'player_id': 'player2', 'picked_by': 'user2'}
        ]
        
        result = self.api.get_draft_picks('draft123')
        
        assert len(result) == 2
        assert result[0]['pick_no'] == 1
        mock_request.assert_called_once_with('/draft/draft123/picks')


class TestSleeperAPIPlayerMethods:
    """Test player-related API methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    @patch.object(SleeperAPI, '_make_request')
    def test_get_all_players(self, mock_request):
        """Test getting all players."""
        mock_request.return_value = {
            'player1': {'full_name': 'Patrick Mahomes', 'position': 'QB'},
            'player2': {'full_name': 'Christian McCaffrey', 'position': 'RB'}
        }
        
        result = self.api.get_all_players()
        
        assert 'player1' in result
        assert result['player1']['full_name'] == 'Patrick Mahomes'
        mock_request.assert_called_once_with('/players/nfl')
    
    @patch.object(SleeperAPI, '_make_request')
    def test_get_all_players_custom_sport(self, mock_request):
        """Test getting all players for custom sport."""
        mock_request.return_value = {}
        
        self.api.get_all_players(sport='mlb')
        
        mock_request.assert_called_once_with('/players/mlb')
    
    @patch.object(SleeperAPI, '_make_request')
    def test_get_player_projections_default(self, mock_request):
        """Test getting player projections with default parameters."""
        mock_request.return_value = {
            'player1': {'pts': 300.5, 'pass_yds': 4000},
            'player2': {'pts': 250.8, 'rush_yds': 1200}
        }
        
        result = self.api.get_player_projections()
        
        assert 'player1' in result
        assert result['player1']['pts'] == 300.5
        mock_request.assert_called_once_with('/projections/nfl/regular/2024')
    
    @patch.object(SleeperAPI, '_make_request')  
    def test_get_player_projections_with_week(self, mock_request):
        """Test getting player projections for specific week."""
        mock_request.return_value = {}
        
        self.api.get_player_projections(season='2023', week=5)
        
        mock_request.assert_called_once_with('/projections/nfl/regular/2023/5')


class TestSleeperAPIPlayerConversion:
    """Test player data conversion methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
        
        # Sample Sleeper player data
        self.sleeper_player = {
            'player_id': 'sleeper123',
            'full_name': 'Patrick Mahomes',
            'first_name': 'Patrick',
            'last_name': 'Mahomes',
            'position': 'QB',
            'team': 'KC',
            'age': 28
        }
        
        self.projections = {
            'sleeper123': {'pts_ppr': 320.5, 'pass_yds': 4200}
        }
    
    def test_convert_to_auction_player_with_projections(self):
        """Test converting Sleeper player to auction format with projections."""
        result = self.api.convert_to_auction_player(self.sleeper_player, self.projections)
        
        assert result['player_id'] == 'sleeper123'
        assert result['name'] == 'Patrick Mahomes'
        assert result['position'] == 'QB'
        assert result['team'] == 'KC'
        assert result['age'] == 28
        assert result['projected_points'] == 320.5
    
    def test_convert_to_auction_player_without_projections(self):
        """Test converting Sleeper player without projections."""
        result = self.api.convert_to_auction_player(self.sleeper_player)
        
        assert result['player_id'] == 'sleeper123'
        assert result['name'] == 'Patrick Mahomes'
        assert result['position'] == 'QB'
        assert result['projected_points'] == 0.0  # Default when no projections
    
    def test_convert_to_auction_player_missing_fields(self):
        """Test converting player with missing fields."""
        incomplete_player = {
            'player_id': 'test123',
            'full_name': 'Test Player'
        }
        
        result = self.api.convert_to_auction_player(incomplete_player)
        
        assert result['player_id'] == 'test123'
        assert result['name'] == 'Test Player'
        assert result['position'] == ''  # Empty string when missing
        assert result['team'] == ''  # Empty string when missing
        assert result['age'] is None  # None when missing


class TestSleeperAPIBulkOperations:
    """Test bulk data operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    @patch.object(SleeperAPI, 'get_fantasy_relevant_players')
    @patch.object(SleeperAPI, 'convert_to_auction_player')
    def test_bulk_convert_players(self, mock_convert, mock_get_players):
        """Test bulk player conversion."""
        mock_players = {
            'player1': {'player_id': 'player1', 'full_name': 'Player One', 'position': 'QB'},
            'player2': {'player_id': 'player2', 'full_name': 'Player Two', 'position': 'RB'}
        }
        mock_get_players.return_value = mock_players
        mock_convert.side_effect = [
            {'player_id': 'player1', 'name': 'Player One', 'position': 'QB'},
            {'player_id': 'player2', 'name': 'Player Two', 'position': 'RB'}
        ]
        
        result = self.api.bulk_convert_players()
        
        assert len(result) == 2
        assert mock_convert.call_count == 2
        mock_get_players.assert_called_once_with(None)
    
    @patch.object(SleeperAPI, 'get_fantasy_relevant_players')
    def test_bulk_convert_players_with_filter(self, mock_get_players):
        """Test bulk player conversion with position filter."""
        mock_get_players.return_value = {}
        
        self.api.bulk_convert_players(['QB', 'RB'])
        
        mock_get_players.assert_called_once_with(['QB', 'RB'])


class TestSleeperAPIErrorHandling:
    """Test error handling across all API methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    @patch.object(SleeperAPI, '_make_request')
    def test_api_methods_handle_errors_gracefully(self, mock_request):
        """Test that API methods handle errors gracefully."""
        mock_request.side_effect = SleeperAPIError("API Error")
        
        # Test methods that should return None on error
        assert self.api.get_user('test') is None
        assert self.api.get_league('test') is None
        assert self.api.get_draft('test') is None
        
        # Test methods that should return empty list on error
        assert self.api.get_user_leagues('test') == []
        assert self.api.get_league_rosters('test') == []
        assert self.api.get_league_users('test') == []
        assert self.api.get_league_drafts('test') == []
        assert self.api.get_draft_picks('test') == []
        
        # Test methods that should return empty dict on error
        assert self.api.get_all_players() == {}
        assert self.api.get_player_projections() == {}


class TestSleeperAPIIntegration:
    """Test integration scenarios and realistic workflows."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    @patch.object(SleeperAPI, '_make_request')
    def test_typical_league_data_workflow(self, mock_request):
        """Test typical workflow of getting league data."""
        # Mock responses in sequence
        mock_request.side_effect = [
            # get_league
            {'league_id': 'league1', 'name': 'Test League', 'total_rosters': 12},
            # get_league_users  
            [{'user_id': 'user1', 'display_name': 'User One'}],
            # get_league_rosters
            [{'roster_id': 1, 'owner_id': 'user1', 'players': ['player1']}],
            # get_league_drafts
            [{'draft_id': 'draft1', 'type': 'auction', 'status': 'complete'}]
        ]
        
        # Execute workflow
        league = self.api.get_league('league1')
        users = self.api.get_league_users('league1') 
        rosters = self.api.get_league_rosters('league1')
        drafts = self.api.get_league_drafts('league1')
        
        # Verify results
        assert league['name'] == 'Test League'
        assert len(users) == 1
        assert len(rosters) == 1
        assert drafts[0]['type'] == 'auction'
        assert mock_request.call_count == 4