"""Balanced draft strategy that adjusts bids based on position scarcity and VOR variance."""

import random
from typing import List, TYPE_CHECKING
from .base_strategy import Strategy

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner


class BalancedStrategy(Strategy):
    """Balanced bidding strategy with VOR variance adjustment and position scarcity awareness."""
    
    def __init__(self, aggression: float = 1.25, vor_variance: float = 1.1):
        """Initialize balanced strategy.
        
        Args:
            aggression: Aggression factor (0.1-1.5) - increased from 1.0 to 1.25
            vor_variance: VOR variance factor (0.1-1.5) - increased from 0.9 to 1.1
        """
        super().__init__(
            "Balanced",
            f"Balanced strategy with aggression={aggression:.1f}, vor_variance={vor_variance:.1f}"
        )
        
        self.aggression = aggression
        self.vor_variance = vor_variance
        
        # Position scarcity factors (increased all values to be more aggressive)
        self.scarcity_factors = {
            'QB': 0.5,  # QB tends to be deep (was 0.3)
            'RB': 1.0,  # RB tends to be scarce (was 0.8)
            'WR': 0.8,  # WR somewhere in the middle (was 0.6)
            'TE': 0.9,  # TE has few elite options (was 0.7)
            'K': 0.3,   # K has little variance (was 0.1)
            'DST': 0.4  # DST has little variance (was 0.2)
        }
    
    def calculate_bid(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        current_bid: float,
        remaining_budget: float,
        remaining_players: List['Player']
    ) -> int:
        """Calculate bid with VOR variance adjustment.
        
        Args:
            player: Player to bid on
            team: Team making the bid
            owner: Owner making the bid
            current_bid: Current highest bid
            remaining_budget: Remaining budget
            remaining_players: List of remaining players
            
        Returns:
            Recommended bid amount as integer
        """
        # Get minimum needed budget to complete roster
        remaining_roster_slots = self._get_remaining_roster_slots(team)
        min_needed = remaining_roster_slots
        
        # If team has just enough budget to complete roster, bid conservatively
        if remaining_budget <= min_needed + 5:
            calculated_bid = max(current_bid + 1, 1.0)
            return self.get_bid_for_player(player, calculated_bid, team, remaining_budget)
        
        # Get position priority
        position_priority = self._calculate_position_priority(player, team)
        
        # If position priority is very low, don't bid much
        if position_priority <= 0.1:
            if current_bid < 5:
                calculated_bid = max(current_bid + 1, 1.0)
                return self.get_bid_for_player(player, calculated_bid, team, remaining_budget)
            else:
                return 0
        
        # Calculate position scarcity
        position_scarcity = self._calculate_position_scarcity(player)
        
        # Get player value (use auction_value as baseline VOR)
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10))
        if player_value <= 0:
            player_value = 10
        
        # Estimate VOR from player value
        baseline_value = 5  # Minimum replacement level value
        vor = max(0, player_value - baseline_value)
        
        # Apply VOR variance to adjust the bid based on position scarcity
        vor_adjusted = vor * (1.0 + (position_scarcity * self.vor_variance))
        
        # Apply aggression factor and position priority
        base_bid = vor_adjusted * self.aggression * position_priority
        
        # Calculate maximum possible bid using the budget constraint system
        max_bid = self.calculate_max_bid(team, remaining_budget)
        
        # Don't bid more than a percentage of remaining budget (apply max % constraint)
        max_percentage_bid = remaining_budget * 0.6  # Max 60% of remaining budget
        max_bid = min(max_bid, max_percentage_bid)
        
        # Ensure bid is at least current bid + 1
        final_bid = max(current_bid + 1, min(base_bid, max_bid))
        
        # Use get_bid_for_player which handles DST/K special cases and ensures integer result
        final_bid_amount = self.get_bid_for_player(player, final_bid, team, remaining_budget)
        
        # Return 0 if we can't afford or don't want to bid higher
        return final_bid_amount if final_bid_amount > current_bid else 0
    
    def should_nominate(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        remaining_budget: float
    ) -> bool:
        """Determine if this player should be nominated.
        
        Args:
            player: Player to potentially nominate
            team: Team considering nomination
            owner: Owner considering nomination
            remaining_budget: Remaining budget
            
        Returns:
            True if player should be nominated
        """
        # Check budget constraints first - avoid nominating if we can't complete roster
        remaining_slots = self._get_remaining_roster_slots(team)
        budget_per_slot = remaining_budget / max(1, remaining_slots)
        
        # If we're running low on budget per slot, only nominate cheap players we need
        if budget_per_slot < 2.0:  # Less than $2 per remaining slot
            player_value = getattr(player, 'auction_value', 10)
            # Only nominate if it's cheap (value < $5) and we need the position
            if player_value > 5.0:
                return False
        
        # Calculate position priority and scarcity
        position_priority = self._calculate_position_priority(player, team)
        position_scarcity = self._calculate_position_scarcity(player)
        
        # Nominate high-priority players for needed positions
        if position_priority > 0.7:
            return True
        
        # Nominate scarce position players (but only if we have budget)
        if position_scarcity > 0.6 and position_priority > 0.3 and budget_per_slot >= 3.0:
            return True
        
        # Nominate valuable players we can afford (only if we have good budget)
        if budget_per_slot >= 5.0:  # Only if we have $5+ per slot
            player_value = getattr(player, 'auction_value', 10)
            if player_value > 20 and player_value < remaining_budget * 0.3:
                return True
        
        # Sometimes nominate to drive up prices for others (only if budget allows)
        if budget_per_slot >= 4.0 and random.random() < 0.15:  # 15% chance
            return True
        
        return False
    
    def _calculate_position_scarcity(self, player: 'Player') -> float:
        """Calculate position scarcity factor (0.0 to 1.0).
        
        Args:
            player: Player to calculate scarcity for
            
        Returns:
            Scarcity factor (higher values mean more scarce)
        """
        # Return scarcity factor for the player's position
        position = getattr(player, 'position', '')
        return self.scarcity_factors.get(position, 0.5)  # Default to 0.5 for unknown positions
    
    def _calculate_position_priority(self, player: 'Player', team: 'Team') -> float:
        """Calculate how much this position is needed (0.0 to 1.0)."""
        position = player.position
        
        # Get current roster composition
        current_roster = getattr(team, 'roster', [])
        position_counts = {}
        for p in current_roster:
            pos = getattr(p, 'position', 'UNKNOWN')
            position_counts[pos] = position_counts.get(pos, 0) + 1
        
        # Position requirements
        position_targets = {
            'QB': 2,
            'RB': 4,
            'WR': 4,
            'TE': 2,
            'K': 1,
            'DST': 1
        }
        
        current_count = position_counts.get(position, 0)
        target_count = position_targets.get(position, 2)
        
        if current_count >= target_count:
            return 0.2  # Low priority if position is full
        
        # Higher priority if we have fewer of this position
        need_ratio = (target_count - current_count) / target_count
        return min(1.0, need_ratio + 0.2)
    
    def _get_remaining_roster_slots(self, team: 'Team') -> int:
        """Calculate how many roster slots still need to be filled."""
        # Assume 15 total roster slots based on config
        total_slots = 15
        current_roster_size = len(getattr(team, 'roster', []))
        return max(0, total_slots - current_roster_size)
