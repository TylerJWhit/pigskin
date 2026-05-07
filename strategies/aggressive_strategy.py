"""Aggressive strategy for auction drafts."""

from typing import List, TYPE_CHECKING
from .base_strategy import Strategy

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner


class AggressiveStrategy(Strategy):
    """Aggressive strategy that bids high on top players."""
    
    def __init__(self):
        super().__init__(
            "Aggressive",
            "Goes all-in on elite players early in the draft"
        )
        self.parameters = {
            'elite_threshold': 25,  # Players worth $25+ are considered elite
            'elite_multiplier': 1.3,  # Bid up to 130% of value for elite players
            'budget_threshold': 0.7  # Stop being aggressive when budget drops below 70%
        }
        
    def calculate_bid(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        current_bid: float,
        remaining_budget: float,
        remaining_players: List['Player']
    ) -> float:
        """Calculate aggressive bid."""
        # Check position priority for mandatory positions
        position_priority = self._calculate_position_priority(player, team)

        max_possible_bid = self.calculate_max_bid(team, remaining_budget)

        # Special handling for mandatory positions (K, DST) with high priority.
        # _calculate_position_priority caps at 1.0, so the gate is > 0.5 when
        # the position is still needed (not yet filled). (#143)
        if player.position in ['K', 'DST'] and position_priority > 0.5:
            min_mandatory_bid = min(15.0, remaining_budget * 0.15)
            return min(current_bid + min_mandatory_bid, max_possible_bid)

        # Guard against ZeroDivisionError when initial_budget is 0. (#145)
        initial_budget = getattr(team, 'initial_budget', None) or remaining_budget or 1
        budget_ratio = remaining_budget / initial_budget
        
        # If budget is low, be conservative
        if budget_ratio < self.parameters['budget_threshold']:
            max_bid = player.auction_value * 0.8
        else:
            # Be aggressive on elite players
            if player.auction_value >= self.parameters['elite_threshold']:
                max_bid = player.auction_value * self.parameters['elite_multiplier']
            else:
                max_bid = player.auction_value * 0.9
                
        max_bid = min(max_bid, remaining_budget)
        
        if current_bid >= max_bid:
            return 0.0
            
        our_bid = min(current_bid + 2, max_bid)  # More aggressive bidding increments
        
        # Enforce budget constraint before returning
        our_bid = self._enforce_budget_constraint(our_bid, team, remaining_budget)
        
        return int(our_bid)
        
    def should_nominate(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        remaining_budget: float
    ) -> bool:
        """Nominate elite players we want."""
        if player.auction_value >= self.parameters['elite_threshold']:
            return True
        if owner is None:
            return False
        return owner.is_target_player(player.player_id)
