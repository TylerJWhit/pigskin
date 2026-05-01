"""Unit tests for SleeperDraftService — closes #245."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSleeperDraftServiceGetUserDrafts(unittest.TestCase):
    """Tests for SleeperDraftService.get_user_drafts()."""

    def _service(self):
        from services.sleeper_draft_service import SleeperDraftService
        svc = SleeperDraftService()
        svc.sleeper_api = MagicMock()
        return svc

    # --- user not found ---
    def test_user_not_found_returns_failure(self):
        svc = self._service()
        svc.sleeper_api.get_user = AsyncMock(return_value=None)

        result = asyncio.run(svc.get_user_drafts("nobody"))

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    # --- no leagues ---
    def test_no_leagues_returns_failure(self):
        svc = self._service()
        svc.sleeper_api.get_user = AsyncMock(return_value={"user_id": "u1"})
        svc.sleeper_api.get_user_leagues = AsyncMock(return_value=[])

        result = asyncio.run(svc.get_user_drafts("testuser"))

        self.assertFalse(result["success"])
        self.assertIn("No leagues", result["error"])

    # --- success with drafts ---
    def test_success_returns_drafts_list(self):
        svc = self._service()
        svc.sleeper_api.get_user = AsyncMock(return_value={"user_id": "u1"})
        svc.sleeper_api.get_user_leagues = AsyncMock(return_value=[
            {"league_id": "l1", "name": "Test League", "draft_id": "d1"},
        ])
        svc.sleeper_api.get_draft = AsyncMock(return_value={"draft_id": "d1", "type": "auction"})

        result = asyncio.run(svc.get_user_drafts("testuser"))

        self.assertTrue(result["success"])
        self.assertEqual(len(result["drafts"]), 1)
        self.assertEqual(result["drafts"][0]["draft_id"], "d1")
        self.assertEqual(result["drafts"][0]["league_name"], "Test League")

    # --- league without draft_id is skipped ---
    def test_league_without_draft_id_skipped(self):
        svc = self._service()
        svc.sleeper_api.get_user = AsyncMock(return_value={"user_id": "u1"})
        svc.sleeper_api.get_user_leagues = AsyncMock(return_value=[
            {"league_id": "l1", "name": "No Draft League"},  # no draft_id
        ])

        result = asyncio.run(svc.get_user_drafts("testuser"))

        self.assertTrue(result["success"])
        self.assertEqual(result["drafts"], [])

    # --- exception → failure dict ---
    def test_exception_returns_error_dict(self):
        svc = self._service()
        svc.sleeper_api.get_user = AsyncMock(side_effect=RuntimeError("API down"))

        result = asyncio.run(svc.get_user_drafts("testuser"))

        self.assertFalse(result["success"])
        self.assertIn("Error", result["error"])


class TestSleeperDraftServiceDisplayDraftInfo(unittest.TestCase):

    def _service(self):
        from services.sleeper_draft_service import SleeperDraftService
        svc = SleeperDraftService()
        svc.sleeper_api = MagicMock()
        return svc

    def test_draft_not_found_returns_failure(self):
        svc = self._service()
        svc.sleeper_api.get_draft = AsyncMock(return_value=None)

        result = asyncio.run(svc.display_draft_info("d999"))

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    def test_success_with_league_id(self):
        svc = self._service()
        svc.sleeper_api.get_draft = AsyncMock(return_value={"draft_id": "d1", "league_id": "l1"})
        svc.sleeper_api.get_draft_picks = AsyncMock(return_value=[])
        svc.sleeper_api.get_league_users = AsyncMock(return_value=[{"user_id": "u1"}])

        with (
            patch("services.sleeper_draft_service.get_sleeper_players", return_value={}),
            patch("services.sleeper_draft_service.print_sleeper_draft"),
        ):
            result = asyncio.run(svc.display_draft_info("d1"))

        self.assertTrue(result["success"])
        self.assertEqual(result["draft_info"]["draft_id"], "d1")

    def test_success_without_league_id(self):
        svc = self._service()
        svc.sleeper_api.get_draft = AsyncMock(return_value={"draft_id": "d1"})  # no league_id
        svc.sleeper_api.get_draft_picks = AsyncMock(return_value=[])

        with (
            patch("services.sleeper_draft_service.get_sleeper_players", return_value={}),
            patch("services.sleeper_draft_service.print_sleeper_draft"),
        ):
            result = asyncio.run(svc.display_draft_info("d1"))

        self.assertTrue(result["success"])

    def test_exception_returns_error_dict(self):
        svc = self._service()
        svc.sleeper_api.get_draft = AsyncMock(side_effect=RuntimeError("timeout"))

        result = asyncio.run(svc.display_draft_info("d1"))

        self.assertFalse(result["success"])


class TestSleeperDraftServiceDisplayLeagueRosters(unittest.TestCase):

    def _service(self):
        from services.sleeper_draft_service import SleeperDraftService
        svc = SleeperDraftService()
        svc.sleeper_api = MagicMock()
        return svc

    def test_no_rosters_returns_failure(self):
        svc = self._service()
        svc.sleeper_api.get_league_rosters = AsyncMock(return_value=[])

        result = asyncio.run(svc.display_league_rosters("l1"))

        self.assertFalse(result["success"])
        self.assertIn("No rosters", result["error"])

    def test_success_returns_rosters(self):
        svc = self._service()
        svc.sleeper_api.get_league_rosters = AsyncMock(return_value=[{"roster_id": 1}])
        svc.sleeper_api.get_league_users = AsyncMock(return_value=[{"user_id": "u1"}])

        with (
            patch("services.sleeper_draft_service.get_sleeper_players", return_value={}),
            patch("services.sleeper_draft_service.print_sleeper_league"),
        ):
            result = asyncio.run(svc.display_league_rosters("l1"))

        self.assertTrue(result["success"])
        self.assertEqual(len(result["rosters"]), 1)

    def test_exception_returns_error_dict(self):
        svc = self._service()
        svc.sleeper_api.get_league_rosters = AsyncMock(side_effect=IOError("network"))

        result = asyncio.run(svc.display_league_rosters("l1"))

        self.assertFalse(result["success"])


class TestSleeperDraftServiceListUserLeagues(unittest.TestCase):

    def _service(self):
        from services.sleeper_draft_service import SleeperDraftService
        svc = SleeperDraftService()
        svc.sleeper_api = MagicMock()
        return svc

    def test_user_not_found_returns_failure(self):
        svc = self._service()
        svc.sleeper_api.get_user = AsyncMock(return_value=None)

        result = asyncio.run(svc.list_user_leagues("ghost"))

        self.assertFalse(result["success"])

    def test_no_leagues_returns_failure(self):
        svc = self._service()
        svc.sleeper_api.get_user = AsyncMock(return_value={"user_id": "u1"})
        svc.sleeper_api.get_user_leagues = AsyncMock(return_value=[])

        result = asyncio.run(svc.list_user_leagues("testuser"))

        self.assertFalse(result["success"])

    def test_success_returns_leagues(self):
        svc = self._service()
        svc.sleeper_api.get_user = AsyncMock(return_value={"user_id": "u1"})
        svc.sleeper_api.get_user_leagues = AsyncMock(return_value=[
            {"league_id": "l1", "name": "My League", "total_rosters": 12,
             "status": "complete", "scoring_settings": {"type": "ppr"},
             "draft_id": "d1"},
        ])

        result = asyncio.run(svc.list_user_leagues("testuser"))

        self.assertTrue(result["success"])
        self.assertEqual(len(result["leagues"]), 1)


class TestSleeperDraftServiceGetCurrentDraftStatus(unittest.TestCase):

    def _service(self):
        from services.sleeper_draft_service import SleeperDraftService
        svc = SleeperDraftService()
        svc.sleeper_api = MagicMock()
        return svc

    def test_propagates_failure_from_get_user_drafts(self):
        svc = self._service()
        # get_user returns None → get_user_drafts fails
        svc.sleeper_api.get_user = AsyncMock(return_value=None)

        result = asyncio.run(svc.get_current_draft_status("nobody"))

        self.assertFalse(result["success"])

    def test_active_draft_classified_correctly(self):
        svc = self._service()
        svc.sleeper_api.get_user = AsyncMock(return_value={"user_id": "u1"})
        svc.sleeper_api.get_user_leagues = AsyncMock(return_value=[
            {"league_id": "l1", "name": "Active League", "draft_id": "d1"},
        ])
        svc.sleeper_api.get_draft = AsyncMock(return_value={
            "draft_id": "d1",
            "league_name": "Active League",
            "status": "drafting",
            "type": "auction",
            "settings": {"rounds": 16, "pick_timer": 60},
        })

        result = asyncio.run(svc.get_current_draft_status("testuser"))

        self.assertTrue(result["success"])
        self.assertEqual(len(result["active_drafts"]), 1)
        self.assertEqual(len(result["completed_drafts"]), 0)

    def test_completed_draft_classified_correctly(self):
        svc = self._service()
        svc.sleeper_api.get_user = AsyncMock(return_value={"user_id": "u1"})
        svc.sleeper_api.get_user_leagues = AsyncMock(return_value=[
            {"league_id": "l1", "name": "Done League", "draft_id": "d1"},
        ])
        svc.sleeper_api.get_draft = AsyncMock(return_value={
            "draft_id": "d1", "league_name": "Done League", "status": "complete"
        })

        result = asyncio.run(svc.get_current_draft_status("testuser"))

        self.assertTrue(result["success"])
        self.assertEqual(len(result["active_drafts"]), 0)
        self.assertEqual(len(result["completed_drafts"]), 1)

    def test_no_drafts_returns_empty_lists(self):
        svc = self._service()
        svc.sleeper_api.get_user = AsyncMock(return_value={"user_id": "u1"})
        svc.sleeper_api.get_user_leagues = AsyncMock(return_value=[
            {"league_id": "l1", "name": "League", "draft_id": "d1"},
        ])
        svc.sleeper_api.get_draft = AsyncMock(return_value={
            "draft_id": "d1", "status": "pre_draft",
        })

        result = asyncio.run(svc.get_current_draft_status("testuser"))

        self.assertTrue(result["success"])
        self.assertEqual(len(result["active_drafts"]), 1)

    def test_exception_returns_error_dict(self):
        svc = self._service()
        svc.sleeper_api.get_user = AsyncMock(side_effect=ConnectionError("down"))

        result = asyncio.run(svc.get_current_draft_status("testuser"))

        self.assertFalse(result["success"])


class TestSleeperDraftServiceConvenienceFunctions(unittest.TestCase):
    """Tests for the sync wrapper convenience functions."""

    def test_display_sleeper_draft_calls_service(self):
        with patch("services.sleeper_draft_service.SleeperDraftService") as MockSvc:
            mock_instance = MagicMock()
            mock_instance.display_draft_info = AsyncMock(return_value={"success": True})
            MockSvc.return_value = mock_instance

            from services.sleeper_draft_service import display_sleeper_draft
            result = display_sleeper_draft("d1")

        self.assertEqual(result["success"], True)

    def test_display_sleeper_league_calls_service(self):
        with patch("services.sleeper_draft_service.SleeperDraftService") as MockSvc:
            mock_instance = MagicMock()
            mock_instance.display_league_rosters = AsyncMock(return_value={"success": True})
            MockSvc.return_value = mock_instance

            from services.sleeper_draft_service import display_sleeper_league
            result = display_sleeper_league("l1")

        self.assertEqual(result["success"], True)

    def test_list_sleeper_leagues_calls_service(self):
        with patch("services.sleeper_draft_service.SleeperDraftService") as MockSvc:
            mock_instance = MagicMock()
            mock_instance.list_user_leagues = AsyncMock(return_value={"success": True})
            MockSvc.return_value = mock_instance

            from services.sleeper_draft_service import list_sleeper_leagues
            result = list_sleeper_leagues("testuser")

        self.assertEqual(result["success"], True)

    def test_get_sleeper_draft_status_calls_service(self):
        with patch("services.sleeper_draft_service.SleeperDraftService") as MockSvc:
            mock_instance = MagicMock()
            mock_instance.get_current_draft_status = AsyncMock(return_value={"success": True})
            MockSvc.return_value = mock_instance

            from services.sleeper_draft_service import get_sleeper_draft_status
            result = get_sleeper_draft_status("testuser")

        self.assertEqual(result["success"], True)


if __name__ == "__main__":
    unittest.main()
