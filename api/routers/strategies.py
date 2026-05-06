"""Strategies router — list available strategies."""
from fastapi import APIRouter
from classes import AVAILABLE_STRATEGIES

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("/", summary="List available strategies")
def list_strategies() -> list[str]:
    """Return the names of all available bidding strategies."""
    return list(AVAILABLE_STRATEGIES.keys())
