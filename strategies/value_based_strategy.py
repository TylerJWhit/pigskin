"""Value-based strategy for auction drafts."""

import random
from typing import List, TYPE_CHECKING
from .base_strategy import Strategy

if TYPE_CHECKING:
    from ..classes.player import Player
    from ..classes.team import Team
    from ..classes.owner import Owner


class ValueBasedStrategy(Strategy):
    """Strategy that bids based on player value relative to auction price."""
    
    def __init__(self):
        super().__init__(
            "Value-Based",
            "Bids based on player value compared to auction value"
        )
        self.parameters = {
            'value_multiplier': 1.4,  # Bid up to 140% of perceived value (was 85%)
            'max_overbid': 1.3,  # Maximum 30% overbid (was 10%)
            'position_premiums': {  # Extra value for certain positions
                'QB': 1.1,
                'RB': 1.3,  # Increased from 1.2
                'WR': 1.2,  # Increased from 1.1
                'TE': 1.1,  # Increased from 1.0
                'K': 1.0,   # Increased from 0.8
                'DST': 1.0  # Increased from 0.8
            }
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
        """Calculate bid based on player value with roster completion logic."""
        # Get minimum needed budget to complete roster
        budget_reservation = self._calculate_budget_reservation(team, remaining_budget)
        usable_budget = max(0, remaining_budget - budget_reservation)
        
        # Force bid on cheap players if roster is incomplete
        if self._should_force_bid(team, remaining_budget, current_bid):
            forced_bid = max(current_bid + 1, 1.0)
            return self._enforce_budget_constraint(forced_bid, team, remaining_budget)
        
        # Get position priority
        position_priority = self._calculate_position_priority(player, team)
        
        # If position priority is very low, don't bid much
        if position_priority <= 0.1:
            low_priority_bid = max(current_bid + 1, 1.0) if current_bid < 5 else 0.0
            return self._enforce_budget_constraint(low_priority_bid, team, remaining_budget)
        
        # Get player value with fallback
        player_value = self._get_player_value(player, 10.0)
        
        # Get position premium
        position_premium = self.parameters['position_premiums'].get(player.position, 1.0)
        adjusted_value = player_value * position_premium * position_priority
        
        # Apply value multiplier
        max_value_bid = adjusted_value * self.parameters['value_multiplier']
        
        # Calculate safe bid limit (more aggressive - use 40% of budget instead of 25%)
        safe_bid_limit = self._calculate_safe_bid_limit(team, remaining_budget, 0.4)
        
        # Don't bid more than safe limit or usable budget
        max_bid = min(max_value_bid, safe_bid_limit, usable_budget)
        
        # Don't bid if current bid is already too high
        if current_bid >= max_bid:
            return 0.0
            
        # Calculate our bid (slightly above current bid)
        our_bid = max(current_bid + 1, min(current_bid + 2, max_bid))
        
        # Apply owner risk tolerance if available (with fallback for mock drafts)
        try:
            risk_factor = owner.get_risk_tolerance() if owner else 0.7
            our_bid *= (0.9 + 0.2 * risk_factor)  # Scale between 90% and 110%
        except (AttributeError, TypeError):
            pass  # Owner might not have risk tolerance method
        
        # Enforce budget constraint before returning
        our_bid = self._enforce_budget_constraint(our_bid, team, remaining_budget)
        
        return int(max(our_bid, 1))
        
    def should_nominate(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        remaining_budget: float
    ) -> bool:
        """Nominate players we value highly or want to force others to bid on."""
        # Check budget constraints first - avoid nominating if we can't complete roster
        remaining_slots = self._get_remaining_roster_slots(team)
        budget_per_slot = remaining_budget / max(1, remaining_slots)
        
        # If we're running low on budget per slot, only nominate cheap players we need
        if budget_per_slot < 2.0:  # Less than $2 per remaining slot
            player_value = self._get_player_value(player, 10.0)
            # Only nominate if it's cheap (value < $5) and we need the position
            if player_value > 5.0:
                return False
        
        # Calculate position priority
        position_priority = self._calculate_position_priority(player, team)
        
        # Nominate high-priority players for needed positions
        if position_priority > 0.7:
            return True
        
        # Check if we need this position
        try:
            needs = team.get_needs()
            if player.position in needs:
                return True
        except (AttributeError, TypeError):
            pass  # Team might not have get_needs method
            
        # Check if it's a target player (but only if we have budget)
        try:
            if owner.is_target_player(player.player_id) and budget_per_slot >= 3.0:
                return True
        except (AttributeError, TypeError):
            pass  # Owner might not have is_target_player method
            
        # Only nominate high-value players to force others to spend if we have good budget
        if budget_per_slot >= 5.0:  # Only if we have $5+ per slot
            player_value = self._get_player_value(player, 10.0)
            if player_value > 20:
                return random.random() < 0.3  # 30% chance
            
        return False
