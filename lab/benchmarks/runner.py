"""Benchmark runner for multi-strategy auction draft comparisons.

Runs a configurable number of simulated drafts for each registered strategy
and records aggregate metrics. Implementation tracked by issue #227.
"""

from __future__ import annotations

from typing import List


class BenchmarkRunner:
    """Orchestrates benchmark runs across multiple strategies.

    Args:
        strategies: List of strategy names to benchmark.
        runs: Number of simulation runs per strategy.
    """

    def __init__(self, strategies: List[str], runs: int = 100) -> None:
        self.strategies = strategies
        self.runs = runs

    def run(self) -> dict:
        """Execute benchmark runs for all configured strategies.

        Returns:
            A mapping of strategy name → aggregate result metrics.

        Raises:
            NotImplementedError: Until issue #227 is implemented.
        """
        raise NotImplementedError("BenchmarkRunner.run — tracked by #227")
