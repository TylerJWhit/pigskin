"""Sleeper API wrapper for fantasy football data."""

import requests
from typing import Dict, List, Optional, Any
import time
from datetime import datetime, timedelta


class SleeperAPIError(Exception):
    """Custom exception for Sleeper API errors."""
    pass


class SleeperAPI:
    """Wrapper for the Sleeper Fantasy Football API."""
    
    BASE_URL = "https://api.sleeper.app/v1"
    
    def __init__(self, rate_limit_delay: float = 0.1):
        """
        Initialize Sleeper API wrapper.
        
        Args:
            rate_limit_delay: Delay between API calls to respect rate limits
        """
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PigskinAuctionDraft/1.0'
        })
        self.last_request_time = 0
        
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Make a request to the Sleeper API with rate limiting."""
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
            
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            response = self.session.get(url, params=params)
            self.last_request_time = time.time()
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # Rate limited, wait and retry once
                time.sleep(1)
                response = self.session.get(url, params=params)
                if response.status_code == 200:
                    return response.json()
                    
            response.raise_for_status()
            
        except requests.RequestException as e:
            raise SleeperAPIError(f"API request failed: {e}")
            
    # User methods
    def get_user(self, username: str) -> Optional[Dict]:
        """Get user information by username."""
        try:
            return self._make_request(f"/user/{username}")
        except SleeperAPIError:
            return None
            
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user information by user ID."""
        try:
            return self._make_request(f"/user/{user_id}")
        except SleeperAPIError:
            return None
            
    # League methods
    def get_user_leagues(self, user_id: str, season: str = "2024") -> List[Dict]:
        """Get leagues for a user in a specific season."""
        try:
            return self._make_request(f"/user/{user_id}/leagues/nfl/{season}") or []
        except SleeperAPIError:
            return []
            
    def get_league(self, league_id: str) -> Optional[Dict]:
        """Get league information."""
        try:
            return self._make_request(f"/league/{league_id}")
        except SleeperAPIError:
            return None
            
    def get_league_rosters(self, league_id: str) -> List[Dict]:
        """Get all rosters in a league."""
        try:
            return self._make_request(f"/league/{league_id}/rosters") or []
        except SleeperAPIError:
            return []
            
    def get_league_users(self, league_id: str) -> List[Dict]:
        """Get all users in a league."""
        try:
            return self._make_request(f"/league/{league_id}/users") or []
        except SleeperAPIError:
            return []
            
    def get_league_matchups(self, league_id: str, week: int) -> List[Dict]:
        """Get matchups for a specific week."""
        try:
            return self._make_request(f"/league/{league_id}/matchups/{week}") or []
        except SleeperAPIError:
            return []
            
    def get_league_transactions(self, league_id: str, week: int) -> List[Dict]:
        """Get transactions for a specific week."""
        try:
            return self._make_request(f"/league/{league_id}/transactions/{week}") or []
        except SleeperAPIError:
            return []
            
    def get_traded_picks(self, league_id: str) -> List[Dict]:
        """Get traded draft picks for a league."""
        try:
            return self._make_request(f"/league/{league_id}/traded_picks") or []
        except SleeperAPIError:
            return []
            
    # Draft methods
    def get_league_drafts(self, league_id: str) -> List[Dict]:
        """Get all drafts for a league."""
        try:
            return self._make_request(f"/league/{league_id}/drafts") or []
        except SleeperAPIError:
            return []
            
    def get_draft(self, draft_id: str) -> Optional[Dict]:
        """Get draft information."""
        try:
            return self._make_request(f"/draft/{draft_id}")
        except SleeperAPIError:
            return None
            
    def get_draft_picks(self, draft_id: str) -> List[Dict]:
        """Get all picks for a draft."""
        try:
            return self._make_request(f"/draft/{draft_id}/picks") or []
        except SleeperAPIError:
            return []
            
    # Player methods
    def get_all_players(self, sport: str = "nfl") -> Dict[str, Dict]:
        """Get all players. Warning: This is a large response."""
        try:
            return self._make_request(f"/players/{sport}") or {}
        except SleeperAPIError:
            return {}
            
    def get_trending_players(self, sport: str = "nfl", type_: str = "add", 
                           hours: int = 24, limit: int = 25) -> List[Dict]:
        """Get trending players (adds/drops)."""
        try:
            params = {
                'type': type_,
                'hours': hours,
                'limit': limit
            }
            return self._make_request(f"/players/{sport}/trending/{type_}", params) or []
        except SleeperAPIError:
            return []
            
    # Stats methods
    def get_player_stats(self, season: str = "2024", week: Optional[int] = None) -> Dict[str, Dict]:
        """Get player stats for season or specific week."""
        try:
            if week:
                return self._make_request(f"/stats/nfl/regular/{season}/{week}") or {}
            else:
                return self._make_request(f"/stats/nfl/regular/{season}") or {}
        except SleeperAPIError:
            return {}
            
    def get_player_projections(self, season: str = "2024", week: Optional[int] = None) -> Dict[str, Dict]:
        """Get player projections for season or specific week."""
        try:
            if week:
                return self._make_request(f"/projections/nfl/regular/{season}/{week}") or {}
            else:
                return self._make_request(f"/projections/nfl/regular/{season}") or {}
        except SleeperAPIError:
            return {}
            
    # State methods
    def get_nfl_state(self) -> Optional[Dict]:
        """Get current NFL state (week, season, etc.)."""
        try:
            return self._make_request("/state/nfl")
        except SleeperAPIError:
            return None
            
    # Utility methods
    def search_players(self, query: str, players_data: Optional[Dict] = None) -> List[Dict]:
        """Search for players by name."""
        if not players_data:
            players_data = self.get_all_players()
            
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
                
                player_data['player_id'] = player_id
                results.append(player_data)
                
        return results[:50]  # Limit results
        
    def get_player_by_name(self, name: str, players_data: Optional[Dict] = None) -> Optional[Dict]:
        """Get a specific player by exact name match."""
        if not players_data:
            players_data = self.get_all_players()
            
        name_lower = name.lower()
        
        for player_id, player_data in players_data.items():
            if not player_data:
                continue
                
            full_name = player_data.get('full_name', '').lower()
            if full_name == name_lower:
                player_data['player_id'] = player_id
                return player_data
                
        return None
        
    def get_fantasy_relevant_players(self, position_filter: Optional[List[str]] = None) -> Dict[str, Dict]:
        """Get fantasy football relevant players."""
        all_players = self.get_all_players()
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
        
    def convert_to_auction_player(self, sleeper_player: Dict, projections: Optional[Dict] = None) -> Dict:
        """Convert Sleeper player data to auction tool Player format."""
        player_id = sleeper_player.get('player_id', '')
        
        # Get projections if available
        projected_points = 0.0
        if projections and player_id in projections:
            proj_data = projections[player_id]
            # Sum up relevant scoring categories (customize based on your scoring)
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
            'auction_value': 0.0,  # Will need to be calculated separately
            'bye_week': sleeper_player.get('bye_week'),
            'age': sleeper_player.get('age'),
            'height': sleeper_player.get('height'),
            'weight': sleeper_player.get('weight'),
            'years_exp': sleeper_player.get('years_exp'),
            'college': sleeper_player.get('college'),
            'injury_status': sleeper_player.get('injury_status')
        }
        
    def bulk_convert_players(self, position_filter: Optional[List[str]] = None) -> List[Dict]:
        """Convert all relevant Sleeper players to auction tool format."""
        sleeper_players = self.get_fantasy_relevant_players(position_filter)
        projections = self.get_player_projections()
        
        converted_players = []
        for player_id, player_data in sleeper_players.items():
            player_data['player_id'] = player_id
            converted = self.convert_to_auction_player(player_data, projections)
            converted_players.append(converted)
            
        return converted_players
        
    def get_league_auction_data(self, league_id: str) -> Dict:
        """Get comprehensive auction-relevant data for a league."""
        league_info = self.get_league(league_id)
        rosters = self.get_league_rosters(league_id)
        users = self.get_league_users(league_id)
        drafts = self.get_league_drafts(league_id)
        
        return {
            'league': league_info,
            'rosters': rosters,
            'users': users,
            'drafts': drafts,
            'scoring_settings': league_info.get('scoring_settings', {}) if league_info else {},
            'roster_positions': league_info.get('roster_positions', []) if league_info else []
        }
