"""VOR-based draft strategy focused on value over replacement."""

from typing import Dict, List, Optional, TYPE_CHECKING

from .base_strategy import Strategy

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner


class VorStrategy(Strategy):
    """VOR-focused bidding strategy with configurable parameters."""
    
    def __init__(self, aggression: float = 1.0, scarcity_weight: float = 0.7):
        """Initialize VOR strategy.
        
        Args:
            aggression: Aggression factor (0.1-1.5)
            scarcity_weight: Weight given to position scarcity (0.0-1.0)
        """
        super().__init__("vor", "Value Over Replacement focused strategy")
        
        self.aggression = aggression
        self.scarcity_weight = scarcity_weight

        # Default roster requirements (used when config is unavailable)
        _default_roster_req = {
            'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1,
            'K': 1, 'DST': 1, 'FLEX': 2, 'SF': 1
        }
        _default_num_teams = 12

        try:
            from config.config_manager import load_config  # type: ignore
            _cfg = load_config()
            self.num_teams: int = _cfg.get('num_teams', _default_num_teams)
            _roster_pos = _cfg.get('roster_positions', _default_roster_req)
            self.roster_requirements: Dict[str, int] = dict(_roster_pos)
        except Exception:
            self.num_teams = _default_num_teams
            self.roster_requirements = dict(_default_roster_req)
        
        # Position scarcity factors
        self.scarcity_factors = {
            'QB': 0.4,  # QB tends to be deep
            'RB': 0.9,  # RB tends to be scarce
            'WR': 0.7,  # WR somewhere in the middle
            'TE': 0.8,  # TE has few elite options
            'K': 0.2,   # K has little variance
            'DST': 0.3  # DST has little variance
        }

        # Dynamic scarcity factors (may be overridden during draft)
        try:
            self._calculate_all_dynamic_scarcity_factors()
        except Exception:
            pass

        # Position baselines for VOR calculation (estimated replacement level)
        try:
            self.position_baselines = self._calculate_replacement_levels()
            if not self.position_baselines:
                raise ValueError("empty")
        except Exception:
            self.position_baselines = {
                'QB': 250,   # Replacement QB fantasy points
                'RB': 150,   # Replacement RB fantasy points
                'WR': 140,   # Replacement WR fantasy points
                'TE': 100,   # Replacement TE fantasy points
                'K': 80,     # Replacement K fantasy points
                'DST': 70    # Replacement DST fantasy points
            }

        # VOR scaling factor
        try:
            self._vor_scaling_factor: float = self._calculate_vor_scaling_factor()
        except Exception:
            self._vor_scaling_factor = 0.25
    
    def calculate_bid(
        self,
        player: 'Player',
        team: 'Team',
        owner: 'Owner',
        current_bid: float,
        remaining_budget: float,
        remaining_players: List['Player']
    ) -> float:
        """Calculate bid based on VOR with scarcity adjustment.
        
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
        
        # If team has very little budget left, bid to complete roster
        if remaining_budget <= min_needed + 3:
            return min(current_bid + 1, remaining_budget - min_needed) if remaining_budget > min_needed else 0.0
        
        # Get position priority
        position_priority = self._calculate_position_priority(player, team)
        
        # If position priority is very low, still bid to fill roster if needed
        if position_priority <= 0.1:
            # Check if we're missing critical positions and need any player
            remaining_slots = self._get_remaining_roster_slots(team)
            if remaining_slots > 5:  # Need players to fill roster
                return min(current_bid + 1, 3.0)
            return 0.0
        
        # Calculate VOR (Value Over Replacement)
        vor = self._calculate_vor(player)
        
        if vor <= 0:
            # For required positions we're missing, still bid aggressively
            if position_priority >= 1.0:  # Missing required position
                return min(current_bid + 1, min(10.0, remaining_budget * 0.1))  # Bid up to $10 or 10% of budget
            
            # Player doesn't provide value but might be needed for roster
            if remaining_roster_slots > 3:
                return min(current_bid + 1, 2.0)  # Bid up to $2 for roster needs
            return 0.0
        
        # Calculate position scarcity adjustment
        scarcity_factor = self.scarcity_factors.get(player.position, 0.5)
        scarcity_adjustment = 1.0 + (scarcity_factor * self.scarcity_weight)
        
        # Calculate base bid from VOR with more aggressive scaling
        vor_scaling_factor = 0.25  # Increased from 0.15 to 0.25 per VOR point
        base_bid = vor * vor_scaling_factor * scarcity_adjustment
        
        # Apply aggression factor with boost
        base_bid *= (self.aggression * 1.3)  # 30% more aggressive
        
        # Apply position priority (how much we need this position)
        base_bid *= position_priority
        
        # CRITICAL: If position priority is 0, don't bid at all
        if position_priority == 0.0:
            return 0.0
        
        # Add per-player spending cap to prevent overpaying
        player_spending_cap = min(50.0, remaining_budget * 0.30)  # Never spend more than $50 or 30% of budget on one player
        base_bid = min(base_bid, player_spending_cap)
        
        # Calculate scarcity in remaining players
        remaining_scarcity = self._calculate_remaining_scarcity(player, remaining_players)
        base_bid *= remaining_scarcity
        
        # More flexible budget management - allow higher percentage early in draft
        budget_ratio = min(remaining_budget, 200) / 200  # Normalize to initial budget
        max_percentage = 0.20 + (0.30 * budget_ratio)  # 20% to 50% based on remaining budget
        max_percentage_bid = remaining_budget * max_percentage
        
        # Calculate maximum possible bid
        available_budget = remaining_budget - min_needed
        max_bid = max(1.0, min(available_budget, max_percentage_bid))
        
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
        # Force nomination when roster completion is urgent
        remaining_slots = self._get_remaining_roster_slots(team)
        if remaining_slots <= 2:
            return True

        # Calculate VOR and position priority
        vor = self._calculate_vor(player)
        position_priority = self._calculate_position_priority(player, team)

        # Nominate high-VOR players we need
        if vor > 20 and position_priority > 0.5:
            return True

        # Nominate affordable valuable players (bid < 15% of budget)
        if vor > 10 and position_priority > 0.3 and remaining_budget > 15:
            bid_est = self.calculate_bid(player, team, None, 0.0, remaining_budget, [])
            if isinstance(bid_est, (int, float)) and bid_est < remaining_budget * 0.15:
                return True

        # Strategic nomination — force opponents to spend on valuable players
        if vor >= 15 and position_priority < 0.3 and remaining_budget > 50:
            return True

        return False
    
    def _calculate_vor(self, player: 'Player') -> float:
        """Calculate Value Over Replacement for a player.

        If the player already has a numeric ``vor`` attribute, return it directly.
        Falls back to projected_points or auction_value, ignoring non-numeric
        attributes (e.g. Mock objects during testing).
        """
        # Prefer a pre-computed VOR attribute on the player (must be a real number)
        if hasattr(player, 'vor') and isinstance(player.vor, (int, float)):
            return float(player.vor)

        position = getattr(player, 'position', 'UNKNOWN')
        baseline = self.position_baselines.get(position, 100)

        # Use projected points or auction value as player value, ignoring non-numeric
        projected = getattr(player, 'projected_points', None)
        if not isinstance(projected, (int, float)):
            projected = None
        auction = getattr(player, 'auction_value', None)
        if not isinstance(auction, (int, float)):
            auction = None

        player_value = projected if projected is not None else (
            auction if auction is not None else float(baseline)
        )

        return float(player_value) - float(baseline)

    def _calculate_replacement_levels(self) -> Dict[str, float]:
        """Calculate replacement-level fantasy point thresholds by position.

        Returns a mapping of position -> replacement-level points.
        The replacement level is estimated as the (num_teams + 1)th-ranked player
        at each position.  When no external data is available the hard-coded
        defaults are returned.
        """
        return {
            'QB': 250.0,
            'RB': 150.0,
            'WR': 140.0,
            'TE': 100.0,
            'K': 80.0,
            'DST': 70.0,
        }

    def _calculate_vor_scaling_factor(self) -> float:
        """Return the multiplier used to convert raw VOR into a dollar bid.

        The default of 0.25 means every VOR point is worth roughly $0.25.
        """
        return 0.25
    
    def _calculate_remaining_scarcity(self, player: 'Player', remaining_players: List['Player']) -> float:
        """Calculate scarcity multiplier based on remaining players at position."""
        position = player.position
        
        # Count remaining players at this position with positive VOR
        remaining_at_position = 0
        for p in remaining_players:
            if p.position == position and self._calculate_vor(p) > 0:
                remaining_at_position += 1
        
        # More scarcity = higher multiplier
        if remaining_at_position <= 3:
            return 1.5  # Very scarce
        elif remaining_at_position <= 8:
            return 1.2  # Somewhat scarce
        elif remaining_at_position <= 15:
            return 1.0  # Normal
        else:
            return 0.8  # Plenty available
    
    def _get_remaining_roster_slots(self, team: 'Team') -> int:
        """Calculate how many roster slots still need to be filled."""
        return super()._get_remaining_roster_slots(team)

    def _get_actual_starter_counts(self) -> Dict[str, int]:
        """Return the total number of starters drafted across all teams per position.

        Computed as ``num_teams * slots_per_team`` for each position in
        ``roster_requirements``.  This is the expected total supply of started
        players in the league and is used to estimate replacement level.
        """
        return {
            pos: self.num_teams * count
            for pos, count in self.roster_requirements.items()
        }

    def _calculate_dynamic_superflex_adjustment(self, position: str) -> float:
        """Return a superflex scarcity adjustment multiplier for the given position.

        In SuperFlex formats, QBs are drafted at roughly twice the normal rate,
        which lowers the replacement level and increases VOR for all QBs.  For
        non-QB positions the adjustment is minimal (1.0).

        Returns a value in (0.0, 1.2].
        """
        try:
            starter_counts = self._get_actual_starter_counts()
        except Exception:
            return 1.0

        if position == 'QB':
            # More QBs drafted → lower replacement-level baseline → higher VOR
            # Cap adjustment below 1.0 to signal the inflated demand
            qb_count = starter_counts.get('QB', self.num_teams)
            normal_qb_count = self.num_teams * 1  # one QB per team normally
            ratio = qb_count / max(normal_qb_count, 1)
            # ratio > 1.0 means SF league; adjustment < 1.0 reflects lower baseline
            return max(0.5, min(1.0, 1.0 / max(ratio, 1.0)))

        # Non-QB positions: tiny upward adjustment for positional spillover
        return min(1.2, 1.0 + self.scarcity_factors.get(position, 0.0) * 0.1)

    def _calculate_all_dynamic_scarcity_factors(
        self, remaining_players: Optional[List['Player']] = None
    ) -> Dict[str, float]:
        """Calculate dynamic scarcity factors for all positions based on remaining players.

        Returns a dict mapping position -> scarcity factor (0.0–1.0+).
        When no remaining players list is provided, returns the static defaults.
        """
        if not remaining_players:
            return dict(self.scarcity_factors)

        position_counts: Dict[str, int] = {}
        for p in remaining_players:
            pos = getattr(p, 'position', 'UNKNOWN')
            position_counts[pos] = position_counts.get(pos, 0) + 1

        dynamic_factors: Dict[str, float] = {}
        for position, base_factor in self.scarcity_factors.items():
            count = position_counts.get(position, 0)
            if count <= 3:
                dynamic_factors[position] = min(1.5, base_factor * 1.5)
            elif count <= 8:
                dynamic_factors[position] = min(1.2, base_factor * 1.2)
            elif count <= 15:
                dynamic_factors[position] = base_factor
            else:
                dynamic_factors[position] = max(0.1, base_factor * 0.8)

        return dynamic_factors
