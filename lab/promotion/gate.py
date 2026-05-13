"""Promotion gate criteria checker for lab strategy graduation.

Evaluates whether a lab strategy meets the performance thresholds required
for promotion to the core production package. Implementation tracked by #80.
"""

from __future__ import annotations

from typing import Any, Dict


def check_promotion_criteria(strategy_name: str, metrics: Dict[str, Any]) -> bool:
    """Evaluate whether a strategy meets promotion thresholds.

    Args:
        strategy_name: The registered name of the strategy to evaluate.
        metrics: Aggregate benchmark metrics for the strategy.

    Returns:
        ``True`` if all promotion criteria are met, ``False`` otherwise.

    Raises:
        NotImplementedError: Until issue #80 is implemented.
    """
    raise NotImplementedError("check_promotion_criteria — tracked by #80")
