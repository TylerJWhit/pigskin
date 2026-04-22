"""Conservative strategy for auction drafts."""

from typing import List, TYPE_CHECKING
from .base_strategy import Strategy

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner


class ConservativeStrategy(Strategy):
    """Conservative strategy focused on value and avoiding overpays."""
    
    def __init__(self):
        super().__init__(
            "Conservative",
            "Focuses on value picks and avoiding overpays"
        )
        self.parameters = {
            'max_value_ratio': 0.85,  # Never bid more than 85% of value
            'sleeper_threshold': 15,  # Players under $15 are sleepers
            'sleeper_multiplier': 1.1  # Slightly overbid on sleepers
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
        """Calculate conservative bid."""
        if player.auction_value < self.parameters['sleeper_threshold']:
            max_bid = player.auction_value * self.parameters['sleeper_multiplier']
        else:
            max_bid = player.auction_value * self.parameters['max_value_ratio']
            
        max_bid = min(max_bid, remaining_budget * 0.2)  # Never spend more than 20% of budget on one player
        
        # Apply budget constraint to ensure we don't overspend
        max_bid = self._enforce_budget_constraint(max_bid, team, remaining_budget)
        
        # Conservative bid: just above current bid but not exceeding our max
        our_bid = min(current_bid + 1, max_bid)
        
        return int(our_bid)
    
    def should_nominate(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        remaining_budget: float
    ) -> bool:
        """Nominate value players or sleepers."""
        # Force nominate if we need to complete roster
        if self.should_force_nominate_for_completion(player, team, remaining_budget):
            return True
        
        # Nominate sleepers
        if player.auction_value < self.parameters['sleeper_threshold']:
            return True
            
        # Nominate if we need the position
        needs = team.get_needs()
        return player.position in needs
