"""Property tests for services/bid_recommendation_service.py (#336).

Tests:
- _get_strategy(key) returns a Strategy for any valid strategy key
- _get_strategy returns the same cached object on repeated calls
- _get_strategy with an unknown key raises ValueError
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from strategies import AVAILABLE_STRATEGIES
from strategies.base_strategy import Strategy
from services.bid_recommendation_service import BidRecommendationService

_VALID_KEYS = sorted(AVAILABLE_STRATEGIES.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _service() -> BidRecommendationService:
    """Create a fresh BidRecommendationService with minimal config."""
    from unittest.mock import MagicMock
    from config.config_manager import DraftConfig

    mock_cfg = MagicMock(spec=DraftConfig)
    mock_cfg.strategy_type = "balanced"
    mock_cfg.sleeper_draft_id = None
    mock_cfg.data_source = "fantasypros"

    mock_manager = MagicMock()
    mock_manager.load_config.return_value = mock_cfg

    return BidRecommendationService(config_manager=mock_manager)


# ---------------------------------------------------------------------------
# Tests — strategy creation
# ---------------------------------------------------------------------------

@given(key=st.sampled_from(_VALID_KEYS))
@settings(max_examples=len(_VALID_KEYS))
def test_get_strategy_valid_key_returns_strategy(key):
    """_get_strategy(key) returns a Strategy instance for any registered key."""
    svc = _service()
    result = svc._get_strategy(key)
    assert isinstance(result, Strategy)


@given(key=st.sampled_from(_VALID_KEYS))
@settings(max_examples=len(_VALID_KEYS))
def test_get_strategy_caches_instance(key):
    """Calling _get_strategy() twice with the same key returns the same object."""
    svc = _service()
    first = svc._get_strategy(key)
    second = svc._get_strategy(key)
    assert first is second


@given(
    key=st.text(min_size=1, max_size=40).filter(lambda k: k not in AVAILABLE_STRATEGIES)
)
@settings(max_examples=30)
def test_get_strategy_unknown_key_raises_value_error(key):
    """_get_strategy() with an unknown key raises ValueError."""
    svc = _service()
    with pytest.raises(ValueError):
        svc._get_strategy(key)
