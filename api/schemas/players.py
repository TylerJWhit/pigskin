"""Player DTO schemas — API representations (not domain objects)."""
from typing import Optional
from pydantic import BaseModel, Field


class PlayerResponse(BaseModel):
    player_id: str
    name: str
    position: str
    nfl_team: str
    projected_points: float = Field(ge=0.0, default=0.0)
    auction_value: float = Field(ge=0.0, default=0.0)
    vor: float = Field(default=0.0)
    bye_week: Optional[int] = None
    is_drafted: bool = False


class PlayerListResponse(BaseModel):
    players: list[PlayerResponse]
    count: int
    total: int
