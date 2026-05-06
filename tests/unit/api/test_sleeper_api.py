"""
Unit tests for Sleeper API wrapper.

This module tests the SleeperAPI class that wraps the Sleeper Fantasy Football API.
Tests validate actual implementation functionality including rate limiting, error handling,
and data conversion methods.

Updated for httpx async migration (#14).
"""

import pytest
from unittest.mock import AsyncMock, patch
import httpx

from api.sleeper_api import SleeperAPI, SleeperAPIError

pytestmark = pytest.mark.asyncio


class TestSleeperAPIInitialization:
    """Test SleeperAPI initialization and configuration."""
    
    def test_sleeper_api_init_default_values(self):
        """Test SleeperAPI initialization with default values."""
        api = SleeperAPI()
        
        assert api.rate_limit_delay == 0.1
        assert api.BASE_URL == "https://api.sleeper.app/v1"
        assert api._headers['User-Agent'] == 'PigskinAuctionDraft/1.0'
        assert api.last_request_time == 0
    
    def test_sleeper_api_init_custom_rate_limit(self):
        """Test SleeperAPI initialization with custom rate limit."""
        custom_delay = 0.5
        api = SleeperAPI(rate_limit_delay=custom_delay)
        
        assert api.rate_limit_delay == custom_delay
        assert api.min_request_interval == custom_delay
    
    def test_sleeper_api_user_agent_header(self):
        """Test that User-Agent header is configured correctly."""
        api = SleeperAPI()
        
        assert api._headers.get('User-Agent') == 'PigskinAuctionDraft/1.0'



class TestSleeperAPIRequestHandling:
    """Test HTTP request handling and rate limiting."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI(rate_limit_delay=0.0)  # No delay for testing
    
    async def test_make_request_success(self, httpx_mock):
        """Test successful API request."""
        httpx_mock.add_response(
            url="https://api.sleeper.app/v1/test",
            json={'test': 'data'},
            status_code=200,
        )
        
        result = await self.api._make_request('/test')
        
        assert result == {'test': 'data'}
    
    async def test_make_request_with_params(self, httpx_mock):
        """Test API request with parameters."""
        httpx_mock.add_response(
            json={'result': 'success'},
            status_code=200,
        )
        
        result = await self.api._make_request('/endpoint', {'season': '2024'})
        
        assert result == {'result': 'success'}
    
    async def test_make_request_rate_limiting_uses_asyncio_sleep(self, httpx_mock):
        """Test that rate limiting uses asyncio.sleep, not time.sleep."""
        httpx_mock.add_response(json={'data': 'test'}, status_code=200)
        
        # Verify that time.sleep is never called (rate limiting must use asyncio.sleep)
        import time as _time
        original = _time.sleep
        called = []
        _time.sleep = lambda *a: called.append(a)
        try:
            await self.api._make_request('/test')
        finally:
            _time.sleep = original
        
        assert called == [], "time.sleep must not be called in async code — use asyncio.sleep"

    async def test_make_request_triggers_rate_limit_sleep(self, httpx_mock):
        """Cover line 54 — asyncio.sleep called when request is too soon."""
        httpx_mock.add_response(json={'ok': True}, status_code=200)
        api = SleeperAPI(rate_limit_delay=10.0)  # Large delay
        import time
        api.last_request_time = time.time()  # Just made a request
        with patch('api.sleeper_api.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await api._make_request('/test')
        mock_sleep.assert_called_once()
    
    async def test_make_request_429_retry(self, httpx_mock):
        """Test handling of 429 rate limit response with retry."""
        httpx_mock.add_response(status_code=429)
        httpx_mock.add_response(json={'retried': 'success'}, status_code=200)
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await self.api._make_request('/test')
        
        assert result == {'retried': 'success'}
    
    async def test_make_request_404_error(self, httpx_mock):
        """Test handling of 404 not found response."""
        httpx_mock.add_response(
            url="https://api.sleeper.app/v1/nonexistent",
            status_code=404,
        )
        
        with pytest.raises(SleeperAPIError, match="API request failed"):
            await self.api._make_request('/nonexistent')
    
    async def test_make_request_network_error(self, httpx_mock):
        """Test handling of network errors."""
        httpx_mock.add_exception(httpx.ConnectError("Connection failed"))
        
        with pytest.raises(SleeperAPIError, match="API request failed"):
            await self.api._make_request('/test')
    
    async def test_make_request_timeout_error(self, httpx_mock):
        """Test handling of timeout errors."""
        httpx_mock.add_exception(httpx.ReadTimeout("Request timed out"))
        
        with pytest.raises(SleeperAPIError, match="API request failed"):
            await self.api._make_request('/test')

    async def test_make_request_429_exhausted(self, httpx_mock):
        """Test 429 retries exhausted raises SleeperAPIError."""
        api = SleeperAPI(rate_limit_delay=0.0, max_retries=2)
        for _ in range(3):  # initial + 2 retries = 3 total 429 responses
            httpx_mock.add_response(status_code=429)
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(SleeperAPIError, match="Rate limited"):
                await api._make_request('/test')



class TestSleeperAPIUserMethods:
    """Test user-related API methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    async def test_get_user_success(self):
        """Test successful user lookup."""
        self.api._make_request = AsyncMock(return_value={
            'user_id': '12345',
            'username': 'testuser',
            'display_name': 'Test User'
        })
        
        result = await self.api.get_user('testuser')
        
        assert result['username'] == 'testuser'
        assert result['user_id'] == '12345'
        self.api._make_request.assert_called_once_with('/user/testuser')
    
    async def test_get_user_not_found(self):
        """Test user lookup when user doesn't exist."""
        self.api._make_request = AsyncMock(side_effect=SleeperAPIError("HTTP 404"))
        
        result = await self.api.get_user('nonexistentuser')
        
        assert result is None
    
    async def test_get_user_leagues_success(self):
        """Test getting user leagues."""
        self.api._make_request = AsyncMock(return_value=[
            {'league_id': 'league1', 'name': 'Test League 1'},
            {'league_id': 'league2', 'name': 'Test League 2'}
        ])
        
        result = await self.api.get_user_leagues('user123')
        
        assert len(result) == 2
        assert result[0]['league_id'] == 'league1'
        self.api._make_request.assert_called_once_with('/user/user123/leagues/nfl/2024')
    
    async def test_get_user_leagues_custom_season(self):
        """Test getting user leagues for custom season."""
        self.api._make_request = AsyncMock(return_value=[])
        
        await self.api.get_user_leagues('user123', season='2023')
        
        self.api._make_request.assert_called_once_with('/user/user123/leagues/nfl/2023')


class TestSleeperAPILeagueMethods:
    """Test league-related API methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    async def test_get_league_success(self):
        """Test successful league lookup."""
        self.api._make_request = AsyncMock(return_value={
            'league_id': 'league123',
            'name': 'Test League',
            'total_rosters': 12,
            'scoring_settings': {'pass_td': 4}
        })
        
        result = await self.api.get_league('league123')
        
        assert result['league_id'] == 'league123'
        assert result['total_rosters'] == 12
        self.api._make_request.assert_called_once_with('/league/league123')
    
    async def test_get_league_rosters(self):
        """Test getting league rosters."""
        self.api._make_request = AsyncMock(return_value=[
            {'roster_id': 1, 'owner_id': 'user1', 'players': ['player1', 'player2']},
            {'roster_id': 2, 'owner_id': 'user2', 'players': ['player3', 'player4']}
        ])
        
        result = await self.api.get_league_rosters('league123')
        
        assert len(result) == 2
        assert result[0]['roster_id'] == 1
        self.api._make_request.assert_called_once_with('/league/league123/rosters')
    
    async def test_get_league_users(self):
        """Test getting league users."""
        self.api._make_request = AsyncMock(return_value=[
            {'user_id': 'user1', 'display_name': 'User One'},
            {'user_id': 'user2', 'display_name': 'User Two'}
        ])
        
        result = await self.api.get_league_users('league123')
        
        assert len(result) == 2
        assert result[0]['display_name'] == 'User One'
        self.api._make_request.assert_called_once_with('/league/league123/users')


class TestSleeperAPIDraftMethods:
    """Test draft-related API methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    async def test_get_league_drafts(self):
        """Test getting league drafts."""
        self.api._make_request = AsyncMock(return_value=[
            {'draft_id': 'draft1', 'type': 'auction', 'status': 'complete'},
            {'draft_id': 'draft2', 'type': 'snake', 'status': 'in_progress'}
        ])
        
        result = await self.api.get_league_drafts('league123')
        
        assert len(result) == 2
        assert result[0]['type'] == 'auction'
        self.api._make_request.assert_called_once_with('/league/league123/drafts')
    
    async def test_get_draft(self):
        """Test getting specific draft details."""
        self.api._make_request = AsyncMock(return_value={
            'draft_id': 'draft123',
            'type': 'auction',
            'status': 'complete',
            'settings': {'budget': 200}
        })
        
        result = await self.api.get_draft('draft123')
        
        assert result['draft_id'] == 'draft123'
        assert result['settings']['budget'] == 200
        self.api._make_request.assert_called_once_with('/draft/draft123')
    
    async def test_get_draft_picks(self):
        """Test getting draft picks."""
        self.api._make_request = AsyncMock(return_value=[
            {'pick_no': 1, 'player_id': 'player1', 'picked_by': 'user1'},
            {'pick_no': 2, 'player_id': 'player2', 'picked_by': 'user2'}
        ])
        
        result = await self.api.get_draft_picks('draft123')
        
        assert len(result) == 2
        assert result[0]['pick_no'] == 1
        self.api._make_request.assert_called_once_with('/draft/draft123/picks')


class TestSleeperAPIPlayerMethods:
    """Test player-related API methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    async def test_get_all_players(self):
        """Test getting all players."""
        self.api._make_request = AsyncMock(return_value={
            'player1': {'full_name': 'Patrick Mahomes', 'position': 'QB'},
            'player2': {'full_name': 'Christian McCaffrey', 'position': 'RB'}
        })
        
        result = await self.api.get_all_players()
        
        assert 'player1' in result
        assert result['player1']['full_name'] == 'Patrick Mahomes'
        self.api._make_request.assert_called_once_with('/players/nfl')
    
    async def test_get_all_players_custom_sport(self):
        """Test getting all players for custom sport."""
        self.api._make_request = AsyncMock(return_value={})
        
        await self.api.get_all_players(sport='mlb')
        
        self.api._make_request.assert_called_once_with('/players/mlb')
    
    async def test_get_player_projections_default(self):
        """Test getting player projections with default parameters."""
        self.api._make_request = AsyncMock(return_value={
            'player1': {'pts': 300.5, 'pass_yds': 4000},
            'player2': {'pts': 250.8, 'rush_yds': 1200}
        })
        
        result = await self.api.get_player_projections()
        
        assert 'player1' in result
        assert result['player1']['pts'] == 300.5
        self.api._make_request.assert_called_once_with('/projections/nfl/regular/2024')
    
    async def test_get_player_projections_with_week(self):
        """Test getting player projections for specific week."""
        self.api._make_request = AsyncMock(return_value={})
        
        await self.api.get_player_projections(season='2023', week=5)
        
        self.api._make_request.assert_called_once_with('/projections/nfl/regular/2023/5')


class TestSleeperAPIPlayerConversion:
    """Test player data conversion methods (synchronous — no HTTP calls)."""
    
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
    """Test bulk data operations (async)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    async def test_bulk_convert_players(self):
        """Test bulk player conversion."""
        mock_players = {
            'player1': {'player_id': 'player1', 'full_name': 'Player One', 'position': 'QB'},
            'player2': {'player_id': 'player2', 'full_name': 'Player Two', 'position': 'RB'}
        }
        self.api.get_fantasy_relevant_players = AsyncMock(return_value=mock_players)
        self.api.get_player_projections = AsyncMock(return_value={})
        
        result = await self.api.bulk_convert_players()
        
        assert len(result) == 2
        self.api.get_fantasy_relevant_players.assert_called_once_with(None)
    
    async def test_bulk_convert_players_with_filter(self):
        """Test bulk player conversion with position filter."""
        self.api.get_fantasy_relevant_players = AsyncMock(return_value={})
        self.api.get_player_projections = AsyncMock(return_value={})
        
        await self.api.bulk_convert_players(['QB', 'RB'])
        
        self.api.get_fantasy_relevant_players.assert_called_once_with(['QB', 'RB'])


class TestSleeperAPIErrorHandling:
    """Test error handling across all API methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    async def test_api_methods_handle_errors_gracefully(self):
        """Test that API methods handle errors gracefully."""
        self.api._make_request = AsyncMock(side_effect=SleeperAPIError("API Error"))
        
        # Test methods that should return None on error
        assert await self.api.get_user('test') is None
        assert await self.api.get_league('test') is None
        assert await self.api.get_draft('test') is None
        
        # Test methods that should return empty list on error
        assert await self.api.get_user_leagues('test') == []
        assert await self.api.get_league_rosters('test') == []
        assert await self.api.get_league_users('test') == []
        assert await self.api.get_league_drafts('test') == []
        assert await self.api.get_draft_picks('test') == []
        
        # Test methods that should return empty dict on error
        assert await self.api.get_all_players() == {}
        assert await self.api.get_player_projections() == {}


class TestSleeperAPIIntegration:
    """Test integration scenarios and realistic workflows."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SleeperAPI()
    
    async def test_typical_league_data_workflow(self):
        """Test typical workflow of getting league data."""
        self.api._make_request = AsyncMock(side_effect=[
            # get_league
            {'league_id': 'league1', 'name': 'Test League', 'total_rosters': 12},
            # get_league_users
            [{'user_id': 'user1', 'display_name': 'User One'}],
            # get_league_rosters
            [{'roster_id': 1, 'owner_id': 'user1', 'players': ['player1']}],
            # get_league_drafts
            [{'draft_id': 'draft1', 'type': 'auction', 'status': 'complete'}]
        ])
        
        # Execute workflow
        league = await self.api.get_league('league1')
        users = await self.api.get_league_users('league1')
        rosters = await self.api.get_league_rosters('league1')
        drafts = await self.api.get_league_drafts('league1')
        
        # Verify results
        assert league['name'] == 'Test League'
        assert len(users) == 1
        assert len(rosters) == 1
        assert drafts[0]['type'] == 'auction'


# ---------------------------------------------------------------------------
# Additional coverage tests for uncovered methods
# ---------------------------------------------------------------------------

class TestSleeperAPIUncoveredMethods:
    """Cover lines 97-100, 139-162, 200, 210-233, 254-257, 264-326, 378-383."""

    def setup_method(self):
        self.api = SleeperAPI()

    # Lines 97-100: get_user_by_id
    async def test_get_user_by_id_success(self):
        self.api._make_request = AsyncMock(return_value={'user_id': 'u1'})
        result = await self.api.get_user_by_id('u1')
        assert result == {'user_id': 'u1'}
        self.api._make_request.assert_called_once_with('/user/u1')

    async def test_get_user_by_id_error_returns_none(self):
        self.api._make_request = AsyncMock(side_effect=SleeperAPIError("err"))
        result = await self.api.get_user_by_id('u1')
        assert result is None

    # Lines 139-144: get_league_matchups
    async def test_get_league_matchups_success(self):
        self.api._make_request = AsyncMock(return_value=[{'matchup_id': 1}])
        result = await self.api.get_league_matchups('league1', 5)
        assert result == [{'matchup_id': 1}]
        self.api._make_request.assert_called_once_with('/league/league1/matchups/5')

    async def test_get_league_matchups_error_returns_empty(self):
        self.api._make_request = AsyncMock(side_effect=SleeperAPIError("err"))
        result = await self.api.get_league_matchups('league1', 5)
        assert result == []

    # Lines 148-153: get_league_transactions
    async def test_get_league_transactions_success(self):
        self.api._make_request = AsyncMock(return_value=[{'transaction_id': 'tx1'}])
        result = await self.api.get_league_transactions('league1', 3)
        assert result == [{'transaction_id': 'tx1'}]
        self.api._make_request.assert_called_once_with('/league/league1/transactions/3')

    async def test_get_league_transactions_error_returns_empty(self):
        self.api._make_request = AsyncMock(side_effect=SleeperAPIError("err"))
        result = await self.api.get_league_transactions('league1', 3)
        assert result == []

    # Lines 157-162: get_traded_picks
    async def test_get_traded_picks_success(self):
        self.api._make_request = AsyncMock(return_value=[{'pick_id': 'p1'}])
        result = await self.api.get_traded_picks('league1')
        assert result == [{'pick_id': 'p1'}]
        self.api._make_request.assert_called_once_with('/league/league1/traded_picks')

    async def test_get_traded_picks_error_returns_empty(self):
        self.api._make_request = AsyncMock(side_effect=SleeperAPIError("err"))
        result = await self.api.get_traded_picks('league1')
        assert result == []

    # Line 200: get_nfl_players (alias)
    async def test_get_nfl_players_calls_get_all_players(self):
        self.api.get_all_players = AsyncMock(return_value={'player1': {'name': 'Josh'}})
        result = await self.api.get_nfl_players()
        self.api.get_all_players.assert_called_once_with('nfl')
        assert 'player1' in result

    # Lines 210-216: get_trending_players
    async def test_get_trending_players_success(self):
        self.api._make_request = AsyncMock(return_value=[{'player_id': 'p1'}])
        result = await self.api.get_trending_players()
        assert result == [{'player_id': 'p1'}]

    async def test_get_trending_players_custom_params(self):
        self.api._make_request = AsyncMock(return_value=[])
        await self.api.get_trending_players(sport='nfl', type_='drop', hours=12, limit=10)
        self.api._make_request.assert_called_once_with(
            '/players/nfl/trending/drop', {'type': 'drop', 'hours': 12, 'limit': 10}
        )

    async def test_get_trending_players_error_returns_empty(self):
        self.api._make_request = AsyncMock(side_effect=SleeperAPIError("err"))
        result = await self.api.get_trending_players()
        assert result == []

    # Lines 223-233: get_player_stats
    async def test_get_player_stats_season(self):
        self.api._make_request = AsyncMock(return_value={'p1': {'pts': 20}})
        result = await self.api.get_player_stats(season='2024')
        assert result == {'p1': {'pts': 20}}
        self.api._make_request.assert_called_once_with('/stats/nfl/regular/2024')

    async def test_get_player_stats_with_week(self):
        self.api._make_request = AsyncMock(return_value={'p1': {'pts': 15}})
        await self.api.get_player_stats(season='2024', week=5)
        self.api._make_request.assert_called_once_with('/stats/nfl/regular/2024/5')

    async def test_get_player_stats_error_returns_empty(self):
        self.api._make_request = AsyncMock(side_effect=SleeperAPIError("err"))
        result = await self.api.get_player_stats()
        assert result == {}

    # Lines 254-257: get_nfl_state
    async def test_get_nfl_state_success(self):
        self.api._make_request = AsyncMock(return_value={'season': '2024', 'week': 5})
        result = await self.api.get_nfl_state()
        assert result == {'season': '2024', 'week': 5}
        self.api._make_request.assert_called_once_with('/state/nfl')

    async def test_get_nfl_state_error_returns_none(self):
        self.api._make_request = AsyncMock(side_effect=SleeperAPIError("err"))
        result = await self.api.get_nfl_state()
        assert result is None

    # Lines 264-285: search_players (sync)
    def test_search_players_no_data_returns_empty(self):
        result = self.api.search_players('josh')
        assert result == []

    def test_search_players_finds_by_name(self):
        players_data = {
            'p1': {'first_name': 'Josh', 'last_name': 'Allen', 'full_name': 'Josh Allen'},
            'p2': {'first_name': 'Patrick', 'last_name': 'Mahomes', 'full_name': 'Patrick Mahomes'},
        }
        result = self.api.search_players('josh', players_data)
        assert len(result) == 1
        assert result[0]['first_name'] == 'Josh'
        assert result[0]['player_id'] == 'p1'

    def test_search_players_no_match(self):
        players_data = {'p1': {'first_name': 'Josh', 'last_name': 'Allen', 'full_name': 'Josh Allen'}}
        result = self.api.search_players('zzzz', players_data)
        assert result == []

    def test_search_players_skips_null_entries(self):
        players_data = {'p1': None, 'p2': {'first_name': 'Josh', 'last_name': 'Allen', 'full_name': 'Josh Allen'}}
        result = self.api.search_players('josh', players_data)
        assert len(result) == 1
        assert result[0]['first_name'] == 'Josh'

    # Lines 291-305: get_player_by_name (sync)
    def test_get_player_by_name_no_data_returns_none(self):
        result = self.api.get_player_by_name('Josh Allen')
        assert result is None

    def test_get_player_by_name_found(self):
        players_data = {'p1': {'full_name': 'Josh Allen'}}
        result = self.api.get_player_by_name('Josh Allen', players_data)
        assert result is not None
        assert result['player_id'] == 'p1'

    def test_get_player_by_name_case_insensitive(self):
        players_data = {'p1': {'full_name': 'Josh Allen'}}
        result = self.api.get_player_by_name('josh allen', players_data)
        assert result is not None

    def test_get_player_by_name_not_found(self):
        players_data = {'p1': {'full_name': 'Josh Allen'}}
        result = self.api.get_player_by_name('Tom Brady', players_data)
        assert result is None

    def test_get_player_by_name_skips_null_entries(self):
        players_data = {'p1': None, 'p2': {'full_name': 'Josh Allen'}}
        result = self.api.get_player_by_name('Josh Allen', players_data)
        assert result is not None

    # Lines 311-326: get_fantasy_relevant_players
    async def test_get_fantasy_relevant_players_default_positions(self):
        self.api.get_all_players = AsyncMock(return_value={
            'p1': {'position': 'QB', 'active': True},
            'p2': {'position': 'K', 'active': True},
            'p3': {'position': 'P', 'active': True},  # punter — not fantasy relevant
        })
        result = await self.api.get_fantasy_relevant_players()
        assert 'p1' in result
        assert 'p2' in result
        assert 'p3' not in result

    async def test_get_fantasy_relevant_players_custom_filter(self):
        self.api.get_all_players = AsyncMock(return_value={
            'p1': {'position': 'QB', 'active': True},
            'p2': {'position': 'RB', 'active': True},
        })
        result = await self.api.get_fantasy_relevant_players(position_filter=['QB'])
        assert 'p1' in result
        assert 'p2' not in result

    async def test_get_fantasy_relevant_players_skips_null(self):
        self.api.get_all_players = AsyncMock(return_value={'p1': None, 'p2': {'position': 'QB', 'active': True}})
        result = await self.api.get_fantasy_relevant_players()
        assert 'p1' not in result
        assert 'p2' in result

    # Lines 378-383: get_league_auction_data
    async def test_get_league_auction_data(self):
        self.api.get_league = AsyncMock(return_value={'league_id': 'l1'})
        self.api.get_league_rosters = AsyncMock(return_value=[{'roster_id': 1}])
        self.api.get_league_users = AsyncMock(return_value=[{'user_id': 'u1'}])
        self.api.get_league_drafts = AsyncMock(return_value=[{'draft_id': 'd1'}])

        result = await self.api.get_league_auction_data('l1')
        assert result['league'] == {'league_id': 'l1'}
        assert result['rosters'] == [{'roster_id': 1}]
        assert result['users'] == [{'user_id': 'u1'}]
        assert result['drafts'] == [{'draft_id': 'd1'}]