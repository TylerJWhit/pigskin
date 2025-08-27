"""League-based draft strategy that adjusts bids based on league trends."""

import random
from typing import List, Dict, TYPE_CHECKING
from .base_strategy import Strategy

if TYPE_CHECKING:
    from ..classes.player import Player
    from ..classes.team import Team
    from ..classes.owner import Owner


class LeagueStrategy(Strategy):
    """League-based bidding strategy that considers league trends."""
    
    def __init__(self, aggression: float = 1.0, trend_adjustment: float = 0.8):
        """Initialize league strategy.
        
        Args:
            aggression: Aggression factor (0.5-1.5)
            trend_adjustment: How much to adjust for league trends (0.5-1.0)
        """
        super().__init__(
            "League",
            f"League-aware strategy with aggression={aggression:.1f}, trend_adj={trend_adjustment:.1f}"
        )
        self.aggression = aggression
        self.trend_adjustment = trend_adjustment
        
        # League trend factors by position - based on typical auction behavior
        self.trend_factors = {
            'QB': 0.9,   # League trends toward undervaluing QBs
            'RB': 1.1,   # League trends toward overvaluing top RBs
            'WR': 1.05,  # League slightly overvalues WRs
            'TE': 0.95,  # League slightly undervalues TEs
            'K': 0.8,    # League significantly undervalues Ks
            'DST': 0.85  # League significantly undervalues DSTs
        }
        
        # Position requirements for league context
        self.roster_requirements = {
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
    ) -> int:
        """Calculate bid with league trend adjustments.
        
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
        
        # Get player value with fallback
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10.0))
        
        # Calculate league trend factor
        league_factor = self._calculate_league_trend_factor(player)
        
        # Calculate base bid with league adjustments
        base_bid = player_value * self.aggression * position_priority * league_factor
        
        # Apply additional league context adjustments
        base_bid = self._apply_league_context_adjustments(base_bid, player, team)
        
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
        """Determine if this player should be nominated (exploit league trends).
        
        Args:
            player: Player to potentially nominate
            team: Team considering nomination
            owner: Owner considering nomination
            remaining_budget: Remaining budget
            
        Returns:
            True if player should be nominated
        """
        # Get league trend factor
        league_factor = self._calculate_league_trend_factor(player)
        
        # Prefer to nominate players league undervalues (lower league factor)
        if league_factor < 0.95:  # Undervalued by league
            position_priority = self._calculate_position_priority(player, team)
            if position_priority > 0.3:  # And we need the position
                return True
        
        # Nominate high-priority players for needed positions
        position_priority = self._calculate_position_priority(player, team)
        if position_priority > 0.7:
            return True
        
        # Nominate valuable players we can afford
        player_value = getattr(player, 'auction_value', 10)
        if player_value > 20 and player_value < remaining_budget * 0.4:
            return True
        
        # Sometimes nominate overvalued players to make others overpay
        if league_factor > 1.05 and random.random() < 0.25:  # 25% chance for overvalued
            return True
        
        # Standard nomination chance
        if random.random() < 0.15:  # 15% chance
            return True
        
        return False
    
    def _calculate_league_trend_factor(self, player: 'Player') -> float:
        """Calculate league trend factor for bid adjustment.
        
        Args:
            player: Player to calculate trend factor for
            
        Returns:
            Trend factor (multiplier)
        """
        position = getattr(player, 'position', '')
        base_factor = self.trend_factors.get(position, 1.0)
        
        # Apply tier adjustments - stars get bid up more in leagues
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 0))
        
        # Determine if this is an elite player
        tier_adjustment = 0.0
        if player_value >= 30:  # Elite tier
            tier_adjustment = 0.15  # Add 15% for elite players
        elif player_value >= 20:  # High tier
            tier_adjustment = 0.1   # Add 10% for high tier players
        elif player_value >= 15:  # Mid tier
            tier_adjustment = 0.05  # Add 5% for mid tier players
        
        # Apply trend adjustment factor
        adjusted_factor = base_factor + tier_adjustment
        
        # Use trend_adjustment to control how much we follow league trends
        final_factor = 1.0 + ((adjusted_factor - 1.0) * self.trend_adjustment)
        
        return final_factor
    
    def _apply_league_context_adjustments(self, base_bid: float, player: 'Player', team: 'Team') -> float:
        """Apply additional league context adjustments to bid.
        
        Args:
            base_bid: Base bid amount
            player: Player being bid on
            team: Team making the bid
            
        Returns:
            Adjusted bid amount
        """
        position = getattr(player, 'position', '')
        
        # Get current roster composition
        current_roster = getattr(team, 'roster', [])
        position_counts = {}
        for p in current_roster:
            pos = getattr(p, 'position', 'UNKNOWN')
            position_counts[pos] = position_counts.get(pos, 0) + 1
        
        current_count = position_counts.get(position, 0)
        target_count = self.roster_requirements.get(position, 2)
        
        # League context adjustments
        if position == 'RB' and current_count == 0:
            # League overvalues RBs, but we still need at least one
            base_bid *= 1.1
        elif position == 'QB' and current_count >= 1:
            # League undervalues backup QBs, but we might still want depth
            base_bid *= 0.9
        elif position == 'TE' and current_count == 0:
            # League undervalues TEs, good opportunity
            base_bid *= 1.05
        elif position in ['K', 'DST']:
            # League generally waits on these positions
            if current_count == 0:
                base_bid *= 0.9  # Be patient like the league
        
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
        target_count = self.roster_requirements.get(position, 2)
        
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
