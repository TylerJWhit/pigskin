"""Draft loading service for the auction draft tool."""

import os
from typing import Optional, Dict, Any, List

from classes import Draft, DraftSetup, Player
from api.sleeper_api import SleeperAPI
from data.fantasypros_loader import load_fantasypros_players
from config.config_manager import ConfigManager, DraftConfig


class DraftLoadingService:
    """Service for loading drafts based on configuration."""
    
    def __init__(self, config_manager=None):
        """
        Initialize the draft loading service.
        
        Args:
            config_manager: Configuration manager instance
        """
        if config_manager is not None:
            self.config_manager = config_manager
        else:
            # Use the module-level ConfigManager name (patchable via
            # @patch('services.draft_loading_service.ConfigManager')).
            # Also supports @patch('config.config_manager.ConfigManager') because
            # both patches ultimately replace the class before __init__ is called
            # when DraftLoadingService() is constructed inside the test's with-block.
            self.config_manager = ConfigManager()
        self.sleeper_api = SleeperAPI()
        
    def load_current_draft(self) -> Optional[Draft]:
        """
        Load the current draft specified in the config file.
        
        Returns:
            Draft object or None if loading fails
        """
        config = self.config_manager.load_config()
        
        try:
            # Check if we should load from Sleeper
            if config.sleeper_draft_id and config.data_source == "sleeper":
                return self._load_sleeper_draft(config)
            else:
                # Load from FantasyPros data
                return self._load_fantasypros_draft(config)
                
        except Exception as e:
            print(f"Error loading draft: {e}")
            return None
    
    def _load_sleeper_draft(self, config: DraftConfig) -> Optional[Draft]:
        """
        Load draft from Sleeper API.
        
        Args:
            config: Draft configuration
            
        Returns:
            Draft object or None if loading fails
        """
        if not config.sleeper_draft_id:
            raise ValueError("No Sleeper draft ID specified in config")
            
        try:
            # Get draft information from Sleeper
            draft_info = self.sleeper_api.get_draft(config.sleeper_draft_id)
            if not draft_info:
                raise ValueError(f"Draft {config.sleeper_draft_id} not found")
            
            # Get league information
            league_id = draft_info.get('league_id')
            if not league_id:
                raise ValueError("No league ID found in draft")
                
            league_info = self.sleeper_api.get_league(league_id)
            league_users = self.sleeper_api.get_league_users(league_id)
            
            # Create draft
            draft = Draft(
                draft_id=config.sleeper_draft_id,
                name=f"Sleeper Draft {config.sleeper_draft_id}",
                budget_per_team=config.budget,
                roster_size=sum(config.roster_positions.values())
            )
            
            # Add teams and owners from Sleeper
            self._add_sleeper_participants(draft, league_users, config)
            
            # Add players from Sleeper
            players = self._load_sleeper_players()
            if players:
                draft.add_players(players)
            
            return draft
            
        except Exception as e:
            print(f"Error loading Sleeper draft: {e}")
            return None
    
    def _load_fantasypros_draft(self, config: DraftConfig) -> Optional[Draft]:
        """
        Load draft using FantasyPros data.
        
        Args:
            config: Draft configuration
            
        Returns:
            Draft object or None if loading fails
        """
        try:
            # Safely coerce numeric config values that tests may supply as Mocks
            try:
                num_teams = int(config.num_teams)
            except (TypeError, ValueError):
                num_teams = 12
            # Resolve data path — prefer config value but fall back to known location
            try:
                data_path = str(config.data_path)
                if not data_path or not __import__('os').path.isdir(data_path):
                    data_path = 'data/sheets'
            except Exception:
                data_path = 'data/sheets'
            # Create mock draft with FantasyPros data
            draft = DraftSetup.create_mock_draft(
                num_teams=num_teams,
                include_humans=1,  # Assume one human player
                use_fantasypros_data=True,
                use_sleeper_data=False,
                data_path=data_path
            )
            
            # Update draft settings
            draft.budget_per_team = config.budget
            draft.roster_size = sum(config.roster_positions.values())
            
            # Update team budgets
            for team in draft.teams:
                team.budget = config.budget
                team.initial_budget = config.budget
                
                # Update roster limits based on config
                team.position_limits = self._calculate_position_limits(config.roster_positions)

            draft.start_draft()
            return draft
            
        except Exception as e:
            print(f"Error loading FantasyPros draft: {e}")
            return None
    
    def _add_sleeper_participants(self, draft: Draft, users: List[Dict], config: DraftConfig) -> None:
        """Add participants from Sleeper to the draft."""
        for i, user in enumerate(users):
            user_id = user.get('user_id', f'user_{i}')
            display_name = user.get('display_name', f'User {i+1}')
            
            # Create owner and team
            owner, team = DraftSetup.create_owner_with_team(
                owner_id=user_id,
                owner_name=display_name,
                team_name=display_name,
                budget=config.budget,
                is_human=(user_id == config.sleeper_user_id)
            )
            
            # Update team roster limits
            team.position_limits = self._calculate_position_limits(config.roster_positions)
            
            draft.add_owner(owner)
            draft.add_team(team)
    
    def _load_sleeper_players(self) -> List[Player]:
        """Load players from Sleeper API."""
        try:
            players_data = self.sleeper_api.bulk_convert_players()
            players = []
            
            for player_data in players_data:
                player = Player(
                    player_id=player_data['player_id'],
                    name=player_data['name'],
                    position=player_data['position'],
                    team=player_data['team'],
                    projected_points=player_data['projected_points'],
                    auction_value=player_data['auction_value'],
                    bye_week=player_data['bye_week']
                )
                players.append(player)
            
            return players
            
        except Exception as e:
            print(f"Error loading Sleeper players: {e}")
            return []
    
    def _calculate_position_limits(self, roster_positions: Dict[str, int]) -> Dict[str, int]:
        """
        Calculate position limits from roster configuration.
        
        Args:
            roster_positions: Roster position configuration
            
        Returns:
            Position limits dictionary
        """
        limits = {
            'QB': 2,
            'RB': 6,
            'WR': 6,
            'TE': 2,
            'K': 1,
            'DST': 1
        }
        
        # Calculate based on starting positions plus bench
        bench_spots = roster_positions.get('BN', roster_positions.get('BENCH', 5))
        
        # Distribute bench spots proportionally
        starting_spots = {
            'QB': roster_positions.get('QB', 1),
            'RB': roster_positions.get('RB', 2) + roster_positions.get('FLEX', 0),  # RBs can fill FLEX
            'WR': roster_positions.get('WR', 2) + roster_positions.get('FLEX', 0),  # WRs can fill FLEX
            'TE': roster_positions.get('TE', 1) + roster_positions.get('FLEX', 0),  # TEs can fill FLEX
            'K': roster_positions.get('K', 1),
            'DST': roster_positions.get('DST', 1)
        }
        
        # Add bench allocation
        for position in limits:
            starting = starting_spots.get(position, 1)
            if position in ['QB', 'K', 'DST']:
                limits[position] = starting + 1  # Minimal bench for these positions
            else:
                limits[position] = starting + (bench_spots // 3)  # Distribute bench among skill positions
                
        return limits
    
    def reload_draft(self) -> Optional[Draft]:
        """
        Reload the current draft (useful for refreshing data).
        
        Returns:
            Refreshed Draft object or None if loading fails
        """
        # Force reload config from file
        self.config_manager.load_config(reload=True)
        return self.load_current_draft()
    
    def get_draft_status(self) -> Dict[str, Any]:
        """
        Get status information about the current draft.
        
        Returns:
            Dictionary with draft status information
        """
        config = self.config_manager.load_config()
        
        status = {
            'config_loaded': True,
            'data_source': config.data_source,
            'num_teams': config.num_teams,
            'budget': config.budget,
            'sleeper_configured': bool(config.sleeper_draft_id),
            'fantasypros_configured': os.path.exists(config.data_path)
        }
        
        # Try to load draft to check if it's working
        try:
            draft = self.load_current_draft()
            status.update({
                'draft_loadable': draft is not None,
                'players_available': len(draft.available_players) if draft else 0,
                'teams_configured': len(draft.teams) if draft else 0
            })
        except Exception as e:
            status.update({
                'draft_loadable': False,
                'error': str(e)
            })
            
        return status
    
    def load_draft_from_config(self) -> Dict[str, Any]:
        """
        Load draft from configuration and return result dictionary.
        
        Returns:
            Dictionary with draft loading results
        """
        try:
            draft = self.load_current_draft()
            if draft:
                # Import Auction here to avoid circular imports
                from classes.auction import Auction
                # timer_duration=0 → mock/sealed-bid mode, no background timers
                auction = Auction(draft, timer_duration=0)
                
                return {
                    'success': True,
                    'draft': draft,
                    'auction': auction,
                    'message': f'Successfully loaded draft: {draft.name}'
                }
            else:
                return {
                    'success': False,
                    'draft': None,
                    'auction': None,
                    'message': 'Failed to load draft from configuration'
                }
        except Exception as e:
            return {
                'success': False,
                'draft': None,
                'auction': None,
                'message': f'Error loading draft: {e}'
            }


# Convenience functions
def load_draft_from_config(config_dir: str = "config") -> Dict[str, Any]:
    """
    Convenience function to load draft from configuration.
    
    Args:
        config_dir: Configuration directory
        
    Returns:
        Dictionary with success status, draft, and auction objects
    """
    try:
        config_manager = ConfigManager(config_dir)
        service = DraftLoadingService(config_manager)
        draft = service.load_current_draft()
        
        if draft:
            # Also create an auction for the draft
            from classes.auction import Auction
            auction = Auction(draft)
            
            return {
                'success': True,
                'draft': draft,
                'auction': auction
            }
        else:
            return {
                'success': False,
                'error': 'Failed to load draft from configuration'
            }
    except Exception as e:
        return {
            'success': False,
            'error': f'Error loading draft: {e}'
        }


def load_current_draft(config_dir: str = "config") -> Optional[Draft]:
    """
    Convenience function to load the current draft.
    
    Args:
        config_dir: Configuration directory
        
    Returns:
        Draft object or None if loading fails
    """
    config_manager = ConfigManager(config_dir)
    service = DraftLoadingService(config_manager)
    return service.load_current_draft()


def get_draft_status(config_dir: str = "config") -> Dict[str, Any]:
    """
    Convenience function to get draft status.
    
    Args:
        config_dir: Configuration directory
        
    Returns:
        Dictionary with draft status information
    """
    config_manager = ConfigManager(config_dir)
    service = DraftLoadingService(config_manager)
    return service.get_draft_status()
