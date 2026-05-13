"""QA Phase 1 — Issue #359: ARCH-005 Config system consolidation

Failing tests that verify:
  1. All production code (cli/, services/, strategies/) uses get_settings()
     from config.settings, not ConfigManager() directly
  2. ConfigManager emits a DeprecationWarning when instantiated
  3. ConfigManager constructor accepts zero arguments (stays backward-compatible
     during the deprecation window)
  4. get_settings() returns a Settings object with the expected fields

These tests MUST FAIL before the fix and PASS after.
"""
import warnings
from pathlib import Path

import pytest

# All tests in this file are QA Phase 1 gates — expected to FAIL until the
# fix for issue #359 is implemented. Remove this mark after implementation.
pytestmark = pytest.mark.xfail(
    strict=False,
    reason="QA Phase 1 gate for #359 — fails until ConfigManager emits DeprecationWarning and call sites migrated",
)


# ---------------------------------------------------------------------------
# Test 1: ConfigManager.__init__ emits DeprecationWarning
# ---------------------------------------------------------------------------

class TestConfigManagerDeprecationWarning:
    def test_config_manager_emits_deprecation_warning(self):
        """Instantiating ConfigManager must emit a DeprecationWarning.

        This is the first step of the migration: callers are warned they should
        switch to get_settings() before ConfigManager is removed.
        """
        from config.config_manager import ConfigManager

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ConfigManager()

        deprecation_warnings = [
            w for w in caught
            if issubclass(w.category, DeprecationWarning)
            and "get_settings" in str(w.message).lower()
        ]
        assert len(deprecation_warnings) >= 1, (
            "ConfigManager() was instantiated without emitting a DeprecationWarning. "
            "After the fix, instantiating ConfigManager must warn callers to use "
            "get_settings() from config.settings instead."
        )


# ---------------------------------------------------------------------------
# Test 2: get_settings() returns a Settings object with required fields
# ---------------------------------------------------------------------------

class TestGetSettingsContract:
    def test_get_settings_returns_settings_object(self):
        """get_settings() must return a Settings instance."""
        from config.settings import get_settings, Settings
        s = get_settings()
        assert isinstance(s, Settings), (
            f"get_settings() returned {type(s)}, expected Settings. "
            "Ensure get_settings() is properly defined in config/settings.py."
        )

    def test_settings_has_required_fields(self):
        """Settings must expose all fields currently provided by DraftConfig."""
        from config.settings import get_settings
        s = get_settings()
        required_fields = [
            "budget", "num_teams", "strategy_type", "data_path",
            "min_projected_points", "refresh_interval",
        ]
        for field in required_fields:
            assert hasattr(s, field), (
                f"Settings is missing field '{field}'. "
                "After the config consolidation, Settings must expose all fields "
                "currently provided by DraftConfig / ConfigManager."
            )


# ---------------------------------------------------------------------------
# Test 3: Services accept Settings injection (not just ConfigManager)
# ---------------------------------------------------------------------------

class TestServicesDIAcceptsSettings:
    def test_bid_recommendation_service_accepts_settings(self):
        """BidRecommendationService must accept a Settings object as config."""
        from config.settings import get_settings
        from services.bid_recommendation_service import BidRecommendationService

        settings = get_settings()
        # Should not raise; the service must accept Settings, not just ConfigManager
        try:
            _ = BidRecommendationService(config_manager=settings)
        except TypeError as e:
            pytest.fail(
                f"BidRecommendationService() raised TypeError when passed a "
                f"Settings object: {e}. After #359, services must accept "
                "Settings via their config_manager parameter."
            )

    def test_tournament_service_accepts_settings(self):
        """TournamentService must accept a Settings object as config."""
        from config.settings import get_settings
        from services.tournament_service import TournamentService

        settings = get_settings()
        try:
            _ = TournamentService(config_manager=settings)
        except TypeError as e:
            pytest.fail(
                f"TournamentService() raised TypeError when passed a "
                f"Settings object: {e}. After #359, services must accept "
                "Settings via their config_manager parameter."
            )


# ---------------------------------------------------------------------------
# Test 4: cli/main.py does not instantiate ConfigManager() directly
# ---------------------------------------------------------------------------

class TestCliDoesNotInstantiateConfigManager:
    def test_cli_main_does_not_call_configmanager_constructor(self):
        """AuctionDraftCLI.__init__ must not call ConfigManager() directly.

        After the migration, the CLI must use get_settings() or accept an
        injected Settings object.  Calling ConfigManager() directly defeats
        the consolidation.
        """
        import ast

        source = (Path(__file__).parent.parent.parent.parent / "cli" / "main.py").read_text()
        tree = ast.parse(source)

        # Find all Call nodes where the function is named ConfigManager
        direct_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "ConfigManager":
                    direct_calls.append(node.lineno)

        assert not direct_calls, (
            f"cli/main.py calls ConfigManager() directly at lines {direct_calls}. "
            "After #359, the CLI must use get_settings() instead."
        )
