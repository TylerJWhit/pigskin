"""Improved Value-based draft strategy."""

from typing import List, Optional, TYPE_CHECKING
import random

from .base_strategy import Strategy

if TYPE_CHECKING:
    from ..classes.player import Player
    from ..classes.team import Team
    from ..classes.owner import Owner


class ImprovedValueStrategy(Strategy):
    """Strategy that bids based on player value with scarcity adjustment."""
    
    def __init__(self, aggression: float = 1.0, scarcity_weight: float = 0.3, randomness: float = 0.0):
        """Initialize improved value strategy.
        
        Args:
            aggression: Aggression factor (1.0 = neutral)
            scarcity_weight: Weight for position scarcity (0.0-1.0)
            randomness: Randomness factor (0.0-1.0)
        """
        super().__init__("improved_value", "Advanced value-based bidding with scarcity adjustment")
        
        self.aggression = aggression
        self.scarcity_weight = scarcity_weight
        self.randomness = randomness
        
        # Position scarcity factors
        self.scarcity_factors = {
            'QB': 0.3,  # QB tends to be deep
            'RB': 0.8,  # RB tends to be scarce
            'WR': 0.6,  # WR somewhere in the middle
            'TE': 0.7,  # TE has few elite options
            'K': 0.1,   # K has little variance
            'DST': 0.2  # DST has little variance
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
        """Calculate bid based on player value with scarcity adjustment.
        
        Args:
            player: Player to bid on
            team: Team making the bid
            owner: Owner making the bid
            current_bid: Current highest bid
            remaining_budget: Remaining budget
            remaining_players: List of remaining players
            
        Returns:
            Recommended bid amount
        """
        # Get minimum needed budget to complete roster
        remaining_roster_slots = self._get_remaining_roster_slots(team)
        min_needed = remaining_roster_slots  # At least $1 per remaining slot
        
        # If team has just enough budget to complete roster, bid conservatively
        if remaining_budget <= min_needed + 5:
            return max(current_bid + 1, 1.0)
        
        # Get position priority factor
        position_priority = self._calculate_position_priority(player, team)
        
        # If position priority is very low, don't bid much
        if position_priority <= 0.1:
            return max(current_bid + 1, 1.0) if current_bid < 5 else 0.0
        
        # Get position urgency
        position_urgency = self._calculate_position_urgency(player, team)
        
        # Use player's auction value as base
        base_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10))
        if base_value <= 0:
            base_value = 10  # Default value
        
        # Calculate position scarcity factor
        scarcity_factor = self.scarcity_factors.get(player.position, 0.5)
        scarcity_adjustment = 1.0 + (scarcity_factor * self.scarcity_weight)
        
        # Calculate base bid with value, scarcity, and aggression
        base_bid = base_value * scarcity_adjustment * self.aggression * position_urgency * position_priority
        
        # Apply randomness if specified
        if self.randomness > 0:
            random_factor = 1.0 + random.uniform(-self.randomness, self.randomness)
            base_bid *= random_factor
        
        # Don't bid more than a percentage of remaining budget
        max_percentage_bid = remaining_budget * 0.4  # Max 40% of remaining budget
        
        # Calculate maximum possible bid (leave enough for minimum roster)
        max_bid = max(1.0, min(remaining_budget - min_needed, max_percentage_bid))
        
        # Ensure bid is at least current bid + 1
        final_bid = max(current_bid + 1, min(base_bid, max_bid))
        
        # Return 0 if we can't afford or don't want to bid higher
        return final_bid if final_bid > current_bid else 0.0
    
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
        # Calculate position priority
        position_priority = self._calculate_position_priority(player, team)
        
        # Nominate high-priority players
        if position_priority > 0.7:
            return True
        
        # Nominate valuable players we can afford
        player_value = getattr(player, 'auction_value', 10)
        if player_value > 20 and player_value < remaining_budget * 0.3:
            return True
        
        # Sometimes nominate players to drive up prices for others
        if random.random() < 0.2:  # 20% chance to nominate for strategic reasons
            return True
        
        return False
    
    def _get_remaining_roster_slots(self, team: 'Team') -> int:
        """Calculate how many roster slots still need to be filled."""
        # Assume 15 total roster slots based on config
        total_slots = 15
        current_roster_size = len(getattr(team, 'roster', []))
        return max(0, total_slots - current_roster_size)
    
    def _calculate_position_priority(self, player: 'Player', team: 'Team') -> float:
        """Calculate how much this position is needed (0.0 to 1.0)."""
        position = player.position
        
        # Get current roster composition
        current_roster = getattr(team, 'roster', [])
        position_counts = {}
        for p in current_roster:
            pos = getattr(p, 'position', 'UNKNOWN')
            position_counts[pos] = position_counts.get(pos, 0) + 1
        
        # Position requirements (simplified)
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
    
    def _calculate_position_urgency(self, player: 'Player', team: 'Team') -> float:
        """Calculate urgency based on how full the team is."""
        current_roster = getattr(team, 'roster', [])
        roster_fullness = len(current_roster) / 15.0  # Assume 15 total slots
        
        # More urgent as roster fills up
        if roster_fullness > 0.8:
            return 2.0  # Very urgent
        elif roster_fullness > 0.6:
            return 1.5  # Somewhat urgent
        else:
            return 1.0  # Normal urgency