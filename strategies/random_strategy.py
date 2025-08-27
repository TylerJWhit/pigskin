"""Random draft strategy with configurable randomness factor."""

from typing import List, Optional, TYPE_CHECKING
import random

from .base_strategy import Strategy

if TYPE_CHECKING:
    from ..classes.player import Player
    from ..classes.team import Team
    from ..classes.owner import Owner


class RandomStrategy(Strategy):
    """Random bidding strategy with configurable aggression and randomness."""
    
    def __init__(self, aggression: Optional[float] = None, randomness: float = 0.5):
        """Initialize random strategy.
        
        Args:
            aggression: Aggression factor (if None, randomized between 0.5 and 1.5)
            randomness: Randomness factor (0.0-1.0, higher = more random)
        """
        super().__init__("random", "Unpredictable strategy with random bid variations")
        
        # Randomize aggression if not provided
        self.aggression = aggression if aggression is not None else random.uniform(0.5, 1.5)
        self.randomness = max(0.0, min(1.0, randomness))  # Ensure between 0 and 1
    
    def calculate_bid(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        current_bid: float,
        remaining_budget: float,
        remaining_players: List['Player']
    ) -> int:
        """Calculate bid with random variations.
        
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

        # Get basic position priority
        position_priority = self._calculate_position_priority(player, team)

        # Random decision: sometimes skip players even if needed
        if random.random() < 0.1:  # 10% chance to randomly skip
            return 0

        # Get player value
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10))

        # Base bid calculation with randomness
        base_value = player_value * position_priority

        # Apply random variation to base value
        random_factor = 1.0 + random.uniform(-self.randomness, self.randomness)
        randomized_value = base_value * random_factor

        # Apply aggression (which may itself be random)
        aggressive_bid = randomized_value * self.aggression
        
        # Add some additional random elements
        if random.random() < 0.3:  # 30% chance for "impulse" bidding
            impulse_factor = random.uniform(1.1, 1.4)
            aggressive_bid *= impulse_factor
        
        # Sometimes be very conservative
        if random.random() < 0.2:  # 20% chance to be extra conservative
            aggressive_bid *= 0.6
        
        # Don't bid more than a random percentage of remaining budget
        max_percentage = random.uniform(0.2, 0.5)  # Between 20% and 50%
        max_percentage_bid = remaining_budget * max_percentage
        
        # Calculate maximum possible bid using the budget constraint system
        max_bid = self.calculate_max_bid(team, remaining_budget)
        
        # Ensure bid is at least current bid + 1 (sometimes +2 or +3 randomly)
        random_increment = random.randint(1, 3)
        final_bid = max(current_bid + random_increment, min(aggressive_bid, max_bid))
        
        # Use get_bid_for_player which handles DST/K special cases and ensures integer result
        final_bid_amount = self.get_bid_for_player(player, final_bid, team, remaining_budget)
        
        # Return 0 if we can't afford or randomly decide not to bid
        return final_bid_amount if final_bid_amount > current_bid else 0
    
    def should_nominate(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        remaining_budget: float
    ) -> bool:
        """Determine if this player should be nominated (with randomness).
        
        Args:
            player: Player to potentially nominate
            team: Team considering nomination
            owner: Owner considering nomination
            remaining_budget: Remaining budget
            
        Returns:
            True if player should be nominated
        """
        # Calculate basic factors
        position_priority = self._calculate_position_priority(player, team)
        player_value = getattr(player, 'auction_value', 10)
        
        # Random nomination chance based on various factors
        nomination_chance = 0.0
        
        # Higher chance for needed positions
        nomination_chance += position_priority * 0.4
        
        # Higher chance for valuable players
        if player_value > 20:
            nomination_chance += 0.3
        elif player_value > 10:
            nomination_chance += 0.2
        
        # Add pure randomness
        nomination_chance += random.uniform(0.0, 0.4)
        
        # Sometimes nominate players we don't need to drive up prices
        if position_priority < 0.3:
            nomination_chance += random.uniform(0.0, 0.2)
        
        # Random decision based on calculated chance
        return random.random() < nomination_chance
    
    def _get_remaining_roster_slots(self, team: 'Team') -> int:
        """Calculate how many roster slots still need to be filled."""
        total_slots = 15  # Based on config
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
            return random.uniform(0.1, 0.3)  # Low but random priority if position is full
        
        # Higher priority if we have fewer of this position, with some randomness
        need_ratio = (target_count - current_count) / target_count
        base_priority = min(1.0, need_ratio + 0.3)
        
        # Add randomness to priority calculation
        random_adjustment = random.uniform(-0.2, 0.2)
        return max(0.1, min(1.0, base_priority + random_adjustment))
