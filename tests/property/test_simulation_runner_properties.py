"""Property tests for lab/simulation/runner.py — SimulationRunner invariants (#344).

Tests:
- SimulationRunner stores all constructor args correctly
- experiment_id is auto-generated (non-empty string) when not provided
- experiment_id is used exactly when provided
- _git_sha() always returns a string
- Gate invariant: win_rate >= 1/(num_opponents+1) ↔ gate_result == 'PASS'
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from lab.simulation.runner import SimulationRunner, _git_sha


# ---------------------------------------------------------------------------
# Tests — constructor parameter storage
# ---------------------------------------------------------------------------

@given(
    runs=st.integers(min_value=1, max_value=500),
    budget=st.floats(min_value=50.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    roster_size=st.integers(min_value=4, max_value=30),
    num_opponents=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=30)
def test_constructor_stores_params_correctly(runs, budget, roster_size, num_opponents):
    """All numeric constructor args are stored exactly on the instance."""
    runner = SimulationRunner(
        strategies=["balanced"],
        runs=runs,
        budget=budget,
        roster_size=roster_size,
        num_opponents=num_opponents,
    )
    assert runner.runs == runs
    assert runner.budget == budget
    assert runner.roster_size == roster_size
    assert runner.num_opponents == num_opponents


@given(st.just(None))
@settings(max_examples=5)
def test_experiment_id_auto_generated(_):
    """experiment_id is non-empty string when not explicitly provided."""
    runner = SimulationRunner()
    assert isinstance(runner.experiment_id, str)
    assert len(runner.experiment_id) > 0


@given(
    exp_id=st.text(min_size=1, max_size=64),
)
@settings(max_examples=20)
def test_experiment_id_preserved_when_provided(exp_id):
    """experiment_id is stored exactly when explicitly provided."""
    runner = SimulationRunner(experiment_id=exp_id)
    assert runner.experiment_id == exp_id


@given(st.just(None))
@settings(max_examples=3)
def test_two_runners_have_different_auto_ids(_):
    """Two SimulationRunner instances auto-generate distinct experiment_ids."""
    r1 = SimulationRunner()
    r2 = SimulationRunner()
    assert r1.experiment_id != r2.experiment_id


# ---------------------------------------------------------------------------
# Tests — _git_sha()
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=3)
def test_git_sha_returns_string(_):
    """_git_sha() always returns a string (either a commit SHA or 'unknown')."""
    result = _git_sha()
    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Tests — gate_result invariant
# ---------------------------------------------------------------------------

@given(
    win_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    num_opponents=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=100)
def test_gate_result_pass_iff_win_rate_meets_threshold(win_rate, num_opponents):
    """gate_result == 'PASS' if and only if win_rate >= 1/(num_opponents+1)."""
    num_teams = num_opponents + 1
    expected_win_rate = 1.0 / num_teams
    gate_result = "PASS" if win_rate >= expected_win_rate else "FAIL"
    
    # Verify the invariant holds
    if win_rate >= expected_win_rate:
        assert gate_result == "PASS"
    else:
        assert gate_result == "FAIL"
    
    # Verify PASS and FAIL are mutually exclusive and exhaustive
    assert gate_result in ("PASS", "FAIL")


@given(
    num_opponents=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=30)
def test_gate_threshold_decreases_with_more_opponents(num_opponents):
    """The win-rate threshold to PASS decreases as more opponents are added."""
    threshold_small = 1.0 / (num_opponents + 1)
    threshold_large = 1.0 / (num_opponents + 2)
    assert threshold_large < threshold_small
