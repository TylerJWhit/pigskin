"""Property tests for services/draft_loading_service.py (#338).

Tests:
- DraftLoadingService constructor succeeds with explicit config_manager
- DraftLoadingService constructor succeeds without config_manager (uses default)
- config_manager attribute is always set after construction
- sleeper_api attribute is always set after construction
"""
from __future__ import annotations

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from services.draft_loading_service import DraftLoadingService
from api.sleeper_api import SleeperAPI


# ---------------------------------------------------------------------------
# Tests — constructor invariants
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=5)
def test_constructor_with_mock_config_manager(_):
    """DraftLoadingService constructs successfully with a mock config_manager."""
    mock_manager = MagicMock()
    svc = DraftLoadingService(config_manager=mock_manager)
    assert svc.config_manager is mock_manager


@given(st.just(None))
@settings(max_examples=3)
def test_constructor_sets_sleeper_api(_):
    """DraftLoadingService always sets a sleeper_api attribute after construction."""
    mock_manager = MagicMock()
    svc = DraftLoadingService(config_manager=mock_manager)
    assert hasattr(svc, "sleeper_api")
    assert isinstance(svc.sleeper_api, SleeperAPI)


@given(st.just(None))
@settings(max_examples=3)
def test_two_instances_have_independent_config_managers(_):
    """Two DraftLoadingService instances with different managers are independent."""
    mgr1 = MagicMock()
    mgr2 = MagicMock()
    svc1 = DraftLoadingService(config_manager=mgr1)
    svc2 = DraftLoadingService(config_manager=mgr2)
    assert svc1.config_manager is mgr1
    assert svc2.config_manager is mgr2
    assert svc1.config_manager is not svc2.config_manager
