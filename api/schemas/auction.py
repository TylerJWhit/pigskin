"""Auction DTO schemas."""
from pydantic import BaseModel, Field


class BidRequest(BaseModel):
    player_id: str
    bid_amount: int = Field(ge=1)
    team_name: str


class BidResponse(BaseModel):
    player_id: str
    winning_bid: int
    winning_team: str
    success: bool
    message: str = ""
