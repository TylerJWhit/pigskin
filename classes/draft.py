"""Draft class for auction draft tool."""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid
import random
import concurrent.futures
from pydantic import BaseModel, Field
from .player import Player
from .team import Team
from .owner import Owner


class DraftState(BaseModel):
    """Serializable snapshot of a Draft's current state."""

    draft_id: str
    name: str
    status: str
    current_round: int = Field(ge=0)
    budget_per_team: float = Field(gt=0)
    roster_size: int = Field(gt=0)
    num_teams: int = Field(gt=0)
    current_player_id: Optional[str] = None
    current_bid: float = Field(ge=0.0, default=0.0)
    team_ids: List[str] = Field(default_factory=list)


class Draft:
    """Represents a single auction draft session."""
    
    def __init__(
        self,
        draft_id: Optional[str] = None,
        name: str = "Auction Draft",
        budget_per_team: float = 200.0,
        roster_size: int = 16,
        num_teams: int = 12
    ):
        self.draft_id = draft_id or str(uuid.uuid4())
        self.name = name
        self.budget_per_team = budget_per_team
        self.roster_size = roster_size
        self.max_roster_size = roster_size
        self.num_teams = num_teams
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
        
    def add_team(self, team: Team, owner=None) -> None:
        """Add a team to the draft.
        
        Args:
            team: The team to add.
            owner: Optional owner to associate with the team and register in the draft.
        """
        if len(self.teams) >= self.num_teams:
            raise ValueError(f"Maximum number of teams ({self.num_teams}) already reached")
        self.teams.append(team)

        # Register the supplied owner if provided
        if owner is not None:
            self.add_owner(owner)

        # Link owner to team if owner exists
        linked_owner = self._get_owner_by_id(team.owner_id)
        if linked_owner:
            linked_owner.assign_team(team)
        
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
        if winner_team is None:
            # No winner found — skip awarding but still clean up auction state
            self.current_player = None
            self.current_bid = 0.0
            self.current_high_bidder = None
            self._advance_nominator()
            if not self._is_draft_complete():
                self._start_new_nomination()
            return
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
        """Get team by owner ID, team ID, or team name."""
        for team in self.teams:
            if team.owner_id == owner_id:
                return team
        # Fallback: match by team_id or team_name
        for team in self.teams:
            if getattr(team, 'team_id', None) == owner_id or getattr(team, 'team_name', None) == owner_id:
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
        nominator = self.get_current_nominator()
        if nominator:
            self._get_team_nomination(nominator)

    def _get_team_nomination(self, team: 'Team') -> Optional['Player']:
        """Get a player nomination from the given team."""
        if not self.available_players:
            return None
        # Ask team strategy first
        for player in self.available_players:
            if hasattr(team, 'should_nominate_player') and team.should_nominate_player(player):
                return player
        # Fall back to random selection
        return random.choice(self.available_players)

    def _get_team_by_id(self, team_id: str) -> Optional['Team']:
        """Get team by team ID."""
        for team in self.teams:
            if team.team_id == team_id:
                return team
        return None

    def _collect_team_bids(self, player: 'Player') -> Dict[str, float]:
        """Collect sealed bids from all teams for a player."""
        bids = {}
        for team in self.teams:
            try:
                bid = team.calculate_bid(player, 0.0, [])
                if bid > 0:
                    bids[team.team_id] = bid
            except Exception as exc:
                import logging
                logging.getLogger(__name__).debug(
                    "Strategy bid failed for team %s: %s", getattr(team, 'team_id', '?'), exc
                )
        return bids

    def _collect_team_bids_parallel(self, player: 'Player') -> Dict[str, float]:
        """Collect sealed bids from all teams in parallel."""
        bids = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_team = {
                executor.submit(team.calculate_bid, player): team
                for team in self.teams
            }
            for future in concurrent.futures.as_completed(future_to_team):
                team = future_to_team[future]
                try:
                    bid = future.result()
                    if bid > 0:
                        bids[team.team_id] = bid
                except Exception:
                    pass
        return bids

    def _determine_auction_winner(self, bids: Dict[str, float]) -> Tuple[Optional[str], float]:
        """Determine auction winner using Vickrey (second-price) logic.

        Returns the highest bidder paying second-highest + 1.
        Ties resolved randomly; single bidder pays their bid.
        """
        if not bids:
            return None, 0.0
        sorted_bids = sorted(bids.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_bids) == 1:
            winner_id, winning_bid = sorted_bids[0]
            return winner_id, winning_bid
        top_bid = sorted_bids[0][1]
        second_bid = sorted_bids[1][1]
        # Handle ties at the top
        tied_winners = [team_id for team_id, bid in sorted_bids if bid == top_bid]
        winner_id = random.choice(tied_winners)
        if len(tied_winners) > 1:
            # All tied — winner pays the tied amount
            return winner_id, top_bid
        # Normal case — winner pays second-highest + 1
        return winner_id, second_bid + 1.0

    def _award_player_to_team(self, player: 'Player', winner_id: str, price: float) -> None:
        """Award a player to the winning team (lookup by team_id)."""
        winner_team = self._get_team_by_id(winner_id)
        if winner_team:
            winner_team.add_player(player, price)
        if player in self.available_players:
            self.available_players.remove(player)
        self.drafted_players.append(player)

    def run_complete_draft(self) -> None:
        """Run a complete automated sealed-bid draft until all rosters are full."""
        while not self._is_draft_complete() and self.available_players:
            nominator = self.get_current_nominator()
            if nominator is None:
                break
            player = self._get_team_nomination(nominator)
            if player is None:
                break
            bids = self._collect_team_bids(player)
            winner_id, winning_bid = self._determine_auction_winner(bids)
            if winner_id:
                self._award_player_to_team(player, winner_id, winning_bid)
            elif player in self.available_players:
                # No bids — remove from pool to prevent infinite loop
                self.available_players.remove(player)
            self._advance_nominator()
        self._complete_draft()
        
    def _is_draft_complete(self) -> bool:
        """Check if the draft is complete."""
        if not self.available_players:
            return True
        for team in self.teams:
            is_complete = (
                team.is_roster_complete()
                if hasattr(team, 'is_roster_complete') and callable(team.is_roster_complete)
                else len(team.roster) >= self.roster_size
            )
            if not is_complete:
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

    def get_state(self) -> "DraftState":
        """Return a serializable Pydantic snapshot of the current draft state."""
        current_player_id = (
            self.current_player.player_id if self.current_player else None
        )
        return DraftState(
            draft_id=self.draft_id,
            name=self.name,
            status=self.status,
            current_round=self.current_round,
            budget_per_team=self.budget_per_team,
            roster_size=self.roster_size,
            num_teams=self.num_teams,
            current_player_id=current_player_id,
            current_bid=self.current_bid,
            team_ids=[t.team_id for t in self.teams],
        )
