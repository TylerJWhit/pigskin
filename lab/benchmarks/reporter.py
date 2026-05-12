"""Benchmark report generator for strategy comparison results.

Formats aggregate benchmark results into human-readable or machine-readable
reports. Implementation tracked by issue #227.
"""

from __future__ import annotations

from typing import Any, Dict


class BenchmarkReporter:
    """Generates reports from benchmark run results.

    Args:
        results: Mapping of strategy name → aggregate metrics, as returned by
            :class:`~lab.benchmarks.runner.BenchmarkRunner`.
    """

    def __init__(self, results: Dict[str, Any]) -> None:
        self.results = results

    def generate_report(self, output_format: str = "text") -> str:
        """Render benchmark results as a formatted report.

        Args:
            output_format: One of ``"text"``, ``"markdown"``, or ``"json"``.

        Returns:
            The formatted report as a string.

        Raises:
            NotImplementedError: Until issue #227 is implemented.
        """
        raise NotImplementedError("BenchmarkReporter.generate_report — tracked by #227")
