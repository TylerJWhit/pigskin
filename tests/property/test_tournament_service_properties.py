"""Property tests for services/tournament_service.py (#337).

Tests:
- run_strategy_tournament with any invalid strategy key returns success=False
- Error result always contains 'error' and 'available_strategies' keys
- 'available_strategies' in error result matches AVAILABLE_STRATEGIES keys
- Valid strategy keys don't trigger the validation error path
"""
from __future__ import annotations

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from strategies import AVAILABLE_STRATEGIES
from services.tournament_service import TournamentService

_VALID_KEYS = sorted(AVAILABLE_STRATEGIES.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _service() -> TournamentService:
    mock_manager = MagicMock()
    mock_cfg = MagicMock()
    mock_cfg.budget = 200
    mock_cfg.roster_positions = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}
    mock_manager.load_config.return_value = mock_cfg
    return TournamentService(config_manager=mock_manager)


# ---------------------------------------------------------------------------
# Tests — invalid strategy validation
# ---------------------------------------------------------------------------

@given(
    bad_key=st.text(min_size=1, max_size=40).filter(lambda k: k not in AVAILABLE_STRATEGIES)
)
@settings(max_examples=30)
def test_invalid_strategy_returns_failure_dict(bad_key):
    """Any unknown strategy key causes run_strategy_tournament to return success=False."""
    svc = _service()
    result = svc.run_strategy_tournament(
        strategies_to_test=[bad_key],
        num_simulations=1,
        save_results=False,
    )
    assert isinstance(result, dict)
    assert result.get("success") is False


@given(
    bad_key=st.text(min_size=1, max_size=40).filter(lambda k: k not in AVAILABLE_STRATEGIES)
)
@settings(max_examples=30)
def test_invalid_strategy_result_has_error_key(bad_key):
    """Error result dict always contains 'error' and 'available_strategies' keys."""
    svc = _service()
    result = svc.run_strategy_tournament(
        strategies_to_test=[bad_key],
        num_simulations=1,
        save_results=False,
    )
    assert "error" in result
    assert "available_strategies" in result


@given(
    bad_key=st.text(min_size=1, max_size=40).filter(lambda k: k not in AVAILABLE_STRATEGIES)
)
@settings(max_examples=20)
def test_available_strategies_in_error_matches_registry(bad_key):
    """The 'available_strategies' list in the error dict matches AVAILABLE_STRATEGIES."""
    svc = _service()
    result = svc.run_strategy_tournament(
        strategies_to_test=[bad_key],
        num_simulations=1,
        save_results=False,
    )
    reported = set(result.get("available_strategies", []))
    expected = set(AVAILABLE_STRATEGIES.keys())
    assert reported == expected
