"""Auction replay backtest harness for strategy value-efficiency evaluation.

Replays historical auction pick data against a given strategy and measures
how efficiently the strategy would have allocated budget. Implementation
tracked by issue #228.
"""

from __future__ import annotations

from typing import Any, List


class AuctionBacktester:
    """Replays historical auction data against a strategy to measure value efficiency.

    Args:
        strategy: An instantiated strategy object with a ``pick()`` interface.
        player_data: List of player records from the auction corpus.
    """

    def __init__(self, strategy: Any, player_data: List[dict]) -> None:
        self.strategy = strategy
        self.player_data = player_data

    def run(self) -> dict:
        """Execute the backtest replay.

        Returns:
            A dict of evaluation metrics (e.g. roster value, budget efficiency).

        Raises:
            NotImplementedError: Until issue #228 is implemented.
        """
        raise NotImplementedError("AuctionBacktester.run — tracked by #228")
