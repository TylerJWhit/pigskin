"""Draft class for auction draft tool."""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid
from .player import Player
from .team import Team
from .owner import Owner


class Draft:
    """Represents a single auction draft session."""
    
    def __init__(
        self,
        draft_id: Optional[str] = None,
        name: str = "Auction Draft",
        budget_per_team: float = 200.0,
        roster_size: int = 16
    ):
        self.draft_id = draft_id or str(uuid.uuid4())
        self.name = name
        self.budget_per_team = budget_per_team
        self.roster_size = roster_size
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        
        # Draft state
        self.status = "created"  # created, started, paused, completed
        self.current_round = 0
        self.current_nominator_index = 0
        self.current_player: Optional[Player] = None
        self.current_bid = 0.0
        self.current_high_bidder: Optional[str] = None
        
        # Participants
        self.teams: List[Team] = []
        self.owners: List[Owner] = []
        self.players: List[Player] = []
        self.drafted_players: List[Player] = []
        self.available_players: List[Player] = []
        
        # Draft history
        self.nominations: List[Dict] = []
        self.bids: List[Dict] = []
        self.transactions: List[Dict] = []
        
    def add_team(self, team: Team) -> None:
        """Add a team to the draft."""
        if len(self.teams) >= 12:  # Max teams
            raise ValueError("Maximum number of teams (12) already reached")
        self.teams.append(team)
        
        # Link owner to team if owner exists
        owner = self._get_owner_by_id(team.owner_id)
        if owner:
            owner.assign_team(team)
        
    def add_owner(self, owner: Owner) -> None:
        """Add an owner to the draft."""
        self.owners.append(owner)
        
        # Link team to owner if team exists
        team = self._get_team_by_owner(owner.owner_id)
        if team:
            owner.assign_team(team)
        
    def add_players(self, players: List[Player]) -> None:
        """Add players to the draft."""
        self.players.extend(players)
        self.available_players.extend(players)
        
    def start_draft(self) -> None:
        """Start the draft."""
        if self.status != "created":
            raise ValueError("Draft has already been started or completed")
            
        if len(self.teams) < 2:
            raise ValueError("Need at least 2 teams to start draft")
            
        self.status = "started"
        self.started_at = datetime.now()
        self.current_round = 1
        self._start_new_nomination()
        
    def nominate_player(self, player: Player, nominating_owner_id: str, initial_bid: float = 1.0) -> None:
        """Nominate a player for auction."""
        if self.status != "started":
            raise ValueError("Draft is not active")
            
        if player not in self.available_players:
            raise ValueError("Player is not available for nomination")
            
        if initial_bid < 1.0:
            raise ValueError("Initial bid must be at least $1")
            
        self.current_player = player
        self.current_bid = initial_bid
        self.current_high_bidder = nominating_owner_id
        
        # Record nomination
        nomination = {
            'timestamp': datetime.now(),
            'round': self.current_round,
            'player': player,
            'nominator': nominating_owner_id,
            'initial_bid': initial_bid
        }
        self.nominations.append(nomination)
        
    def place_bid(self, bidder_id: str, bid_amount: float) -> bool:
        """Place a bid on the current player."""
        if self.status != "started":
            raise ValueError("Draft is not active")
            
        if not self.current_player:
            raise ValueError("No player currently being auctioned")
            
        if bid_amount <= self.current_bid:
            return False  # Bid too low
            
        # Check if bidder has enough budget
        bidder_team = self._get_team_by_owner(bidder_id)
        if not bidder_team or bid_amount > bidder_team.budget:
            return False  # Insufficient budget
            
        self.current_bid = bid_amount
        self.current_high_bidder = bidder_id
        
        # Record bid
        bid = {
            'timestamp': datetime.now(),
            'round': self.current_round,
            'player': self.current_player,
            'bidder': bidder_id,
            'amount': bid_amount
        }
        self.bids.append(bid)
        return True
        
    def complete_auction(self) -> None:
        """Complete the current player auction."""
        if not self.current_player or not self.current_high_bidder:
            raise ValueError("No active auction to complete")
            
        player = self.current_player
        winner_id = self.current_high_bidder
        final_price = self.current_bid
        
        # Award player to winning team
        winner_team = self._get_team_by_owner(winner_id)
        if winner_team:
            winner_team.add_player(player, final_price)
            
        # Remove from available players
        self.available_players.remove(player)
        self.drafted_players.append(player)
        
        # Record transaction
        transaction = {
            'timestamp': datetime.now(),
            'round': self.current_round,
            'player': player,
            'winning_bidder': winner_id,
            'final_price': final_price
        }
        self.transactions.append(transaction)
        
        # Clear current auction state
        self.current_player = None
        self.current_bid = 0.0
        self.current_high_bidder = None
        
        # Move to next nomination
        self._advance_nominator()
        
        # Check if draft is complete
        if self._is_draft_complete():
            self._complete_draft()
        else:
            self._start_new_nomination()
            
    def pause_draft(self) -> None:
        """Pause the draft."""
        if self.status == "started":
            self.status = "paused"
            
    def resume_draft(self) -> None:
        """Resume a paused draft."""
        if self.status == "paused":
            self.status = "started"
            
    def _get_team_by_owner(self, owner_id: str) -> Optional[Team]:
        """Get team by owner ID."""
        for team in self.teams:
            if team.owner_id == owner_id:
                return team
        return None
        
    def _get_owner_by_id(self, owner_id: str) -> Optional[Owner]:
        """Get owner by owner ID."""
        for owner in self.owners:
            if owner.owner_id == owner_id:
                return owner
        return None
        
    def _advance_nominator(self) -> None:
        """Move to the next nominator."""
        self.current_nominator_index = (self.current_nominator_index + 1) % len(self.teams)
        if self.current_nominator_index == 0:
            self.current_round += 1
            
    def _start_new_nomination(self) -> None:
        """Start a new nomination phase."""
        return
        
    def _is_draft_complete(self) -> bool:
        """Check if the draft is complete."""
        # Draft is complete when all teams have full rosters or no more players available
        for team in self.teams:
            if len(team.roster) < self.roster_size and self.available_players:
                return False
        return True
        
    def _complete_draft(self) -> None:
        """Complete the draft."""
        self.status = "completed"
        self.completed_at = datetime.now()
        
    def get_current_nominator(self) -> Optional[Team]:
        """Get the team that should nominate next."""
        if self.teams:
            return self.teams[self.current_nominator_index]
        return None
        
    def get_draft_summary(self) -> Dict:
        """Get a summary of the draft."""
        total_spent = sum(team.get_total_spent() for team in self.teams)
        avg_spent = total_spent / len(self.teams) if self.teams else 0
        
        return {
            'draft_id': self.draft_id,
            'name': self.name,
            'status': self.status,
            'current_round': self.current_round,
            'teams': len(self.teams),
            'players_drafted': len(self.drafted_players),
            'players_available': len(self.available_players),
            'total_spent': total_spent,
            'average_spent': avg_spent,
            'started_at': self.started_at,
            'completed_at': self.completed_at
        }
        
    def get_leaderboard(self) -> List[Dict]:
        """Get current leaderboard based on projected points."""
        leaderboard = []
        for team in self.teams:
            leaderboard.append({
                'team': team,
                'projected_points': team.get_projected_points(),
                'total_spent': team.get_total_spent(),
                'remaining_budget': team.budget,
                'roster_size': len(team.roster)
            })
        
        # Sort by projected points (descending)
        leaderboard.sort(key=lambda x: x['projected_points'], reverse=True)
        return leaderboard
        
    def __str__(self) -> str:
        return f"{self.name} ({self.status})"
        
    def __repr__(self) -> str:
        return f"Draft(id='{self.draft_id}', name='{self.name}', status='{self.status}')"
        
    def to_dict(self) -> Dict:
        """Convert draft to dictionary representation."""
        return {
            'draft_id': self.draft_id,
            'name': self.name,
            'budget_per_team': self.budget_per_team,
            'roster_size': self.roster_size,
            'status': self.status,
            'current_round': self.current_round,
            'teams': [team.to_dict() for team in self.teams],
            'summary': self.get_draft_summary(),
            'leaderboard': self.get_leaderboard()
        }
