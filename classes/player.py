"""Player class for auction draft tool."""

from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Player(BaseModel):
    """Represents a fantasy football player in the auction draft."""

    player_id: str
    name: str = Field(min_length=1)
    position: Literal['QB', 'RB', 'WR', 'TE', 'K', 'DST', 'FLEX', 'SF', 'IDP', 'DL', 'LB', 'DB']
    nfl_team: str  # renamed from 'team' to avoid pydantic BaseModel field collision
    projected_points: float = Field(ge=0.0, default=0.0)
    auction_value: float = Field(ge=0.0, default=0.0)
    bye_week: Optional[int] = Field(ge=1, le=18, default=None)
    is_drafted: bool = False
    drafted_price: Optional[float] = None
    draft_price: Optional[float] = None  # backward-compat alias; synced with drafted_price
    drafted_by: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    def __init__(
        self,
        player_id: str,
        name: str = '',
        position: str = 'RB',
        team: str = '',
        projected_points: float = 0.0,
        auction_value: float = 0.0,
        bye_week: Optional[int] = None,
        *,
        nfl_team: str = '',
        **kwargs,
    ):
        """Initialize Player with backward-compatible positional and keyword arguments.

        Accepts both ``team=`` (legacy) and ``nfl_team=`` (new) for the NFL team field.
        Positional arg order mirrors the original class: player_id, name, position, team,
        projected_points, auction_value, bye_week.
        """
        final_nfl_team = nfl_team if nfl_team else team
        super().__init__(
            player_id=player_id,
            name=name,
            position=position,
            nfl_team=final_nfl_team,
            projected_points=projected_points,
            auction_value=auction_value,
            bye_week=bye_week,
            **kwargs,
        )

    @field_validator('player_id')
    @classmethod
    def player_id_not_none(cls, v: str) -> str:
        if v is None:
            raise ValueError("player_id cannot be None")
        return v

    @property
    def team(self) -> str:
        """Backward-compatible alias for nfl_team."""
        return self.nfl_team

    def __hash__(self) -> int:
        return hash(self.player_id)

    def mark_as_drafted(self, price: float, owner_id: str) -> None:
        """Mark player as drafted with the given price and owner."""
        self.is_drafted = True
        self.drafted_price = price
        self.draft_price = price  # Keep alias in sync
        self.drafted_by = owner_id

    def get_value_over_replacement(self, replacement_value: float) -> float:
        """Calculate value over replacement player."""
        return max(0, self.projected_points - replacement_value)

    def __str__(self) -> str:
        return f"{self.name} ({self.position}, {self.nfl_team})"

    def __repr__(self) -> str:
        return f"Player(id='{self.player_id}', name='{self.name}', position='{self.position}')"

    def to_dict(self) -> Dict:
        """Convert player to dictionary representation."""
        return {
            'player_id': self.player_id,
            'name': self.name,
            'position': self.position,
            'team': self.nfl_team,  # keep 'team' key for backward compat
            'projected_points': self.projected_points,
            'auction_value': self.auction_value,
            'bye_week': self.bye_week,
            'is_drafted': self.is_drafted,
            'drafted_price': self.drafted_price,
            'drafted_by': self.drafted_by
        }
