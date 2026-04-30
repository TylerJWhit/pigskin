"""Auction router — placeholder."""
from fastapi import APIRouter

router = APIRouter(prefix="/auction", tags=["auction"])


@router.get("/", summary="Auction operations (not yet implemented)")
def auction_index() -> dict:
    return {"message": "Not yet implemented"}
