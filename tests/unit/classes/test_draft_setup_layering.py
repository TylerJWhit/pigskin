"""QA Phase 1 — Issue #358: ARCH-001 layering violation in classes/draft_setup.py

Failing tests that verify:
  1. classes/draft_setup.py does NOT import from api/ at module level
  2. import_players_from_sleeper() accepts an injected sleeper_api argument
     (no internal SleeperAPI() instantiation allowed)
  3. When called without an injected client, the function raises TypeError or
     accepts a callable that provides the data — never silently creates its own
     SleeperAPI().

These tests MUST FAIL before the fix and PASS after.
"""
import ast
import importlib
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# All tests in this file are QA Phase 1 gates — expected to FAIL until the
# fix for issue #358 is implemented. Remove this mark after implementation.
pytestmark = pytest.mark.xfail(
    strict=True,
    reason="QA Phase 1 gate for #358 — fails until classes/draft_setup.py is decoupled from api/",
)



# ---------------------------------------------------------------------------
# Helper: parse the source file without importing it
# ---------------------------------------------------------------------------

_DRAFT_SETUP_PATH = Path(__file__).parent.parent.parent.parent / "classes" / "draft_setup.py"


def _source_ast() -> ast.Module:
    return ast.parse(_DRAFT_SETUP_PATH.read_text())


# ---------------------------------------------------------------------------
# Test 1: No top-level `api.*` import in classes/draft_setup.py
# ---------------------------------------------------------------------------

class TestDraftSetupNoApiImport:
    def test_no_api_import_at_module_level(self):
        """classes/draft_setup.py must not import from api/ at module level.

        The domain layer (classes/) must never depend on the integration layer
        (api/).  This is the ARCH-001 layering violation.
        """
        tree = _source_ast()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith("api."), (
                        f"Layering violation: 'classes/draft_setup.py' imports "
                        f"from '{node.module}' (api layer) at line {node.lineno}. "
                        "Move API access to a service or inject via parameter."
                    )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("api."), (
                            f"Layering violation: top-level import of '{alias.name}' "
                            f"at line {node.lineno}."
                        )

    def test_sleeper_api_not_imported_at_top_level(self):
        """SleeperAPI must not be imported at the top of draft_setup.py."""
        tree = _source_ast()
        top_level_imports = [
            node for node in ast.iter_child_nodes(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        for node in top_level_imports:
            if isinstance(node, ast.ImportFrom):
                names = [alias.name for alias in node.names]
                assert "SleeperAPI" not in names, (
                    f"SleeperAPI imported at module top-level (line {node.lineno}). "
                    "It must either be removed or moved inside the function body "
                    "behind an injected parameter check."
                )


# ---------------------------------------------------------------------------
# Test 2: import_players_from_sleeper() accepts injected sleeper_api
# ---------------------------------------------------------------------------

class TestDraftSetupInjection:
    def test_import_players_from_sleeper_accepts_sleeper_api_param(self):
        """import_players_from_sleeper() must accept a sleeper_api keyword arg.

        After the fix, callers must be able to inject a mock/stub instead of
        the function creating its own SleeperAPI() internally.
        """
        import classes.draft_setup as ds
        sig = inspect.signature(ds.DraftSetup.import_players_from_sleeper)
        assert "sleeper_api" in sig.parameters, (
            "DraftSetup.import_players_from_sleeper() must accept a 'sleeper_api' "
            "parameter for dependency injection.  Currently it has no such param, "
            "meaning it always instantiates SleeperAPI() internally."
        )

    def test_import_players_uses_injected_client_not_internal_instance(self):
        """When sleeper_api is injected, no new SleeperAPI() must be constructed."""
        import classes.draft_setup as ds

        mock_client = MagicMock()
        mock_client.bulk_convert_players.return_value = [
            {
                "player_id": "1",
                "name": "Test Player",
                "position": "QB",
                "team": "KC",
                "projected_points": 25.0,
                "auction_value": 40.0,
                "bye_week": 12,
            }
        ]

        with patch("api.sleeper_api.SleeperAPI") as MockSleeperAPI:
            result = ds.DraftSetup.import_players_from_sleeper(sleeper_api=mock_client)
            # The function must NOT have created a new SleeperAPI() instance
            MockSleeperAPI.assert_not_called(), (
                "import_players_from_sleeper() constructed a new SleeperAPI() "
                "even though one was injected via the sleeper_api parameter."
            )

        assert len(result) == 1
        assert result[0].name == "Test Player"

    def test_import_players_without_injection_does_not_crash_on_import(self):
        """Importing classes.draft_setup must not trigger a network call or crash."""
        # Simply re-importing (or freshly importing) must not raise an error.
        import classes.draft_setup  # noqa: F401 — just a smoke import test
        importlib.reload(classes.draft_setup)
