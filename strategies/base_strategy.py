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
        
    def __str__(self) -> str:
        return f"{self.name}: {self.description}"

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Wrap calculate_bid to apply team.enforce_budget_constraint when available.
        # Only uses the constrained value if it is a real number; otherwise falls back
        # to the raw value.  Returns 0 when the (constrained) bid cannot beat current_bid.
        if 'calculate_bid' in cls.__dict__:
            _orig_calc = cls.__dict__['calculate_bid']

            def _wrapped_calculate_bid(self, player, team, owner, current_bid, remaining_budget, remaining_players, _f=_orig_calc):
                raw = _f(self, player, team, owner, current_bid, remaining_budget, remaining_players)
                if not isinstance(raw, (int, float)):
                    return 0
                enforce = getattr(team, 'enforce_budget_constraint', None)
                if callable(enforce):
                    result = enforce(raw, remaining_budget)
                    if isinstance(result, (int, float)):
                        return 0 if result <= current_bid else result
                return 0 if raw <= current_bid else int(raw)

            cls.calculate_bid = _wrapped_calculate_bid

        # Wrap should_nominate to apply a slot/priority guard when team exposes
        # delegation methods.  When very few roster slots remain, only nominate
        # players for positions we actually need (priority >= 0.3).
        if 'should_nominate' in cls.__dict__:
            _orig_nom = cls.__dict__['should_nominate']

            def _wrapped_should_nominate(self, player, team, owner, remaining_budget, _f=_orig_nom):
                get_slots = getattr(team, 'get_remaining_roster_slots', None)
                get_prio = getattr(team, 'calculate_position_priority', None)
                if callable(get_slots) and callable(get_prio):
                    try:
                        slots = get_slots()
                        priority = get_prio(getattr(player, 'position', 'UNKNOWN'))
                        if slots <= 2 and priority < 0.3:
                            return False
                    except Exception:
                        pass
                return _f(self, player, team, owner, remaining_budget)

            cls.should_nominate = _wrapped_should_nominate

    def set_parameter(self, key: str, value) -> None:
        """Set a strategy parameter."""
        if self.parameters is None:
            self.parameters = {}
        self.parameters[key] = value
        
    def get_parameter(self, key: str, default=None):
        """Get a strategy parameter."""
        return self.parameters.get(key, default)
    
    # Common helper methods that all strategies can use
    def _get_remaining_roster_slots(self, team: 'Team') -> int:
        """Return remaining roster slots, delegating to team when possible."""
        get_slots = getattr(team, 'get_remaining_roster_slots', None)
        if callable(get_slots):
            return get_slots()
        # Fallback: compute from roster_config
        if hasattr(team, 'roster_config') and team.roster_config and isinstance(team.roster_config, dict):
            total_slots = sum(team.roster_config.values())
        else:
            total_slots = 15
        current_roster_size = len(getattr(team, 'roster', []))
        return max(0, total_slots - current_roster_size)

    def _get_required_positions_needed(self, team: 'Team') -> int:
        """Return count of roster positions still needed, delegating to team when possible."""
        return self._get_remaining_roster_slots(team)

    def _calculate_position_priority(self, player: 'Player', team: 'Team') -> float:
        """Return position priority, delegating to team when possible."""
        get_prio = getattr(team, 'calculate_position_priority', None)
        if callable(get_prio):
            return get_prio(getattr(player, 'position', 'UNKNOWN'))
        # Fallback internal computation
        position = getattr(player, 'position', 'UNKNOWN')
        current_roster = getattr(team, 'roster', [])
        position_counts: Dict[str, int] = {}
        for p in current_roster:
            pos = getattr(p, 'position', 'UNKNOWN')
            position_counts[pos] = position_counts.get(pos, 0) + 1
        roster_config = getattr(team, 'roster_config', None)
        if isinstance(roster_config, dict):
            needed = roster_config.get(position, 1)
        else:
            needed = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DST': 1}.get(position, 1)
        current = position_counts.get(position, 0)
        if current >= needed:
            return 0.1
        return min(1.0, (needed - current) / max(needed, 1) + 0.2)
    
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
        """Return minimum budget to reserve, delegating to team when possible."""
        calc_min = getattr(team, 'calculate_minimum_budget_needed', None)
        if callable(calc_min):
            return calc_min(remaining_budget)
        return self._calculate_minimum_budget_needed(team, remaining_budget)

    def _should_force_bid(self, team: 'Team', remaining_budget: float, current_bid: float) -> bool:
        """Determine if we must bid to avoid an incomplete roster."""
        remaining_slots = self._get_remaining_roster_slots(team)
        if remaining_slots == 0:
            return False
        budget_per_slot = remaining_budget / remaining_slots
        if remaining_slots == 1:
            return remaining_budget >= current_bid
        if remaining_slots <= 3:
            return current_bid <= budget_per_slot * 1.5
        if remaining_slots <= 6:
            return current_bid <= budget_per_slot * 0.8
        if budget_per_slot < 3.0:
            return current_bid < budget_per_slot * 2.0
        return False

    def should_force_nominate_for_completion(self, player: 'Player', team: 'Team', remaining_budget: float) -> bool:
        """Determine if we should force nominate this player to complete the roster."""
        remaining_slots = self._get_remaining_roster_slots(team)
        if remaining_slots < 3:
            return False
        position_priority = self._calculate_position_priority(player, team)
        if remaining_budget <= remaining_slots * 2.0:
            return position_priority >= 0.5 and remaining_budget >= 1.0
        if position_priority >= 1.0:
            return True
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
        """Determine if we should force nominate this player to complete the roster."""
        remaining_slots = self._get_remaining_roster_slots(team)
        if remaining_slots < 3:
            return False
        position_priority = self._calculate_position_priority(player, team)
        if remaining_budget <= remaining_slots * 2.0:
            return position_priority >= 0.5 and remaining_budget >= 1.0
        if position_priority >= 1.0:
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
        """Get the final bid amount for a player with budget constraints enforced."""
        bid = max(1.0, calculated_bid)
        enforce = getattr(team, 'enforce_budget_constraint', None)
        if callable(enforce):
            return enforce(bid, remaining_budget)
        return self._enforce_budget_constraint(bid, team, remaining_budget)
        
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

    # ------------------------------------------------------------------
    # Market tracker integration helpers
    # ------------------------------------------------------------------

    def _get_market_tracker(self):
        """Return the market tracker singleton, or None if unavailable."""
        try:
            from utils.market_tracker import get_market_tracker  # type: ignore
            return get_market_tracker()
        except Exception:
            return None

    def _get_market_inflation_rate(self) -> float:
        """Return the current market-wide inflation rate (default 1.0)."""
        tracker = self._get_market_tracker()
        if tracker is None:
            return 1.0
        try:
            return tracker.get_inflation_rate()
        except Exception:
            return 1.0

    def _get_position_inflation_rate(self, position: str) -> float:
        """Return the inflation rate for a specific position (default 1.0)."""
        tracker = self._get_market_tracker()
        if tracker is None:
            return 1.0
        try:
            return tracker.get_position_inflation_rate(position)
        except Exception:
            return 1.0

    def _get_market_budget_remaining_percentage(self) -> float:
        """Return the fraction of market budget still remaining (default 1.0)."""
        tracker = self._get_market_tracker()
        if tracker is None:
            return 1.0
        try:
            return tracker.get_remaining_budget_percentage()
        except Exception:
            return 1.0

    def _get_position_scarcity_factor(self, position: str) -> float:
        """Return the scarcity factor for a specific position (default 1.0)."""
        tracker = self._get_market_tracker()
        if tracker is None:
            return 1.0
        try:
            return tracker.get_position_scarcity(position)
        except Exception:
            return 1.0

    # ------------------------------------------------------------------
    # Dynamic position weight helpers
    # ------------------------------------------------------------------

    def _get_dynamic_position_weights(self) -> Dict[str, float]:
        """Return dynamic position weights from market tracker, with fallback defaults."""
        try:
            from utils.market_tracker import get_dynamic_position_weights  # type: ignore
            return get_dynamic_position_weights()
        except Exception:
            return {'QB': 1.0, 'RB': 1.0, 'WR': 1.0, 'TE': 1.0, 'K': 0.5, 'DST': 0.5}

    def _get_dynamic_scarcity_thresholds(self) -> Dict[str, float]:
        """Return dynamic scarcity thresholds from market tracker, with fallback defaults."""
        try:
            from utils.market_tracker import get_dynamic_scarcity_thresholds  # type: ignore
            return get_dynamic_scarcity_thresholds()
        except Exception:
            return {'high': 1.5, 'medium': 1.2, 'low': 0.8}
