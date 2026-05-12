"""Failing tests for CLI season default and dependency deduplication.

Issue #171: cli/main.py hard-codes the season string '2024' in
            handle_sleeper_status() and handle_sleeper_leagues().  The default
            must be datetime.now().year (as a string).

Issue #172: ConfigManager and SleeperAPI are each instantiated twice per CLI
            run — once in AuctionDraftCLI.__init__() and again in
            CommandProcessor.__init__().  They must be instantiated exactly once
            and the single instance must be shared between both objects.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Issue #171 — Season default must be the current year
# ---------------------------------------------------------------------------

class TestCliSeasonDefault:
    """The CLI must default to the current calendar year, not the hardcoded '2024'."""

    CURRENT_YEAR = str(datetime.now().year)

    def test_handle_sleeper_status_uses_current_year_as_default(self):
        """handle_sleeper_status() with no season arg must use the current year.

        The command currently defaults to '2024'; this test fails until #171 is
        fixed.
        """
        from cli.main import AuctionDraftCLI

        cli = AuctionDraftCLI()

        # Provide a username but NO season argument — the default must kick in.
        captured_season = []

        def _fake_get_status(username, season):
            captured_season.append(season)
            return {"success": True}

        cli.command_processor.get_sleeper_draft_status = _fake_get_status
        # Patch load_config to return an object without sleeper_username so our
        # explicit arg is used.
        mock_config = MagicMock()
        mock_config.sleeper_username = None
        cli.config_manager.load_config = MagicMock(return_value=mock_config)

        cli.handle_sleeper_status(["testuser"])  # no season arg

        assert len(captured_season) == 1, "get_sleeper_draft_status was not called"
        assert captured_season[0] == self.CURRENT_YEAR, (
            f"Expected default season '{self.CURRENT_YEAR}', "
            f"got '{captured_season[0]}' — hardcoded '2024' not yet removed (#171)"
        )

    def test_handle_sleeper_leagues_uses_current_year_as_default(self):
        """handle_sleeper_leagues() with no season arg must use the current year."""
        from cli.main import AuctionDraftCLI

        cli = AuctionDraftCLI()

        captured_season = []

        def _fake_list_leagues(username, season):
            captured_season.append(season)
            return {"success": True}

        cli.command_processor.list_sleeper_leagues = _fake_list_leagues
        mock_config = MagicMock()
        mock_config.sleeper_username = None
        cli.config_manager.load_config = MagicMock(return_value=mock_config)

        cli.handle_sleeper_leagues(["testuser"])  # no season arg

        assert len(captured_season) == 1, "list_sleeper_leagues was not called"
        assert captured_season[0] == self.CURRENT_YEAR, (
            f"Expected default season '{self.CURRENT_YEAR}', "
            f"got '{captured_season[0]}' — hardcoded '2024' not yet removed (#171)"
        )

    def test_season_default_matches_current_year_not_literal_2024(self):
        """The CLI default season must not be the literal string '2024'."""
        assert self.CURRENT_YEAR != "2024" or pytest.skip(
            "This test is only meaningful when the calendar year is not 2024"
        )
        # If CURRENT_YEAR != '2024' then any test above that captured '2024'
        # will already fail.  This test documents the intent explicitly.
        assert self.CURRENT_YEAR == str(datetime.now().year)


# ---------------------------------------------------------------------------
# Issue #172 — ConfigManager and SleeperAPI instantiated exactly once
# ---------------------------------------------------------------------------

class TestCliSingletonDependencies:
    """ConfigManager and SleeperAPI must be created exactly once per CLI run.

    Currently AuctionDraftCLI and CommandProcessor each create their own
    instances.  After #172 is fixed they must share a single instance.
    """

    def test_config_manager_instantiated_once(self):
        """ConfigManager() is constructed exactly once when AuctionDraftCLI is created.

        Currently it is constructed twice (once in AuctionDraftCLI.__init__ and
        again in CommandProcessor.__init__), so this test fails until #172 is fixed.
        """
        from config.config_manager import ConfigManager
        from cli.main import AuctionDraftCLI

        instance_ids: list = []
        original_init = ConfigManager.__init__

        def _tracking_init(self_inner, *args, **kwargs):
            instance_ids.append(id(self_inner))
            original_init(self_inner, *args, **kwargs)

        with patch.object(ConfigManager, "__init__", _tracking_init):
            AuctionDraftCLI()

        assert len(instance_ids) == 1, (
            f"ConfigManager.__init__ was called {len(instance_ids)} time(s); "
            "expected exactly 1.  Duplicate instantiation not yet removed (#172)."
        )

    def test_sleeper_api_instantiated_once(self):
        """SleeperAPI() is constructed exactly once when AuctionDraftCLI is created.

        Currently it is constructed twice (once in AuctionDraftCLI.__init__ and
        again in CommandProcessor.__init__), so this test fails until #172 is fixed.
        """
        from api.sleeper_api import SleeperAPI
        from cli.main import AuctionDraftCLI

        instance_ids: list = []
        original_init = SleeperAPI.__init__

        def _tracking_init(self_inner, *args, **kwargs):
            instance_ids.append(id(self_inner))
            original_init(self_inner, *args, **kwargs)

        with patch.object(SleeperAPI, "__init__", _tracking_init):
            AuctionDraftCLI()

        assert len(instance_ids) == 1, (
            f"SleeperAPI.__init__ was called {len(instance_ids)} time(s); "
            "expected exactly 1.  Duplicate instantiation not yet removed (#172)."
        )

    def test_command_processor_receives_shared_config_manager(self):
        """CommandProcessor must use the same ConfigManager instance as AuctionDraftCLI."""
        from cli.main import AuctionDraftCLI

        cli = AuctionDraftCLI()
        assert cli.config_manager is cli.command_processor.config_manager, (
            "AuctionDraftCLI.config_manager and CommandProcessor.config_manager are "
            "different objects — the instance is not shared (#172)."
        )

    def test_command_processor_receives_shared_sleeper_api(self):
        """CommandProcessor must use the same SleeperAPI instance as AuctionDraftCLI."""
        from cli.main import AuctionDraftCLI

        cli = AuctionDraftCLI()
        assert cli.sleeper_api is cli.command_processor.sleeper_api, (
            "AuctionDraftCLI.sleeper_api and CommandProcessor.sleeper_api are "
            "different objects — the instance is not shared (#172)."
        )
