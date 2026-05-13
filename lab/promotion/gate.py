"""Promotion gate criteria checker for lab strategy graduation.

Evaluates whether a lab strategy meets the performance thresholds required
for promotion to the core production package. Implementation tracked by #80.
"""

from __future__ import annotations

from typing import Any, Dict, List


def check_promotion_criteria(strategy_name: str, metrics: Dict[str, Any]) -> bool:
    """Evaluate whether a strategy meets promotion thresholds.

    Args:
        strategy_name: The registered name of the strategy to evaluate.
        metrics: Aggregate benchmark metrics for the strategy.

    Returns:
        ``True`` if all promotion criteria are met, ``False`` otherwise.
    """
    gate = PromotionGate()
    return gate.evaluate([metrics])


class PromotionGate:
    """Evaluates whether lab benchmark results meet promotion criteria.

    A strategy is promoted when the average win_rate >= 0.6 and
    average efficiency >= 0.75 across all result entries.
    """

    WIN_RATE_THRESHOLD: float = 0.6
    EFFICIENCY_THRESHOLD: float = 0.75

    def evaluate(self, results: List[Dict[str, Any]]) -> bool:
        """Evaluate benchmark results against promotion thresholds.

        Args:
            results: List of result dicts, each with at least
                     ``win_rate`` and ``efficiency`` keys.

        Returns:
            ``True`` if results meet all thresholds, ``False`` otherwise.
        """
        if not results:
            return False

        avg_win_rate = sum(r.get("win_rate", 0.0) for r in results) / len(results)
        avg_efficiency = sum(r.get("efficiency", 0.0) for r in results) / len(results)

        return avg_win_rate >= self.WIN_RATE_THRESHOLD and avg_efficiency >= self.EFFICIENCY_THRESHOLD

