"""QA Phase 1 — Issue #366: Decompose cli/commands.py god-module

Failing tests that verify:
  1. cli/commands.py is split into focused submodule files (or
     a commands/ package) with no single file exceeding 400 lines.
  2. Each command handler class is importable from its own module.
  3. All existing CommandProcessor public methods remain callable
     after the split (regression gate).
  4. No command behavior changes — output format, return values, and
     error handling must be identical to pre-split behavior.

These tests MUST FAIL before the fix and PASS after.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

# All tests in this file are QA Phase 1 gates — expected to FAIL until the
# fix for issue #366 is implemented. Remove this mark after implementation.
pytestmark = pytest.mark.xfail(
    strict=True,
    reason="QA Phase 1 gate for #366 — fails until cli/commands.py is decomposed",
)

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_COMMANDS_PATH = _REPO_ROOT / "cli" / "commands.py"


# ---------------------------------------------------------------------------
# Test 1: cli/commands.py is below 400 lines (or replaced by a package)
# ---------------------------------------------------------------------------

class TestCommandsModuleSize:
    def test_commands_module_not_a_god_module(self):
        """cli/commands.py must be < 400 lines, OR cli/commands/ must be a package.

        Currently cli/commands.py is ~1761 lines (MI=0, CC=323) — a god-module.
        After the refactor, either:
          (a) cli/commands.py is <= 400 lines, OR
          (b) cli/commands/ is a package directory with __init__.py
        """
        commands_pkg = _REPO_ROOT / "cli" / "commands"
        if commands_pkg.is_dir() and (commands_pkg / "__init__.py").exists():
            # Option B: package — pass
            return

        # Option A: single file must be <= 400 lines
        if _COMMANDS_PATH.exists():
            lines = len(_COMMANDS_PATH.read_text().splitlines())
            assert lines <= 400, (
                f"cli/commands.py is {lines} lines — still a god-module. "
                "Split it into focused submodules (e.g., cli/commands/bid.py, "
                "cli/commands/mock.py, cli/commands/tournament.py, etc.) or "
                "create a cli/commands/ package.  Target: <= 400 lines per file."
            )
        else:
            pytest.fail(
                "Neither cli/commands.py nor cli/commands/ package exists. "
                "Ensure the split produces an importable module."
            )


# ---------------------------------------------------------------------------
# Test 2: Individual command handler imports work
# ---------------------------------------------------------------------------

class TestCommandHandlerImports:
    @pytest.mark.xfail(strict=False, reason="Import works today; only decomposition structure changes")
    def test_bid_handler_importable(self):
        """A bid recommendation handler must be importable after the split."""
        try:
            from cli.commands import CommandProcessor  # noqa: F401
        except ImportError as e:
            pytest.fail(f"Cannot import CommandProcessor from cli.commands: {e}")

    def test_all_public_methods_present(self):
        """All CommandProcessor public methods must still exist after the split."""
        from cli.commands import CommandProcessor

        expected_methods = [
            "get_bid_recommendation_detailed",
            "run_enhanced_mock_draft",
            "run_elimination_tournament",
            "run_comprehensive_tournament",
            "get_sleeper_draft_status",
            "list_sleeper_leagues",
            "test_sleeper_connectivity",
        ]
        for method in expected_methods:
            assert hasattr(CommandProcessor, method), (
                f"CommandProcessor.{method}() no longer exists after the split. "
                "All public methods must remain accessible via cli.commands.CommandProcessor."
            )


# ---------------------------------------------------------------------------
# Test 3: No single file in cli/commands/ exceeds 400 lines
# ---------------------------------------------------------------------------

class TestNoGodModulesInCommandsPackage:
    def test_no_commands_submodule_exceeds_400_lines(self):
        """Every file in cli/commands/ (if a package) must be <= 400 lines."""
        commands_pkg = _REPO_ROOT / "cli" / "commands"
        if not commands_pkg.is_dir():
            pytest.skip("cli/commands/ is not yet a package — checking single file instead")

        oversized = []
        for py_file in commands_pkg.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            lines = len(py_file.read_text().splitlines())
            if lines > 400:
                oversized.append((py_file.name, lines))

        assert not oversized, (
            "The following cli/commands/ submodules still exceed 400 lines: "
            + ", ".join(f"{name} ({n} lines)" for name, n in oversized)
        )


# ---------------------------------------------------------------------------
# Test 4: CommandProcessor behavior regression — bid recommendation
# ---------------------------------------------------------------------------

class TestCommandProcessorBidRegressionAfterSplit:
    def test_get_bid_recommendation_detailed_returns_dict(self):
        """get_bid_recommendation_detailed() must still return a dict after the split."""
        from cli.commands import CommandProcessor

        mock_service_result = {
            "success": True,
            "recommended_bid": 25,
            "player_name": "Josh Allen",
            "bid_difference": 5,
            "value_tier": "good_value",
            "reasoning": "Mock reasoning",
        }
        with patch(
            "services.bid_recommendation_service.BidRecommendationService.recommend_bid",
            return_value=mock_service_result,
        ):
            processor = CommandProcessor()
            result = processor.get_bid_recommendation_detailed("Josh Allen", 20.0)

        assert isinstance(result, dict), (
            f"get_bid_recommendation_detailed() returned {type(result)}, expected dict. "
            "Behavior must not change after the commands.py split."
        )
        assert "success" in result or "recommended_bid" in result or "error" in result, (
            "Result dict must contain 'success', 'recommended_bid', or 'error' key."
        )
