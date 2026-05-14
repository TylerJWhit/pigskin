"""Gate tests for #419: Migrate CommandProcessor from ConfigManager to get_settings().

These tests define the acceptance criteria for the ConfigManager → get_settings()
migration in cli/commands/__init__.py.  Tests that verify the *current* (broken)
state will pass; tests that verify the *desired* (post-migration) state are
marked xfail.

These tests are stricter replacements for the existing
``test_cli_commands_configmanager_call_is_documented_todo`` test in
``tests/unit/config/test_config_consolidation.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[3]
COMMANDS_INIT = REPO_ROOT / "cli" / "commands" / "__init__.py"


def _count_configmanager_constructor_calls(source: str) -> list[int]:
    """Return line numbers of bare ``ConfigManager()`` call-expressions in *source*."""
    tree = ast.parse(source)
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ConfigManager"
    ]


# ---------------------------------------------------------------------------
# Current-state assertions (document what exists right now)
# These help catch accidental regressions during the migration.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_commands_init_exists():
    """Sanity: cli/commands/__init__.py must exist (always passes)."""
    assert COMMANDS_INIT.exists(), "cli/commands/__init__.py is missing"


@pytest.mark.unit
def test_current_todo_comment_present():
    """The TODO(#359-followon) comment is present in the current source (pre-migration).

    This test will become irrelevant once #419 is implemented; it is kept here
    as documentation that the comment was intentionally removed during migration.
    """
    source = COMMANDS_INIT.read_text()
    # This assertion documents the *current* state.  Once migrated the TODO
    # should be gone and the xfail test below will gate on that.
    # We don't assert here — just record the finding in a skippable way.
    has_todo = "TODO(#359-followon)" in source
    pytest.skip(f"informational: TODO(#359-followon) present={has_todo}")


# ---------------------------------------------------------------------------
# AC 1 — CommandProcessor.__init__ must NOT instantiate ConfigManager()
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.xfail(
    strict=False,
    reason="pending #419: CommandProcessor still calls ConfigManager() directly",
)
def test_command_processor_no_configmanager_instantiation():
    """CommandProcessor.__init__ must not call ConfigManager() — use get_settings() instead."""
    source = COMMANDS_INIT.read_text()
    lines = _count_configmanager_constructor_calls(source)
    assert not lines, (
        f"Found ConfigManager() constructor call(s) at lines {lines} in "
        "cli/commands/__init__.py.  Migration to get_settings() not complete."
    )


# ---------------------------------------------------------------------------
# AC 2 — CommandProcessor must expose self.settings, not self.config_manager
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.xfail(
    strict=False,
    reason="pending #419: CommandProcessor still stores self.config_manager",
)
def test_command_processor_has_settings_attribute():
    """After migration, CommandProcessor must store settings as self.settings."""
    source = COMMANDS_INIT.read_text()
    assert "self.settings" in source, (
        "cli/commands/__init__.py must assign self.settings after #419 migration"
    )


@pytest.mark.unit
@pytest.mark.xfail(
    strict=False,
    reason="pending #419: CommandProcessor still stores self.config_manager",
)
def test_command_processor_no_config_manager_attribute():
    """After migration, CommandProcessor must NOT store self.config_manager."""
    source = COMMANDS_INIT.read_text()
    assert "self.config_manager" not in source, (
        "cli/commands/__init__.py must not assign self.config_manager after migration"
    )


@pytest.mark.unit
@pytest.mark.xfail(
    strict=False,
    reason="pending #419: CommandProcessor still stores self.config_manager",
)
def test_command_processor_settings_is_settings_instance():
    """At runtime, CommandProcessor().settings must be a Settings object."""
    from config.settings import Settings
    from cli.commands import CommandProcessor

    cp = CommandProcessor()
    assert hasattr(cp, "settings"), "CommandProcessor instance must have .settings attribute"
    assert isinstance(cp.settings, Settings), (
        f"CommandProcessor().settings must be a Settings instance, got {type(cp.settings)}"
    )


# ---------------------------------------------------------------------------
# AC 3 — TODO comment is gone (replaced by real implementation)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.xfail(
    strict=False,
    reason="pending #419: TODO(#359-followon) comment still present",
)
def test_todo_comment_removed():
    """After migration, the TODO(#359-followon) comment must be gone."""
    source = COMMANDS_INIT.read_text()
    assert "TODO(#359-followon)" not in source, (
        "cli/commands/__init__.py still contains TODO(#359-followon) comment — "
        "migration to get_settings() not complete"
    )


# ---------------------------------------------------------------------------
# AC 4 — config/settings.py must have a roster_positions field
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.xfail(
    strict=False,
    reason="pending #419: Settings does not yet have roster_positions field",
)
def test_settings_has_roster_positions_field():
    """Settings model must declare a roster_positions field for post-migration use."""
    from config.settings import Settings

    model_fields = getattr(Settings, "model_fields", None) or getattr(
        Settings, "__fields__", {}
    )
    assert "roster_positions" in model_fields, (
        "config/settings.py Settings class must define a roster_positions field"
    )


@pytest.mark.unit
@pytest.mark.xfail(
    strict=False,
    reason="pending #419: Settings does not yet have roster_positions field",
)
def test_settings_roster_positions_has_default():
    """Settings.roster_positions should have a sensible default (list of positions)."""
    from config.settings import Settings

    s = Settings()
    assert hasattr(s, "roster_positions"), (
        "Settings instance must expose roster_positions attribute"
    )
    rp = s.roster_positions
    assert isinstance(rp, (list, dict, str)), (
        f"roster_positions must be a list/dict/str, got {type(rp)}"
    )


# ---------------------------------------------------------------------------
# AC 5 — get_settings() is used in the import block (not ConfigManager)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.xfail(
    strict=False,
    reason="pending #419: get_settings not yet imported in cli/commands/__init__.py",
)
def test_get_settings_imported_in_commands_init():
    """After migration, cli/commands/__init__.py must import get_settings."""
    source = COMMANDS_INIT.read_text()
    assert "get_settings" in source, (
        "cli/commands/__init__.py must import or call get_settings after #419 migration"
    )
