"""Bid recommendation command handler."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    pass


class BidMixin:
    """Mixin providing bid recommendation commands."""

    def get_bid_recommendation_detailed(
        self,
        player_name: str,
        current_bid: float = 1.0,
        sleeper_draft_id: Optional[str] = None,
    ) -> Dict:
        """Get detailed bid recommendation with enhanced display."""
        print(f"Analyzing '{player_name}' for bid recommendation...")

        # Try to get sleeper_draft_id from config if not provided
        if not sleeper_draft_id:
            try:
                config = self.config_manager.load_config()
                sleeper_draft_id = getattr(config, "sleeper_draft_id", None)
                if sleeper_draft_id:
                    print(f"Using Sleeper draft ID from config: {sleeper_draft_id}")
            except Exception:
                pass

        from services.bid_recommendation_service import BidRecommendationService

        service = BidRecommendationService(self.config_manager)
        result = service.recommend_bid(player_name, current_bid, sleeper_draft_id=sleeper_draft_id)

        if not result.get("success", False):
            return {
                "success": False,
                "error": result.get("error", "Failed to get recommendation"),
            }

        enhanced_result = result.copy()

        bid_diff = result["bid_difference"]
        if bid_diff > 10:
            enhanced_result["recommendation_level"] = "STRONG BUY"
        elif bid_diff > 5:
            enhanced_result["recommendation_level"] = "BUY"
        elif bid_diff > 0:
            enhanced_result["recommendation_level"] = "WEAK BUY"
        else:
            enhanced_result["recommendation_level"] = "PASS"

        value_ratio = result.get("auction_value", result.get("recommended_bid", 1)) / max(result["recommended_bid"], 1)
        if value_ratio > 1.5:
            enhanced_result["value_assessment"] = "EXCELLENT VALUE"
        elif value_ratio > 1.2:
            enhanced_result["value_assessment"] = "GOOD VALUE"
        elif value_ratio > 0.9:
            enhanced_result["value_assessment"] = "FAIR VALUE"
        else:
            enhanced_result["value_assessment"] = "OVERPRICED"

        return enhanced_result
