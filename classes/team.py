"""Team class for auction draft tool."""

import logging
from typing import Dict, List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field
from .player import Player

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .strategy import Strategy


class TeamState(BaseModel):
    """Serializable snapshot of a Team's state."""

    team_id: str
    owner_id: str
    team_name: str
    budget: int = Field(ge=0)
    initial_budget: int = Field(ge=0)
    roster_player_ids: List[str] = Field(default_factory=list)


class Team:
    """Represents a fantasy team in the auction draft."""
    
    def __init__(
        self,
        team_id: str,
        owner_id: str,
        team_name: str,
        budget: int = 200,
        roster_config: Optional[dict] = None
    ):
        if int(budget) < 0:
            raise ValueError(f"budget cannot be negative, got {budget}")
        self.team_id = team_id
        self.owner_id = owner_id
        self.team_name = team_name
        self.budget = int(budget)
        self.initial_budget = int(budget)
        self.roster: List[Player] = []
        self.strategy: Optional['Strategy'] = None  # Strategy can be assigned to team
        
        # Use config-based roster positions if provided, otherwise use defaults
        if roster_config:
            self.roster_config = roster_config.copy()
            # Calculate flexible limits based on config
            self.position_limits = self._calculate_position_limits(roster_config)
        else:
            # Legacy hardcoded limits for backward compatibility
            self.roster_config = {
                'QB': 2, 'RB': 6, 'WR': 6, 'TE': 2, 'K': 1, 'DST': 1
            }
            self.position_limits = self.roster_config.copy()
            
        self.starting_lineup = {
            'QB': 1,
            'RB': 2,
            'WR': 2,
            'TE': 1,
            'FLEX': 1,  # RB/WR/TE
            'K': 1,
            'DST': 1,
            'BENCH': 6
        }
        # Add compatibility property for strategies
        self.roster_requirements = self.position_limits.copy()  # Use position_limits as roster requirements
        
    def add_player(self, player: Player, price: float) -> bool:
        """Add a player to the team if budget allows and roster space is available."""
        if price > self.budget:
            return False
        
        # Check if we have roster space
        if not self._can_add_player(player):
            return False
            
        # Track budget depletion only for teams that are running low
        self.roster.append(player)
        self.budget -= int(price)  # Ensure integer operation
        player.mark_as_drafted(int(price), self.owner_id)
        
        # Calculate remaining slots after this addition
        total_slots = sum(self.roster_config.values()) if self.roster_config else 15
        current_roster_size = len(self.roster)
        remaining_slots = total_slots - current_roster_size
        
        # Only warn when budget gets critically low
        if remaining_slots > 0 and self.budget < remaining_slots:
            logger.warning("%s: Budget ($%d) < remaining slots (%d) after paying $%d for %s",
                          self.team_name, self.budget, remaining_slots, int(price), player.name)
        
        return True
        
    def remove_player(self, player: Player) -> bool:
        """Remove a player from the team and restore budget."""
        if player in self.roster:
            self.roster.remove(player)
            if player.drafted_price:
                self.budget += int(player.drafted_price)  # Ensure integer operation
            player.is_drafted = False
            player.drafted_price = None
            player.draft_price = None
            player.drafted_by = None
            return True
        return False
        
    def get_position_count(self, position: str) -> int:
        """Get count of players at a specific position."""
        return sum(1 for player in self.roster if player.position == position)
        
    def get_players_by_position(self, position: str) -> List[Player]:
        """Get all players at a specific position."""
        return [player for player in self.roster if player.position == position]
        
    def get_remaining_roster_slots(self) -> int:
        """Return the number of roster slots not yet filled."""
        total_slots = sum(self.roster_config.values()) if self.roster_config else 15
        return max(0, total_slots - len(self.roster))

    def get_remaining_roster_slots_by_position(self) -> Dict[str, int]:
        """Return unfilled slots per position keyed by position string."""
        if not self.roster_config:
            return {}
        return {
            pos: max(0, capacity - self.get_position_count(pos))
            for pos, capacity in self.roster_config.items()
        }

    def calculate_position_priority(self, position: str) -> float:
        """Return priority for filling a position (0.0 – 2.0)."""
        if not self.roster_config:
            return 1.0
        needed = self.roster_config.get(position, 0)
        current = self.get_position_count(position)
        if current >= needed:
            return 0.1
        remaining_fraction = (needed - current) / max(needed, 1)
        return min(2.0, remaining_fraction + 0.2)

    def calculate_minimum_budget_needed(self, remaining_budget: float) -> float:
        """Estimate the minimum budget required to complete the roster."""
        slots = self.get_remaining_roster_slots()
        return max(0.0, float(slots))

    def enforce_budget_constraint(self, proposed_bid: float, remaining_budget: float) -> int:
        """Clamp a proposed bid so the team can still complete its roster."""
        slots = self.get_remaining_roster_slots()
        # Reserve $1 per remaining slot (after the current pick)
        reservation = max(0, slots - 1)
        usable = max(0.0, remaining_budget - reservation)
        return max(0, min(int(proposed_bid), int(usable)))

    def get_total_spent(self) -> float:
        """Get total amount spent on players."""
        return self.initial_budget - self.budget
        
    def get_projected_points(self) -> float:
        """Get total projected points for the team's optimal starting lineup only."""
        return self.get_starter_projected_points()
    
    def get_starter_projected_points(self) -> float:
        """Calculate projected points for optimal starting lineup only."""
        if not self.roster_config:
            # Fallback for legacy config
            return sum(player.projected_points for player in self.roster)
        
        config = self.roster_config
        starter_points = 0.0
        
        # Group players by position
        players_by_pos = {}
        for player in self.roster:
            pos = player.position
            if pos not in players_by_pos:
                players_by_pos[pos] = []
            players_by_pos[pos].append(player)
        
        # Sort each position by projected points (highest first)
        for pos in players_by_pos:
            players_by_pos[pos].sort(key=lambda p: p.projected_points, reverse=True)
        
        # Fill starting positions
        used_players = set()
        
        # Fill direct starting positions first
        for pos, needed in config.items():
            if pos in ['FLEX', 'BN', 'BENCH']:
                continue
            
            available = [p for p in players_by_pos.get(pos, []) if p not in used_players]
            for i in range(min(needed, len(available))):
                starter_points += available[i].projected_points
                used_players.add(available[i])
        
        # Fill FLEX positions with best remaining RB/WR/TE
        flex_needed = config.get('FLEX', 0)
        flex_candidates = []
        for pos in ['RB', 'WR', 'TE']:
            flex_candidates.extend([p for p in players_by_pos.get(pos, []) if p not in used_players])
        
        # Sort flex candidates by points and take the best
        flex_candidates.sort(key=lambda p: p.projected_points, reverse=True)
        for i in range(min(flex_needed, len(flex_candidates))):
            starter_points += flex_candidates[i].projected_points
            used_players.add(flex_candidates[i])
        
        return starter_points
        
    def is_roster_complete(self) -> bool:
        """Check if roster meets minimum requirements from roster_config."""
        required_positions = self.roster_config if self.roster_config else {
            'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DST': 1
        }
        for position, min_count in required_positions.items():
            if self.get_position_count(position) < min_count:
                return False
        return True

    def get_needs(self) -> List[str]:
        """Get list of positions that still need to be filled."""
        needs = []
        required_positions = self.roster_config if self.roster_config else {
            'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DST': 1
        }
        for position, min_count in required_positions.items():
            current_count = self.get_position_count(position)
            if current_count < min_count:
                needs.extend([position] * (min_count - current_count))
        return needs
        
    def set_strategy(self, strategy: 'Strategy') -> None:
        """Assign a strategy to this team."""
        self.strategy = strategy
        
    def get_strategy(self) -> Optional['Strategy']:
        """Get the team's assigned strategy."""
        return self.strategy
        
    def calculate_bid(
        self,
        player: Player,
        current_bid_or_owner=None,
        remaining_players_or_bid=None,
        owner_data_or_players=None,
        owner_data: Optional[Dict] = None,
        current_bid: Optional[float] = None,
        remaining_players: Optional[List] = None,
    ) -> int:
        """
        Calculate bid for a player using the team's strategy.
        If no strategy is assigned, returns 0.

        Accepts two calling conventions:
          Old (kwargs): calculate_bid(player, current_bid=X, remaining_players=Y, owner_data=Z)
          Old (positional): calculate_bid(player, current_bid, remaining_players, owner_data)
          New: calculate_bid(player, owner, current_bid, remaining_players)
        """
        from .owner import Owner as _Owner
        # Handle explicit keyword args (old convention via keyword)
        if current_bid is not None or remaining_players is not None:
            _current_bid = current_bid if current_bid is not None else (current_bid_or_owner if isinstance(current_bid_or_owner, (int, float)) else 0.0)
            _remaining = remaining_players if remaining_players is not None else (remaining_players_or_bid if isinstance(remaining_players_or_bid, list) else [])
            _owner_data = owner_data if owner_data is not None else (owner_data_or_players if isinstance(owner_data_or_players, dict) else None)
            mock_owner = self._build_owner(_owner_data)
        elif isinstance(current_bid_or_owner, _Owner):
            # New positional convention: (player, owner, current_bid, remaining_players)
            mock_owner = current_bid_or_owner
            _current_bid = remaining_players_or_bid if isinstance(remaining_players_or_bid, (int, float)) else 0.0
            _remaining = owner_data_or_players if isinstance(owner_data_or_players, list) else []
        else:
            # Old positional convention: (player, current_bid, remaining_players[, owner_data])
            _current_bid = current_bid_or_owner if isinstance(current_bid_or_owner, (int, float)) else 0.0
            _remaining = remaining_players_or_bid if isinstance(remaining_players_or_bid, list) else []
            _owner_data = owner_data_or_players if isinstance(owner_data_or_players, dict) else owner_data
            mock_owner = self._build_owner(_owner_data)

        if not self.strategy:
            return 0

        result = self.strategy.calculate_bid(
            player=player,
            team=self,
            owner=mock_owner,
            current_bid=_current_bid,
            remaining_budget=self.budget,
            remaining_players=_remaining if _remaining is not None else []
        )
        return int(result) if isinstance(result, (int, float)) else 0

    def _build_owner(self, owner_data=None):
        """Build an Owner object from owner_data dict or return a default."""
        from .owner import Owner
        if owner_data and isinstance(owner_data, dict):
            o = Owner(
                owner_id=self.owner_id,
                name=owner_data.get('name', 'Unknown'),
                is_human=owner_data.get('is_human', True)
            )
            if 'preferences' in owner_data:
                o.preferences.update(owner_data['preferences'])
            return o
        return Owner(owner_id=self.owner_id, name='Team Owner', is_human=False)
        
    def should_nominate_player(
        self,
        player: Player,
        owner_data: Optional[Dict] = None
    ) -> bool:
        """
        Determine if team should nominate a player using the team's strategy.
        If no strategy is assigned, returns False.
        """
        if not self.strategy:
            return False
            
        # Create a mock owner object if owner_data is provided
        from .owner import Owner
        if owner_data:
            mock_owner = Owner(
                owner_id=self.owner_id,
                name=owner_data.get('name', 'Unknown'),
                is_human=owner_data.get('is_human', True)
            )
            # Update preferences if provided
            if 'preferences' in owner_data:
                mock_owner.preferences.update(owner_data['preferences'])
        else:
            # Create basic mock owner
            mock_owner = Owner(
                owner_id=self.owner_id,
                name='Team Owner',
                is_human=False
            )
            
        return self.strategy.should_nominate(
            player=player,
            team=self,
            owner=mock_owner,
            remaining_budget=self.budget
        )
        
    def _calculate_position_limits(self, roster_config: dict) -> dict:
        """Calculate position limits that account for FLEX and BN positions."""
        limits = {}
        
        # Direct position mappings
        for pos in ['QB', 'K', 'DST']:
            if pos in roster_config:
                limits[pos] = roster_config[pos]
        
        # For RB, WR, TE - they can also fill FLEX and BN/BENCH spots
        flex_spots = roster_config.get('FLEX', 0) 
        bench_spots = roster_config.get('BN', roster_config.get('BENCH', 0))
        
        # Calculate maximum possible for flex-eligible positions
        # Each can fill their base spots + all FLEX spots + all BN spots
        for pos in ['RB', 'WR', 'TE']:
            base_spots = roster_config.get(pos, 0)
            limits[pos] = base_spots + flex_spots + bench_spots
            
        return limits
    
    def _can_add_player(self, player: Player) -> bool:
        """Check if a player can be added considering FLEX and BN positions."""
        # First check if roster is full
        total_roster_spots = sum(self.roster_config.values())
        if len(self.roster) >= total_roster_spots:
            return False
        
        # If using legacy config (no FLEX/BN), use simple position limits
        if 'FLEX' not in self.roster_config and 'BN' not in self.roster_config:
            position_count = self.get_position_count(player.position)
            return position_count < self.position_limits.get(player.position, 0)
        
        # For config with FLEX/BN, check if player can fit in any slot
        return self._can_fit_in_roster_structure(player)
    
    def _can_fit_in_roster_structure(self, player: Player) -> bool:
        """Check if player can fit considering the specific roster structure and position caps."""
        pos = player.position
        current_counts = self._get_position_counts()
        config = self.roster_config
        
        # First check position caps - prevent hoarding one position
        position_caps = self._get_position_caps()
        current_pos_count = current_counts.get(pos, 0)
        max_allowed = position_caps.get(pos, 0)
        
        if current_pos_count >= max_allowed:
            return False  # Hit position cap
        
        # Check total roster space
        total_roster_spots = sum(config.values())
        if len(self.roster) >= total_roster_spots:
            return False  # Roster full
        
        # Check if we can fit in direct position slots
        direct_needed = config.get(pos, 0)
        direct_filled = current_counts.get(pos, 0)
        
        if direct_filled < direct_needed:
            return True  # Can fill direct position slot
        
        # Check if we can fit in FLEX (for RB/WR/TE)
        if pos in ['RB', 'WR', 'TE'] and 'FLEX' in config:
            flex_needed = config['FLEX']
            flex_filled = self._count_flex_usage(current_counts)
            if flex_filled < flex_needed:
                return True  # Can fill FLEX slot
                
        # Check if we can fit in BN/BENCH slots
        if 'BN' in config or 'BENCH' in config:
            bn_needed = config.get('BN', 0) + config.get('BENCH', 0)
            bn_filled = self._count_bench_usage(current_counts)
            
            if bn_filled < bn_needed:
                return True  # Can fill BN/BENCH slot
                
        return False  # No available slots

    def _has_minimum_required_positions(self, current_counts: dict) -> bool:
        """Check if team has minimum required positions filled."""
        required_positions = self._get_required_positions()
        
        for pos, min_needed in required_positions.items():
            if current_counts.get(pos, 0) < min_needed:
                return False
        return True
    
    def _get_required_positions(self) -> dict:
        """Get minimum required positions based on config, accounting for FLEX requirements."""
        if not self.roster_config:
            return {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DST': 1}
        
        required = {}
        flex_count = self.roster_config.get('FLEX', 0)
        
        for pos, count in self.roster_config.items():
            if pos not in ['FLEX', 'BN', 'BENCH']:
                required[pos] = count
        
        # Add FLEX requirements - need at least 1 of each RB/WR/TE to cover FLEX if we have FLEX spots
        if flex_count > 0:
            # Ensure we have at least enough RB+WR+TE to fill base positions + FLEX
            # Minimum: 1 of each position to ensure we can fill any FLEX combination
            required['RB'] = max(required.get('RB', 0), 1)
            required['WR'] = max(required.get('WR', 0), 1) 
            required['TE'] = max(required.get('TE', 0), 1)
        
        return required
    
    def _get_position_counts(self) -> dict:
        """Get current count of players by position."""
        counts = {}
        for player in self.roster:
            pos = player.position
            counts[pos] = counts.get(pos, 0) + 1
        return counts
    
    def _count_flex_usage(self, position_counts: dict) -> int:
        """Count how many FLEX spots are being used by RB/WR/TE players."""
        config = self.roster_config
        flex_usage = 0
        
        for pos in ['RB', 'WR', 'TE']:
            direct_slots = config.get(pos, 0)
            current_count = position_counts.get(pos, 0)
            excess = max(0, current_count - direct_slots)
            flex_usage += excess
            
        return flex_usage
    
    def _count_bench_usage(self, position_counts: dict) -> int:
        """Count how many BN/BENCH spots are being used."""
        config = self.roster_config
        total_direct_and_flex = 0
        
        # Count all direct position slots
        for pos, count in config.items():
            if pos not in ['FLEX', 'BN', 'BENCH']:
                total_direct_and_flex += count
        
        # Add FLEX slots
        total_direct_and_flex += config.get('FLEX', 0)
        
        # Current roster size minus direct+flex = bench usage
        current_roster_size = len(self.roster)
        return max(0, current_roster_size - total_direct_and_flex)
    
    def get_available_budget_for_bidding(self) -> float:
        """Get budget available for bidding, reserving $1 per unfilled required position."""
        current_counts = self._get_position_counts()
        required_positions = self._get_required_positions()
        
        # Calculate how many required positions still need to be filled
        unfilled_required = 0
        for pos, min_needed in required_positions.items():
            current_filled = current_counts.get(pos, 0)
            if current_filled < min_needed:
                unfilled_required += (min_needed - current_filled)
        
        # Reserve $1 for each unfilled required position
        reserved_budget = unfilled_required * 1.0
        available_budget = max(0, self.budget - reserved_budget)
        
        return available_budget
    
    def can_bid(self, player: Optional[Player] = None, min_bid: float = 1.0) -> bool:
        """
        Check if team can participate in bidding.
        
        Args:
            player: Optional player to check if team can use them
            min_bid: Minimum bid amount to check against budget
            
        Returns:
            True if team can bid, False otherwise
        """
        # Check if team has enough budget for minimum bid
        if self.budget < min_bid:
            return False
            
        # Check if roster is already full
        total_roster_spots = sum(self.roster_config.values())
        if len(self.roster) >= total_roster_spots:
            return False
            
        # If a specific player is provided, check if team can use them
        if player is not None:
            if not self._can_add_player(player):
                return False
                
        return True
    
    def has_critical_position_need(self, player_position: str) -> bool:
        """Check if adding this position would address a critical team need."""
        current_counts = self._get_position_counts()
        required_positions = self._get_required_positions()
        
        # Check if this position is completely missing and required
        current_filled = current_counts.get(player_position, 0)
        min_needed = required_positions.get(player_position, 0)
        
        # Critical need: we have 0 of a required position
        if min_needed > 0 and current_filled == 0:
            return True
            
        # Also critical if we're low on total distinct positions
        distinct_positions_needed = len([pos for pos, count in required_positions.items() if count > 0])
        distinct_positions_filled = len([pos for pos, count in current_counts.items() if count > 0])
        
        # If we're missing more than 2 position types, this is critical
        if distinct_positions_needed - distinct_positions_filled > 2:
            return player_position in required_positions
            
        return False

    def __str__(self) -> str:
        return f"{self.team_name} (Owner: {self.owner_id}, Budget: ${self.budget:.2f})"
        
    def __repr__(self) -> str:
        return f"Team(id='{self.team_id}', name='{self.team_name}', budget={self.budget})"
        
    def to_dict(self) -> Dict:
        """Convert team to dictionary representation."""
        return {
            'team_id': self.team_id,
            'owner_id': self.owner_id,
            'team_name': self.team_name,
            'budget': self.budget,
            'initial_budget': self.initial_budget,
            'roster': [player.to_dict() for player in self.roster],
            'strategy': self.strategy.name if self.strategy else None,
            'total_spent': self.get_total_spent(),
            'projected_points': self.get_projected_points(),
            'is_complete': self.is_roster_complete(),
            'needs': self.get_needs()
        }

    def get_state(self) -> "TeamState":
        """Return a serializable Pydantic snapshot of the team's current state."""
        return TeamState(
            team_id=self.team_id,
            owner_id=self.owner_id,
            team_name=self.team_name,
            budget=self.budget,
            initial_budget=self.initial_budget,
            roster_player_ids=[p.player_id for p in self.roster],
        )
    
    def _get_position_caps(self) -> dict:
        """Get maximum allowed players per position based on roster structure."""
        if not self.roster_config:
            return {'QB': 2, 'RB': 8, 'WR': 8, 'TE': 2, 'K': 1, 'DST': 1}
            
        config = self.roster_config
        bn_slots = config.get('BN', 0) + config.get('BENCH', 0)
        flex_slots = config.get('FLEX', 0)
        
        caps = {}
        
        # QB: Number of starters + 1
        caps['QB'] = config.get('QB', 0) + 1
        
        # RB/WR: 2 + FLEX + some BN (40% of bench for skill positions)
        rb_wr_bench = int(bn_slots * 0.4)  # 40% of bench for RB/WR
        caps['RB'] = 2 + flex_slots + rb_wr_bench
        caps['WR'] = 2 + flex_slots + rb_wr_bench  
        
        # TE: Number of TEs + 1
        caps['TE'] = config.get('TE', 0) + 1
        
        # K: Number of starters (no bench)
        caps['K'] = config.get('K', 0)
        
        # DST: Number of starters (no bench)
        caps['DST'] = config.get('DST', 0)
        
        return caps
