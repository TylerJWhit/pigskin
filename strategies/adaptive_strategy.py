"""Adaptive draft strategy that adjusts based on draft conditions."""

from typing import List, TYPE_CHECKING

from .base_strategy import Strategy

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner


class AdaptiveStrategy(Strategy):
    """Adaptive bidding strategy that adjusts to draft conditions."""
    
    def __init__(self, base_aggression: float = 1.0, adapt_factor: float = 0.5):
        """Initialize adaptive strategy.
        
        Args:
            base_aggression: Base aggression factor (0.1-1.5)
            adapt_factor: Adaptation factor (0.0-1.0)
        """
        super().__init__("adaptive", "Adaptive strategy that learns from draft trends")
        
        self.base_aggression = base_aggression
        self.adapt_factor = adapt_factor
        self.current_aggression = base_aggression
        
        # Track draft trends
        self.bid_history = []
        self.position_trends = {
            'QB': 1.0, 'RB': 1.0, 'WR': 1.0, 'TE': 1.0, 'K': 1.0, 'DST': 1.0
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
        """Calculate bid with adaptive adjustment.
        
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
        
        # If team has very little budget left, bid more aggressively to complete roster
        if remaining_budget <= min_needed + 3:
            return min(current_bid + 1, remaining_budget - min_needed) if remaining_budget > min_needed else 0.0
        
        # Get position priority
        position_priority = self._calculate_position_priority(player, team)
        
        # Calculate maximum possible bid to ensure roster completion (needed for mandatory positions)
        max_possible_bid = self.calculate_max_bid(team, remaining_budget)
        
        # Special handling for mandatory positions (K, DST) with very high priority
        if position_priority >= 2.0 and player.position in ['K', 'DST']:
            # We MUST have these positions - bid aggressively even if player value is low
            min_mandatory_bid = min(10.0, remaining_budget * 0.1)  # At least $10 or 10% of budget
            return min(current_bid + min_mandatory_bid, max_possible_bid)
        
        # If position priority is very low, still bid minimally to fill roster if needed
        if position_priority <= 0.1:
            if remaining_roster_slots > 5:  # Need players to fill roster
                return min(current_bid + 1, 3.0)  # Bid up to $3 for roster filler
            return 0.0
        
        # Get player value
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10))
        if player_value <= 0:
            player_value = 10
        
        # Calculate position trend factor
        position_factor = self.position_trends.get(player.position, 1.0)
        
        # Calculate adaptive aggression for this position
        adaptive_aggression = self.current_aggression * position_factor
        
        # Calculate base bid with more aggressive scaling
        base_bid = player_value * adaptive_aggression * position_priority * 1.2  # 20% more aggressive
        
        # Allow higher percentage of budget, especially early in draft
        budget_ratio = min(remaining_budget, 200) / 200  # Normalize to initial budget
        max_percentage = 0.15 + (0.25 * budget_ratio)  # 15% to 40% based on remaining budget
        max_percentage_bid = remaining_budget * max_percentage
        
        # Calculate maximum possible bid (already calculated above, but ensure constraint)
        available_budget = remaining_budget - min_needed
        max_bid = max(1.0, min(available_budget, max_percentage_bid, max_possible_bid))
        
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
        # Calculate position priority
        position_priority = self._calculate_position_priority(player, team)
        
        # Nominate high-priority players for needed positions
        if position_priority > 0.7:
            return True
        
        # For adaptive strategy, look for undervalued positions
        position_factor = self.position_trends.get(player.position, 1.0)
        
        # If this position is being undervalued (factor < 1.0), nominate more often
        if position_factor < 0.8 and position_priority > 0.3:
            return True
        
        # Nominate valuable players we can afford
        player_value = getattr(player, 'auction_value', 10)
        if player_value > 15 and player_value < remaining_budget * 0.25:
            return True
        
        return False
    
    def update_draft_trends(self, player: 'Player', winning_bid: float) -> None:
        """Update draft trends based on recent bids.
        
        Args:
            player: Player that was drafted
            winning_bid: Winning bid amount
        """
        # Record bid in history
        self.bid_history.append((player, winning_bid))
        
        # Update position trends
        position = player.position
        player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10))
        
        if position and player_value > 0:
            # Calculate expected bid based on our base aggression
            expected_bid = player_value * self.base_aggression
            
            # Calculate ratio of actual to expected
            ratio = winning_bid / expected_bid if expected_bid > 0 else 1.0
            
            # Update position trend with exponential smoothing
            current = self.position_trends.get(position, 1.0)
            self.position_trends[position] = (current * 0.7) + (ratio * 0.3)
        
        # Update overall aggression
        self._update_aggression()
    
    def _update_aggression(self) -> None:
        """Update current aggression based on recent trends."""
        # Only adapt if we have enough data
        if len(self.bid_history) < 3:
            return
        
        # Get recent bids (last 10 or all if fewer)
        recent_bids = self.bid_history[-10:] if len(self.bid_history) >= 10 else self.bid_history
        
        # Calculate average bid ratio
        ratios = []
        for player, bid in recent_bids:
            player_value = getattr(player, 'auction_value', getattr(player, 'projected_points', 10))
            if player_value > 0:
                expected = player_value * self.base_aggression
                ratio = bid / expected if expected > 0 else 1.0
                ratios.append(ratio)
        
        if ratios:
            avg_ratio = sum(ratios) / len(ratios)
            
            # Adapt current aggression toward observed market behavior
            base = self.base_aggression
            adapt = self.adapt_factor
            
            # Move current aggression toward the observed ratio
            self.current_aggression = (base * (1 - adapt)) + (base * avg_ratio * adapt)
            
            # Ensure within reasonable bounds
            self.current_aggression = max(0.5 * base, min(1.5 * base, self.current_aggression))
    
    def _get_remaining_roster_slots(self, team: 'Team') -> int:
        """Calculate how many roster slots still need to be filled."""
        # Use base class implementation
        return super()._get_remaining_roster_slots(team)