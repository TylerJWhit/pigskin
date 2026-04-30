"""Players router — placeholder."""
from fastapi import APIRouter

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/", summary="List players (not yet implemented)")
def list_players() -> dict:
    return {"message": "Not yet implemented"}
