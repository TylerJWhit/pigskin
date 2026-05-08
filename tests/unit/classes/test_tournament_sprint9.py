"""Sprint 9 QA tests — Issue #119: _analyze_results uses wrong key for multi-word strategy names.

These tests FAIL before the fix and PASS after.
"""

from unittest.mock import Mock

from classes.tournament import Tournament
from classes.team import Team


def _make_team_with_owner(owner_id: str, projected_points: float = 100.0) -> Mock:
    """Return a mock Team with a given owner_id and projected points."""
    team = Mock(spec=Team)
    team.owner_id = owner_id
    team.get_projected_points.return_value = projected_points
    team.get_total_spent.return_value = 150.0
    team.budget = 50
    team.roster = []
    return team


def _make_mock_draft(teams):
    """Return a mock Draft whose get_leaderboard returns the given teams ranked."""
    draft = Mock()
    leaderboard = [
        {
            "team": team,
            "projected_points": team.get_projected_points(),
            "total_spent": team.get_total_spent(),
            "remaining_budget": team.budget,
            "roster_size": len(team.roster),
        }
        for team in teams
    ]
    leaderboard.sort(key=lambda x: x["projected_points"], reverse=True)
    draft.get_leaderboard.return_value = leaderboard
    return draft


class TestIssue119AnalyzeResultsMultiWordStrategy:
    """Issue #119 — _analyze_results splits owner_id on '_' and takes only [0], losing multi-word names."""

    def test_multi_word_strategy_key_preserved_in_results(self):
        """'aggressive_budget' strategy must appear as key in results, not just 'aggressive'."""
        tournament = Tournament(name="Test", num_simulations=1)

        # Simulate the owner_id format used by _run_single_simulation:
        # owner_id = f"{config['owner_name']}_{simulation_id}_{team_index}"
        # For owner_name="aggressive_budget", sim=0, i=0 → "aggressive_budget_0_0"
        team = _make_team_with_owner("aggressive_budget_0_0", projected_points=200.0)
        mock_draft = _make_mock_draft([team])
        tournament.completed_drafts = [mock_draft]

        tournament._analyze_results()

        assert "aggressive_budget" in tournament.results, (
            f"Expected 'aggressive_budget' in results keys, but got: {list(tournament.results.keys())}. "
            "Issue #119: owner_id.split('_')[0] only captures 'aggressive', losing '_budget'."
        )

    def test_single_word_strategy_still_works(self):
        """Single-word strategy name 'balanced' must still appear correctly (baseline)."""
        tournament = Tournament(name="Test", num_simulations=1)

        team = _make_team_with_owner("balanced_0_0", projected_points=150.0)
        mock_draft = _make_mock_draft([team])
        tournament.completed_drafts = [mock_draft]

        tournament._analyze_results()

        assert "balanced" in tournament.results, (
            f"Expected 'balanced' in results, got: {list(tournament.results.keys())}"
        )

    def test_wrong_key_not_in_results(self):
        """The truncated key 'aggressive' alone must NOT be the result key for multi-word strategy."""
        tournament = Tournament(name="Test", num_simulations=1)

        team = _make_team_with_owner("aggressive_budget_0_0", projected_points=200.0)
        mock_draft = _make_mock_draft([team])
        tournament.completed_drafts = [mock_draft]

        tournament._analyze_results()

        # With the bug, 'aggressive' IS a key but 'aggressive_budget' is NOT
        # After the fix, 'aggressive_budget' IS a key and 'aggressive' alone is NOT
        # This test will FAIL with the bug because the assertion below fails:
        assert "aggressive" not in tournament.results or "aggressive_budget" in tournament.results, (
            "BUG present: results contain truncated key 'aggressive' but not full key "
            f"'aggressive_budget'. results={list(tournament.results.keys())}"
        )

    def test_multi_word_strategy_stats_are_populated(self):
        """Results for multi-word strategy should have valid statistics."""
        tournament = Tournament(name="Test", num_simulations=1)

        team = _make_team_with_owner("value_over_replacement_0_0", projected_points=180.0)
        mock_draft = _make_mock_draft([team])
        tournament.completed_drafts = [mock_draft]

        tournament._analyze_results()

        assert "value_over_replacement" in tournament.results, (
            f"Expected 'value_over_replacement' in results, got: {list(tournament.results.keys())}. "
            "Issue #119 still present."
        )
        stats = tournament.results.get("value_over_replacement", {})
        assert stats.get("simulations", 0) >= 1
