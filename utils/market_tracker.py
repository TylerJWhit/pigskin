"""Market tracker utilities for tracking draft market conditions.

This module provides singleton access to market tracking state during
an auction draft. The tracker monitors inflation, budget consumption,
and position scarcity in real time.
"""

from typing import Dict


_market_tracker_instance = None


def get_market_tracker():
    """Return the market tracker singleton instance, or None if not initialized."""
    return _market_tracker_instance


def set_market_tracker(tracker) -> None:
    """Set the market tracker singleton instance."""
    global _market_tracker_instance
    _market_tracker_instance = tracker


def get_dynamic_position_weights() -> Dict[str, float]:
    """Return dynamic position weights based on current market conditions.

    Weights are multipliers applied to base value calculations. A weight > 1.0
    increases bidding aggression for that position; < 1.0 decreases it.
    """
    tracker = get_market_tracker()
    if tracker is not None and hasattr(tracker, 'get_position_weights'):
        try:
            return tracker.get_position_weights()
        except Exception:
            pass
    return {'QB': 1.0, 'RB': 1.0, 'WR': 1.0, 'TE': 1.0, 'K': 0.5, 'DST': 0.5}


def get_dynamic_scarcity_thresholds() -> Dict[str, float]:
    """Return dynamic scarcity thresholds based on current market conditions.

    Thresholds define the scarcity factor cutoffs for high/medium/low
    scarcity classification.
    """
    tracker = get_market_tracker()
    if tracker is not None and hasattr(tracker, 'get_scarcity_thresholds'):
        try:
            return tracker.get_scarcity_thresholds()
        except Exception:
            pass
    return {'high': 1.5, 'medium': 1.2, 'low': 0.8}
