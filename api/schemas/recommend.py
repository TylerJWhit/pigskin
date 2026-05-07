"""Bid recommendation DTO schemas (ADR-002)."""
from typing import Optional

from pydantic import BaseModel, Field


class BidRecommendationRequest(BaseModel):
    """Request body for POST /recommend/bid."""

    player_name: str = Field(..., min_length=1, description="Name of the player to bid on")
    current_bid: float = Field(..., ge=0.0, description="Current highest bid (0 if no bids yet)")
    team_budget: float = Field(..., ge=0.0, description="Remaining team budget in dollars")
    roster_spots_remaining: int = Field(
        default=1, ge=1, description="Number of roster spots still to fill"
    )
    player_id: Optional[str] = Field(default=None, description="Sleeper player ID (optional)")
    strategy_override: Optional[str] = Field(
        default=None, description="Override the configured strategy"
    )
    sleeper_draft_id: Optional[str] = Field(
        default=None, description="Sleeper draft ID for live draft context"
    )


class BidRecommendationResponse(BaseModel):
    """Response body for POST /recommend/bid."""

    recommended_bid: float = Field(..., description="Recommended bid amount in dollars")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score [0, 1]")
    rationale: str = Field(..., description="Human-readable explanation for the recommendation")
