"""Draft DTO schemas."""
from typing import Optional
from pydantic import BaseModel, Field


class DraftCreateRequest(BaseModel):
    budget: int = Field(ge=1, default=200)
    num_teams: int = Field(ge=2, le=32, default=10)
    strategy_type: str = "value"
    sleeper_draft_id: Optional[str] = None


class DraftStatusResponse(BaseModel):
    draft_id: str
    status: str
    budget: int
    num_teams: int
    players_drafted: int
