"""AuctionBacktester — replays historical auction data with a candidate strategy.

Issue #196: AuctionBacktester(strategy, player_data).run() implementation.
"""

from __future__ import annotations

from typing import Any, Dict, List


class AuctionBacktester:
    """Replays historical auction data against a strategy to measure value efficiency.

    Args:
        strategy: An instantiated strategy object with a pick() interface.
        player_data: List of player records from the auction corpus.
    """

    def __init__(self, strategy: Any, player_data: List[dict]) -> None:
        self.strategy = strategy
        self.player_data = player_data

    def run(self) -> Dict[str, float]:
        """Execute the backtest replay.

        Computes efficiency_score = sum(auction_value) / sum(actual_price),
        capped at [0.0, 1.0].

        Returns:
            Dict with keys: efficiency_score, total_spend, total_value.
        """
        if not self.player_data:
            return {"efficiency_score": 0.0, "total_spend": 0.0, "total_value": 0.0}

        total_value = sum(float(p.get("auction_value", 0)) for p in self.player_data)
        total_spend = sum(float(p.get("actual_price", 0)) for p in self.player_data)

        if total_spend == 0:
            efficiency_score = 0.0
        else:
            efficiency_score = min(1.0, total_value / total_spend)

        return {
            "efficiency_score": efficiency_score,
            "total_spend": total_spend,
            "total_value": total_value,
        }
