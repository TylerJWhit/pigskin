"""Basic draft strategy with configurable aggression factor."""

import random
from typing import List, TYPE_CHECKING
from .base_strategy import Strategy

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner


class BasicStrategy(Strategy):
    """Simple bidding strategy with configurable aggression factor."""
    
    def __init__(self, aggression: float = 1.0):
        """Initialize basic strategy.
        
        Args:
            aggression: Aggression factor (0.1-1.5)
        """
        super().__init__(
            "Basic",
            f"Basic strategy with aggression={aggression:.1f}"
        )
        
        self.aggression = aggression
    
    def calculate_bid(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        current_bid: float,
        remaining_budget: float,
        remaining_players: List['Player']
    ) -> int:
        """Calculate bid amount for a player.
        
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
        # Check if we need to force completion of roster
        if self.should_force_nominate_for_completion(player, team, remaining_budget):
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
        
        # Get player value
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10))
        
        # Calculate position urgency based on roster needs
        position_urgency = self._calculate_position_urgency(player, team)
        
        # Apply strategy's aggression factor
        base_bid = player_value * self.aggression * position_priority * position_urgency
        
        # Calculate maximum safe bid
        max_bid = self.calculate_max_bid(team, remaining_budget)
        
        # Don't bid more than max bid
        final_bid = min(base_bid, max_bid)
        
        # Ensure bid is at least current bid + 1
        final_bid = max(current_bid + 1, final_bid)
        
        # Use get_bid_for_player which handles DST/K special cases and ensures integer result
        safe_bid_amount = self.get_bid_for_player(player, final_bid, team, remaining_budget)
        return safe_bid_amount if safe_bid_amount > current_bid else 0
    
    def should_nominate(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        remaining_budget: float
    ) -> bool:
        """Nominate a player based on basic strategy.
        
        Args:
            player: Player to potentially nominate
            team: Team considering nomination
            owner: Owner considering nomination
            remaining_budget: Remaining budget
            
        Returns:
            True if player should be nominated
        """
        # Force nominate if we need to complete roster
        if self.should_force_nominate_for_completion(player, team, remaining_budget):
            return True
        
        # Calculate position priority
        position_priority = self._calculate_position_priority(player, team)
        
        # Nominate high-priority players for needed positions
        if position_priority > 0.7:
            return True
        
        # Nominate valuable players we can afford
        player_value = getattr(player, 'auction_value', 10)
        if player_value > 20 and player_value < remaining_budget * 0.3:
            return True
        
        # Sometimes nominate to drive up prices
        if random.random() < 0.2:  # 20% chance
            return True
        
        return False
    
    def _calculate_position_urgency(self, player: 'Player', team: 'Team') -> float:
        """Calculate urgency multiplier based on position needs."""
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
            return 0.5  # Low urgency if position is filled
        
        # Higher urgency if we're close to completing this position
        remaining_needed = target_count - current_count
        if remaining_needed == 1:
            return 2.0  # Very urgent - last player needed
        elif remaining_needed == 2:
            return 1.5  # Somewhat urgent
        else:
            return 1.0  # Normal urgency
    
    def _get_remaining_roster_slots(self, team: 'Team') -> int:
        """Calculate how many roster slots still need to be filled."""
        # Use base class implementation
        return super()._get_remaining_roster_slots(team)
