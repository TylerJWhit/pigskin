"""
Failing tests for Sprint 9 P2 bug in BidRecommendationService.

Issue covered:
  #136 — recommend_bid / recommend_nomination swallow exceptions silently

These tests FAIL against the current implementation and should PASS after fixes.
"""
from __future__ import annotations

import logging
import unittest
from unittest.mock import MagicMock, patch


def _make_service():
    from services.bid_recommendation_service import BidRecommendationService

    svc = BidRecommendationService.__new__(BidRecommendationService)
    svc.config_manager = MagicMock()
    svc.draft_service = MagicMock()
    svc._strategy_cache = {}
    svc.sleeper_available = False
    svc.sleeper_api = MagicMock()
    svc.sleeper_draft_service = MagicMock()
    svc.get_sleeper_players = MagicMock(return_value={})
    return svc


# ---------------------------------------------------------------------------
# Issue #136 — exceptions must propagate (not be swallowed) from recommend_bid
# ---------------------------------------------------------------------------

class TestRecommendBidExceptionPropagation(unittest.TestCase):
    """
    #136: recommend_bid wraps everything in `except Exception as e` and returns
    _error_response(...), swallowing the stack trace.  After the fix the
    exception must propagate so callers and loggers can observe it.
    """

    def test_config_load_error_propagates_from_recommend_bid(self):
        """
        A ValueError raised by config_manager.load_config() must propagate out
        of recommend_bid — currently it is silently swallowed.
        """
        svc = _make_service()
        svc.config_manager.load_config.side_effect = ValueError("corrupt config")

        with self.assertRaises(ValueError):
            svc.recommend_bid("Patrick Mahomes", 10.0)

    def test_strategy_error_propagates_from_recommend_bid(self):
        """
        A RuntimeError raised when creating/getting a strategy must propagate.
        """
        svc = _make_service()
        mock_config = MagicMock()
        mock_config.strategy_type = "balanced"
        mock_config.sleeper_draft_id = None
        svc.config_manager.load_config.return_value = mock_config

        with patch(
            "services.bid_recommendation_service.create_strategy",
            side_effect=RuntimeError("strategy unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                svc.recommend_bid("Patrick Mahomes", 10.0)

    def test_draft_loading_error_propagates_from_recommend_bid(self):
        """
        An IOError from the draft loading service must propagate out of
        recommend_bid rather than be silently swallowed.
        """
        svc = _make_service()
        mock_config = MagicMock()
        mock_config.strategy_type = "balanced"
        mock_config.sleeper_draft_id = None
        svc.config_manager.load_config.return_value = mock_config

        mock_strategy = MagicMock()
        with patch(
            "services.bid_recommendation_service.create_strategy",
            return_value=mock_strategy,
        ):
            svc.draft_service.load_current_draft.side_effect = IOError("disk error")
            with self.assertRaises(IOError):
                svc.recommend_bid("Patrick Mahomes", 10.0)


# ---------------------------------------------------------------------------
# Issue #136 — exceptions must propagate from recommend_nomination
# ---------------------------------------------------------------------------

class TestRecommendNominationExceptionPropagation(unittest.TestCase):
    """
    #136: recommend_nomination has the same silent-swallow pattern as
    recommend_bid.  Exceptions raised inside must propagate to the caller.
    """

    def test_config_load_error_propagates_from_recommend_nomination(self):
        """
        A ValueError raised by config_manager.load_config() must propagate out
        of recommend_nomination.
        """
        svc = _make_service()
        svc.config_manager.load_config.side_effect = ValueError("corrupt config")

        with self.assertRaises(ValueError):
            svc.recommend_nomination()

    def test_strategy_error_propagates_from_recommend_nomination(self):
        """
        A RuntimeError from strategy creation must propagate out of
        recommend_nomination.
        """
        svc = _make_service()
        mock_config = MagicMock()
        mock_config.strategy_type = "balanced"
        svc.config_manager.load_config.return_value = mock_config

        with patch(
            "services.bid_recommendation_service.create_strategy",
            side_effect=RuntimeError("strategy unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                svc.recommend_nomination()

    def test_draft_load_error_propagates_from_recommend_nomination(self):
        """
        An IOError from load_current_draft must propagate out of
        recommend_nomination rather than be silently swallowed.
        """
        svc = _make_service()
        mock_config = MagicMock()
        mock_config.strategy_type = "balanced"
        svc.config_manager.load_config.return_value = mock_config

        mock_strategy = MagicMock()
        with patch(
            "services.bid_recommendation_service.create_strategy",
            return_value=mock_strategy,
        ):
            svc.draft_service.load_current_draft.side_effect = IOError("disk error")
            with self.assertRaises(IOError):
                svc.recommend_nomination()


# ---------------------------------------------------------------------------
# Issue #136 — logger.exception must be called before any error return
# ---------------------------------------------------------------------------

class TestRecommendBidLogsException(unittest.TestCase):
    """
    #136: The fix should also add a module-level logger and call
    logger.exception (or logger.error) before returning the error response,
    so stack traces are visible in production logs.
    """

    def test_module_has_logger(self):
        """bid_recommendation_service must define a module-level logger."""
        import services.bid_recommendation_service as mod

        self.assertTrue(
            hasattr(mod, "logger"),
            "Module services/bid_recommendation_service.py must define "
            "`logger = logging.getLogger(__name__)` at module level.",
        )
        self.assertIsInstance(mod.logger, logging.Logger)


if __name__ == "__main__":
    unittest.main()
