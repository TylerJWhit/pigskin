#!/usr/bin/env python3
"""
Enhanced VOR Strategy with Market Inflation Adjustment

This demonstrates how a VOR strategy could be enhanced to consider
league-wide budget constraints and market inflation.
"""

import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from typing import List, TYPE_CHECKING
from strategies.base_strategy import Strategy

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner


class InflationAwareVorStrategy(Strategy):
    """Enhanced VOR strategy that adjusts for market inflation."""
    
    def __init__(self, aggression: float = 1.0, scarcity_weight: float = 0.7, inflation_sensitivity: float = 0.5):
        super().__init__("inflation_vor", "VOR strategy with market inflation adjustment")
        
        self.aggression = aggression
        self.scarcity_weight = scarcity_weight
        self.inflation_sensitivity = inflation_sensitivity
        
        # Position baselines for VOR calculation
        self.position_baselines = {
            'QB': 250, 'RB': 150, 'WR': 140, 'TE': 100, 'K': 80, 'DST': 70
        }
        
        # Scarcity factors
        self.scarcity_factors = {
            'QB': 0.4, 'RB': 0.9, 'WR': 0.7, 'TE': 0.8, 'K': 0.2, 'DST': 0.3
        }
    
    def calculate_bid(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        current_bid: float,
        remaining_budget: float,
        remaining_players: List['Player'],
        **kwargs
    ) -> float:
        """Calculate bid with inflation adjustment."""
        
        # Check if we have additional context about other teams
        all_teams = kwargs.get('all_teams', [team])  # Fallback to just our team
        
        # Basic budget constraint check
        remaining_roster_slots = self._get_remaining_roster_slots(team)
        min_needed = remaining_roster_slots
        
        if remaining_budget <= min_needed + 5:
            return max(current_bid + 1, 1.0)
        
        # Get position priority
        position_priority = self._calculate_position_priority(player, team)
        if position_priority <= 0.1:
            return max(current_bid + 1, 1.0) if current_bid < 5 else 0.0
        
        # Calculate VOR
        vor = self._calculate_vor(player)
        if vor <= 0:
            return max(current_bid + 1, 1.0) if current_bid < 3 else 0.0
        
        # Calculate market inflation factor
        inflation_factor = self._calculate_inflation_factor(all_teams, remaining_players)
        
        # Calculate scarcity adjustment
        scarcity_factor = self.scarcity_factors.get(player.position, 0.5)
        scarcity_adjustment = 1.0 + (scarcity_factor * self.scarcity_weight)
        
        # Calculate remaining player scarcity
        remaining_scarcity = self._calculate_remaining_scarcity(player, remaining_players)
        
        # Calculate base bid with all factors
        vor_scaling_factor = 0.15  # $0.15 per VOR point
        base_bid = (vor * vor_scaling_factor * 
                   scarcity_adjustment * 
                   self.aggression * 
                   position_priority * 
                   remaining_scarcity *
                   inflation_factor)  # This is the key addition
        
        # Apply budget constraints
        max_percentage_bid = remaining_budget * 0.4
        max_bid = max(1.0, min(remaining_budget - min_needed, max_percentage_bid))
        
        final_bid = max(current_bid + 1, min(base_bid, max_bid))
        return final_bid if final_bid > current_bid else 0.0
    
    def _calculate_inflation_factor(self, all_teams: List, remaining_players: List['Player']) -> float:
        """Calculate market inflation based on league-wide budget situation."""
        
        # Calculate total remaining budget across all teams
        total_remaining_budget = sum(getattr(team, 'budget', 200) for team in all_teams)
        
        # Calculate total remaining roster slots
        total_remaining_slots = sum(
            max(0, 15 - len(getattr(team, 'roster', []))) 
            for team in all_teams
        )
        
        # If no teams provided or no data, assume neutral inflation
        if not all_teams or total_remaining_slots == 0:
            return 1.0
        
        # Calculate average budget per remaining slot
        avg_budget_per_slot = total_remaining_budget / total_remaining_slots if total_remaining_slots > 0 else 1.0
        
        # Standard budget per slot in a typical auction (e.g., $200/15 slots = $13.33)
        standard_budget_per_slot = 200 / 15  # ~$13.33
        
        # Calculate raw inflation ratio
        raw_inflation = avg_budget_per_slot / standard_budget_per_slot
        
        # Apply sensitivity factor - how much we care about inflation
        # sensitivity = 0 means ignore inflation, sensitivity = 1 means full adjustment
        inflation_factor = 1.0 + (raw_inflation - 1.0) * self.inflation_sensitivity
        
        # Bound the inflation factor to reasonable limits
        inflation_factor = max(0.5, min(2.0, inflation_factor))
        
        return inflation_factor
    
    def _calculate_vor(self, player: 'Player') -> float:
        """Calculate Value Over Replacement for a player."""
        position = player.position
        baseline = self.position_baselines.get(position, 100)
        
        player_value = getattr(player, 'projected_points', 
                              getattr(player, 'auction_value', baseline))
        
        vor = max(0, player_value - baseline)
        return vor
    
    def _calculate_remaining_scarcity(self, player: 'Player', remaining_players: List['Player']) -> float:
        """Calculate scarcity multiplier based on remaining players at position."""
        position = player.position
        
        remaining_at_position = sum(
            1 for p in remaining_players 
            if p.position == position and self._calculate_vor(p) > 0
        )
        
        if remaining_at_position <= 3:
            return 1.5  # Very scarce
        elif remaining_at_position <= 8:
            return 1.2  # Somewhat scarce
        elif remaining_at_position <= 15:
            return 1.0  # Normal
        else:
            return 0.8  # Plenty available
    
    def _get_remaining_roster_slots(self, team) -> int:
        """Calculate how many roster slots still need to be filled."""
        total_slots = 15
        current_roster_size = len(getattr(team, 'roster', []))
        return max(0, total_slots - current_roster_size)
    
    def _calculate_position_priority(self, player, team) -> float:
        """Calculate how much this position is needed (0.0 to 1.0)."""
        position = player.position
        
        current_roster = getattr(team, 'roster', [])
        position_counts = {}
        for p in current_roster:
            pos = getattr(p, 'position', 'UNKNOWN')
            position_counts[pos] = position_counts.get(pos, 0) + 1
        
        position_targets = {
            'QB': 2, 'RB': 4, 'WR': 4, 'TE': 2, 'K': 1, 'DST': 1
        }
        
        current_count = position_counts.get(position, 0)
        target_count = position_targets.get(position, 2)
        
        if current_count >= target_count:
            return 0.2
        
        need_ratio = (target_count - current_count) / target_count
        return min(1.0, need_ratio + 0.3)


def test_inflation_aware_strategy():
    """Test the inflation-aware VOR strategy."""
    print("Testing Inflation-Aware VOR Strategy")
    print("=" * 50)
    
    # This would show how the strategy responds to different market conditions
    # In practice, this would be integrated with the auction system
    pass


if __name__ == "__main__":
    test_inflation_aware_strategy()
