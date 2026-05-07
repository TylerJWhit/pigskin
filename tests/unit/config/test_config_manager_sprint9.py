"""Sprint 9 QA tests — Issues #163 and #164: config_manager exception handling.

Issue #163: load_config() must handle PermissionError / OSError gracefully.
  - FAILS before fix  (raw PermissionError propagates unhandled)
  - PASSES after fix  (exception caught; returns default OR raises meaningful exception)

Issue #164: Settings-layer exceptions must NOT be silently swallowed.
  - FAILS before fix  (except Exception: pass swallows everything silently)
  - PASSES after fix  (exception propagates to caller)
"""

import json
import os
import pytest
from unittest.mock import patch

from config.config_manager import ConfigManager


@pytest.fixture
def tmp_config_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def manager(tmp_config_dir):
    return ConfigManager(config_dir=tmp_config_dir)


@pytest.fixture
def manager_with_valid_config(tmp_config_dir):
    """ConfigManager whose config.json already exists with valid contents."""
    config_file = os.path.join(tmp_config_dir, "config.json")
    with open(config_file, "w") as f:
        json.dump({"budget": 200, "num_teams": 10}, f)
    mgr = ConfigManager(config_dir=tmp_config_dir)
    return mgr


# ── Issue #163 ────────────────────────────────────────────────────────────────


class TestLoadConfigPermissionError:
    """Issue #163: PermissionError / OSError from open() must not propagate raw."""

    def test_load_config_handles_permission_error_gracefully(
        self, manager_with_valid_config
    ):
        """PermissionError from open() should be caught; raw propagation is the bug.

        Currently FAILS because the except clause only catches
        (json.JSONDecodeError, FileNotFoundError, KeyError), letting PermissionError escape.
        After fix (add PermissionError / OSError to the handler) this PASSES.
        """
        # Force reload so the cached _config doesn't short-circuit the open() call
        manager_with_valid_config._config = None

        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            try:
                result = manager_with_valid_config.load_config()
                # Returning a default DraftConfig is acceptable (one valid fix)
                assert result is not None, "load_config() returned None; expected a default config"
            except PermissionError as exc:
                pytest.fail(
                    f"load_config() let a raw PermissionError propagate (Issue #163): {exc}"
                )

    def test_load_config_handles_os_error_gracefully(self, manager_with_valid_config):
        """OSError from open() should also be handled gracefully (not propagate raw).

        Currently FAILS for the same reason as the PermissionError case.
        """
        manager_with_valid_config._config = None

        with patch("builtins.open", side_effect=OSError("I/O error")):
            try:
                result = manager_with_valid_config.load_config()
                assert result is not None
            except OSError as exc:
                pytest.fail(
                    f"load_config() let a raw OSError propagate (Issue #163): {exc}"
                )


# ── Issue #164 ────────────────────────────────────────────────────────────────


class TestLoadConfigSettingsLayerException:
    """Issue #164: ValidationError (or any exception) from the Settings layer must propagate."""

    def test_load_config_does_not_swallow_settings_validation_error(
        self, manager_with_valid_config
    ):
        """When get_settings() raises, the exception must NOT be silently swallowed.

        Currently FAILS because the code has:
            except Exception:
                pass  # settings layer is best-effort; json fallback still works

        After fix (remove the blanket suppression / let meaningful errors surface)
        this PASSES.
        """
        manager_with_valid_config._config = None

        sentinel_exc = ValueError("Simulated settings ValidationError — bad .env value")

        with patch("config.settings.get_settings", side_effect=sentinel_exc):
            with pytest.raises(ValueError, match="bad .env value"):
                manager_with_valid_config.load_config()

    def test_load_config_settings_error_is_not_silently_ignored(
        self, manager_with_valid_config
    ):
        """Caller must receive some signal when settings parsing fails.

        A second angle: after loading, a raised exception must not leave the
        caller with a silently corrupted / partially-applied config and no warning.

        Currently FAILS: load_config() returns a DraftConfig without surfacing the error.
        After fix: exception propagates (or a specific config-layer exception is raised).
        """
        manager_with_valid_config._config = None

        class FakeValidationError(Exception):
            """Stand-in for pydantic ValidationError."""

        with patch("config.settings.get_settings", side_effect=FakeValidationError("parse error")):
            with pytest.raises(FakeValidationError):
                manager_with_valid_config.load_config()
