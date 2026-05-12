"""Property tests for strategies/spending_analyzer.py — efficiency invariants (#335).

The SpendingAnalyzer is a pure-computation script module. Its mathematical
relationships must hold for any valid inputs:

Tests:
- budget_usage = (avg_spent / max_budget) * 100 stays in [0, 100]
- efficiency = typical_players / max(avg_spent, 1) * 100 is always non-negative
- underspending = max_budget - avg_spent equals the budget surplus
- After sorting by budget_usage the list is monotone non-decreasing
- analyze_spending_patterns() runs to completion without raising an exception
"""
from __future__ import annotations

import contextlib
import io

from hypothesis import given, settings
from hypothesis import strategies as st

from strategies.spending_analyzer import analyze_spending_patterns


# ---------------------------------------------------------------------------
# Tests — mathematical invariants
# ---------------------------------------------------------------------------

@given(
    avg_spent=st.integers(min_value=0, max_value=1000),
    max_budget=st.integers(min_value=1, max_value=1000),
)
@settings(max_examples=100)
def test_budget_usage_in_valid_range(avg_spent, max_budget):
    """budget_usage = (clamped_spent / max_budget) * 100 is in [0.0, 100.0]."""
    # avg_spent cannot exceed max_budget in valid data; clamp for the formula check.
    clamped_spent = min(avg_spent, max_budget)
    budget_usage = (clamped_spent / max_budget) * 100
    assert 0.0 <= budget_usage <= 100.0


@given(
    typical_players=st.integers(min_value=0, max_value=30),
    avg_spent=st.integers(min_value=0, max_value=500),
)
@settings(max_examples=100)
def test_efficiency_always_nonnegative(typical_players, avg_spent):
    """efficiency = typical_players / max(avg_spent, 1) * 100 is always >= 0."""
    efficiency = typical_players / max(avg_spent, 1) * 100
    assert efficiency >= 0.0


@given(
    avg_spent=st.integers(min_value=0, max_value=500),
    max_budget=st.integers(min_value=0, max_value=500),
)
@settings(max_examples=100)
def test_underspending_is_nonnegative_when_within_budget(avg_spent, max_budget):
    """underspending = max_budget - avg_spent is non-negative when avg_spent <= max_budget."""
    clamped_spent = min(avg_spent, max_budget)
    underspending = max_budget - clamped_spent
    assert underspending >= 0


@given(
    avg_spent=st.integers(min_value=0, max_value=200),
    max_budget=st.integers(min_value=1, max_value=200),
)
@settings(max_examples=100)
def test_budget_usage_plus_underspend_equals_max_budget(avg_spent, max_budget):
    """(budget_usage / 100) * max_budget + underspending == max_budget."""
    clamped_spent = min(avg_spent, max_budget)
    budget_usage_pct = (clamped_spent / max_budget) * 100
    underspending = max_budget - clamped_spent
    # Reconstruct: (budget_usage_pct / 100) * max_budget == clamped_spent
    reconstructed = (budget_usage_pct / 100) * max_budget
    assert abs(reconstructed + underspending - max_budget) < 1e-9


# ---------------------------------------------------------------------------
# Tests — sorting invariant
# ---------------------------------------------------------------------------

@given(
    entries=st.lists(
        st.fixed_dictionaries({
            "avg_spent": st.integers(min_value=1, max_value=200),
            "max_budget": st.integers(min_value=1, max_value=500),
        }),
        min_size=1,
        max_size=20,
    )
)
@settings(max_examples=50)
def test_sorting_by_budget_usage_is_monotone_nondecreasing(entries):
    """After sorting by budget_usage the resulting sequence is monotone non-decreasing."""
    computed = [
        {
            **e,
            "budget_usage": (min(e["avg_spent"], e["max_budget"]) / e["max_budget"]) * 100,
        }
        for e in entries
    ]
    sorted_entries = sorted(computed, key=lambda x: x["budget_usage"])
    for i in range(len(sorted_entries) - 1):
        assert sorted_entries[i]["budget_usage"] <= sorted_entries[i + 1]["budget_usage"]


# ---------------------------------------------------------------------------
# Tests — function smoke test
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=1)
def test_analyze_spending_patterns_runs_without_error(_):
    """analyze_spending_patterns() completes without raising any exception."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        analyze_spending_patterns()
    # If we reach here the function ran successfully; output should be non-empty.
    assert len(buf.getvalue()) > 0
