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

        For each player, asks the strategy for a bid via ``strategy.bid(player,
        remaining_budget)``.  A player is "won" when ``strategy_bid >=
        actual_price``.  ``efficiency_score`` is the ratio of projected auction
        value won to actual spend, capped at [0.0, 1.0].

        Returns:
            Dict with keys: efficiency_score, total_spend, total_value.
        """
        if not self.player_data:
            return {"efficiency_score": 0.0, "total_spend": 0.0, "total_value": 0.0}

        # Seed budget from total market spend so the strategy has a realistic cap.
        remaining_budget = sum(float(p.get("actual_price", 0)) for p in self.player_data)
        total_spend = 0.0
        total_value = 0.0

        for player in self.player_data:
            actual_price = float(player.get("actual_price", 0))
            auction_value = float(player.get("auction_value", 0))
            strategy_bid = float(self.strategy.bid(player, remaining_budget))
            if strategy_bid >= actual_price:
                total_spend += actual_price
                total_value += auction_value
                remaining_budget -= actual_price

        if total_spend == 0:
            efficiency_score = 0.0
        else:
            efficiency_score = min(1.0, total_value / total_spend)

        return {
            "efficiency_score": efficiency_score,
            "total_spend": total_spend,
            "total_value": total_value,
        }
