"""Auction DTO schemas."""
from pydantic import BaseModel, Field


class BidRequest(BaseModel):
    player_id: str = Field(min_length=1)
    bid_amount: int = Field(ge=1)
    team_name: str = Field(min_length=1)


class BidResponse(BaseModel):
    player_id: str
    winning_bid: int
    winning_team: str
    success: bool
    message: str = ""
