"""VOR-based draft strategy focused on value over replacement."""

from typing import List, Optional, TYPE_CHECKING

from .base_strategy import Strategy

if TYPE_CHECKING:
    from ..classes.player import Player
    from ..classes.team import Team
    from ..classes.owner import Owner


class VorStrategy(Strategy):
    """VOR-focused bidding strategy with configurable parameters."""
    
    def __init__(self, aggression: float = 1.0, scarcity_weight: float = 0.7):
        """Initialize VOR strategy.
        
        Args:
            aggression: Aggression factor (0.1-1.5)
            scarcity_weight: Weight given to position scarcity (0.0-1.0)
        """
        super().__init__("vor", "Value Over Replacement focused strategy")
        
        self.aggression = aggression
        self.scarcity_weight = scarcity_weight
        
        # Position scarcity factors
        self.scarcity_factors = {
            'QB': 0.4,  # QB tends to be deep
            'RB': 0.9,  # RB tends to be scarce
            'WR': 0.7,  # WR somewhere in the middle
            'TE': 0.8,  # TE has few elite options
            'K': 0.2,   # K has little variance
            'DST': 0.3  # DST has little variance
        }
        
        # Position baselines for VOR calculation (estimated replacement level)
        self.position_baselines = {
            'QB': 250,   # Replacement QB fantasy points
            'RB': 150,   # Replacement RB fantasy points
            'WR': 140,   # Replacement WR fantasy points
            'TE': 100,   # Replacement TE fantasy points
            'K': 80,     # Replacement K fantasy points
            'DST': 70    # Replacement DST fantasy points
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
        """Calculate bid based on VOR with scarcity adjustment.
        
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
        min_needed = max(0, remaining_roster_slots - 1)  # Reserve $1 per remaining slot minus current
        
        # If team has very little budget left, bid to complete roster
        if remaining_budget <= min_needed + 3:
            return min(current_bid + 1, remaining_budget - min_needed) if remaining_budget > min_needed else 0.0
        
        # Get position priority
        position_priority = self._calculate_position_priority(player, team)
        
        # If position priority is very low, still bid to fill roster if needed
        if position_priority <= 0.1:
            # Check if we're missing critical positions and need any player
            remaining_slots = self._get_remaining_roster_slots(team)
            if remaining_slots > 5:  # Need players to fill roster
                return min(current_bid + 1, 3.0)
            return 0.0
        
        # Calculate VOR (Value Over Replacement)
        vor = self._calculate_vor(player)
        
        if vor <= 0:
            # For required positions we're missing, still bid aggressively
            if position_priority >= 1.0:  # Missing required position
                return min(current_bid + 1, min(10.0, remaining_budget * 0.1))  # Bid up to $10 or 10% of budget
            
            # Player doesn't provide value but might be needed for roster
            if remaining_roster_slots > 3:
                return min(current_bid + 1, 2.0)  # Bid up to $2 for roster needs
            return 0.0
        
        # Calculate position scarcity adjustment
        scarcity_factor = self.scarcity_factors.get(player.position, 0.5)
        scarcity_adjustment = 1.0 + (scarcity_factor * self.scarcity_weight)
        
        # Calculate base bid from VOR with more aggressive scaling
        vor_scaling_factor = 0.25  # Increased from 0.15 to 0.25 per VOR point
        base_bid = vor * vor_scaling_factor * scarcity_adjustment
        
        # Apply aggression factor with boost
        base_bid *= (self.aggression * 1.3)  # 30% more aggressive
        
        # Apply position priority (how much we need this position)
        base_bid *= position_priority
        
        # CRITICAL: If position priority is 0, don't bid at all
        if position_priority == 0.0:
            return 0.0
        
        # Add per-player spending cap to prevent overpaying
        player_spending_cap = min(50.0, remaining_budget * 0.30)  # Never spend more than $50 or 30% of budget on one player
        base_bid = min(base_bid, player_spending_cap)
        
        # Calculate scarcity in remaining players
        remaining_scarcity = self._calculate_remaining_scarcity(player, remaining_players)
        base_bid *= remaining_scarcity
        
        # More flexible budget management - allow higher percentage early in draft
        budget_ratio = min(remaining_budget, 200) / 200  # Normalize to initial budget
        max_percentage = 0.20 + (0.30 * budget_ratio)  # 20% to 50% based on remaining budget
        max_percentage_bid = remaining_budget * max_percentage
        
        # Calculate maximum possible bid
        available_budget = remaining_budget - min_needed
        max_bid = max(1.0, min(available_budget, max_percentage_bid))
        
        # Ensure bid is at least current bid + 1
        final_bid = max(current_bid + 1, min(base_bid, max_bid))
        
        # Enforce budget constraint before returning
        final_bid = self._enforce_budget_constraint(final_bid, team, remaining_budget)
        
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
        # Calculate VOR and position priority
        vor = self._calculate_vor(player)
        position_priority = self._calculate_position_priority(player, team)
        
        # Nominate high-VOR players we need
        if vor > 50 and position_priority > 0.6:
            return True
        
        # Nominate valuable players we can afford
        if vor > 30 and vor * 0.15 < remaining_budget * 0.3:
            return True
        
        # Sometimes nominate medium-value players to drive up prices
        if vor > 15 and position_priority < 0.3:
            return True
        
        return False
    
    def _calculate_vor(self, player: 'Player') -> float:
        """Calculate Value Over Replacement for a player."""
        position = player.position
        baseline = self.position_baselines.get(position, 100)
        
        # Use projected points or auction value as player value
        player_value = getattr(player, 'projected_points', 
                              getattr(player, 'auction_value', baseline))
        
        # VOR is the difference between player value and replacement level
        vor = max(0, player_value - baseline)
        return vor
    
    def _calculate_remaining_scarcity(self, player: 'Player', remaining_players: List['Player']) -> float:
        """Calculate scarcity multiplier based on remaining players at position."""
        position = player.position
        
        # Count remaining players at this position with positive VOR
        remaining_at_position = 0
        for p in remaining_players:
            if p.position == position and self._calculate_vor(p) > 0:
                remaining_at_position += 1
        
        # More scarcity = higher multiplier
        if remaining_at_position <= 3:
            return 1.5  # Very scarce
        elif remaining_at_position <= 8:
            return 1.2  # Somewhat scarce
        elif remaining_at_position <= 15:
            return 1.0  # Normal
        else:
            return 0.8  # Plenty available
    
    def _get_remaining_roster_slots(self, team: 'Team') -> int:
        """Calculate how many roster slots still need to be filled."""
        # Use base class implementation
        return super()._get_remaining_roster_slots(team)
