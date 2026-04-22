"""Base strategy class for auction draft tool."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner


class Strategy(ABC):
    """Abstract base class for auction draft strategies."""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.parameters = {}
        
    @abstractmethod
    def calculate_bid(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        current_bid: float,
        remaining_budget: float,
        remaining_players: List['Player']
    ) -> int:
        """Calculate the bid amount for a player as an integer."""
        pass
        
    @abstractmethod
    def should_nominate(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        remaining_budget: float
    ) -> bool:
        """Determine if this player should be nominated."""
        pass
        
    def set_parameter(self, key: str, value) -> None:
        """Set a strategy parameter."""
        self.parameters[key] = value
        
    def get_parameter(self, key: str, default=None):
        """Get a strategy parameter."""
        return self.parameters.get(key, default)
    
    # Common helper methods that all strategies can use
    def _get_remaining_roster_slots(self, team: 'Team') -> int:
        """Calculate how many roster slots still need to be filled."""
        # Try to get total slots from team's roster config first
        if hasattr(team, 'roster_config') and team.roster_config:
            total_slots = sum(team.roster_config.values())
        else:
            # Default assumption based on typical fantasy roster
            total_slots = 15
        
        current_roster_size = len(getattr(team, 'roster', []))
        return max(0, total_slots - current_roster_size)
    
    def _get_required_positions_needed(self, team: 'Team') -> int:
        """Calculate how many required positions still need to be filled.
        
        ALL roster positions are required, including FLEX and BENCH slots.
        """
        # All remaining roster slots are required - there are no "optional" slots
        # FLEX and BENCH are just as required as starting positions
        return self._get_remaining_roster_slots(team)
    
    def _calculate_position_priority(self, player: 'Player', team: 'Team') -> float:
        """Calculate how much this position is needed (0.0 to 1.0).
        
        Uses team's actual roster configuration to determine position targets,
        accounting for FLEX and BENCH spots properly.
        """
        position = player.position
        
        # Get current roster composition
        current_roster = getattr(team, 'roster', [])
        position_counts = {}
        for p in current_roster:
            pos = getattr(p, 'position', 'UNKNOWN')
            position_counts[pos] = position_counts.get(pos, 0) + 1
        
        # Get position targets from team's roster configuration
        if hasattr(team, 'roster_config') and team.roster_config:
            config = team.roster_config
            flex_spots = config.get('FLEX', 0)
            bench_spots = config.get('BN', config.get('BENCH', 0))
            
            # Calculate minimum requirements first (starter positions)
            min_requirements = {
                'QB': config.get('QB', 1),
                'RB': config.get('RB', 2), 
                'WR': config.get('WR', 2),
                'TE': config.get('TE', 1),
                'K': config.get('K', 1),
                'DST': config.get('DST', 1)
            }
            
            # Calculate optimal targets including FLEX and BENCH
            # FLEX can be filled by RB, WR, or TE
            # BENCH can be filled by any position
            total_flex_eligible = flex_spots + bench_spots
            
            position_targets = {
                'QB': min_requirements['QB'] + (bench_spots // 6),  # Small QB depth
                'RB': min_requirements['RB'] + max(1, total_flex_eligible // 2),  # RBs are valuable for FLEX
                'WR': min_requirements['WR'] + max(1, total_flex_eligible // 2),  # WRs are valuable for FLEX  
                'TE': min_requirements['TE'] + min(1, total_flex_eligible // 4),  # Some TE depth
                'K': min_requirements['K'],  # Usually just 1 K
                'DST': min_requirements['DST']  # Usually just 1 DST
            }
        else:
            # Fallback for teams without roster config (should be rare)
            position_targets = {
                'QB': 1,
                'RB': 4,  # 2 starters + 2 depth
                'WR': 4,  # 2 starters + 2 depth
                'TE': 2,  # 1 starter + 1 depth
                'K': 1,
                'DST': 1
            }
        
        current_count = position_counts.get(position, 0)
        target_count = position_targets.get(position, 1)
        
        # Check if we've already met minimum requirements
        if hasattr(team, 'roster_config') and team.roster_config:
            min_req = {
                'QB': team.roster_config.get('QB', 1),
                'RB': team.roster_config.get('RB', 2), 
                'WR': team.roster_config.get('WR', 2),
                'TE': team.roster_config.get('TE', 1),
                'K': team.roster_config.get('K', 1),
                'DST': team.roster_config.get('DST', 1)
            }.get(position, 0)
            
            # If we haven't met minimum requirements for K or DST, make it HIGHEST priority
            if position in ['K', 'DST'] and current_count < min_req:
                return 2.0  # Even higher than normal high priority
            
            # If we haven't met minimum requirements for other positions, high priority
            if current_count < min_req:
                return 1.0
        
        # If position is completely filled, very low priority
        if current_count >= target_count:
            return 0.1
        
        # Calculate priority based on need ratio
        need_ratio = (target_count - current_count) / target_count
        
        # Boost priority for positions we have none of
        if current_count == 0:
            need_ratio += 0.3
            
        return min(1.0, need_ratio + 0.2)
    
    def _get_player_value(self, player: 'Player', fallback: float = 10.0) -> float:
        """Get player value with proper fallbacks."""
        # Try auction_value first
        if hasattr(player, 'auction_value') and player.auction_value > 0:
            return player.auction_value
        
        # Try projected_points as fallback
        if hasattr(player, 'projected_points') and player.projected_points > 0:
            return player.projected_points
        
        # Use fallback value
        return fallback
    
    def _calculate_budget_reservation(self, team: 'Team', remaining_budget: float) -> float:
        """Calculate minimum budget to reserve for completing roster."""
        return self._calculate_minimum_budget_needed(team, remaining_budget)
    
    def _should_force_bid(self, team: 'Team', remaining_budget: float, current_bid: float) -> bool:
        """Determine if we should force a bid to avoid incomplete roster."""
        remaining_slots = self._get_remaining_roster_slots(team)
        
        # If we have many slots left and low budget, we need to bid on cheap players
        if remaining_slots > 5 and remaining_budget > remaining_slots:
            return current_bid <= 5.0  # Bid on cheap players
        
        # If we're close to running out of slots, bid more aggressively
        if remaining_slots <= 3 and remaining_budget > remaining_slots:
            return current_bid <= remaining_budget * 0.3
        
        return False
    
    def _calculate_safe_bid_limit(self, team: 'Team', remaining_budget: float, max_percentage: float = 0.3) -> int:
        """Calculate maximum safe bid amount.
        
        Returns integer bid amount.
        """
        budget_reservation = self._calculate_budget_reservation(team, remaining_budget)
        usable_budget = max(0, remaining_budget - budget_reservation)
        
        # Don't spend more than percentage of usable budget on one player
        max_bid = usable_budget * max_percentage
        
        return max(1, int(max_bid))
    
    def should_force_nominate_for_completion(self, player: 'Player', team: 'Team', remaining_budget: float) -> bool:
        """Determine if we should force nominate this player to complete roster.
        
        Args:
            player: Player being considered for nomination
            team: Team considering nomination
            remaining_budget: Team's remaining budget
            
        Returns:
            True if we should nominate this player to help complete roster
        """
        remaining_slots = self._get_remaining_roster_slots(team)
        
        # If we have few roster slots remaining, we should prioritize roster completion
        if remaining_slots >= 3:
            position_priority = self._calculate_position_priority(player, team)
            
            # If we have very little budget left, we should nominate cheap players we need
            if remaining_budget <= remaining_slots * 2.0:  # Less than $2 per remaining slot
                # Force nominate if this is a needed position and we can afford it
                return position_priority >= 0.5 and remaining_budget >= 1.0
                
            # Also force nominate if we need this position type badly
            if position_priority >= 1.0:  # High priority position (like missing K/DST)
                return True
                
        return False
    
    def _enforce_budget_constraint(self, proposed_bid: float, team: 'Team', remaining_budget: float) -> int:
        """Enforce budget constraint using the max bid calculation.
        
        Returns the minimum of the proposed bid and the maximum allowable bid as integer.
        """
        max_allowable_bid = self.calculate_max_bid(team, remaining_budget)
        
        # Return the smaller of proposed bid or maximum allowable bid as integer
        return min(int(proposed_bid), max_allowable_bid)
    
    def calculate_max_bid(self, team: 'Team', remaining_budget: float) -> int:
        """Calculate the maximum possible bid while ensuring roster completion.
        
        Args:
            team: Team making the bid
            remaining_budget: Team's remaining budget
            
        Returns:
            Maximum allowable bid amount as integer
        """
        remaining_slots = self._get_remaining_roster_slots(team)
        
        if remaining_slots == 0:
            return int(remaining_budget)  # Can bid everything if roster is complete
        
        if remaining_slots == 1:
            # If this is the last slot, we can bid our entire remaining budget
            return max(1, int(remaining_budget))
        
        # Reserve $1 per remaining slot AFTER this bid (remaining_slots - 1)
        # because winning this bid fills one slot
        slots_after_this_bid = remaining_slots - 1
        min_budget_needed = slots_after_this_bid * 1.0
        
        # Maximum bid is remaining budget minus what we need for remaining slots
        max_bid = remaining_budget - min_budget_needed
        
        # Special case: if team is severely budget-constrained, allow minimal overbidding
        # to prevent auction stalls when teams can't even bid $1
        if max_bid < 1 and remaining_budget > 0:
            # Allow teams to bid $1 even if they're slightly short, to prevent stalls
            # This simulates real-world scenarios where teams might go slightly over budget
            return 1
        
        # Must be at least $1 to make a valid bid, return as integer
        return max(1, int(max_bid)) if max_bid >= 1 else 0
    
    def _calculate_minimum_budget_needed(self, team: 'Team', remaining_budget: float) -> float:
        """Calculate the minimum budget needed to complete the roster.
        
        All remaining roster slots are required and must be budgeted for at $1 each.
        """
        remaining_slots = self._get_remaining_roster_slots(team)
        
        # Reserve exactly $1 per remaining roster slot since minimum bid is $1
        # All slots (starting, FLEX, and BENCH) are required to complete the roster
        return remaining_slots * 1.0
    
    def safe_bid(self, calculated_bid: float, team: 'Team', remaining_budget: float) -> int:
        """Return the safe bid amount ensuring roster completion.
        
        Args:
            calculated_bid: The bid amount calculated by the strategy
            team: Team making the bid
            remaining_budget: Team's remaining budget
            
        Returns:
            The minimum of calculated_bid and max allowable bid as integer
        """
        max_allowable = self.calculate_max_bid(team, remaining_budget)
        return min(int(calculated_bid), max_allowable)
    
    def get_bid_for_player(self, player: 'Player', calculated_bid: float, team: 'Team', remaining_budget: float) -> int:
        """Get the final bid amount for a player, applying special rules for certain positions.
        
        Args:
            player: The player being bid on
            calculated_bid: The bid amount calculated by the strategy
            team: Team making the bid
            remaining_budget: Team's remaining budget
            
        Returns:
            Final bid amount as integer, minimum $1, with budget constraints enforced
        """
        # All bids must be at least $1 (minimum bid amount)
        calculated_bid = max(1.0, calculated_bid)
        
        # CRITICAL: Always enforce budget constraints at this final stage
        # This is the last line of defense before a bid is returned
        safe_bid_amount = self._enforce_budget_constraint(calculated_bid, team, remaining_budget)
        
        # If safe bid is 0, we can't afford to bid
        return safe_bid_amount
        
    def calculate_bid_with_constraints(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        current_bid: float,
        remaining_budget: float,
        remaining_players: List['Player']
    ) -> int:
        """Calculate bid with guaranteed budget constraint enforcement.
        
        This method wraps the abstract calculate_bid method to ensure budget
        constraints are always applied, regardless of strategy implementation.
        """
        # Call the strategy's calculate_bid method
        raw_bid = self.calculate_bid(player, team, owner, current_bid, remaining_budget, remaining_players)
        
        # Always apply budget constraints as final safeguard
        constrained_bid = self._enforce_budget_constraint(float(raw_bid), team, remaining_budget)
        
        return constrained_bid
    
    def __str__(self) -> str:
        return f"{self.name}: {self.description}"
