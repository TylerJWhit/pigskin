"""Elite hybrid strategy that focuses on elite players at key positions."""

import random
from typing import List, TYPE_CHECKING
from .base_strategy import Strategy

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner


class EliteHybridStrategy(Strategy):
    """Strategy that focuses on elite players at key positions."""
    
    def __init__(self, aggression: float = 1.2, vor_variance: float = 0.8):
        """Initialize elite hybrid strategy.
        
        Args:
            aggression: Aggression factor (1.0 = neutral, higher = more aggressive)
            vor_variance: VOR variance factor (0.0-1.0)
        """
        super().__init__(
            "Elite Hybrid",
            f"Elite-focused strategy with aggression={aggression:.1f}, vor_variance={vor_variance:.1f}"
        )
        
        self.aggression = aggression
        self.vor_variance = vor_variance
        
        # Elite player thresholds by auction value
        self.elite_thresholds = {
            'QB': 25,   # Elite QB threshold
            'RB': 35,   # Elite RB threshold 
            'WR': 30,   # Elite WR threshold
            'TE': 20,   # Elite TE threshold
            'K': 5,     # Elite K threshold
            'DST': 5    # Elite DST threshold
        }
        
        # Position scarcity factors (similar to balanced strategy)
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
        """Calculate bid with focus on elite players.
        
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
        min_needed = remaining_roster_slots
        
        # If team has just enough budget to complete roster, bid conservatively
        if remaining_budget <= min_needed + 5:
            return max(current_bid + 1, 1.0)
        
        # Get position priority
        position_priority = self._calculate_position_priority(player, team)
        
        # If position priority is very low, don't bid much
        if position_priority <= 0.1:
            return max(current_bid + 1, 1.0) if current_bid < 5 else 0.0
        
        # Get player value
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10))
        if player_value <= 0:
            player_value = 10
        
        # Check if this is an elite player
        is_elite = self._is_elite_player(player)
        
        # Calculate position scarcity
        position_scarcity = self._calculate_position_scarcity(player)
        
        # Calculate base bid with scarcity adjustment
        base_bid = player_value * self.aggression * position_priority
        
        # Apply elite player premium
        if is_elite:
            elite_factor = self._calculate_elite_factor(player)
            base_bid *= elite_factor
            
            # Be even more aggressive for elite players in scarce positions
            if position_scarcity > 0.6:
                base_bid *= 1.3  # 30% bonus for elite players in scarce positions
        
        # Apply VOR variance based on position scarcity
        vor_adjustment = 1.0 + (position_scarcity * self.vor_variance)
        base_bid *= vor_adjustment
        
        # Don't bid more than a percentage of remaining budget (higher for elite players)
        max_percentage = 0.5 if is_elite else 0.35
        max_percentage_bid = remaining_budget * max_percentage
        
        # Calculate maximum possible bid
        max_bid = max(1.0, min(remaining_budget - min_needed, max_percentage_bid))
        
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
        """Determine if this player should be nominated (prefer elite players).
        
        Args:
            player: Player to potentially nominate
            team: Team considering nomination
            owner: Owner considering nomination
            remaining_budget: Remaining budget
            
        Returns:
            True if player should be nominated
        """
        # Always nominate elite players we need
        if self._is_elite_player(player):
            position_priority = self._calculate_position_priority(player, team)
            if position_priority > 0.3:  # Lower threshold for elite players
                return True
        
        # Calculate position priority for non-elite players
        position_priority = self._calculate_position_priority(player, team)
        
        # Nominate high-priority players for needed positions
        if position_priority > 0.7:
            return True
        
        # Nominate valuable players we can afford
        player_value = getattr(player, 'auction_value', 10)
        if player_value > 25 and player_value < remaining_budget * 0.4:
            return True
        
        # Sometimes nominate to drive up prices
        if random.random() < 0.15:  # 15% chance
            return True
        
        return False
    
    def _is_elite_player(self, player: 'Player') -> bool:
        """Check if player meets elite thresholds for their position."""
        position = getattr(player, 'position', '')
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 0))
        
        threshold = self.elite_thresholds.get(position, 20)
        return player_value >= threshold
    
    def _calculate_elite_factor(self, player: 'Player') -> float:
        """Calculate elite player premium factor."""
        position = getattr(player, 'position', '')
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 0))
        
        threshold = self.elite_thresholds.get(position, 20)
        
        if player_value >= threshold * 1.5:
            # Super-elite player
            if position in ['RB', 'WR']:
                return 2.0  # 100% premium for super-elite skill position players
            else:
                return 1.8  # 80% premium for super-elite other positions
        elif player_value >= threshold:
            # Elite player
            return 1.5  # 50% premium for elite players
        else:
            return 1.0  # No premium
    
    def _calculate_position_scarcity(self, player: 'Player') -> float:
        """Calculate position scarcity factor (0.0 to 1.0)."""
        position = getattr(player, 'position', '')
        return self.scarcity_factors.get(position, 0.5)
    
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
    
