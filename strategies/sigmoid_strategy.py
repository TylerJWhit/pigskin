"""Sigmoid strategy for auction drafts."""

import math
from typing import List, TYPE_CHECKING
from .base_strategy import Strategy

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner


class SigmoidStrategy(Strategy):
    """Strategy that uses sigmoid curves to model bidding behavior."""
    
    def __init__(self):
        super().__init__(
            "Sigmoid",
            "Uses sigmoid curves to model adaptive bidding based on draft progress and team needs"
        )
        self.parameters = {
            'base_multiplier': 1.05,  # Base value multiplier (increased from 0.95)
            'steepness': 8.0,  # Sigmoid curve steepness
            'midpoint': 0.5,  # Sigmoid curve midpoint
            'need_boost': 1.35,  # Multiplier when we need the position (increased from 1.25)
            'elite_threshold': 25,  # Elite player threshold (lowered from 30)
            'late_draft_threshold': 0.8,  # When to consider it "late" in draft
            'budget_pressure_factor': 2.2  # How much budget pressure affects bidding (increased from 2.0)
        }
        
    def _sigmoid(self, x: float, steepness: float = None, midpoint: float = None) -> float:
        """Calculate sigmoid function value."""
        if steepness is None:
            steepness = self.parameters['steepness']
        if midpoint is None:
            midpoint = self.parameters['midpoint']
            
        try:
            return 1 / (1 + math.exp(-steepness * (x - midpoint)))
        except OverflowError:
            return 0.0 if steepness * (x - midpoint) < 0 else 1.0
        
    def _calculate_draft_progress(self, remaining_players: List['Player']) -> float:
        """Calculate how far we are through the draft (0.0 to 1.0)."""
        # This is a simple estimation - in a real implementation you'd track this better
        if not remaining_players:
            return 1.0
        
        # Estimate based on remaining high-value players
        high_value_remaining = sum(1 for p in remaining_players if p.auction_value > 15)
        total_high_value = max(50, high_value_remaining)  # Estimate total high-value players
        
        return 1.0 - (high_value_remaining / total_high_value)
        
    def _calculate_budget_pressure(self, remaining_budget: float, team: 'Team') -> float:
        """Calculate budget pressure (0.0 = no pressure, 1.0 = high pressure)."""
        # Guard against ZeroDivisionError when initial_budget or roster_requirements is 0. (#146)
        _raw_budget = getattr(team, 'initial_budget', None)
        initial_budget = _raw_budget if isinstance(_raw_budget, (int, float)) and _raw_budget > 0 else (remaining_budget or 1)
        budget_ratio = remaining_budget / initial_budget
        total_requirements = sum(getattr(team, 'roster_requirements', {}).values())
        roster_filled_ratio = (len(getattr(team, 'roster', [])) / total_requirements
                               if total_requirements > 0 else 0.0)
        
        # More pressure if we have little budget relative to roster spots left
        return max(0.0, min(1.0, (1.0 - budget_ratio) + roster_filled_ratio - 0.5))
        
    def _calculate_positional_need(self, player: 'Player', team: 'Team') -> float:
        """Calculate how much we need this position (0.0 to 1.0)."""
        try:
            needs = team.get_needs()
            if not isinstance(needs, (dict, list)):
                return 0.5
        except Exception:
            return 0.5
        
        if player.position not in needs:
            return 0.0
            
        # Calculate need based on how many spots we still need to fill
        required = needs.get(player.position, 0) if isinstance(needs, dict) else \
                   getattr(team, 'roster_requirements', {}).get(player.position, 0) if hasattr(team, 'roster_requirements') else 0
        if not isinstance(required, (int, float)):
            return 0.5
        current = len([p for p in team.roster if getattr(p, 'position', None) == player.position])
        
        if required == 0:
            return 0.0
            
        need_ratio = max(0.0, (required - current) / required)
        return need_ratio
        
    def calculate_bid(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        current_bid: float,
        remaining_budget: float,
        remaining_players: List['Player']
    ) -> float:
        """Calculate bid using sigmoid-based modeling."""
        # Base value calculation
        base_value = player.auction_value * self.parameters['base_multiplier']
        
        # Calculate various factors
        draft_progress = self._calculate_draft_progress(remaining_players)
        budget_pressure = self._calculate_budget_pressure(remaining_budget, team)
        positional_need = self._calculate_positional_need(player, team)
        
        # Early draft factor - be more aggressive early, conservative late
        early_aggression = 1.0 - self._sigmoid(draft_progress, steepness=6.0, midpoint=0.3)
        
        # Need-based multiplier using sigmoid
        need_multiplier = 1.0 + (self.parameters['need_boost'] - 1.0) * self._sigmoid(positional_need)
        
        # Elite player factor
        is_elite = player.auction_value >= self.parameters['elite_threshold']
        elite_factor = 1.2 if is_elite else 1.0
        
        # Budget pressure adjustment - be more conservative when budget is tight
        budget_factor = 1.0 - (budget_pressure * 0.3)  # Reduce by up to 30%
        
        # Late draft urgency - if draft is almost over and we need players
        late_urgency = 1.0
        if draft_progress > self.parameters['late_draft_threshold'] and positional_need > 0.5:
            late_urgency = 1.3  # Be more aggressive late if we need the position
            
        # Risk tolerance from owner (with fallback for mock drafts)
        try:
            _rf = owner.get_risk_tolerance() if owner else 0.7
            risk_factor = float(_rf) if isinstance(_rf, (int, float)) else 0.7
        except (AttributeError, TypeError):
            risk_factor = 0.7  # Default moderate risk
        risk_adjustment = 0.8 + (0.4 * risk_factor)  # Scale between 0.8 and 1.2
        
        # Combine all factors
        max_bid = (base_value * 
                  need_multiplier * 
                  elite_factor * 
                  budget_factor * 
                  late_urgency * 
                  risk_adjustment * 
                  (1.0 + early_aggression * 0.2))  # Up to 20% more aggressive early
        
        # Smart budget management - leave minimum for remaining required roster spots
        roster_spots_needed = sum(team.roster_config.values()) - len(team.roster)
        min_budget_reserve = max(0, roster_spots_needed - 1)  # Reserve $1 per remaining spot minus current player
        available_budget = remaining_budget - min_budget_reserve
        
        # Don't exceed available budget but be more aggressive than before
        max_bid = min(max_bid, available_budget)
        
        # Don't bid if current bid is already too high
        if current_bid >= max_bid:
            return 0.0
            
        # Calculate increment based on player value and competition
        if player.auction_value >= 20:
            increment = 2  # Bigger increments for valuable players
        else:
            increment = 1
            
        our_bid = min(current_bid + increment, max_bid)
        
        # Enforce budget constraint before returning
        our_bid = self._enforce_budget_constraint(our_bid, team, remaining_budget)
        
        return int(our_bid)
        
    def should_nominate(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        remaining_budget: float
    ) -> bool:
        """Determine nomination strategy using sigmoid logic."""
        # Calculate factors
        positional_need = self._calculate_positional_need(player, team)
        
        # Always nominate if it's a target player
        if owner.is_target_player(player.player_id):
            return True
            
        # Use sigmoid to determine nomination probability based on need
        need_probability = self._sigmoid(positional_need, steepness=5.0, midpoint=0.4)
        
        # Elite players - nominate with moderate probability to force others to spend
        if player.auction_value >= self.parameters['elite_threshold']:
            elite_probability = 0.4
            return max(need_probability, elite_probability) > 0.5
            
        # Value players - nominate if we need them
        return need_probability > 0.6
