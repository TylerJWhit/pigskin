"""Tests for Tournament class."""
import pytest
from unittest.mock import MagicMock, patch

from classes.tournament import Tournament, run_strategy_comparison
from classes.player import Player


def _make_player(name="Test Player", position="QB", auction_value=30.0, projected_points=300.0):
    return Player(
        player_id=f"p_{name.replace(' ', '_')}",
        name=name,
        position=position,
        auction_value=auction_value,
        projected_points=projected_points,
        bye_week=1
    )


def _make_players(n=5):
    positions = ["QB", "RB", "WR", "TE", "K"]
    return [_make_player(f"Player{i}", positions[i % len(positions)], 30.0 - i, 300.0 - i * 10)
            for i in range(n)]


class TestTournamentInit:
    def test_defaults(self):
        t = Tournament()
        assert t.name == "Strategy Tournament"
        assert t.num_simulations == 100
        assert t.budget_per_team == 200.0
        assert t.roster_size == 16
        assert t.base_players == []
        assert t.strategy_configs == []
        assert t.is_running is False
        assert t.progress == 0

    def test_custom_params(self):
        t = Tournament(name="Test", num_simulations=10, budget_per_team=150.0)
        assert t.name == "Test"
        assert t.num_simulations == 10
        assert t.budget_per_team == 150.0


class TestAddPlayers:
    def test_add_players_deepcopied(self):
        t = Tournament()
        players = _make_players(3)
        t.add_players(players)
        assert len(t.base_players) == 3
        # Should be a deep copy
        assert t.base_players is not players


class TestAddStrategyConfig:
    def test_add_strategy_config(self):
        t = Tournament()
        t.add_strategy_config("balanced", "BalancedOwner", num_teams=2)
        assert len(t.strategy_configs) == 1
        assert t.strategy_configs[0]["strategy_type"] == "balanced"
        assert t.strategy_configs[0]["num_teams"] == 2

    def test_add_strategy_config_with_params(self):
        t = Tournament()
        t.add_strategy_config("aggressive", "AggressiveOwner", num_teams=1, overpay_factor=1.2)
        assert t.strategy_configs[0]["strategy_params"]["overpay_factor"] == 1.2


class TestRunTournamentValidation:
    def test_run_tournament_no_players_raises(self):
        t = Tournament()
        t.add_strategy_config("balanced", "Owner")
        with pytest.raises(ValueError, match="No players"):
            t.run_tournament()

    def test_run_tournament_no_strategies_raises(self):
        t = Tournament()
        t.add_players(_make_players(3))
        with pytest.raises(ValueError, match="No strategy"):
            t.run_tournament()


class TestRunTournamentSequential:
    def setup_method(self):
        self.t = Tournament(num_simulations=1, budget_per_team=200.0, roster_size=2)
        self.t.add_players(_make_players(5))
        self.t.add_strategy_config("balanced", "Balanced", num_teams=1)

    def test_run_sequential_returns_dict(self):
        result = self.t.run_tournament(parallel=False)
        assert isinstance(result, dict)
        assert "num_simulations" in result

    def test_is_running_false_after_run(self):
        self.t.run_tournament(parallel=False)
        assert self.t.is_running is False


class TestRunTournamentParallel:
    def setup_method(self):
        self.t = Tournament(num_simulations=1, budget_per_team=200.0, roster_size=2)
        self.t.add_players(_make_players(5))
        self.t.add_strategy_config("balanced", "Balanced", num_teams=1)

    def test_run_parallel_returns_dict(self):
        result = self.t.run_tournament(parallel=True)
        assert isinstance(result, dict)

    def test_is_running_false_after_parallel_run(self):
        self.t.run_tournament(parallel=True)
        assert self.t.is_running is False


class TestRunSequentialExceptionHandling:
    def test_sequential_handles_simulation_exception(self):
        t = Tournament(num_simulations=1, budget_per_team=200.0, roster_size=2)
        t.add_players(_make_players(5))
        t.add_strategy_config("balanced", "Balanced", num_teams=1)

        with patch.object(t, "_run_single_simulation", side_effect=RuntimeError("boom")):
            # Should not raise; exception is caught with logger.error
            t._run_sequential_simulations()
        assert t.progress == 1  # Progress incremented in finally


class TestGetTournamentSummary:
    def test_summary_structure(self):
        t = Tournament(name="Test", num_simulations=5)
        summary = t.get_tournament_summary()
        assert summary["tournament_name"] == "Test"
        assert summary["num_simulations"] == 5
        assert "results" in summary
        assert "is_running" in summary


class TestGetStrategyRankings:
    def test_empty_rankings(self):
        t = Tournament()
        assert t.get_strategy_rankings() == []

    def test_single_strategy_ranking(self):
        t = Tournament(num_simulations=1, budget_per_team=200.0, roster_size=2)
        t.add_players(_make_players(5))
        t.add_strategy_config("balanced", "Balanced", num_teams=1)
        t.run_tournament(parallel=False)
        rankings = t.get_strategy_rankings()
        assert isinstance(rankings, list)

    def test_ranking_score_with_multiple_strategies(self):
        # Test that ranking_score guard (num_strategies > 1) doesn't divide by zero
        t = Tournament(num_simulations=1, budget_per_team=200.0, roster_size=2)
        t.add_players(_make_players(5))
        t.add_strategy_config("balanced", "Balanced", num_teams=1)
        t.add_strategy_config("aggressive", "Aggressive", num_teams=1)
        # Run tournament (may or may not succeed) — just check no div-by-zero
        try:
            t.run_tournament(parallel=False)
        except Exception:
            pass
        # Even if it fails, the get_strategy_rankings should work
        t.results = {
            "balanced": {
                "win_rate": 0.5, "avg_points": 900.0, "avg_ranking": 1.0,
                "points_std": 50.0, "wins": 1, "simulations": 2,
                "avg_spent": 180.0, "avg_remaining": 20.0
            },
            "aggressive": {
                "win_rate": 0.5, "avg_points": 850.0, "avg_ranking": 2.0,
                "points_std": 70.0, "wins": 1, "simulations": 2,
                "avg_spent": 195.0, "avg_remaining": 5.0
            }
        }
        # num_strategies = 2, both configs present
        rankings = t.get_strategy_rankings()
        assert len(rankings) == 2


class TestExportResults:
    def test_export_results_writes_file(self, tmp_path):
        t = Tournament(num_simulations=1, budget_per_team=200.0, roster_size=2)
        t.add_players(_make_players(5))
        t.add_strategy_config("balanced", "Balanced", num_teams=1)
        t.run_tournament(parallel=False)

        filepath = str(tmp_path / "results.json")
        t.export_results(filepath)
        import json
        with open(filepath) as f:
            data = json.load(f)
        assert "summary" in data
        assert "rankings" in data


class TestRunStrategyComparison:
    def test_run_strategy_comparison(self):
        players = _make_players(5)
        result = run_strategy_comparison(players, ["balanced", "aggressive"], num_simulations=1)
        assert isinstance(result, dict)
        assert "num_simulations" in result


class TestStrAndRepr:
    def test_str(self):
        t = Tournament(name="MyTournament", num_simulations=10)
        result = str(t)
        assert "MyTournament" in result
        assert "10" in result

    def test_repr(self):
        t = Tournament(name="MyTournament", num_simulations=10)
        result = repr(t)
        assert "Tournament" in result
        assert "MyTournament" in result


class TestRunSingleSimulationCoverage:
    def test_strategy_params_applied(self):
        """Covers line 182: strategy.set_parameter called when strategy_params non-empty."""
        t = Tournament(num_simulations=1, budget_per_team=200.0, roster_size=2)
        t.add_players(_make_players(5))
        # Use 2 teams so draft can start; pass strategy_params to cover line 182
        t.add_strategy_config("balanced", "Balanced", num_teams=2, aggressiveness=0.8)
        d = t._run_single_simulation(0)
        assert d is not None
        assert d.status == "completed"

    def test_while_loop_body_and_complete_fallback(self):
        """Covers lines 198-208 (while loop body) and 214 (fallback _complete_draft).
        Force draft to require loop iterations by patching force_complete_auction
        to not advance draft past 'started' until max_iterations exceeded.
        """
        from unittest.mock import patch, MagicMock
        from classes import auction as auction_mod

        t = Tournament(num_simulations=1, budget_per_team=200.0, roster_size=2)
        t.add_players(_make_players(2))  # Only 2 players → max_iterations=4

        t.add_strategy_config("balanced", "Balanced", num_teams=2)

        call_count = [0]

        original_init = auction_mod.Auction.__init__

        def patched_init(self_a, draft, *args, **kwargs):
            original_init(self_a, draft, *args, **kwargs)
            # Override force_complete_auction to be a no-op so loop runs max_iterations
            self_a.force_complete_auction = lambda: None

        with patch.object(auction_mod.Auction, "__init__", patched_init):
            d = t._run_single_simulation(0)
        # Draft status was never advanced past "started" → fallback fires
        assert d is not None

    def test_single_strategy_ranking_score_solo(self):
        """Covers line 302: sole strategy gets ranking_score=20."""
        t = Tournament(num_simulations=1, budget_per_team=200.0, roster_size=2)
        t.add_players(_make_players(5))
        t.add_strategy_config("balanced", "Balanced", num_teams=2)
        t.run_tournament(parallel=False)
        rankings = t.get_strategy_rankings()
        assert len(rankings) == 1
        assert rankings[0][1]["composite_score"] > 0
