"""Owner class for auction draft tool."""

from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .team import Team


class Owner:
    """Represents an owner participating in the auction draft."""
    
    def __init__(
        self,
        owner_id: str,
        name: str,
        email: Optional[str] = None,
        is_human: bool = True
    ):
        self.owner_id = owner_id
        self.name = name
        self.email = email
        self.is_human = is_human
        self.team: Optional['Team'] = None  # Owner owns a team
        self.draft_history: List[Dict] = []
        self.preferences = {
            'risk_tolerance': 0.5,  # 0.0 (conservative) to 1.0 (aggressive)
            'position_priorities': ['RB', 'WR', 'QB', 'TE', 'K', 'DST'],
            'max_bid_percentage': 0.3,  # Max % of budget for single player
            'target_players': [],
            'avoid_players': []
        }
        
    def update_preferences(self, **kwargs) -> None:
        """Update owner preferences."""
        for key, value in kwargs.items():
            if key in self.preferences:
                self.preferences[key] = value
                
    def add_draft_action(self, action: Dict) -> None:
        """Add a draft action to history."""
        self.draft_history.append(action)
        
    def get_risk_tolerance(self) -> float:
        """Get the owner's risk tolerance level."""
        return self.preferences['risk_tolerance']
        
    def get_position_priorities(self) -> List[str]:
        """Get the owner's position draft priorities."""
        return self.preferences['position_priorities']
        
    def get_max_bid_percentage(self) -> float:
        """Get maximum percentage of budget to bid on single player."""
        return self.preferences['max_bid_percentage']
        
    def is_target_player(self, player_id: str) -> bool:
        """Check if player is on target list."""
        return player_id in self.preferences['target_players']
        
    def is_avoid_player(self, player_id: str) -> bool:
        """Check if player is on avoid list."""
        return player_id in self.preferences['avoid_players']
        
    def add_target_player(self, player_id: str) -> None:
        """Add player to target list."""
        if player_id not in self.preferences['target_players']:
            self.preferences['target_players'].append(player_id)
            
    def remove_target_player(self, player_id: str) -> None:
        """Remove player from target list."""
        if player_id in self.preferences['target_players']:
            self.preferences['target_players'].remove(player_id)
            
    def add_avoid_player(self, player_id: str) -> None:
        """Add player to avoid list."""
        if player_id not in self.preferences['avoid_players']:
            self.preferences['avoid_players'].append(player_id)
            
    def remove_avoid_player(self, player_id: str) -> None:
        """Remove player from avoid list."""
        if player_id in self.preferences['avoid_players']:
            self.preferences['avoid_players'].remove(player_id)
            
    def assign_team(self, team: 'Team') -> None:
        """Assign a team to this owner."""
        self.team = team
        
    def get_team(self) -> Optional['Team']:
        """Get the owner's team."""
        return self.team
        
    def has_team(self) -> bool:
        """Check if owner has a team assigned."""
        return self.team is not None
        
    def get_roster_spots(self) -> List[Dict]:
        """Get roster spots with current players."""
        if not self.team:
            return []
            
        roster_spots = []
        position_counts = {}
        
        # Count current players by position
        for player in self.team.roster:
            pos = player.position
            position_counts[pos] = position_counts.get(pos, 0) + 1
            roster_spots.append({
                'position': pos,
                'player': player,
                'is_filled': True
            })
            
        # Add empty spots based on position limits
        for position, limit in self.team.position_limits.items():
            current_count = position_counts.get(position, 0)
            empty_spots = limit - current_count
            
            for _ in range(empty_spots):
                roster_spots.append({
                    'position': position,
                    'player': None,
                    'is_filled': False
                })
                
        return roster_spots
        
    def get_available_roster_spots(self) -> Dict[str, int]:
        """Get count of available spots by position."""
        if not self.team:
            return {}
            
        available_spots = {}
        position_counts = {}
        
        # Count current players by position
        for player in self.team.roster:
            pos = player.position
            position_counts[pos] = position_counts.get(pos, 0) + 1
            
        # Calculate available spots
        for position, limit in self.team.position_limits.items():
            current_count = position_counts.get(position, 0)
            available_spots[position] = max(0, limit - current_count)
            
        return available_spots
            
    def get_draft_summary(self) -> Dict:
        """Get summary of draft actions."""
        total_actions = len(self.draft_history)
        successful_bids = sum(1 for action in self.draft_history 
                            if action.get('type') == 'bid' and action.get('successful', False))
        total_spent = sum(action.get('amount', 0) for action in self.draft_history 
                         if action.get('type') == 'bid' and action.get('successful', False))
        
        return {
            'total_actions': total_actions,
            'successful_bids': successful_bids,
            'total_spent': total_spent,
            'average_bid': total_spent / successful_bids if successful_bids > 0 else 0
        }
        
    def __str__(self) -> str:
        return f"{self.name} ({'Human' if self.is_human else 'AI'})"
        
    def __repr__(self) -> str:
        return f"Owner(id='{self.owner_id}', name='{self.name}', is_human={self.is_human})"
        
    def to_dict(self) -> Dict:
        """Convert owner to dictionary representation."""
        return {
            'owner_id': self.owner_id,
            'name': self.name,
            'email': self.email,
            'is_human': self.is_human,
            'has_team': self.has_team(),
            'team_id': self.team.team_id if self.team else None,
            'team_name': self.team.team_name if self.team else None,
            'preferences': self.preferences,
            'draft_history': self.draft_history,
            'draft_summary': self.get_draft_summary(),
            'roster_spots': self.get_roster_spots() if self.team else [],
            'available_spots': self.get_available_roster_spots() if self.team else {}
        }
