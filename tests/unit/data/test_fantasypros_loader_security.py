"""Security tests for FantasyProsLoader — path traversal prevention (Issue #165).

Phase 1 QA: these tests FAIL before the fix is applied because
FantasyProsLoader does not yet validate ``data_path`` on construction.

They PASS once the fix enforces path canonicalization via ``Path.resolve()``
and raises ``ValueError`` for paths that resolve outside the project's
data directory, without revealing the actual path in the error message.
"""

import pytest
from pathlib import Path

from data.fantasypros_loader import FantasyProsLoader

# Derive project root from this file's location:
# tests/unit/data/ -> tests/unit/ -> tests/ -> project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class TestDataPathTraversalSecurity:
    """FantasyProsLoader must reject data_path values that escape the project."""

    def test_data_path_traversal_raises_value_error(self):
        """Absolute path clearly outside the project raises ValueError.

        EXPECTED TO FAIL before fix: the constructor stores ``data_path``
        without any canonicalization or boundary check, so no ValueError
        is raised for ``/tmp``.
        """
        with pytest.raises(ValueError):
            FantasyProsLoader("/tmp")

    def test_data_path_valid_path_does_not_raise(self):
        """The canonical data/sheets path within the project does NOT raise.

        Validates acceptance criterion 2: existing behaviour for valid paths
        is unchanged after the fix is applied.
        """
        valid_path = str(_PROJECT_ROOT / "data" / "sheets")
        # Must construct without raising ValueError
        loader = FantasyProsLoader(valid_path)
        assert loader.data_path == valid_path

    def test_data_path_relative_escape_raises(self):
        """A path that resolves outside the project data directory raises ValueError.

        EXPECTED TO FAIL before fix: the constructor stores ``data_path``
        without calling ``Path.resolve()``, so the escape is not detected.

        The path ``<project>/data/../../etc`` resolves to the parent of the
        project directory followed by ``etc`` — clearly outside ``<project>/data``.
        """
        escape_path = str(_PROJECT_ROOT / "data" / ".." / ".." / "etc")
        with pytest.raises(ValueError):
            FantasyProsLoader(escape_path)

    def test_error_message_does_not_reveal_path(self):
        """ValueError message must NOT expose the supplied file system path.

        EXPECTED TO FAIL before fix: no ValueError is raised at all, so
        the assertion about the message is never reached.

        Validates acceptance criterion 1 (safe error message).
        """
        traversal = "/etc/passwd"
        with pytest.raises(ValueError) as exc_info:
            FantasyProsLoader(traversal)
        assert "/etc/passwd" not in str(exc_info.value), (
            "Error message must not disclose the actual path (information disclosure)"
        )
