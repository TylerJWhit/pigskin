"""Tests for lab/simulation/runner.py — closes #257."""
from __future__ import annotations

import tempfile
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tournament_results(strategy_key: str, wins: int = 10, simulations: int = 20):
    """Return a fake tournament all_results dict as Tournament._analyze_results produces."""
    return {
        strategy_key: {
            "simulations": simulations,
            "wins": wins,
            "win_rate": wins / simulations,
            "avg_points": 900.0,
            "avg_spent": 190.0,
            "avg_remaining": 10.0,
            "avg_ranking": 2.5,
            "points_std": 50.0,
            "best_points": 1100.0,
            "worst_points": 700.0,
            "median_ranking": 2.0,
        }
    }


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestSimulationRunnerUnit(unittest.TestCase):
    """Tests for SimulationRunner internals with mocked Tournament."""

    def setUp(self):
        from lab.simulation.runner import SimulationRunner
        self.RunnerClass = SimulationRunner

    def test_benchmark_strategy_returns_win_rate(self):
        runner = self.RunnerClass(
            strategies=["balanced"], runs=20, num_opponents=11
        )
        fake_results = _make_tournament_results("balanced", wins=5, simulations=20)
        with patch("lab.simulation.runner._run_tournament_for_strategy", return_value=fake_results):
            players = [MagicMock()]
            summary = runner._benchmark_strategy("balanced", players)

        self.assertAlmostEqual(summary["win_rate"], 0.25)

    def test_benchmark_strategy_gate_pass(self):
        """Strategy with above-random win rate should get PASS gate."""
        runner = self.RunnerClass(
            strategies=["balanced"], runs=12, num_opponents=11
        )
        # 12 teams; random chance = 1/12 ≈ 0.083.  We give 3/12 = 0.25 → PASS.
        fake_results = _make_tournament_results("balanced", wins=3, simulations=12)
        with patch("lab.simulation.runner._run_tournament_for_strategy", return_value=fake_results):
            summary = runner._benchmark_strategy("balanced", [])

        self.assertEqual(summary["gate_result"], "PASS")

    def test_benchmark_strategy_gate_fail(self):
        """Strategy with below-random win rate should get FAIL gate."""
        runner = self.RunnerClass(
            strategies=["balanced"], runs=12, num_opponents=11
        )
        # 0 wins → FAIL
        fake_results = _make_tournament_results("balanced", wins=0, simulations=12)
        with patch("lab.simulation.runner._run_tournament_for_strategy", return_value=fake_results):
            summary = runner._benchmark_strategy("balanced", [])

        self.assertEqual(summary["gate_result"], "FAIL")

    def test_benchmark_strategy_missing_key_returns_not_evaluated(self):
        """If the focal strategy key is absent from tournament output, NOT_EVALUATED."""
        runner = self.RunnerClass(strategies=["balanced"], runs=5, num_opponents=11)
        with patch("lab.simulation.runner._run_tournament_for_strategy", return_value={}):
            summary = runner._benchmark_strategy("balanced", [])

        self.assertEqual(summary["gate_result"], "NOT_EVALUATED")
        self.assertEqual(summary["win_rate"], 0.0)

    def test_benchmark_strategy_tournament_exception_not_evaluated(self):
        """A failing tournament returns NOT_EVALUATED without propagating."""
        runner = self.RunnerClass(strategies=["balanced"], runs=5, num_opponents=11)
        with patch(
            "lab.simulation.runner._run_tournament_for_strategy",
            side_effect=RuntimeError("boom"),
        ):
            summary = runner._benchmark_strategy("balanced", [])

        self.assertEqual(summary["gate_result"], "NOT_EVALUATED")

    def test_budget_efficiency_computed(self):
        runner = self.RunnerClass(strategies=["balanced"], runs=20, num_opponents=11)
        fake_results = _make_tournament_results("balanced", wins=10, simulations=20)
        with patch("lab.simulation.runner._run_tournament_for_strategy", return_value=fake_results):
            summary = runner._benchmark_strategy("balanced", [])

        # avg_points=900, avg_spent=190 → 900/190 ≈ 4.74
        self.assertGreater(summary["avg_budget_efficiency"], 0)

    def test_unknown_strategy_key_raises(self):
        runner = self.RunnerClass(strategies=["nonexistent_xyz"], runs=5)
        with patch("lab.simulation.runner._load_players", return_value=[]):
            with self.assertRaises(ValueError):
                runner.run()

    def test_list_strategies_cli(self):
        """--list-strategies should print strategy keys and return normally."""
        from lab.simulation.runner import main
        import io

        captured = io.StringIO()
        with patch("sys.stdout", captured):
            main(["--list-strategies"])  # should return without raising

        output = captured.getvalue()
        self.assertIn("balanced", output)

    def test_experiment_id_defaults_to_short_uuid(self):
        runner = self.RunnerClass()
        self.assertEqual(len(runner.experiment_id), 8)

    def test_custom_experiment_id_preserved(self):
        runner = self.RunnerClass(experiment_id="myexperiment")
        self.assertEqual(runner.experiment_id, "myexperiment")


class TestPersistResults(unittest.TestCase):
    """Tests for _persist_results — writes to in-memory SQLite."""

    def test_persist_creates_benchmark_run(self):
        import asyncio
        from lab.simulation.runner import _persist_results

        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite+aiosqlite:///{tmpdir}/test.db"
            summaries = {
                "balanced": {
                    "win_rate": 0.25,
                    "win_rate_stddev": 0.1,
                    "avg_rank": 3.0,
                    "avg_budget_efficiency": 4.5,
                    "gate_result": "PASS",
                    "raw_results": [],
                }
            }
            asyncio.run(
                _persist_results(
                    experiment_id="test123",
                    strategy_summaries=summaries,
                    total_runs=20,
                    opponent_set=["balanced"] * 11,
                    db_url=db_url,
                )
            )

            # Read back and verify.
            import asyncio as _asyncio
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import select
            from lab.results_db.models import BenchmarkRun, StrategyResult

            async def _check():
                engine = create_async_engine(db_url)
                factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
                async with factory() as s:
                    runs = (await s.execute(select(BenchmarkRun))).scalars().all()
                    results = (await s.execute(select(StrategyResult))).scalars().all()
                await engine.dispose()
                return runs, results

            runs, results = _asyncio.run(_check())

        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].experiment_id, "test123")
        self.assertEqual(runs[0].simulation_count, 20)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].strategy_name, "balanced")
        self.assertAlmostEqual(results[0].win_rate, 0.25)
        self.assertEqual(results[0].gate_result, "PASS")

    def test_persist_multiple_strategies(self):
        import asyncio
        from lab.simulation.runner import _persist_results

        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite+aiosqlite:///{tmpdir}/test2.db"
            summaries = {
                "balanced": {"win_rate": 0.1, "win_rate_stddev": None, "avg_rank": 4.0,
                              "avg_budget_efficiency": 3.5, "gate_result": "FAIL", "raw_results": []},
                "aggressive": {"win_rate": 0.15, "win_rate_stddev": None, "avg_rank": 3.0,
                                "avg_budget_efficiency": 4.0, "gate_result": "PASS", "raw_results": []},
            }
            asyncio.run(
                _persist_results(
                    experiment_id="multi",
                    strategy_summaries=summaries,
                    total_runs=10,
                    opponent_set=["balanced"] * 11,
                    db_url=db_url,
                )
            )

            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import select
            from lab.results_db.models import StrategyResult

            async def _check():
                engine = create_async_engine(db_url)
                factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
                async with factory() as s:
                    results = (await s.execute(select(StrategyResult))).scalars().all()
                await engine.dispose()
                return results

            results = asyncio.run(_check())

        self.assertEqual(len(results), 2)
        names = {r.strategy_name for r in results}
        self.assertIn("balanced", names)
        self.assertIn("aggressive", names)


class TestRunTournamentForStrategy(unittest.TestCase):
    """Tests for _run_tournament_for_strategy helper."""

    def test_returns_dict_with_strategy_key(self):
        from lab.simulation.runner import _run_tournament_for_strategy

        mock_summary = {
            "results": _make_tournament_results("balanced", wins=3, simulations=5)
        }
        mock_tournament = MagicMock()
        mock_tournament.run_tournament.return_value = mock_summary

        with patch("lab.simulation.runner.Tournament", return_value=mock_tournament):
            result = _run_tournament_for_strategy(
                strategy_key="balanced",
                players=[],
                budget=200,
                roster_size=16,
                num_opponents=3,
                runs=5,
            )

        self.assertIn("balanced", result)
        self.assertAlmostEqual(result["balanced"]["win_rate"], 0.6)

    def test_adds_correct_number_of_opponents(self):
        from lab.simulation.runner import _run_tournament_for_strategy

        mock_tournament = MagicMock()
        mock_tournament.run_tournament.return_value = {"results": {}}

        with patch("lab.simulation.runner.Tournament", return_value=mock_tournament):
            _run_tournament_for_strategy(
                strategy_key="balanced",
                players=[],
                budget=200,
                roster_size=16,
                num_opponents=3,
                runs=5,
            )

        # add_strategy_config called once for focal + 3 for opponents = 4 total
        self.assertEqual(mock_tournament.add_strategy_config.call_count, 4)


if __name__ == "__main__":
    unittest.main()


class TestRunnerExtraCoverage(unittest.TestCase):
    """Cover remaining uncovered lines in runner.py."""

    def test_get_git_version_exception(self):
        """Cover lines 44-46: exception handler returns 'unknown'."""
        from lab.simulation.runner import _git_sha
        with patch("subprocess.run", side_effect=FileNotFoundError("no git")):
            result = _git_sha()
        self.assertEqual(result, "unknown")

    def test_load_players(self):
        """Cover lines 51-54: _load_players calls FantasyProsLoader."""
        from lab.simulation.runner import _load_players
        mock_players = [MagicMock(), MagicMock()]
        mock_loader = MagicMock()
        mock_loader.load_all_players.return_value = mock_players
        import data.fantasypros_loader as fl_mod
        with patch.object(fl_mod, "FantasyProsLoader", return_value=mock_loader):
            result = _load_players()
        self.assertEqual(result, mock_players)

    def test_simulation_runner_run_with_all_strategies(self):
        """Cover lines 195-237: run() method with 'all' strategies."""
        from lab.simulation.runner import SimulationRunner
        import strategies as strats_mod

        mock_summary = {
            "win_rate": 0.5,
            "avg_rank": 2.0,
            "avg_budget_efficiency": 0.9,
            "gate_result": "promoted",
        }

        with patch("lab.simulation.runner._load_players", return_value=[MagicMock()]), \
             patch("lab.simulation.runner._persist_results") as mock_persist, \
             patch.object(SimulationRunner, "_benchmark_strategy", return_value=mock_summary), \
             patch.object(strats_mod, "AVAILABLE_STRATEGIES", {"balanced": MagicMock(), "basic": MagicMock()}):
            mock_persist.return_value = None
            runner = SimulationRunner(
                strategies=["all"],
                runs=2,
                budget=200,
                roster_size=16,
                num_opponents=2,
                db_url=None,
                experiment_id="test-run",
            )
            result = runner.run()

        self.assertIn("balanced", result)
        self.assertIn("basic", result)

    def test_simulation_runner_run_unknown_key_raises(self):
        """Cover: unknown strategy key raises ValueError."""
        from lab.simulation.runner import SimulationRunner
        import strategies as strats_mod

        with patch("lab.simulation.runner._load_players", return_value=[]), \
             patch.object(strats_mod, "AVAILABLE_STRATEGIES", {"balanced": MagicMock()}):
            runner = SimulationRunner(
                strategies=["nonexistent_key"],
                runs=1,
                budget=200,
                roster_size=16,
                num_opponents=2,
                db_url=None,
            )

            with self.assertRaises(ValueError):
                runner.run()

    def test_main_list_strategies(self):
        """Cover lines 370-372: main() with --list."""
        from lab.simulation.runner import main
        import strategies as strats_mod
        with patch("sys.argv", ["runner.py", "--list"]), \
             patch.object(strats_mod, "AVAILABLE_STRATEGIES", {"balanced": MagicMock(), "basic": MagicMock()}):
            main()  # Should just print and return

    def test_main_runs(self):
        """Cover lines 374-395: main() run path."""
        from lab.simulation.runner import main
        mock_summaries = {
            "balanced": {"win_rate": 0.5, "avg_rank": 2.0, "avg_budget_efficiency": 0.9, "gate_result": ""},
        }
        mock_runner = MagicMock()
        mock_runner.run = MagicMock(return_value=mock_summaries)
        mock_runner.experiment_id = "test"

        with patch("sys.argv", ["runner.py", "--strategies", "balanced", "--runs", "1"]), \
             patch("lab.simulation.runner.SimulationRunner", return_value=mock_runner):
            main()
