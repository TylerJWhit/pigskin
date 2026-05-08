"""
Failing tests for Sprint 9 P2 bug in TournamentService.

Issue covered:
  #137 — stop_tournament() doesn't terminate parallel workers

These tests FAIL against the current implementation and should PASS after fixes.
"""
from __future__ import annotations

import concurrent.futures
import unittest
from unittest.mock import MagicMock, patch


def _make_service():
    mock_config_manager = MagicMock()
    mock_config = MagicMock()
    mock_config.budget = 200
    mock_config.data_source = "fantasypros"
    mock_config.data_path = "data/sheets"
    mock_config.min_projected_points = 0
    mock_config.roster_positions = {
        "QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1, "BN": 5
    }
    mock_config_manager.load_config.return_value = mock_config

    with patch("services.tournament_service.ConfigManager", return_value=mock_config_manager):
        from services.tournament_service import TournamentService
        svc = TournamentService(config_manager=mock_config_manager)
    return svc, mock_config, mock_config_manager


# ---------------------------------------------------------------------------
# Issue #137 — stop_tournament must cancel/terminate in-flight workers
# ---------------------------------------------------------------------------

class TestStopTournamentTerminatesWorkers(unittest.TestCase):
    """
    #137: stop_tournament() only sets `self.current_tournament.is_running = False`
    but does not cancel dispatched concurrent.futures workers.

    After the fix, stop_tournament should shut down the tracked executor so
    in-flight simulations are actually cancelled.
    """

    def test_stop_tournament_shuts_down_tracked_executor(self):
        """
        After the fix, TournamentService must track its executor and call
        executor.shutdown(wait=False) when stop_tournament() is invoked.

        Currently stop_tournament() ignores any executor, so this test FAILS.
        """
        svc, _, _ = _make_service()

        mock_tournament = MagicMock()
        mock_tournament.completed_drafts = []
        mock_tournament.is_running = True

        mock_executor = MagicMock(spec=concurrent.futures.ThreadPoolExecutor)
        # Set the executor reference that the fix should store on the service
        svc._executor = mock_executor
        svc.current_tournament = mock_tournament

        result = svc.stop_tournament()

        self.assertTrue(result["success"])
        mock_executor.shutdown.assert_called_once_with(wait=False), (
            "stop_tournament() must call executor.shutdown(wait=False) to cancel "
            "in-flight workers, but it did not."
        )

    def test_stop_tournament_cancels_pending_futures(self):
        """
        If the service stores pending futures, stop_tournament() must cancel them.

        Currently no futures are tracked, so this test FAILS.
        """
        svc, _, _ = _make_service()

        mock_tournament = MagicMock()
        mock_tournament.completed_drafts = []
        mock_tournament.is_running = True

        # Create mock futures that are not yet done
        future1 = MagicMock(spec=concurrent.futures.Future)
        future1.done.return_value = False
        future1.cancel.return_value = True

        future2 = MagicMock(spec=concurrent.futures.Future)
        future2.done.return_value = False
        future2.cancel.return_value = True

        # Set the futures list that the fix should store on the service
        svc._pending_futures = [future1, future2]
        svc.current_tournament = mock_tournament

        result = svc.stop_tournament()

        self.assertTrue(result["success"])
        future1.cancel.assert_called_once(), (
            "stop_tournament() must cancel pending futures — future1.cancel() was not called."
        )
        future2.cancel.assert_called_once(), (
            "stop_tournament() must cancel pending futures — future2.cancel() was not called."
        )

    def test_stop_tournament_with_no_executor_still_succeeds(self):
        """
        stop_tournament() must remain safe when no executor is tracked
        (e.g. no tournament has been started, or it completed already).
        This test documents the expected graceful-degradation behaviour.
        """
        svc, _, _ = _make_service()

        mock_tournament = MagicMock()
        mock_tournament.completed_drafts = []
        mock_tournament.is_running = True
        svc.current_tournament = mock_tournament
        # No _executor or _pending_futures set

        result = svc.stop_tournament()

        # Should still succeed without raising
        self.assertTrue(result["success"])

    def test_stop_tournament_sets_is_running_false(self):
        """
        Baseline: stop_tournament() must still set is_running = False
        (this should already pass; kept as a regression guard).
        """
        svc, _, _ = _make_service()

        mock_tournament = MagicMock()
        mock_tournament.completed_drafts = []
        mock_tournament.is_running = True
        svc.current_tournament = mock_tournament

        svc.stop_tournament()

        self.assertFalse(mock_tournament.is_running)


if __name__ == "__main__":
    unittest.main()
