"""Hybrid strategies combining multiple strategy approaches."""

import random
from typing import List, TYPE_CHECKING
from .base_strategy import Strategy

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner


class ValueRandomStrategy(Strategy):
    """Hybrid strategy combining value-based and random approaches."""
    
    def __init__(self, aggression: float = 1.0, randomness: float = 0.3, 
                 scarcity_weight: float = 0.5):
        """Initialize value-random hybrid strategy.
        
        Args:
            aggression: Aggression factor (default: 1.0)
            randomness: Randomness factor (0.0-1.0, default: 0.3)
            scarcity_weight: Weight for position scarcity (default: 0.5)
        """
        super().__init__(
            "Value Random",
            f"Value-based strategy with {randomness:.1f} randomness, aggression={aggression:.1f}"
        )
        self.aggression = aggression
        self.randomness = randomness
        self.scarcity_weight = scarcity_weight
        
        # Position scarcity factors
        self.scarcity_factors = {
            'QB': 0.2,  # QB has many viable options
            'RB': 0.4,  # RB is somewhat scarce
            'WR': 0.3,  # WR has good depth
            'TE': 0.5,  # TE has limited elite options
            'K': 0.1,   # K has little variance
            'DST': 0.1  # DST has little variance
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
        """Calculate bid with random variation."""
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
        player_value = self._calculate_value_with_scarcity(player)
        
        # Calculate base bid
        base_bid = player_value * self.aggression * position_priority
        
        # Apply randomness
        if random.random() < self.randomness:
            # Random adjustment between 80% and 120% of base bid
            random_factor = 0.8 + (random.random() * 0.4)
            base_bid *= random_factor
        
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
        """Determine if this player should be nominated."""
        position_priority = self._calculate_position_priority(player, team)
        
        # Nominate high-priority players for needed positions
        if position_priority > 0.6:
            return True
        
        # Nominate valuable players we can afford
        player_value = getattr(player, 'auction_value', 10)
        if player_value > 20 and player_value < remaining_budget * 0.4:
            return True
        
        # Random nominations to drive up prices
        if random.random() < self.randomness * 0.5:  # Half the randomness factor
            return True
        
        return False
    
    def _calculate_value_with_scarcity(self, player: 'Player') -> float:
        """Calculate player value with position scarcity consideration."""
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10))
        position = getattr(player, 'position', '')
        
        # Apply scarcity factor
        scarcity_factor = self.scarcity_factors.get(position, 0.3)
        scarcity_multiplier = 1.0 + (scarcity_factor * self.scarcity_weight)
        
        return player_value * scarcity_multiplier
    
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
        total_slots = 15
        current_roster_size = len(getattr(team, 'roster', []))
        return max(0, total_slots - current_roster_size)


class ValueSmartStrategy(Strategy):
    """Hybrid strategy combining value-based and smart adaptation approaches."""
    
    def __init__(self, aggression: float = 1.0, adapt_factor: float = 0.5, 
                 scarcity_weight: float = 0.5):
        """Initialize value-smart hybrid strategy.
        
        Args:
            aggression: Aggression factor (default: 1.0)
            adapt_factor: Adaptation factor (default: 0.5)
            scarcity_weight: Weight for position scarcity (default: 0.5)
        """
        super().__init__(
            "Value Smart",
            f"Value-based strategy with smart adaptation, adapt_factor={adapt_factor:.1f}"
        )
        self.aggression = aggression
        self.adapt_factor = adapt_factor
        self.scarcity_weight = scarcity_weight
        
        # Position scarcity factors
        self.scarcity_factors = {
            'QB': 0.2,
            'RB': 0.4,
            'WR': 0.3,
            'TE': 0.5,
            'K': 0.1,
            'DST': 0.1
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
        """Calculate bid with team needs adaptation."""
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
        player_value = self._calculate_value_with_scarcity(player)
        
        # Calculate base bid
        base_bid = player_value * self.aggression * position_priority
        
        # Apply smart adaptation based on team needs
        position = getattr(player, 'position', '')
        current_roster = getattr(team, 'roster', [])
        position_count = sum(1 for p in current_roster 
                           if getattr(p, 'position', '') == position)
        
        if position_count == 0:
            # Boost bid for positions we don't have
            base_bid *= (1.0 + self.adapt_factor)
        elif position_count >= 2:
            # Reduce bid for positions we have plenty of
            reduction = self.adapt_factor * 0.5 * (position_count - 1)
            base_bid *= (1.0 - min(reduction, 0.6))  # Cap reduction at 60%
        
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
        """Determine if this player should be nominated."""
        position_priority = self._calculate_position_priority(player, team)
        
        # Nominate high-priority players for needed positions
        if position_priority > 0.6:
            return True
        
        # Nominate valuable players we can afford
        player_value = getattr(player, 'auction_value', 10)
        if player_value > 20 and player_value < remaining_budget * 0.4:
            return True
        
        # Sometimes nominate to drive up prices
        if random.random() < 0.15:  # 15% chance
            return True
        
        return False
    
    def _calculate_value_with_scarcity(self, player: 'Player') -> float:
        """Calculate player value with position scarcity consideration."""
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10))
        position = getattr(player, 'position', '')
        
        # Apply scarcity factor
        scarcity_factor = self.scarcity_factors.get(position, 0.3)
        scarcity_multiplier = 1.0 + (scarcity_factor * self.scarcity_weight)
        
        return player_value * scarcity_multiplier
    
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
        total_slots = 15
        current_roster_size = len(getattr(team, 'roster', []))
        return max(0, total_slots - current_roster_size)


class ImprovedValueStrategy(Strategy):
    """Improved value strategy with better scarcity handling."""
    
    def __init__(self, aggression: float = 1.1, scarcity_weight: float = 0.6):
        """Initialize improved value strategy.
        
        Args:
            aggression: Aggression factor (default: 1.1)
            scarcity_weight: Weight for position scarcity (default: 0.6)
        """
        super().__init__(
            "Improved Value",
            f"Improved value strategy with aggression={aggression:.1f}, scarcity={scarcity_weight:.1f}"
        )
        self.aggression = aggression
        self.scarcity_weight = scarcity_weight
        
        # More nuanced scarcity weights based on position analysis
        self.scarcity_factors = {
            'QB': 0.2,  # QB has depth
            'RB': 0.5,  # RB is scarce
            'WR': 0.4,  # WR has good depth but elite matters
            'TE': 0.6,  # TE has very limited elite options
            'K': 0.1,   # K has little variance
            'DST': 0.1  # DST has little variance
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
        """Calculate bid with improved scarcity consideration."""
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
        
        # Get player value with improved scarcity consideration
        player_value = self._calculate_value_with_scarcity(player)
        
        # Calculate base bid
        base_bid = player_value * self.aggression * position_priority
        
        # Don't bid more than a percentage of remaining budget
        max_percentage_bid = remaining_budget * 0.45  # Slightly more aggressive
        
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
        """Determine if this player should be nominated."""
        position_priority = self._calculate_position_priority(player, team)
        
        # Nominate high-priority players for needed positions
        if position_priority > 0.6:
            return True
        
        # Nominate valuable players we can afford
        player_value = getattr(player, 'auction_value', 10)
        if player_value > 25 and player_value < remaining_budget * 0.4:
            return True
        
        # Sometimes nominate to drive up prices
        if random.random() < 0.2:  # 20% chance
            return True
        
        return False
    
    def _calculate_value_with_scarcity(self, player: 'Player') -> float:
        """Calculate player value with improved scarcity consideration."""
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10))
        position = getattr(player, 'position', '')
        
        # Apply improved scarcity factor
        scarcity_factor = self.scarcity_factors.get(position, 0.3)
        scarcity_multiplier = 1.0 + (scarcity_factor * self.scarcity_weight)
        
        return player_value * scarcity_multiplier
    
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
        total_slots = 15
        current_roster_size = len(getattr(team, 'roster', []))
        return max(0, total_slots - current_roster_size)
