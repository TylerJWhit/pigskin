"""Sleeper API wrapper for fantasy football data."""

import asyncio
import random
import httpx
from typing import Dict, List, Optional, Any
import time
from urllib.parse import quote


def _safe_path(value: str) -> str:
    """URL-encode a path segment so user-supplied values cannot alter the URL structure."""
    return quote(str(value), safe="")


class SleeperAPIError(Exception):
    """Custom exception for Sleeper API errors."""


class SleeperAPI:
    """Async wrapper for the Sleeper Fantasy Football API."""
    
    BASE_URL = "https://api.sleeper.app/v1"
    
    def __init__(self, rate_limit_delay: float = 0.1, max_retries: int = 5,
                 backoff_base: float = 2.0, backoff_jitter: float = 0.5):
        """
        Initialize Sleeper API wrapper.

        Args:
            rate_limit_delay: Minimum delay between API calls (seconds).
            max_retries: Maximum number of retry attempts on 429 or transient errors.
            backoff_base: Exponential backoff base multiplier (seconds).
            backoff_jitter: Maximum random jitter added to each backoff delay (seconds).
        """
        self.rate_limit_delay = rate_limit_delay
        self.min_request_interval = rate_limit_delay  # alias for tests
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_jitter = backoff_jitter
        self._headers = {'User-Agent': 'PigskinAuctionDraft/1.0'}
        self.last_request_time = 0
        
    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Make an async request to the Sleeper API with rate limiting and exponential backoff.

        Only HTTP 429 (rate-limited) responses trigger retries with exponential backoff.
        All other non-200 responses raise SleeperAPIError immediately.
        """
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)

        url = f"{self.BASE_URL}{endpoint}"

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(headers=self._headers) as client:
                    response = await client.get(url, params=params)
                self.last_request_time = time.time()

                if response.status_code == 200:
                    try:
                        return response.json()
                    except Exception as e:
                        raise SleeperAPIError(
                            f"Failed to decode JSON response from {url}: {e}"
                        ) from e

                if response.status_code == 429:
                    if attempt < self.max_retries:
                        delay = (
                            self.backoff_base * (2 ** attempt)
                            + random.uniform(0, self.backoff_jitter)
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise SleeperAPIError(
                        f"Rate limited after {self.max_retries} retries: {url}"
                    )

                # Non-429 HTTP errors are not retried
                response.raise_for_status()

            except httpx.HTTPStatusError as e:
                raise SleeperAPIError(f"API request failed: {e}") from e
            except httpx.RequestError as e:
                raise SleeperAPIError(f"API request failed: {e}") from e
            
    # User methods
    async def get_user(self, username: str) -> Optional[Dict]:
        """Get user information by username."""
        try:
            return await self._make_request(f"/user/{_safe_path(username)}")
        except SleeperAPIError:
            return None

    async def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user information by user ID."""
        try:
            return await self._make_request(f"/user/{_safe_path(user_id)}")
        except SleeperAPIError:
            return None

    # League methods
    async def get_user_leagues(self, user_id: str, season: str = "2024") -> List[Dict]:
        """Get leagues for a user in a specific season."""
        try:
            return await self._make_request(
                f"/user/{_safe_path(user_id)}/leagues/nfl/{_safe_path(season)}"
            ) or []
        except SleeperAPIError:
            return []

    async def get_league(self, league_id: str) -> Optional[Dict]:
        """Get league information."""
        try:
            return await self._make_request(f"/league/{_safe_path(league_id)}")
        except SleeperAPIError:
            return None

    async def get_league_rosters(self, league_id: str) -> List[Dict]:
        """Get all rosters in a league."""
        try:
            return await self._make_request(
                f"/league/{_safe_path(league_id)}/rosters"
            ) or []
        except SleeperAPIError:
            return []

    async def get_league_users(self, league_id: str) -> List[Dict]:
        """Get all users in a league."""
        try:
            return await self._make_request(
                f"/league/{_safe_path(league_id)}/users"
            ) or []
        except SleeperAPIError:
            return []

    async def get_league_matchups(self, league_id: str, week: int) -> List[Dict]:
        """Get matchups for a specific week."""
        try:
            return await self._make_request(
                f"/league/{_safe_path(league_id)}/matchups/{_safe_path(week)}"
            ) or []
        except SleeperAPIError:
            return []

    async def get_league_transactions(self, league_id: str, week: int) -> List[Dict]:
        """Get transactions for a specific week."""
        try:
            return await self._make_request(
                f"/league/{_safe_path(league_id)}/transactions/{_safe_path(week)}"
            ) or []
        except SleeperAPIError:
            return []

    async def get_traded_picks(self, league_id: str) -> List[Dict]:
        """Get traded draft picks for a league."""
        try:
            return await self._make_request(
                f"/league/{_safe_path(league_id)}/traded_picks"
            ) or []
        except SleeperAPIError:
            return []

    # Draft methods
    async def get_league_drafts(self, league_id: str) -> List[Dict]:
        """Get all drafts for a league."""
        try:
            return await self._make_request(
                f"/league/{_safe_path(league_id)}/drafts"
            ) or []
        except SleeperAPIError:
            return []

    async def get_draft(self, draft_id: str) -> Optional[Dict]:
        """Get draft information."""
        try:
            return await self._make_request(f"/draft/{_safe_path(draft_id)}")
        except SleeperAPIError:
            return None

    async def get_draft_picks(self, draft_id: str) -> List[Dict]:
        """Get all picks for a draft."""
        try:
            return await self._make_request(
                f"/draft/{_safe_path(draft_id)}/picks"
            ) or []
        except SleeperAPIError:
            return []
            
    # Player methods
    async def get_all_players(self, sport: str = "nfl") -> Dict[str, Dict]:
        """Get all players. Warning: This is a large response."""
        try:
            return await self._make_request(f"/players/{sport}") or {}
        except SleeperAPIError:
            return {}

    async def get_nfl_players(self, sport: str = "nfl") -> Dict[str, Dict]:
        """Alias for get_all_players for backward-compatibility."""
        return await self.get_all_players(sport)
            
    async def get_trending_players(
        self,
        sport: str = "nfl",
        type_: str = "add",
        hours: int = 24,
        limit: int = 25,
    ) -> List[Dict]:
        """Get trending players (adds/drops)."""
        try:
            params = {'type': type_, 'hours': hours, 'limit': limit}
            return await self._make_request(
                f"/players/{sport}/trending/{type_}", params
            ) or []
        except SleeperAPIError:
            return []
            
    # Stats methods
    async def get_player_stats(
        self, season: str = "2024", week: Optional[int] = None
    ) -> Dict[str, Dict]:
        """Get player stats for season or specific week."""
        try:
            if week:
                return await self._make_request(
                    f"/stats/nfl/regular/{season}/{week}"
                ) or {}
            else:
                return await self._make_request(
                    f"/stats/nfl/regular/{season}"
                ) or {}
        except SleeperAPIError:
            return {}
            
    async def get_player_projections(
        self, season: str = "2024", week: Optional[int] = None
    ) -> Dict[str, Dict]:
        """Get player projections for season or specific week."""
        try:
            if week:
                return await self._make_request(
                    f"/projections/nfl/regular/{season}/{week}"
                ) or {}
            else:
                return await self._make_request(
                    f"/projections/nfl/regular/{season}"
                ) or {}
        except SleeperAPIError:
            return {}
            
    # State methods
    async def get_nfl_state(self) -> Optional[Dict]:
        """Get current NFL state (week, season, etc.)."""
        try:
            return await self._make_request("/state/nfl")
        except SleeperAPIError:
            return None
            
    # Utility methods (sync — no HTTP calls; operate on already-fetched data)
    def search_players(
        self, query: str, players_data: Optional[Dict] = None
    ) -> List[Dict]:
        """Search for players by name (synchronous — operates on provided data)."""
        if not players_data:
            return []  # callers must await get_all_players() first
            
        results = []
        query_lower = query.lower()
        
        for player_id, player_data in players_data.items():
            if not player_data:
                continue
                
            full_name = player_data.get('full_name', '').lower()
            first_name = player_data.get('first_name', '').lower()
            last_name = player_data.get('last_name', '').lower()
            
            if (query_lower in full_name or 
                query_lower in first_name or 
                query_lower in last_name):
                
                results.append({**player_data, 'player_id': player_id})
                
        return results[:50]  # Limit results
        
    def get_player_by_name(
        self, name: str, players_data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Get a specific player by exact name match (synchronous — operates on provided data)."""
        if not players_data:
            return None  # callers must await get_all_players() first
            
        name_lower = name.lower()
        
        for player_id, player_data in players_data.items():
            if not player_data:
                continue
                
            full_name = player_data.get('full_name', '').lower()
            if full_name == name_lower:
                return {**player_data, 'player_id': player_id}
                
        return None
        
    async def get_fantasy_relevant_players(
        self, position_filter: Optional[List[str]] = None
    ) -> Dict[str, Dict]:
        """Get fantasy football relevant players."""
        all_players = await self.get_all_players()
        relevant_players = {}
        
        fantasy_positions = position_filter or ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
        
        for player_id, player_data in all_players.items():
            if not player_data:
                continue
                
            position = player_data.get('position')
            if position in fantasy_positions:
                # Only include active players
                if player_data.get('active', True):
                    relevant_players[player_id] = player_data
                    
        return relevant_players
        
    def convert_to_auction_player(
        self, sleeper_player: Dict, projections: Optional[Dict] = None
    ) -> Dict:
        """Convert Sleeper player data to auction tool Player format (synchronous)."""
        player_id = sleeper_player.get('player_id', '')
        
        # Get projections if available
        projected_points = 0.0
        if projections and player_id in projections:
            proj_data = projections[player_id]
            projected_points = (
                proj_data.get('pts_ppr', 0) or
                proj_data.get('pts_std', 0) or
                proj_data.get('pts_half_ppr', 0) or
                0
            )
            
        return {
            'player_id': player_id,
            'name': sleeper_player.get('full_name', ''),
            'position': sleeper_player.get('position', ''),
            'team': sleeper_player.get('team', ''),
            'projected_points': float(projected_points),
            'auction_value': 0.0,
            'bye_week': sleeper_player.get('bye_week'),
            'age': sleeper_player.get('age'),
            'height': sleeper_player.get('height'),
            'weight': sleeper_player.get('weight'),
            'years_exp': sleeper_player.get('years_exp'),
            'college': sleeper_player.get('college'),
            'injury_status': sleeper_player.get('injury_status')
        }
        
    async def bulk_convert_players(
        self, position_filter: Optional[List[str]] = None
    ) -> List[Dict]:
        """Convert all relevant Sleeper players to auction tool format."""
        sleeper_players = await self.get_fantasy_relevant_players(position_filter)
        projections = await self.get_player_projections()
        
        converted_players = []
        for player_id, player_data in sleeper_players.items():
            player_data_copy = {**player_data, 'player_id': player_id}
            converted = self.convert_to_auction_player(player_data_copy, projections)
            converted_players.append(converted)
            
        return converted_players
        
    async def get_league_auction_data(self, league_id: str) -> Dict:
        """Get comprehensive auction-relevant data for a league."""
        league_info = await self.get_league(league_id)
        rosters = await self.get_league_rosters(league_id)
        users = await self.get_league_users(league_id)
        drafts = await self.get_league_drafts(league_id)
        
        return {
            'league': league_info,
            'rosters': rosters,
            'users': users,
            'drafts': drafts,
            'scoring_settings': league_info.get('scoring_settings', {}) if league_info else {},
            'roster_positions': league_info.get('roster_positions', []) if league_info else []
        }


