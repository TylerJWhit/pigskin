"""Auction class for auction draft tool."""

import logging
from typing import Dict, List, Optional, Callable, Tuple
import threading
from .draft import Draft
from .player import Player
from .team import Team
from .strategy import Strategy


logger = logging.getLogger(__name__)


class Auction:
    """Handles the real-time auction mechanics for a draft."""
    
    def __init__(
        self,
        draft: Draft,
        players: Optional[List] = None,
        strategies: Optional[Dict] = None,
        bid_timer: int = 30,
        nomination_timer: int = 60,
        timer_duration: Optional[int] = None,
    ):
        self.draft = draft
        self.bid_timer = timer_duration if timer_duration is not None else bid_timer
        self.nomination_timer = nomination_timer

        # Thread safety lock for all shared-state mutations
        self._lock = threading.RLock()

        # Auction state
        self.is_active = False
        self.current_timer: Optional[threading.Timer] = None
        self.auto_bid_enabled = {}  # owner_id -> bool
        self.strategies = {}  # owner_id -> Strategy

        # Populate strategies from the optional dict (CR-01 backward compat)
        if strategies:
            for owner_id, strategy in strategies.items():
                self.strategies[owner_id] = strategy
                self.auto_bid_enabled[owner_id] = True

        # Events and callbacks
        self.on_bid_placed: List[Callable] = []
        self.on_player_nominated: List[Callable] = []
        self.on_auction_completed: List[Callable] = []
        self.on_timer_tick: List[Callable] = []

    @property
    def current_player(self):
        """Current player being auctioned (delegates to draft)."""
        return self.draft.current_player

    @property
    def current_bid(self):
        """Current highest bid (delegates to draft)."""
        return self.draft.current_bid
        
    def start_auction(self) -> None:
        """Start the auction system and run the complete draft synchronously."""
        if self.draft.status != "started":
            raise ValueError("Draft must be started before auction can begin")

        self.is_active = True
        try:
            self.draft.run_complete_draft()
        finally:
            self.is_active = False
        
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
        """Nominate a player for auction.

        In mock/timer-disabled mode (bid_timer == 0), all strategy bids are
        collected immediately and the auction resolves synchronously — no
        background timer is started.
        """
        # Validate: if player is a bare string ID, look it up; raise if not found
        if isinstance(player, str):
            found = next(
                (p for p in self.draft.available_players if p.player_id == player or p.name == player),
                None
            )
            if found is None:
                raise ValueError(f"Player '{player}' not found in available players")
            player = found
        with self._lock:
            try:
                self.draft.nominate_player(player, nominating_owner_id, initial_bid)
                self.is_active = True
                self._notify_player_nominated(player, nominating_owner_id, initial_bid)
                # Only start background timer if bid_timer > 0; otherwise bids
                # are placed manually and resolved via end_current_auction().
                if self.bid_timer > 0:
                    self._start_bid_timer()
                return True
            except ValueError:
                return False

    def _resolve_mock_auction(self, player: 'Player') -> None:
        """Collect all strategy bids immediately and award player to highest bidder."""
        bids = self._collect_sealed_bids(player)
        winner_id, price = self._determine_auction_winner(bids)
        if player in self.draft.available_players:
            self.draft.available_players.remove(player)
        self.draft.drafted_players.append(player)
        if winner_id:
            self._award_player_to_team(player, winner_id, price)
            player.is_drafted = True
        # Reset draft nomination state
        self.draft.current_player = None
        self.draft.current_bid = 0.0
        self.draft.current_high_bidder = None
        self.is_active = False
            
    def place_bid(self, bidder_id: str, bid_amount: float) -> bool:
        """Place a bid on the current player."""
        if bid_amount < 0:
            raise ValueError(f"Bid amount must be non-negative, got {bid_amount}")
        with self._lock:
            if not self.is_active:
                return False

            # CR-06: Prevent the current high bidder from bidding against themselves
            if self.draft.current_high_bidder == bidder_id:
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

    def end_current_auction(self) -> None:
        """End bidding on the current player and award to highest bidder."""
        if self.current_timer:
            self.current_timer.cancel()
            self.current_timer = None
        if self.draft.current_player:
            self.draft.complete_auction()
        self.is_active = False
            
    def _start_nomination_timer(self) -> None:
        """Start timer for player nomination."""
        if self.current_timer:
            self.current_timer.cancel()
            self.current_timer = None

        self.draft.time_remaining = self.nomination_timer
        if self.nomination_timer <= 0:
            return  # Timers disabled (e.g. in tests)
        t = threading.Timer(1.0, self._nomination_timer_tick)
        t.daemon = True
        self.current_timer = t
        t.start()

    def _start_bid_timer(self) -> None:
        """Start timer for bidding phase."""
        if self.current_timer:
            self.current_timer.cancel()
            self.current_timer = None

        self.draft.time_remaining = self.bid_timer
        if self.bid_timer <= 0:
            return  # Timers disabled (e.g. in tests)
        t = threading.Timer(1.0, self._bid_timer_tick)
        t.daemon = True
        self.current_timer = t
        t.start()
        
    def _nomination_timer_tick(self) -> None:
        """Handle nomination timer tick."""
        if not self.is_active:
            return

        with self._lock:
            self.draft.time_remaining -= 1
            time_left = self.draft.time_remaining

        self._notify_timer_tick("nomination", time_left)

        if time_left <= 0:
            self._auto_nominate_player()
        else:
            t = threading.Timer(1.0, self._nomination_timer_tick)
            t.daemon = True
            self.current_timer = t
            t.start()

    def _bid_timer_tick(self) -> None:
        """Handle bid timer tick."""
        if not self.is_active:
            return

        with self._lock:
            self.draft.time_remaining -= 1
            time_left = self.draft.time_remaining

        self._notify_timer_tick("bidding", time_left)

        if time_left <= 0:
            with self._lock:
                if self.draft.current_player:  # Guard against double-fire
                    self._complete_current_auction()
        else:
            t = threading.Timer(1.0, self._bid_timer_tick)
            t.daemon = True
            self.current_timer = t
            t.start()
            
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
    
    def _complete_current_auction(self) -> None:
        """Complete the current player auction."""
        if self.draft.current_player:
            player = self.draft.current_player
            self.draft.complete_auction()
            self._notify_auction_completed(player, None, 0.0)

            if self.draft.status == "completed":
                self.stop_auction()
            else:
                self._start_nomination_timer()

    def _get_team_nomination(self, team: 'Team') -> Optional['Player']:
        """Get a player nomination from the given team."""
        available = [p for p in self.draft.available_players if not getattr(p, 'is_drafted', False)]
        if not available:
            return None
        # Try team's strategy first
        if getattr(team, 'strategy', None):
            owner = self.draft._get_owner_by_id(team.owner_id)
            for player in available:
                try:
                    if team.strategy.should_nominate(
                        player, team, owner, getattr(team, 'budget', 200)
                    ):
                        return player
                except Exception:
                    pass
        # Fall back to highest-value available player
        import random
        return random.choice(available)

    def _collect_sealed_bids(self, player: 'Player') -> Dict[str, float]:
        """Collect sealed bids from all eligible teams for a player."""
        bids = {}
        for team in self.draft.teams:
            try:
                can_bid = team.can_bid(player, 1.0) if hasattr(team, 'can_bid') else True
                if not can_bid:
                    continue
                owner = self.draft._get_owner_by_id(team.owner_id)
                owner_data = owner.to_dict() if owner and hasattr(owner, 'to_dict') else None
                remaining = [p for p in self.draft.available_players if not getattr(p, 'is_drafted', False)]
                # Prefer a direct calculate_bid on the team object (supports Mocks in tests)
                if hasattr(team, 'calculate_bid') and callable(getattr(team, 'calculate_bid')):
                    bid = team.calculate_bid(
                        player=player,
                        current_bid=self.draft.current_bid,
                        remaining_players=remaining,
                        owner_data=owner_data
                    )
                else:
                    bid = 0.0
                bid_float = float(bid)
                if bid_float > 0:
                    bids[team.team_id] = bid_float
            except Exception:
                pass
        return bids

    def _determine_auction_winner(self, bids: Dict[str, float]) -> Tuple[Optional[str], float]:
        """Determine auction winner using Vickrey (second-price) logic."""
        import random
        if not bids:
            return None, 0.0
        sorted_bids = sorted(bids.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_bids) == 1:
            return sorted_bids[0][0], sorted_bids[0][1]
        top_bid = sorted_bids[0][1]
        second_bid = sorted_bids[1][1]
        tied_winners = [tid for tid, bid in sorted_bids if bid == top_bid]
        winner_id = random.choice(tied_winners)
        if len(tied_winners) > 1:
            # Tie at the top: winner pays top_bid + 1 (can't use second-price)
            return winner_id, top_bid + 1.0
        return winner_id, second_bid + 1.0

    def _award_player_to_team(
        self, player: 'Player', winner_id: str, price: float
    ) -> None:
        """Award a player to the winning team (lookup by owner_id or team_id)."""
        # Try owner_id lookup first, then team_id as fallback
        winner_team = self.draft._get_team_by_owner(winner_id)
        if winner_team is None and hasattr(self.draft, '_get_team_by_id'):
            winner_team = self.draft._get_team_by_id(winner_id)
        if winner_team:
            winner_team.add_player(player, price)
            player.mark_as_drafted(price, winner_id)
        self._notify_auction_completed(player, winner_team, price)

    def _sort_players_by_value(self, players: List['Player']) -> List['Player']:
        """Return players sorted by value (VOR descending, then auction_value descending)."""
        def _value_key(p: 'Player') -> float:
            if hasattr(p, 'vor') and p.vor is not None:
                return float(p.vor)
            return float(getattr(p, 'auction_value', 0))

        return sorted(players, key=_value_key, reverse=True)

    def _notify_auction_completed(self, player: 'Player', team: Optional['Team'], price: float) -> None:
        """Fire all on_auction_completed callbacks with (player, team, price)."""
        for callback in self.on_auction_completed:
            try:
                callback(player, team, price)
            except Exception:
                pass

    def get_auction_state(self) -> Dict:
        """Return the current auction state."""
        return {
            'is_active': self.is_active,
            'draft_status': getattr(self.draft, 'status', 'unknown'),
            'current_player': getattr(self.draft, 'current_player', None),
            'current_bid': getattr(self.draft, 'current_bid', 0.0),
            'current_high_bidder': getattr(self.draft, 'current_high_bidder', None),
            'current_nominator': getattr(self.draft, 'current_nominator', None),
            'auto_bid_enabled': self.auto_bid_enabled,
        }

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
                            logger.warning("AUCTION CONSTRAINT: %s bid $%s -> $%s (max allowed: $%s)", team.team_name, max_bid, constrained_bid, max_allowable_bid)
                    elif owner_id in self.strategies:
                        strategy = self.strategies[owner_id]
                        if hasattr(strategy, 'calculate_max_bid'):
                            max_allowable_bid = strategy.calculate_max_bid(team, team.budget)
                            constrained_bid = min(max_bid, max_allowable_bid)
                            if constrained_bid < max_bid:
                                logger.warning("AUCTION CONSTRAINT: %s bid $%s -> $%s (max allowed: $%s)", team.team_name, max_bid, constrained_bid, max_allowable_bid)
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

    def __str__(self) -> str:
        return f"Auction for {self.draft.name} ({'Active' if self.is_active else 'Inactive'})"
        
    def __repr__(self) -> str:
        return f"Auction(draft_id='{self.draft.draft_id}', is_active={self.is_active})"
