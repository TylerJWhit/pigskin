"""Recommend router — bid recommendation endpoint (ADR-002, issue #179)."""
from fastapi import APIRouter, HTTPException

from api.schemas.recommend import BidRecommendationRequest, BidRecommendationResponse
from services.bid_recommendation_service import BidRecommendationService

router = APIRouter(prefix="/recommend", tags=["recommend"])

_service = BidRecommendationService()


@router.post(
    "/bid",
    response_model=BidRecommendationResponse,
    summary="Get a bid recommendation for a player",
    description=(
        "Returns a recommended bid amount, confidence score, and rationale "
        "for the requested player based on the configured bidding strategy. "
        "Returns HTTP 503 if no draft context is available."
    ),
)
def recommend_bid(request: BidRecommendationRequest) -> BidRecommendationResponse:
    """POST /recommend/bid — ADR-002."""
    team_context = {
        "budget": request.team_budget,
        "roster_spots_remaining": request.roster_spots_remaining,
    }

    result = _service.recommend_bid(
        player_name=request.player_name,
        current_bid=request.current_bid,
        team_context=team_context,
        strategy_override=request.strategy_override,
        sleeper_draft_id=request.sleeper_draft_id,
    )

    # Service signals failure with success=False
    if not result.get("success", True) or result.get("error"):
        raise HTTPException(
            status_code=503,
            detail=result.get("error", "Draft context unavailable"),
        )

    return BidRecommendationResponse(
        recommended_bid=float(result.get("recommended_bid", 1.0)),
        confidence=float(result.get("confidence", 0.5)),
        rationale=str(result.get("rationale", result.get("reasoning", ""))),
    )
