"""Strategy DTO schemas."""
from pydantic import BaseModel


class StrategyListResponse(BaseModel):
    strategies: list[str]
    count: int
