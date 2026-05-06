"""Draft router — placeholder."""
from fastapi import APIRouter

router = APIRouter(prefix="/draft", tags=["draft"])


@router.get("/", summary="Draft operations (not yet implemented)")
def draft_index() -> dict:
    return {"message": "Not yet implemented"}
