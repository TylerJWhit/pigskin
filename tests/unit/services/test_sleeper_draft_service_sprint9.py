"""
Failing tests for Sprint 9 P2 bugs in SleeperDraftService.

Issues covered:
  #134 — Hardcoded default season '2024'
  #135 — Missing None-guard on get_league_users result
  #275 — get_user_drafts silently swallows exceptions

These tests FAIL against the current implementation and should PASS after fixes.
"""
from __future__ import annotations

import asyncio
import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


def _service():
    from services.sleeper_draft_service import SleeperDraftService
    svc = SleeperDraftService()
    svc.sleeper_api = MagicMock()
    return svc


# ---------------------------------------------------------------------------
# Issue #134 — Hardcoded default season '2024'
# ---------------------------------------------------------------------------

class TestDefaultSeasonNotHardcoded2024(unittest.TestCase):
    """
    #134: The default season value on get_user_drafts, list_user_leagues, and
    get_current_draft_status must NOT be the string literal '2024'.
    It should be derived from config or the current calendar year.
    """

    def test_get_user_drafts_default_season_is_not_2024(self):
        """When no season arg is supplied, the API must NOT be called with '2024'."""
        svc = _service()
        svc.sleeper_api.get_user = AsyncMock(return_value={"user_id": "u1"})
        svc.sleeper_api.get_user_leagues = AsyncMock(return_value=[])

        asyncio.run(svc.get_user_drafts("testuser"))

        call_args = svc.sleeper_api.get_user_leagues.call_args
        # Grab season from positional or keyword args
        if call_args.args and len(call_args.args) >= 2:
            season_used = call_args.args[1]
        else:
            season_used = call_args.kwargs.get("season", call_args.args[0] if call_args.args else None)

        self.assertNotEqual(
            season_used,
            "2024",
            "Default season is still hardcoded to '2024' — should use current year or config.",
        )

    def test_get_user_drafts_default_season_reflects_current_year(self):
        """Default season should equal the current calendar year (or come from config)."""
        svc = _service()
        svc.sleeper_api.get_user = AsyncMock(return_value={"user_id": "u1"})
        svc.sleeper_api.get_user_leagues = AsyncMock(return_value=[])

        asyncio.run(svc.get_user_drafts("testuser"))

        call_args = svc.sleeper_api.get_user_leagues.call_args
        if call_args.args and len(call_args.args) >= 2:
            season_used = call_args.args[1]
        else:
            season_used = call_args.kwargs.get("season")

        expected_year = str(datetime.date.today().year)
        self.assertEqual(
            season_used,
            expected_year,
            f"Default season should be '{expected_year}', got '{season_used}'.",
        )

    def test_list_user_leagues_default_season_is_not_2024(self):
        """list_user_leagues default season must not be '2024'."""
        svc = _service()
        svc.sleeper_api.get_user = AsyncMock(return_value={"user_id": "u1"})
        svc.sleeper_api.get_user_leagues = AsyncMock(return_value=[])

        asyncio.run(svc.list_user_leagues("testuser"))

        call_args = svc.sleeper_api.get_user_leagues.call_args
        if call_args.args and len(call_args.args) >= 2:
            season_used = call_args.args[1]
        else:
            season_used = call_args.kwargs.get("season")

        self.assertNotEqual(
            season_used,
            "2024",
            "list_user_leagues default season is still hardcoded to '2024'.",
        )


# ---------------------------------------------------------------------------
# Issue #135 — Missing None-guard on get_league_users result
# ---------------------------------------------------------------------------

class TestGetLeagueUsersNoneGuard(unittest.TestCase):
    """
    #135: When get_league_users() returns None, display_draft_info and
    display_league_rosters must NOT raise TypeError or return success=False.
    They should treat the users map as empty ({}) and continue.
    """

    def test_display_draft_info_handles_none_league_users_gracefully(self):
        """display_draft_info should succeed even when get_league_users returns None."""
        svc = _service()
        svc.sleeper_api.get_draft = AsyncMock(
            return_value={"draft_id": "d1", "league_id": "l1"}
        )
        svc.sleeper_api.get_draft_picks = AsyncMock(return_value=[])
        svc.sleeper_api.get_league_users = AsyncMock(return_value=None)

        with patch("services.sleeper_draft_service.get_sleeper_players", return_value={}):
            with patch("services.sleeper_draft_service.print_sleeper_draft"):
                result = asyncio.run(svc.display_draft_info("d1"))

        self.assertTrue(
            result.get("success"),
            "display_draft_info should succeed when get_league_users returns None, "
            f"but got: {result}",
        )
        self.assertEqual(
            result.get("users_info"),
            {},
            "users_info should be empty dict when get_league_users returns None.",
        )

    def test_display_league_rosters_handles_none_league_users_gracefully(self):
        """display_league_rosters should succeed even when get_league_users returns None."""
        svc = _service()
        svc.sleeper_api.get_league_rosters = AsyncMock(
            return_value=[{"roster_id": "r1", "owner_id": "u1"}]
        )
        svc.sleeper_api.get_league_users = AsyncMock(return_value=None)

        with patch("services.sleeper_draft_service.get_sleeper_players", return_value={}):
            with patch("services.sleeper_draft_service.print_sleeper_league"):
                result = asyncio.run(svc.display_league_rosters("l1"))

        self.assertTrue(
            result.get("success"),
            "display_league_rosters should succeed when get_league_users returns None, "
            f"but got: {result}",
        )
        self.assertEqual(
            result.get("users_info"),
            {},
            "users_info should be empty dict when get_league_users returns None.",
        )


# ---------------------------------------------------------------------------
# Issue #275 — get_user_drafts silently swallows exceptions
# ---------------------------------------------------------------------------

class TestGetUserDraftsExceptionPropagation(unittest.TestCase):
    """
    #275: get_user_drafts currently catches ALL exceptions and returns an error
    dict, silently discarding stack traces. After the fix, the exception must
    propagate (or be re-raised with context) so callers and logging can see it.
    """

    def test_api_exception_propagates_from_get_user_drafts(self):
        """
        A RuntimeError from get_user() should propagate out of get_user_drafts,
        not be silently swallowed into an error-dict return value.
        """
        svc = _service()
        svc.sleeper_api.get_user = AsyncMock(side_effect=RuntimeError("API down"))

        with self.assertRaises(RuntimeError):
            asyncio.run(svc.get_user_drafts("testuser"))

    def test_get_user_leagues_exception_propagates(self):
        """
        A ConnectionError from get_user_leagues should propagate out of
        get_user_drafts, not be silently swallowed.
        """
        svc = _service()
        svc.sleeper_api.get_user = AsyncMock(return_value={"user_id": "u1"})
        svc.sleeper_api.get_user_leagues = AsyncMock(
            side_effect=ConnectionError("network failure")
        )

        with self.assertRaises(ConnectionError):
            asyncio.run(svc.get_user_drafts("testuser"))

    def test_get_draft_exception_propagates(self):
        """
        A ValueError from get_draft should propagate out of get_user_drafts.
        """
        svc = _service()
        svc.sleeper_api.get_user = AsyncMock(return_value={"user_id": "u1"})
        svc.sleeper_api.get_user_leagues = AsyncMock(
            return_value=[{"league_id": "l1", "name": "L1", "draft_id": "d1"}]
        )
        svc.sleeper_api.get_draft = AsyncMock(side_effect=ValueError("bad draft id"))

        with self.assertRaises(ValueError):
            asyncio.run(svc.get_user_drafts("testuser"))


if __name__ == "__main__":
    unittest.main()
