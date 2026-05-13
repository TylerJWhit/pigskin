"""
Sleeper Draft Service for displaying current draft information.

This service handles fetching and displaying current Sleeper draft data
including draft order, picks, and league information.
"""

import asyncio
import datetime
import logging
from typing import Dict, Any

from api.sleeper_api import SleeperAPI
from utils.print_module import print_sleeper_draft, print_sleeper_league
from utils.sleeper_cache import get_sleeper_players

logger = logging.getLogger(__name__)


class SleeperDraftService:
    """Service for fetching and displaying Sleeper draft information."""
    
    def __init__(self, sleeper_api: SleeperAPI = None):
        self.sleeper_api = sleeper_api if sleeper_api is not None else SleeperAPI()
        
    async def get_user_drafts(self, username: str, season: str = str(datetime.date.today().year)) -> Dict[str, Any]:
        """
        Get all drafts for a user.
        
        Args:
            username: Sleeper username
            season: NFL season year
            
        Returns:
            Dictionary with success status and draft information
        """
        # Get user info
        user = await self.sleeper_api.get_user(username)
        if not user:
            return {
                'success': False,
                'error': f"User '{username}' not found"
            }

        user_id = user['user_id']

        # Get user's leagues
        leagues = await self.sleeper_api.get_user_leagues(user_id, season)
        if not leagues:
            return {
                'success': False,
                'error': f"No leagues found for user '{username}' in {season}"
            }

        # Get drafts for each league
        drafts = []
        for league in leagues:
            draft_id = league.get('draft_id')

            if draft_id:
                draft_info = await self.sleeper_api.get_draft(draft_id)
                if draft_info:
                    draft_info['league_name'] = league.get('name', 'Unknown League')
                    drafts.append(draft_info)

        return {
            'success': True,
            'user': user,
            'leagues': leagues,
            'drafts': drafts
        }
    
    async def display_draft_info(self, draft_id: str) -> Dict[str, Any]:
        """
        Display detailed information about a specific draft.
        
        Args:
            draft_id: Sleeper draft ID
            
        Returns:
            Dictionary with success status and display result
        """
        try:
            # Get draft info
            draft_info = await self.sleeper_api.get_draft(draft_id)
            if not draft_info:
                return {
                    'success': False,
                    'error': f"Draft '{draft_id}' not found"
                }
            
            # Get draft picks
            picks = await self.sleeper_api.get_draft_picks(draft_id)
            
            # Get league info
            league_id = draft_info.get('league_id')
            users_info = {}
            
            if league_id:
                # Get league users
                users = await self.sleeper_api.get_league_users(league_id)
                users_info = {user['user_id']: user for user in (users or [])}
                
            # Always get players info from cache (needed for player names)
            players_info = get_sleeper_players()
            
            # Display the draft information using the print module
            print_sleeper_draft(draft_info, users_info, picks, players_info)
            
            return {
                'success': True,
                'draft_info': draft_info,
                'picks': picks,
                'users_info': users_info
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Error displaying draft info: {e}"
            }
    
    async def display_league_rosters(self, league_id: str) -> Dict[str, Any]:
        """
        Display current rosters for a league.
        
        Args:
            league_id: Sleeper league ID
            
        Returns:
            Dictionary with success status and display result
        """
        try:
            # Get league rosters
            rosters = await self.sleeper_api.get_league_rosters(league_id)
            if not rosters:
                return {
                    'success': False,
                    'error': f"No rosters found for league '{league_id}'"
                }
            
            # Get league users
            users = await self.sleeper_api.get_league_users(league_id)
            users_info = {user['user_id']: user for user in (users or [])}
            
            # Get players info from cache
            players_info = get_sleeper_players()
            
            # Display the roster information using the print module
            print_sleeper_league(rosters, users_info, players_info)
            
            return {
                'success': True,
                'rosters': rosters,
                'users_info': users_info
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Error displaying league rosters: {e}"
            }
    
    async def list_user_leagues(self, username: str, season: str = str(datetime.date.today().year)) -> Dict[str, Any]:
        """
        List all leagues for a user.
        
        Args:
            username: Sleeper username
            season: NFL season year
            
        Returns:
            Dictionary with success status and leagues list
        """
        try:
            # Get user info
            user = await self.sleeper_api.get_user(username)
            if not user:
                return {
                    'success': False,
                    'error': f"User '{username}' not found"
                }
            
            user_id = user['user_id']
            
            # Get user's leagues
            leagues = await self.sleeper_api.get_user_leagues(user_id, season)
            if not leagues:
                return {
                    'success': False,
                    'error': f"No leagues found for user '{username}' in {season}"
                }
            
            # Print leagues information
            logger.info("LEAGUES FOR %s (%s)", username.upper(), season)
            
            for i, league in enumerate(leagues, 1):
                league_id = league['league_id']
                league_name = league.get('name', 'Unknown League')
                total_rosters = league.get('total_rosters', 0)
                status = league.get('status', 'unknown')
                scoring_type = league.get('scoring_settings', {}).get('type', 'unknown')
                
                logger.info("%2d. %s", i, league_name)
                logger.info("    League ID: %s", league_id)
                logger.info("    Teams: %s", total_rosters)
                logger.info("    Status: %s", status.title())
                logger.info("    Scoring: %s", scoring_type.title())
                
                # Show draft info if available
                draft_id = league.get('draft_id')
                if draft_id:
                    logger.info("    Draft ID: %s", draft_id)
            
            return {
                'success': True,
                'user': user,
                'leagues': leagues
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Error listing leagues: {e}"
            }
    
    async def get_current_draft_status(self, username: str, season: str = str(datetime.date.today().year)) -> Dict[str, Any]:
        """
        Get current draft status for a user's leagues.
        
        Args:
            username: Sleeper username
            season: NFL season year
            
        Returns:
            Dictionary with current draft information
        """
        try:
            result = await self.get_user_drafts(username, season)
            if not result['success']:
                return result
            
            drafts = result['drafts']
            
            # Find active/upcoming drafts
            active_drafts = []
            completed_drafts = []
            
            for draft in drafts:
                status = draft.get('status', 'unknown')
                if status in ['pre_draft', 'drafting']:
                    active_drafts.append(draft)
                elif status == 'complete':
                    completed_drafts.append(draft)
            
            logger.info("DRAFT STATUS FOR %s (%s)", username.upper(), season)
            
            if active_drafts:
                logger.info("ACTIVE/UPCOMING DRAFTS (%d):", len(active_drafts))
                for draft in active_drafts:
                    draft_id = draft['draft_id']
                    league_name = draft.get('league_name', 'Unknown League')
                    status = draft.get('status', 'unknown')
                    draft_type = draft.get('type', 'unknown')
                    
                    logger.info("  * %s", league_name)
                    logger.info("    Draft ID: %s", draft_id)
                    logger.info("    Status: %s", status.title())
                    logger.info("    Type: %s", draft_type.title())
                    
                    settings = draft.get('settings', {})
                    if settings:
                        rounds = settings.get('rounds', 'Unknown')
                        pick_timer = settings.get('pick_timer', 'Unknown')
                        logger.info("    Rounds: %s", rounds)
                        logger.info("    Pick Timer: %ss", pick_timer)
            
            if completed_drafts:
                logger.info("COMPLETED DRAFTS (%d):", len(completed_drafts))
                for draft in completed_drafts:
                    draft_id = draft['draft_id']
                    league_name = draft.get('league_name', 'Unknown League')
                    logger.info("  * %s (ID: %s)", league_name, draft_id)
            
            if not active_drafts and not completed_drafts:
                logger.info("No drafts found for this user.")
            
            return {
                'success': True,
                'active_drafts': active_drafts,
                'completed_drafts': completed_drafts
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Error getting draft status: {e}"
            }


# Convenience functions (sync wrappers — use asyncio.run for CLI callers)
def display_sleeper_draft(draft_id: str) -> Dict[str, Any]:
    """Display Sleeper draft information."""
    service = SleeperDraftService()
    return asyncio.run(service.display_draft_info(draft_id))


def display_sleeper_league(league_id: str) -> Dict[str, Any]:
    """Display Sleeper league rosters."""
    service = SleeperDraftService()
    return asyncio.run(service.display_league_rosters(league_id))


def list_sleeper_leagues(username: str, season: str = str(datetime.date.today().year)) -> Dict[str, Any]:
    """List Sleeper leagues for a user."""
    service = SleeperDraftService()
    return asyncio.run(service.list_user_leagues(username, season))


def get_sleeper_draft_status(username: str, season: str = str(datetime.date.today().year)) -> Dict[str, Any]:
    """Get current draft status for a user."""
    service = SleeperDraftService()
    return asyncio.run(service.get_current_draft_status(username, season))
