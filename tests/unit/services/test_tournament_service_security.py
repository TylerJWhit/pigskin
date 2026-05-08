"""Security tests for TournamentService — CWD-relative save path (Issue #133).

Phase 1 QA: these tests FAIL before the fix is applied because
``_save_tournament_results`` writes to a CWD-relative ``results/`` path and
performs no validation that the resolved filepath stays within the project's
results directory.

They PASS once the fix anchors the path to the project root and raises
``ValueError`` when the computed filepath resolves outside the allowed
``results/`` directory.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

# Derive project root from this file's location:
# tests/unit/services/ -> tests/unit/ -> tests/ -> project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _make_service():
    """Build a TournamentService with a fully mocked ConfigManager."""
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
    return svc


class TestSaveTournamentResultsSecurity:
    """_save_tournament_results must reject paths that escape the results directory."""

    def test_save_results_path_traversal_rejected(self):
        """Filename derived from a traversal timestamp raises ValueError.

        EXPECTED TO FAIL before fix: ``_save_tournament_results`` does not
        validate the resolved filepath against the project's ``results/``
        directory, so no ValueError is raised.

        The mock causes ``strftime`` to return a string containing ``../``
        sequences.  When joined with ``results/``, the resolved path escapes
        the results directory entirely (and the project tree).

        Path anatomy:
          filepath = "results/tournament_results_../../../../tmp/evil.json"
          components: results / tournament_results_.. / .. / .. / .. / tmp / evil.json
          resolved  : <parent-of-project>/tmp/evil.json  ← escapes results/
        """
        svc = _make_service()
        with patch("services.tournament_service.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "../../../../tmp/evil"
            with pytest.raises(ValueError):
                svc._save_tournament_results({})

    def test_save_results_valid_path_accepted(self):
        """Normal call with a valid timestamp does NOT raise — existing behaviour preserved.

        Validates acceptance criterion 3: the write path for a standard
        ``%Y%m%d_%H%M%S`` timestamp must succeed without raising ValueError.
        File I/O is fully mocked so no real files are written.
        """
        svc = _make_service()
        with patch("builtins.open", mock_open()), \
             patch("os.makedirs"):
            # Must complete without raising ValueError
            svc._save_tournament_results({"completed_simulations": 1, "results": {}})
