"""QA Phase 1 — Issue #190: lab-ci GitHub Actions nightly benchmark workflow

Failing tests that verify the promotion pipeline components integrate correctly
and that the expected workflow entry points exist and are callable.

These tests MUST FAIL before the fix and PASS after.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# All tests in this file are QA Phase 1 gates — expected to FAIL until the
# fix for issue #190 is implemented. Remove this mark after implementation.
pytestmark = pytest.mark.xfail(
    strict=False,
    reason="QA Phase 1 gate for #190 — fails until lab-ci workflow and PromotionGate/BenchmarkRunner are implemented",
)

_REPO_ROOT = Path(__file__).parent.parent.parent.parent


# ---------------------------------------------------------------------------
# Test 1: Workflow file exists at the expected path
# ---------------------------------------------------------------------------

class TestLabCiWorkflowFileExists:
    def test_lab_ci_workflow_file_exists(self):
        """A lab-ci GitHub Actions workflow must exist at .github/workflows/lab-ci.yml."""
        workflow_path = _REPO_ROOT / ".github" / "workflows" / "lab-ci.yml"
        assert workflow_path.exists(), (
            f"Expected lab-ci workflow at {workflow_path} but it does not exist. "
            "Create .github/workflows/lab-ci.yml with a nightly schedule trigger "
            "and workflow_dispatch as specified in issue #190."
        )

    def test_lab_ci_workflow_has_schedule_trigger(self):
        """The lab-ci workflow must have a schedule (cron) trigger."""
        import yaml

        workflow_path = _REPO_ROOT / ".github" / "workflows" / "lab-ci.yml"
        if not workflow_path.exists():
            pytest.skip("Workflow file not yet created")

        with open(workflow_path) as f:
            content = yaml.safe_load(f)

        triggers = content.get("on", content.get(True, {}))
        assert "schedule" in triggers, (
            "lab-ci.yml must define an 'on.schedule' (cron) trigger. "
            "Add: 'on:\\n  schedule:\\n    - cron: \"0 6 * * *\"'"
        )

    def test_lab_ci_workflow_has_workflow_dispatch(self):
        """The lab-ci workflow must support manual triggering via workflow_dispatch."""
        import yaml

        workflow_path = _REPO_ROOT / ".github" / "workflows" / "lab-ci.yml"
        if not workflow_path.exists():
            pytest.skip("Workflow file not yet created")

        with open(workflow_path) as f:
            content = yaml.safe_load(f)

        triggers = content.get("on", content.get(True, {}))
        assert "workflow_dispatch" in triggers, (
            "lab-ci.yml must define an 'on.workflow_dispatch' trigger for manual runs."
        )

    def test_lab_ci_workflow_no_hardcoded_secrets(self):
        """The lab-ci workflow must not contain any hardcoded secret values."""
        workflow_path = _REPO_ROOT / ".github" / "workflows" / "lab-ci.yml"
        if not workflow_path.exists():
            pytest.skip("Workflow file not yet created")

        content = workflow_path.read_text()
        # No raw API keys, tokens, or passwords
        dangerous_patterns = [
            "PIGSKIN_API_KEY: ",   # key directly assigned (not ${{ secrets.* }})
        ]
        for pattern in dangerous_patterns:
            if pattern in content:
                # Allow if immediately followed by ${{ secrets.
                idx = content.index(pattern)
                after = content[idx + len(pattern):idx + len(pattern) + 15]
                assert after.startswith("${{"), (
                    f"Potential hardcoded secret near '{pattern}' in lab-ci.yml. "
                    "Always use ${{{{ secrets.SECRET_NAME }}}} syntax."
                )


# ---------------------------------------------------------------------------
# Test 2: PromotionGate.evaluate() is callable and returns a typed result
# ---------------------------------------------------------------------------

class TestPromotionGateEvaluate:
    def test_promotion_gate_evaluate_exists(self):
        """PromotionGate must have an evaluate() method."""
        from lab.promotion.gate import PromotionGate
        assert hasattr(PromotionGate, "evaluate"), (
            "PromotionGate must define an evaluate() method. "
            "This is called by the lab-ci workflow to decide whether to open a PR."
        )

    def test_promotion_gate_evaluate_returns_bool_or_result(self):
        """PromotionGate.evaluate() must return a truthy/falsy value or a typed result."""
        from lab.promotion.gate import PromotionGate

        gate = PromotionGate()
        mock_results = [
            {"strategy": "balanced", "win_rate": 0.65, "efficiency": 0.82},
            {"strategy": "value_smart", "win_rate": 0.55, "efficiency": 0.75},
        ]
        try:
            result = gate.evaluate(mock_results)
        except TypeError as e:
            pytest.fail(
                f"PromotionGate.evaluate() raised TypeError: {e}. "
                "It must accept a list of result dicts."
            )
        # Result must be truthy-evaluable (bool, int, named result, etc.)
        assert result is not None, "PromotionGate.evaluate() must return a non-None value."


# ---------------------------------------------------------------------------
# Test 3: BenchmarkRunner runs at least one strategy without errors
# ---------------------------------------------------------------------------

class TestBenchmarkRunnerSmoke:
    def test_benchmark_runner_importable(self):
        """lab.benchmarks.runner must be importable."""
        try:
            from lab.benchmarks.runner import BenchmarkRunner  # noqa: F401
        except ImportError as e:
            pytest.fail(
                f"Cannot import BenchmarkRunner from lab.benchmarks.runner: {e}. "
                "Ensure lab/benchmarks/runner.py defines BenchmarkRunner."
            )

    def test_benchmark_runner_has_run_method(self):
        """BenchmarkRunner must define a run() method."""
        from lab.benchmarks.runner import BenchmarkRunner
        assert hasattr(BenchmarkRunner, "run"), (
            "BenchmarkRunner must define a run() method that executes benchmarks "
            "and returns a list of result dicts."
        )

    def test_benchmark_runner_run_returns_list_or_dict(self):
        """BenchmarkRunner.run() must return a list or dict of results (not raise)."""
        from lab.benchmarks.runner import BenchmarkRunner

        runner = BenchmarkRunner(strategies=["balanced"], runs=1)
        try:
            results = runner.run()
        except NotImplementedError:
            pytest.fail(
                "BenchmarkRunner.run() raises NotImplementedError — issue #190 "
                "requires this to be implemented so the lab-ci workflow can call it."
            )
        except Exception as e:
            pytest.fail(f"BenchmarkRunner.run() raised unexpected {type(e).__name__}: {e}")

        assert isinstance(results, (list, dict)), (
            f"BenchmarkRunner.run() returned {type(results)}, expected list or dict."
        )
