"""Refined value random strategy that combines value bidding with smart randomness."""

import random
from typing import List, TYPE_CHECKING
from .base_strategy import Strategy

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner


class RefinedValueRandomStrategy(Strategy):
    """Strategy that combines value bidding with randomness and refinements."""
    
    def __init__(self, aggression: float = 1.1, randomness: float = 0.35, 
                 scarcity_weight: float = 0.5):
        """Initialize refined value random strategy.
        
        Args:
            aggression: Aggression factor (default: 1.1)
            randomness: Randomness factor (0.0-1.0, default: 0.35)
            scarcity_weight: Weight for position scarcity (default: 0.5)
        """
        super().__init__(
            "Refined Value Random",
            f"Refined value strategy with {randomness:.2f} randomness, aggression={aggression:.1f}"
        )
        self.aggression = aggression
        self.randomness = randomness
        self.scarcity_weight = scarcity_weight
        
        # Enhanced scarcity factors for refined strategy
        self.scarcity_factors = {
            'QB': 0.4,  # Moderate QB scarcity
            'RB': 0.9,  # High RB scarcity
            'WR': 0.7,  # Good WR scarcity
            'TE': 0.8,  # High TE scarcity
            'K': 0.2,   # Low K scarcity
            'DST': 0.3  # Low DST scarcity
        }
        
        # Position requirements for draft context
        self.position_targets = {
            'QB': 2,
            'RB': 4,
            'WR': 4,
            'TE': 2,
            'K': 1,
            'DST': 1
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
        """Calculate bid with refined value and randomness.
        
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
        
        # Get player value with scarcity consideration
        player_value = self._calculate_refined_value(player)
        
        # Calculate draft progress for contextual adjustments
        draft_progress = self._calculate_draft_progress(team)
        
        # Calculate base bid with draft stage refinements
        base_bid = player_value * self.aggression * position_priority
        base_bid = self._apply_draft_stage_refinements(base_bid, player, team, draft_progress)
        
        # Apply smart randomness
        base_bid = self._apply_smart_randomness(base_bid, player, position_priority)
        
        # Don't bid more than a percentage of remaining budget
        max_percentage_bid = remaining_budget * 0.4
        
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
        """Determine if this player should be nominated (with refined logic).
        
        Args:
            player: Player to potentially nominate
            team: Team considering nomination
            owner: Owner considering nomination
            remaining_budget: Remaining budget
            
        Returns:
            True if player should be nominated
        """
        position_priority = self._calculate_position_priority(player, team)
        draft_progress = self._calculate_draft_progress(team)
        
        # Early draft: nominate high-value players
        if draft_progress < 0.3:
            player_value = getattr(player, 'auction_value', 10)
            if player_value > 25 and position_priority > 0.4:
                return True
        
        # Mid draft: nominate based on team needs
        elif draft_progress < 0.7:
            if position_priority > 0.6:
                return True
        
        # Late draft: nominate needed positions aggressively
        else:
            if position_priority > 0.5:
                return True
        
        # Nominate valuable players we can afford
        player_value = getattr(player, 'auction_value', 10)
        if player_value > 20 and player_value < remaining_budget * 0.4:
            return True
        
        # Random nominations with refined probability
        random_chance = self.randomness * 0.6  # 60% of randomness factor
        if random.random() < random_chance:
            return True
        
        return False
    
    def _calculate_refined_value(self, player: 'Player') -> float:
        """Calculate player value with refined scarcity consideration."""
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10))
        position = getattr(player, 'position', '')
        
        # Apply enhanced scarcity factor
        scarcity_factor = self.scarcity_factors.get(position, 0.5)
        scarcity_multiplier = 1.0 + (scarcity_factor * self.scarcity_weight)
        
        return player_value * scarcity_multiplier
    
    def _calculate_draft_progress(self, team: 'Team') -> float:
        """Calculate how far through the draft we are (0.0 to 1.0)."""
        current_roster = getattr(team, 'roster', [])
        current_roster_size = len(current_roster)
        total_roster_size = 15  # Assume 15 roster spots
        
        return min(1.0, current_roster_size / total_roster_size)
    
    def _apply_draft_stage_refinements(
        self, 
        base_bid: float, 
        player: 'Player', 
        team: 'Team', 
        draft_progress: float
    ) -> float:
        """Apply refinements based on draft stage."""
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10))

        if draft_progress < 0.3:
            # Early draft - be more aggressive on high-value players
            if player_value > 25:
                base_bid *= 1.2
            elif player_value > 20:
                base_bid *= 1.1
        
        elif draft_progress > 0.7:
            # Late draft - be more aggressive on needed positions
            position_priority = self._calculate_position_priority(player, team)
            if position_priority > 0.7:
                base_bid *= 1.3
            elif position_priority > 0.5:
                base_bid *= 1.15
        
        else:
            # Mid draft - balanced approach with slight value emphasis
            if player_value > 20:
                base_bid *= 1.05
        
        return base_bid
    
    def _apply_smart_randomness(
        self, 
        base_bid: float, 
        player: 'Player', 
        position_priority: float
    ) -> float:
        """Apply smart randomness that considers player value and position needs."""
        if random.random() < self.randomness:
            # Higher priority positions get less randomness variance
            if position_priority > 0.7:
                # Low variance for high priority positions (±10%)
                random_factor = 0.9 + (random.random() * 0.2)
            elif position_priority > 0.4:
                # Medium variance for medium priority positions (±15%)
                random_factor = 0.85 + (random.random() * 0.3)
            else:
                # High variance for low priority positions (±25%)
                random_factor = 0.75 + (random.random() * 0.5)
            
            base_bid *= random_factor
        
        return base_bid
    
    def _calculate_position_priority(self, player: 'Player', team: 'Team') -> float:
        """Calculate how much this position is needed (0.0 to 1.0)."""
        position = player.position
        
        # Get current roster composition
        current_roster = getattr(team, 'roster', [])
        position_counts = {}
        for p in current_roster:
            pos = getattr(p, 'position', 'UNKNOWN')
            position_counts[pos] = position_counts.get(pos, 0) + 1
        
        current_count = position_counts.get(position, 0)
        target_count = self.position_targets.get(position, 2)
        
        if current_count >= target_count:
            return 0.2  # Low priority if position is full
        
        # Higher priority if we have fewer of this position
        need_ratio = (target_count - current_count) / target_count
        return min(1.0, need_ratio + 0.2)
    
