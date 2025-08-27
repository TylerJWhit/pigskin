"""Auction class for auction draft tool."""

from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
import threading
import time
from .draft import Draft
from .player import Player
from .team import Team
from .owner import Owner
from .strategy import Strategy


class Auction:
    """Handles the real-time auction mechanics for a draft."""
    
    def __init__(
        self,
        draft: Draft,
        bid_timer: int = 30,
        nomination_timer: int = 60
    ):
        self.draft = draft
        self.bid_timer = bid_timer
        self.nomination_timer = nomination_timer
        
        # Auction state
        self.is_active = False
        self.current_timer: Optional[threading.Timer] = None
        self.auto_bid_enabled = {}  # owner_id -> bool
        self.strategies = {}  # owner_id -> Strategy
        
        # Events and callbacks
        self.on_bid_placed: List[Callable] = []
        self.on_player_nominated: List[Callable] = []
        self.on_auction_completed: List[Callable] = []
        self.on_timer_tick: List[Callable] = []
        
    def start_auction(self) -> None:
        """Start the auction system."""
        if self.draft.status != "started":
            raise ValueError("Draft must be started before auction can begin")
            
        self.is_active = True
        self._start_nomination_timer()
        
    def stop_auction(self) -> None:
        """Stop the auction system."""
        self.is_active = False
        if self.current_timer:
            self.current_timer.cancel()
            
    def nominate_player(
        self,
        player: Player,
        nominating_owner_id: str,
        initial_bid: float = 1.0
    ) -> bool:
        """Nominate a player for auction."""
        try:
            self.draft.nominate_player(player, nominating_owner_id, initial_bid)
            self._start_bid_timer()
            self._notify_player_nominated(player, nominating_owner_id, initial_bid)
            return True
        except ValueError:
            return False
            
    def place_bid(self, bidder_id: str, bid_amount: float) -> bool:
        """Place a bid on the current player."""
        if not self.is_active:
            return False
            
        success = self.draft.place_bid(bidder_id, bid_amount)
        if success:
            self._start_bid_timer()  # Reset timer
            self._notify_bid_placed(bidder_id, bid_amount)
            
            # Trigger auto-bids from other participants
            self._process_auto_bids()
            
        return success
        
    def enable_auto_bid(self, owner_id: str, strategy: Strategy) -> None:
        """Enable auto-bidding for an owner with given strategy."""
        self.auto_bid_enabled[owner_id] = True
        self.strategies[owner_id] = strategy
        
    def disable_auto_bid(self, owner_id: str) -> None:
        """Disable auto-bidding for an owner."""
        self.auto_bid_enabled[owner_id] = False
        if owner_id in self.strategies:
            del self.strategies[owner_id]
            
    def force_complete_auction(self) -> None:
        """Force complete the current player auction."""
        if self.draft.current_player:
            self._complete_current_auction()
            
    def _start_nomination_timer(self) -> None:
        """Start timer for player nomination."""
        if self.current_timer:
            self.current_timer.cancel()
            
        self.draft.time_remaining = self.nomination_timer
        self.current_timer = threading.Timer(1.0, self._nomination_timer_tick)
        self.current_timer.start()
        
    def _start_bid_timer(self) -> None:
        """Start timer for bidding phase."""
        if self.current_timer:
            self.current_timer.cancel()
            
        self.draft.time_remaining = self.bid_timer
        self.current_timer = threading.Timer(1.0, self._bid_timer_tick)
        self.current_timer.start()
        
    def _nomination_timer_tick(self) -> None:
        """Handle nomination timer tick."""
        if not self.is_active:
            return
            
        self.draft.time_remaining -= 1
        self._notify_timer_tick("nomination", self.draft.time_remaining)
        
        if self.draft.time_remaining <= 0:
            self._auto_nominate_player()
        else:
            self.current_timer = threading.Timer(1.0, self._nomination_timer_tick)
            self.current_timer.start()
            
    def _bid_timer_tick(self) -> None:
        """Handle bid timer tick."""
        if not self.is_active:
            return
            
        self.draft.time_remaining -= 1
        self._notify_timer_tick("bidding", self.draft.time_remaining)
        
        if self.draft.time_remaining <= 0:
            self._complete_current_auction()
        else:
            self.current_timer = threading.Timer(1.0, self._bid_timer_tick)
            self.current_timer.start()
            
    def _auto_nominate_player(self) -> None:
        """Auto-nominate a player when timer expires."""
        current_nominator = self.draft.get_current_nominator()
        if not current_nominator:
            return
            
        # Find a suitable player to nominate
        available_players = [p for p in self.draft.available_players if not p.is_drafted]
        if not available_players:
            return
            
        owner_id = current_nominator.owner_id
        
        # Check if team needs to prioritize roster completion due to low budget
        remaining_slots = self._get_remaining_roster_slots(current_nominator)
        needs_roster_completion = current_nominator.budget <= remaining_slots * 2.0  # Less than $2 per slot
        
        if needs_roster_completion:
            # For low budget teams, prioritize cheap players for needed positions
            sorted_players = self._sort_players_for_roster_completion(available_players, current_nominator)
        else:
            # Normal case: try highest value players first
            sorted_players = sorted(available_players, key=lambda p: getattr(p, 'auction_value', 10), reverse=True)
        
        # Try to use team's built-in strategy first
        if current_nominator.strategy:
            owner = self.draft._get_owner_by_id(owner_id)
            owner_data = owner.to_dict() if owner else None
            
            for player in sorted_players:
                if current_nominator.should_nominate_player(player, owner_data):
                    self.nominate_player(player, owner_id)
                    return
        # Fallback to auction's assigned strategy        
        elif owner_id in self.strategies:
            strategy = self.strategies[owner_id]
            owner = self.draft._get_owner_by_id(owner_id)
            if owner:
                for player in sorted_players:
                    if strategy.should_nominate(player, current_nominator, owner, current_nominator.budget):
                        self.nominate_player(player, owner_id)
                        return
                        
        # Force nomination for teams that need roster completion
        if needs_roster_completion and sorted_players:
            # Force nominate the cheapest player that helps with roster completion
            self.nominate_player(sorted_players[0], owner_id)
        elif sorted_players:
            # Normal fallback: nominate highest value available player  
            self.nominate_player(sorted_players[0], owner_id)
    
    def _sort_players_for_roster_completion(self, available_players, team):
        """Sort players to prioritize cheap needed positions for roster completion."""
        # Get current roster composition
        current_roster = getattr(team, 'roster', [])
        position_counts = {}
        for p in current_roster:
            pos = getattr(p, 'position', 'UNKNOWN')
            position_counts[pos] = position_counts.get(pos, 0) + 1
        
        # Define minimum requirements
        min_requirements = {
            'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DST': 1
        }
        
        def priority_score(player):
            position = getattr(player, 'position', 'UNKNOWN')
            value = getattr(player, 'auction_value', 10)
            
            # Calculate priority: higher priority for needed positions, lower for expensive players
            current_count = position_counts.get(position, 0)
            min_needed = min_requirements.get(position, 0)
            
            if current_count < min_needed:
                # Needed position - prioritize cheaper players
                need_priority = 100 - value  # Lower cost = higher priority
            else:
                # Not critically needed - much lower priority
                need_priority = 10 - value
                
            return need_priority
        
        return sorted(available_players, key=priority_score, reverse=True)
    
    def _get_remaining_roster_slots(self, team) -> int:
        """Calculate how many roster slots still need to be filled."""
        if hasattr(team, 'roster_config') and team.roster_config:
            total_slots = sum(team.roster_config.values())
        else:
            total_slots = 15  # Default roster size
        
        current_roster_size = len(getattr(team, 'roster', []))
        return max(0, total_slots - current_roster_size)
    
    def _sort_players_for_roster_completion(self, available_players, team):
        """Sort players to prioritize roster completion for low budget teams."""
        # For roster completion, prioritize cheap players first
        # Sort by auction value (low to high) for teams needing to complete roster
        return sorted(available_players, key=lambda player: player.auction_value)
        
    def _complete_current_auction(self) -> None:
        """Complete the current player auction."""
        if self.draft.current_player:
            self.draft.complete_auction()
            self._notify_auction_completed()
            
            if self.draft.status == "completed":
                self.stop_auction()
            else:
                self._start_nomination_timer()
                
    def _process_auto_bids(self) -> None:
        """Process auto-bids using simplified sealed bid auction logic."""
        if not self.draft.current_player:
            return
            
        current_player = self.draft.current_player
        current_bid = self.draft.current_bid
        
        # Collect all valid bids from eligible teams
        valid_bids = []
        
        for team in self.draft.teams:
            owner_id = team.owner_id
            if (owner_id in self.auto_bid_enabled and 
                self.auto_bid_enabled[owner_id] and 
                team.can_bid(current_player, current_bid + 1)):
                
                remaining_players = [p for p in self.draft.available_players if not p.is_drafted]
                max_bid = 0
                
                # Get team's maximum willingness to pay using their strategy with constraints
                if team.strategy:
                    owner = self.draft._get_owner_by_id(owner_id)
                    owner_data = owner.to_dict() if owner else None
                    # Use constrained bid calculation if available
                    if hasattr(team.strategy, 'calculate_bid_with_constraints'):
                        max_bid = team.strategy.calculate_bid_with_constraints(
                            current_player,
                            team,
                            owner,
                            current_bid,
                            team.budget,
                            remaining_players
                        )
                    else:
                        max_bid = team.calculate_bid(
                            player=current_player,
                            current_bid=current_bid,
                            remaining_players=remaining_players,
                            owner_data=owner_data
                        )
                elif owner_id in self.strategies:
                    strategy = self.strategies[owner_id]
                    owner = self.draft._get_owner_by_id(owner_id)
                    if owner:
                        # Use constrained bid calculation if available
                        if hasattr(strategy, 'calculate_bid_with_constraints'):
                            max_bid = strategy.calculate_bid_with_constraints(
                                current_player,
                                team,
                                owner,
                                current_bid,
                                team.budget,
                                remaining_players
                            )
                        else:
                            max_bid = strategy.calculate_bid(
                                current_player,
                                team,
                                owner,
                                current_bid,
                                team.budget,
                                remaining_players
                            )
                
                # Only include bids that are valid and respect budget constraints
                if max_bid > current_bid:
                    # Apply budget constraint check at auction level
                    if team.strategy and hasattr(team.strategy, 'calculate_max_bid'):
                        max_allowable_bid = team.strategy.calculate_max_bid(team, team.budget)
                        constrained_bid = min(max_bid, max_allowable_bid)
                        if constrained_bid < max_bid:
                            print(f"🚫 AUCTION CONSTRAINT: {team.team_name} bid ${max_bid} → ${constrained_bid} (max allowed: ${max_allowable_bid})")
                    elif owner_id in self.strategies:
                        strategy = self.strategies[owner_id]
                        if hasattr(strategy, 'calculate_max_bid'):
                            max_allowable_bid = strategy.calculate_max_bid(team, team.budget)
                            constrained_bid = min(max_bid, max_allowable_bid)
                            if constrained_bid < max_bid:
                                print(f"🚫 AUCTION CONSTRAINT: {team.team_name} bid ${max_bid} → ${constrained_bid} (max allowed: ${max_allowable_bid})")
                        else:
                            constrained_bid = max_bid
                    else:
                        constrained_bid = max_bid
                    
                    # Final check: bid must be positive and within budget
                    if constrained_bid > current_bid and constrained_bid <= team.budget:
                        valid_bids.append((owner_id, team, constrained_bid))
        
        # Determine winner and final price
        if not valid_bids:
            return  # No valid bids
        
        # Sort bids by amount (highest first)
        valid_bids.sort(key=lambda x: x[2], reverse=True)
        
        # Get winner and calculate final price
        winner_id, winner_team, highest_bid = valid_bids[0]
        
        if len(valid_bids) == 1:
            # Only one bidder - pay minimum increment
            final_price = current_bid + 1
        elif len(valid_bids) > 1 and valid_bids[0][2] == valid_bids[1][2]:
            # Tie for highest bid - winner pays their full bid (random selection handled by sort stability)
            final_price = highest_bid
        else:
            # Normal case - winner pays $1 more than second highest
            second_highest = valid_bids[1][2]
            final_price = second_highest + 1
        
        # Ensure final price doesn't exceed winner's budget or their max bid
        final_price = min(final_price, winner_team.budget, highest_bid)
        
        # Place the winning bid
        if final_price > current_bid:
            success = self.draft.place_bid(winner_id, final_price)
            if success:
                self._notify_bid_placed(winner_id, final_price)
                    
    def _notify_bid_placed(self, bidder_id: str, amount: float) -> None:
        """Notify listeners that a bid was placed."""
        for callback in self.on_bid_placed:
            try:
                callback(bidder_id, amount, self.draft.current_player)
            except Exception:
                pass  # Don't let callback errors break the auction
                
    def _notify_player_nominated(self, player: Player, nominator_id: str, initial_bid: float) -> None:
        """Notify listeners that a player was nominated."""
        for callback in self.on_player_nominated:
            try:
                callback(player, nominator_id, initial_bid)
            except Exception:
                pass
                
    def _notify_auction_completed(self) -> None:
        """Notify listeners that an auction was completed."""
        for callback in self.on_auction_completed:
            try:
                callback(self.draft.current_player, self.draft.current_high_bidder, self.draft.current_bid)
            except Exception:
                pass
                
    def _notify_timer_tick(self, phase: str, time_remaining: int) -> None:
        """Notify listeners of timer tick."""
        for callback in self.on_timer_tick:
            try:
                callback(phase, time_remaining)
            except Exception:
                pass
                
    def add_bid_listener(self, callback: Callable) -> None:
        """Add a callback for bid events."""
        self.on_bid_placed.append(callback)
        
    def add_nomination_listener(self, callback: Callable) -> None:
        """Add a callback for nomination events."""
        self.on_player_nominated.append(callback)
        
    def add_completion_listener(self, callback: Callable) -> None:
        """Add a callback for auction completion events."""
        self.on_auction_completed.append(callback)
        
    def add_timer_listener(self, callback: Callable) -> None:
        """Add a callback for timer tick events."""
        self.on_timer_tick.append(callback)
        
    def get_auction_state(self) -> Dict:
        """Get current auction state."""
        return {
            'is_active': self.is_active,
            'current_player': self.draft.current_player.to_dict() if self.draft.current_player else None,
            'current_bid': self.draft.current_bid,
            'current_high_bidder': self.draft.current_high_bidder,
            'time_remaining': self.draft.time_remaining,
            'current_nominator': self.draft.get_current_nominator().to_dict() if self.draft.get_current_nominator() else None,
            'auto_bid_enabled': dict(self.auto_bid_enabled)
        }
        
    def __str__(self) -> str:
        return f"Auction for {self.draft.name} ({'Active' if self.is_active else 'Inactive'})"
        
    def __repr__(self) -> str:
        return f"Auction(draft_id='{self.draft.draft_id}', is_active={self.is_active})"
