"""Unit tests for SimulationRunner — QA Phase 1 — closes #187."""
from __future__ import annotations

import unittest
from unittest.mock import patch


class TestSimulationRunnerInstantiation(unittest.TestCase):
    """SimulationRunner can be instantiated with no args."""

    def test_instantiation(self):
        from lab.simulation.runner import SimulationRunner

        runner = SimulationRunner()
        self.assertIsNotNone(runner)


class TestSimulationRunnerRun(unittest.TestCase):
    """run(n_simulations=N) returns a list of N SimulationResult objects."""

    def _make_result(self, name: str = "balanced", score: float = 0.5):
        from lab.simulation.runner import SimulationResult

        return SimulationResult(strategy_name=name, score=score)

    def test_run_returns_list_of_n_results(self):
        from lab.simulation.runner import SimulationRunner

        runner = SimulationRunner(strategies=["balanced"])
        with patch.object(runner, "_run_single", side_effect=[
            self._make_result(score=0.9),
            self._make_result(score=0.5),
            self._make_result(score=0.3),
        ]):
            results = runner.run(n_simulations=3)

        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 3)

    def test_each_result_has_required_fields(self):
        from lab.simulation.runner import SimulationRunner

        runner = SimulationRunner(strategies=["balanced"])
        with patch.object(runner, "_run_single", side_effect=[
            self._make_result("balanced", 0.9),
            self._make_result("balanced", 0.5),
            self._make_result("balanced", 0.3),
        ]):
            results = runner.run(n_simulations=3)

        for r in results:
            self.assertIsInstance(r.strategy_name, str)
            self.assertIsInstance(r.score, float)
            self.assertIsInstance(r.rank, int)

    def test_strategy_error_doesnt_crash(self):
        """A simulation that raises should not propagate — it produces an error result."""
        from lab.simulation.runner import SimulationRunner

        runner = SimulationRunner(strategies=["balanced"])
        call_count = 0

        def flaky_side_effect(sim_id: int):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("strategy exploded")
            return self._make_result(score=0.5)

        with patch.object(runner, "_run_single", side_effect=flaky_side_effect):
            results = runner.run(n_simulations=3)

        # All 3 results returned despite one failure
        self.assertEqual(len(results), 3)

    def test_results_sorted_by_rank(self):
        """Rank 1 corresponds to highest score; results are in ascending rank order."""
        from lab.simulation.runner import SimulationRunner

        runner = SimulationRunner(strategies=["balanced"])
        with patch.object(runner, "_run_single", side_effect=[
            self._make_result(score=0.3),
            self._make_result(score=0.9),
            self._make_result(score=0.5),
        ]):
            results = runner.run(n_simulations=3)

        ranks = [r.rank for r in results]
        self.assertEqual(ranks, sorted(ranks))
        # Rank 1 has the highest score
        self.assertEqual(results[0].rank, 1)
        self.assertGreaterEqual(results[0].score, results[1].score)
        self.assertGreaterEqual(results[1].score, results[2].score)
