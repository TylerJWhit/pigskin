"""Player class for auction draft tool."""

from typing import Dict, Optional


class Player:
    """Represents a fantasy football player in the auction draft."""
    
    def __init__(
        self,
        player_id: str,
        name: str,
        position: str,
        team: str,
        projected_points: float = 0.0,
        auction_value: float = 0.0,
        bye_week: Optional[int] = None
    ):
        if player_id is None:
            raise ValueError("player_id cannot be None")
        if not isinstance(projected_points, (int, float)):
            raise TypeError(f"projected_points must be numeric, got {type(projected_points).__name__}")
        self.player_id = player_id
        self.name = name
        self.position = position
        self.team = team
        self.projected_points = projected_points
        self.auction_value = auction_value
        self.bye_week = bye_week
        self.is_drafted = False
        self.drafted_price: Optional[float] = None
        self.draft_price: Optional[float] = None  # Alias for drafted_price
        self.drafted_by: Optional[str] = None
        
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
        return f"{self.name} ({self.position}, {self.team})"
        
    def __repr__(self) -> str:
        return f"Player(id='{self.player_id}', name='{self.name}', position='{self.position}')"
        
    def to_dict(self) -> Dict:
        """Convert player to dictionary representation."""
        return {
            'player_id': self.player_id,
            'name': self.name,
            'position': self.position,
            'team': self.team,
            'projected_points': self.projected_points,
            'auction_value': self.auction_value,
            'bye_week': self.bye_week,
            'is_drafted': self.is_drafted,
            'drafted_price': self.drafted_price,
            'drafted_by': self.drafted_by
        }
