"""Utilities for setting up draft relationships and importing from Sleeper API."""

from typing import List, Dict, Optional

from .player import Player
from .team import Team
from .owner import Owner
from .draft import Draft
from .strategy import Strategy, create_strategy
from api.sleeper_api import SleeperAPI


class DraftSetup:
    """Utility class for setting up draft relationships and importing data."""
    
    @staticmethod
    def create_owner_with_team(
        owner_id: str,
        owner_name: str,
        team_name: str,
        budget: float = 200.0,
        is_human: bool = True,
        email: Optional[str] = None,
        strategy: Optional[Strategy] = None
    ) -> tuple[Owner, Team]:
        """
        Create an owner and team with proper relationships established.
        
        Returns:
            Tuple of (Owner, Team) with relationships properly linked
        """
        # Create owner
        owner = Owner(
            owner_id=owner_id,
            name=owner_name,
            email=email,
            is_human=is_human
        )
        
        # Create team
        team = Team(
            team_id=f"team_{owner_id}",
            owner_id=owner_id,
            team_name=team_name,
            budget=budget
        )
        
        # Establish relationships
        owner.assign_team(team)
        
        # Assign strategy if provided
        if strategy:
            team.set_strategy(strategy)
            
        return owner, team
    
    @staticmethod
    def setup_draft_with_participants(
        draft_name: str,
        participants: List[Dict],
        budget_per_team: float = 200.0,
        roster_size: int = 16
    ) -> Draft:
        """
        Create a draft with multiple participants.
        
        Args:
            draft_name: Name of the draft
            participants: List of participant dicts with keys:
                - owner_id: str
                - owner_name: str
                - team_name: str
                - is_human: bool (default True)
                - email: str (optional)
                - strategy_type: str (optional, e.g., 'value', 'aggressive', 'conservative')
                - strategy_params: dict (optional)
            budget_per_team: Budget for each team
            roster_size: Roster size for each team
            
        Returns:
            Draft with all relationships established
        """
        draft = Draft(
            name=draft_name,
            budget_per_team=budget_per_team,
            roster_size=roster_size
        )
        
        for participant in participants:
            # Create strategy if specified
            strategy = None
            if 'strategy_type' in participant:
                strategy = create_strategy(participant['strategy_type'])
                # Apply custom parameters if provided
                if 'strategy_params' in participant:
                    for param, value in participant['strategy_params'].items():
                        strategy.set_parameter(param, value)
            
            # Create owner and team
            owner, team = DraftSetup.create_owner_with_team(
                owner_id=participant['owner_id'],
                owner_name=participant['owner_name'],
                team_name=participant['team_name'],
                budget=budget_per_team,
                is_human=participant.get('is_human', True),
                email=participant.get('email'),
                strategy=strategy
            )
            
            # Add to draft
            draft.add_owner(owner)
            draft.add_team(team)
            
        return draft
    
    @staticmethod
    def import_players_from_sleeper(
        position_filter: Optional[List[str]] = None,
        min_projected_points: float = 0.0
    ) -> List[Player]:
        """
        Import players from Sleeper API and convert to Player objects.
        
        Args:
            position_filter: List of positions to include (e.g., ['QB', 'RB', 'WR'])
            min_projected_points: Minimum projected points to include player
            
        Returns:
            List of Player objects
        """
        sleeper_api = SleeperAPI()
        
        try:
            # Get player data from Sleeper
            converted_players = sleeper_api.bulk_convert_players(position_filter)
            
            players = []
            for player_data in converted_players:
                if player_data['projected_points'] >= min_projected_points:
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
            print(f"Error importing players from Sleeper: {e}")
            return []
    
    @staticmethod
    def import_players_from_fantasypros(
        data_path: str = "data/data/sheets",
        min_projected_points: float = 0.0,
        position_filter: Optional[List[str]] = None
    ) -> List[Player]:
        """
        Import players from FantasyPros CSV files.
        
        Args:
            data_path: Path to the directory containing CSV files
            min_projected_points: Minimum projected points to include player
            position_filter: List of positions to include (e.g., ['QB', 'RB', 'WR'])
            
        Returns:
            List of Player objects with auction values calculated
        """
        try:
            # Import only when needed to avoid circular imports
            from data.fantasypros_loader import FantasyProsLoader
            
            loader = FantasyProsLoader(data_path)
            all_players = loader.load_all_players(min_projected_points)
            
            # Filter by position if specified
            if position_filter:
                all_players = [p for p in all_players if p.position in position_filter]
            
            # Calculate auction values
            loader.calculate_auction_values(all_players)
            
            return all_players
            
        except Exception as e:
            print(f"Error importing players from FantasyPros: {e}")
            return []
    
    @staticmethod
    def calculate_auction_values(players: List[Player], total_budget: float = 2400.0) -> None:
        """
        Calculate auction values for players based on projected points.
        Modifies players in-place.
        
        Args:
            players: List of Player objects
            total_budget: Total budget across all teams (12 teams * $200 = $2400)
        """
        if not players:
            return
            
        # Calculate total projected points
        total_points = sum(player.projected_points for player in players)
        
        if total_points == 0:
            return
            
        # Reserve some budget for low-value players (kickers, defenses, etc.)
        usable_budget = total_budget * 0.85  # Use 85% of budget for value calculation
        
        # Calculate value per point
        value_per_point = usable_budget / total_points
        
        # Assign auction values
        for player in players:
            base_value = player.projected_points * value_per_point
            
            # Add position-based adjustments
            position_multipliers = {
                'QB': 1.0,
                'RB': 1.2,  # Premium for RB scarcity
                'WR': 1.1,  # Slight premium for WR
                'TE': 1.0,
                'K': 0.5,   # Discount for kickers
                'DST': 0.5  # Discount for defenses
            }
            
            multiplier = position_multipliers.get(player.position, 1.0)
            player.auction_value = max(1.0, base_value * multiplier)  # Minimum $1
    
    @staticmethod
    def create_mock_draft(
        num_teams: int = 8,
        include_humans: int = 2,
        use_sleeper_data: bool = False,
        use_fantasypros_data: bool = True,
        data_path: str = "data/data/sheets"
    ) -> Draft:
        """
        Create a mock draft for testing purposes.
        
        Args:
            num_teams: Number of teams in the draft
            include_humans: Number of human participants
            use_sleeper_data: Whether to import real player data from Sleeper
            use_fantasypros_data: Whether to import data from FantasyPros CSVs
            data_path: Path to FantasyPros CSV files
            
        Returns:
            Draft ready for simulation
        """
        participants = []
        strategy_types = ['value', 'aggressive', 'conservative']
        
        for i in range(num_teams):
            is_human = i < include_humans
            strategy_type = None if is_human else strategy_types[i % len(strategy_types)]
            
            participant = {
                'owner_id': f"owner_{i+1}",
                'owner_name': f"{'Human' if is_human else 'AI'} Owner {i+1}",
                'team_name': f"Team {i+1}",
                'is_human': is_human
            }
            
            if strategy_type:
                participant['strategy_type'] = strategy_type
                
            participants.append(participant)
        
        # Create draft
        draft = DraftSetup.setup_draft_with_participants(
            draft_name="Mock Draft",
            participants=participants
        )
        
        # Add players - prioritize FantasyPros data
        players_added = False
        
        if use_fantasypros_data:
            players = DraftSetup.import_players_from_fantasypros(data_path)
            if players:
                draft.add_players(players)
                players_added = True
                print(f"Loaded {len(players)} players from FantasyPros CSV files")
        
        if not players_added and use_sleeper_data:
            players = DraftSetup.import_players_from_sleeper()
            if players:
                DraftSetup.calculate_auction_values(players)
                draft.add_players(players)
                players_added = True
                print(f"Loaded {len(players)} players from Sleeper API")
        
        if not players_added:
            # Fallback to mock players
            players = DraftSetup._create_mock_players()
            draft.add_players(players)
            print(f"Using {len(players)} mock players")
            
        return draft
    
    @staticmethod
    def _create_mock_players() -> List[Player]:
        """Create mock players for testing."""
        mock_players = [
            # QBs
            Player("qb1", "Josh Allen", "QB", "BUF", 350.0, 45.0, 12),
            Player("qb2", "Lamar Jackson", "QB", "BAL", 330.0, 40.0, 14),
            Player("qb3", "Patrick Mahomes", "QB", "KC", 320.0, 38.0, 10),
            
            # RBs
            Player("rb1", "Christian McCaffrey", "RB", "SF", 280.0, 60.0, 9),
            Player("rb2", "Austin Ekeler", "RB", "LAC", 250.0, 50.0, 5),
            Player("rb3", "Derrick Henry", "RB", "TEN", 240.0, 45.0, 7),
            
            # WRs
            Player("wr1", "Cooper Kupp", "WR", "LAR", 270.0, 55.0, 7),
            Player("wr2", "Davante Adams", "WR", "LV", 260.0, 50.0, 6),
            Player("wr3", "Tyreek Hill", "WR", "MIA", 250.0, 48.0, 11),
            
            # TEs
            Player("te1", "Travis Kelce", "TE", "KC", 200.0, 35.0, 10),
            Player("te2", "Mark Andrews", "TE", "BAL", 180.0, 25.0, 14),
            
            # K and DST
            Player("k1", "Justin Tucker", "K", "BAL", 120.0, 5.0, 14),
            Player("dst1", "Bills Defense", "DST", "BUF", 110.0, 8.0, 12)
        ]
        
        return mock_players


# Convenience functions
def create_simple_draft(owner_names: List[str], team_names: List[str]) -> Draft:
    """Create a simple draft with human participants."""
    participants = []
    for i, (owner_name, team_name) in enumerate(zip(owner_names, team_names)):
        participants.append({
            'owner_id': f"owner_{i+1}",
            'owner_name': owner_name,
            'team_name': team_name,
            'is_human': True
        })
    
    return DraftSetup.setup_draft_with_participants("Simple Draft", participants)


def create_ai_vs_human_draft(human_name: str, human_team: str, ai_count: int = 7) -> Draft:
    """Create a draft with one human vs multiple AI opponents."""
    participants = [{
        'owner_id': 'human_1',
        'owner_name': human_name,
        'team_name': human_team,
        'is_human': True
    }]
    
    strategies = ['value', 'aggressive', 'conservative']
    for i in range(ai_count):
        strategy_type = strategies[i % len(strategies)]
        participants.append({
            'owner_id': f'ai_{i+1}',
            'owner_name': f'AI {strategy_type.title()} {i+1}',
            'team_name': f'AI Team {i+1}',
            'is_human': False,
            'strategy_type': strategy_type
        })
    
    return DraftSetup.setup_draft_with_participants("Human vs AI Draft", participants)
