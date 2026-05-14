# QA Validation Plan — Testing Refactor (ADR-010)

**Date:** 2026-05-13  
**ADR:** ADR-010  
**Prepared by:** QA Agent  
**Scope:** Validating the test-suite refactor itself, not production code changes

---

## Regression Definition

> **An unacceptable regression is any of the following:**
> - A test that passed before the refactor now fails (exit-code change or status `FAILED`)
> - A test that was collected before the refactor is no longer collected (silent deletion)
> - A test that was `XFAIL` (expected failure) unexpectedly becomes `ERROR` (import error or collection crash)
> - The total collected test count drops below 2076 at any gate where no tests have been intentionally merged/removed
> - A previously-silent `DeprecationWarning` becomes an `ERROR` due to unintended `-W error` escalation
> - Coverage drops below the `fail_under` threshold set in Phase 4

> **Acceptable non-regressions:**
> - `XPASS` (unexpected pass) for any of the 5 QA-gate xfail files — these are the target outcome of the issues they guard
> - Test count change caused by a documented merge of duplicate tests (must match merge manifest)
> - A `DeprecationWarning` from `ConfigManager()` in `draft_loading_service.py` — tracked in issue #393, out of scope here

---

## Section 1: Pre-Refactor Baseline Capture (Gate 0)

Run the following commands **on the unmodified branch** (before any PR changes). Commit or archive every output file. All subsequent gates compare against these snapshots.

### 1.1 — Lock the test count

```bash
source venv/bin/activate
pytest --collect-only -q 2>/dev/null | tail -1
# Expected: "2076 tests collected" (or current count — record the exact number)
```

### 1.2 — Capture the full test name list

```bash
pytest --collect-only -q 2>/dev/null \
    | grep "::" \
    | sort \
    > /tmp/baseline_test_names.txt

wc -l /tmp/baseline_test_names.txt
# Commit this file or store it as a CI artifact
```

### 1.3 — Capture current xfail/xpass breakdown

```bash
pytest -v --tb=no -q 2>/dev/null \
    | grep -E "XFAIL|XPASS" \
    > /tmp/baseline_xfail.txt

cat /tmp/baseline_xfail.txt
# Expected: entries for 5 files:
#   tests/unit/strategies/test_position_targets_hardcoding.py
#   tests/unit/classes/test_draft_setup_layering.py
#   tests/unit/config/test_config_consolidation.py
#   tests/unit/cli/test_commands_decomposition.py
#   tests/unit/lab/test_lab_ci_pipeline.py
```

### 1.4 — Capture DeprecationWarning inventory

```bash
pytest -W error::DeprecationWarning --tb=short -q 2>&1 \
    | grep -E "DeprecationWarning|FAILED|ERROR" \
    > /tmp/baseline_deprecation_warnings.txt

cat /tmp/baseline_deprecation_warnings.txt
# Expected: failures from ConfigManager() in draft_loading_service.py (issue #393)
# Record exact count of failures so Phase 4 can distinguish old from new
```

### 1.5 — Confirm no existing coverage config

```bash
grep -n "tool.coverage\|fail_under" pyproject.toml
# Expected: no matches — confirms pyproject.toml has no coverage section yet
```

### 1.6 — Record which root-level files are currently collected

```bash
pytest --collect-only -q tests/ 2>/dev/null \
    | grep "^tests/test_" \
    | sed 's/::.*$//' \
    | sort -u \
    > /tmp/baseline_root_files.txt

wc -l /tmp/baseline_root_files.txt
# Expected: 28 lines — one per root-level test file
```

---

## Section 2: Per-Phase Validation Gates

Each gate must exit 0 (or meet the documented criterion) before proceeding to the next phase.

---

### Phase 0 — Add `--strict-markers` and fix unregistered markers

**Goal:** Confirm that every marker in use across the test suite is declared in `pytest.ini`, then lock the suite against future undeclared markers.

#### Step 0.1 — Dry-run with `--strict-markers` (before any fixes)

```bash
pytest --collect-only --strict-markers -q 2>&1 \
    | grep -E "PytestUnknownMarkWarning|ERROR|error" \
    | sort -u
```

**Pass criterion:** Output is empty (no unknown markers), or output lists only the markers that will be added to `pytest.ini` in this phase.  
**Fail criterion:** Any `PytestUnknownMarkWarning` for a marker not in the fix plan.

#### Step 0.2 — After adding `--strict-markers` to `pytest.ini` `addopts` and fixing all gaps

```bash
pytest --tb=short -q 2>&1 | tail -5
```

**Pass criteria (all must hold):**
- Exit code 0
- Collected test count equals baseline (2076, or current baseline from Gate 0)
- Zero `FAILED`, zero `ERROR`
- XFAIL count matches `/tmp/baseline_xfail.txt` (no change to xfail status)
- No `PytestUnknownMarkWarning` anywhere in stdout/stderr

**What counts as a regression:** Any previously-passing test now has `FAILED` or `ERROR` status.

**Edge case:** `test_pytest_marks.py` asserts that all markers in `REQUIRED_MARKS` are registered. If `property` is absent from `REQUIRED_MARKS` (known gap per ADR-010 §1), this test will fail. Fix: add `property` to `REQUIRED_MARKS` in `tests/unit/test_pytest_marks.py` as part of this phase.

---

### Phase 1 — Add `@pytest.mark` annotations to all unmarked files

**Goal:** Every file in `tests/unit/` and `tests/integration/` carries at least one `pytestmark` or per-test `@pytest.mark.*` annotation. This enables selective test runs by marker.

#### Step 1.1 — Smoke: run only the `unit` marker before and after

Before annotating (should collect 0 if `--strict-markers` is on but no files are annotated yet):

```bash
pytest -m unit --collect-only -q 2>/dev/null | tail -1
# Record baseline unit-marked count
```

After annotating:

```bash
pytest -m unit --collect-only -q 2>/dev/null | tail -1
# Must be > 0 and ≤ total count
```

#### Step 1.2 — Full suite regression check

```bash
pytest --tb=short -q 2>&1 | tail -5
```

**Pass criteria:**
- Exit code 0
- Collected count unchanged from Phase 0 gate
- Zero `FAILED`, zero `ERROR`
- XFAIL count unchanged from baseline

#### Step 1.3 — Marker isolation check

```bash
pytest -m "unit or integration or property" --collect-only -q 2>/dev/null | tail -1
# Must match total collected count — every test file must carry one of these markers
```

**Pass criterion:** Count from this command equals the total test count. Any test not reachable by `unit or integration or property` is an unmarked test that was missed.

**What counts as a regression:** Any test that was collected before is now excluded by the marker filter.

---

### Phase 2 — Structural consolidation (root → `unit/`) and sprint-file renames

**Goal:** All 28 root-level test files moved/merged into canonical `tests/unit/` subdirectory files; 4 sprint-labeled root files absorbed into their target canonical files. No tests are deleted.

#### Step 2.1 — Pre-move: snapshot merged-in test names

Before merging each sprint/root file, capture its test names:

```bash
# Example for test_sprint7_regressions.py before merge
pytest --collect-only -q tests/test_sprint7_regressions.py 2>/dev/null \
    | grep "::" | sort > /tmp/sprint7_before_merge.txt
```

Repeat for: `test_sprint7b_regressions.py`, `test_sprint7c_regressions.py`, `test_sprint8_regressions.py`, `test_f811_regressions.py`, and each of the 23 other root test files.

#### Step 2.2 — After each individual file move/merge

```bash
pytest --collect-only -q 2>/dev/null | tail -1
# Count must be ≥ baseline (never drop below 2076 mid-phase unless a file
# was intentionally removed AND its tests appear in a canonical file)
```

Verify the moved tests are present in the destination file:

```bash
# Example: after merging sprint7 into unit/strategies/test_base_strategy.py
pytest --collect-only -q tests/unit/strategies/test_base_strategy.py 2>/dev/null \
    | grep "::" | sort > /tmp/sprint7_after_merge.txt

diff /tmp/sprint7_before_merge.txt /tmp/sprint7_after_merge.txt
# Expected: all sprint7 test names appear as added lines in the after-merge file
```

#### Step 2.3 — After all 28 root files are removed

```bash
# Root tests/ directory should have NO test_*.py files remaining
ls tests/test_*.py 2>&1
# Expected: "No such file or directory" or empty listing

# Full suite must still pass
pytest --tb=short -q 2>&1 | tail -5
```

**Pass criteria:**
- Exit code 0
- `ls tests/test_*.py` returns no files
- Collected count equals baseline (all tests preserved, none deleted)
- Zero `FAILED`, zero `ERROR`
- XFAIL count unchanged from baseline

#### Step 2.4 — Diff collected test names against baseline

```bash
pytest --collect-only -q 2>/dev/null \
    | grep "::" \
    | sort \
    > /tmp/phase2_test_names.txt

diff /tmp/baseline_test_names.txt /tmp/phase2_test_names.txt
```

**Pass criterion:** No lines prefixed with `<` (i.e., no tests present in baseline that are now missing). Lines prefixed with `>` are permitted only if they correspond to documented test additions (from merges that produced new parametrized IDs or renamed classes).

**Gotchas specific to this codebase:**

1. **`sys.path.insert` in root test files.** Three root files (`test_f811_regressions.py`, `test_sprint7_regressions.py`, `test_sprint8_regressions.py`) contain `sys.path.insert(0, ...)`. These lines must be **deleted** when moving those files into `unit/` — they are no longer needed because `pytest.ini` already sets `pythonpath = . tests`. Do not delete the `sys.path.insert` at `tests/unit/utils/test_utils_coverage.py` line 431 — that one is inside a test function body and is testing path manipulation behavior, not a module-level hack.

2. **`tests/__init__.py` imports `BaseTestCase`.** The file `tests/__init__.py` contains `from .test_base import BaseTestCase, TestDataGenerator, run_test_suite`. This import will crash as soon as `test_base.py` is deleted. Update or clear `tests/__init__.py` as part of Phase 2 (or Phase 4 at the latest), before deleting `test_base.py`.

3. **Five files inherit from `BaseTestCase`:** `test_classes.py`, `test_integration.py`, `test_data_api.py`, `test_services.py`, `test_strategies.py`. All five are root-level files that will be moved in Phase 2. Ensure each destination canonical file no longer imports from `test_base`; instead use conftest fixtures or inline the setUp logic.

4. **Sprint-file `unittest.TestCase` subclasses.** Per ADR-010 §4.2, existing `unittest.TestCase` subclasses may remain as-is during migration; conversion to plain pytest classes is a follow-up. Verify the migrated classes still run by checking they appear in `pytest --collect-only` output (pytest collects `unittest.TestCase` subclasses natively).

5. **`testpaths = tests` in `pytest.ini`.** After the move, `testpaths` still resolves to `tests/`, which includes `tests/unit/`. No change needed — but confirm that `tests/integration/` is also discovered (it falls within `tests/`).

---

### Phase 3 — Strategy xfail removal and strategy test restoration

**Goal:** Remove `pytestmark = pytest.mark.xfail(...)` from all 5 QA-gate files after their tracked issues are resolved. The removed xfail tests must now either PASS or be explicitly skipped with justification.

**Prerequisite:** Confirm the underlying issue for each xfail file is resolved before removing its mark. The 5 files and their issues:

| File | Issue | Condition for xfail removal |
|---|---|---|
| `tests/unit/strategies/test_position_targets_hardcoding.py` | #213–217 | Hardcoded `total_slots=15` / `position_targets` removed from all strategy files |
| `tests/unit/classes/test_draft_setup_layering.py` | #358 | `classes/draft_setup.py` decoupled from `api/` |
| `tests/unit/config/test_config_consolidation.py` | #359 | `ConfigManager()` emits `DeprecationWarning`; all production callers migrated to `get_settings()` |
| `tests/unit/cli/test_commands_decomposition.py` | #366 | `cli/commands.py` decomposed below 400 lines |
| `tests/unit/lab/test_lab_ci_pipeline.py` | #190 | `PromotionGate` / `BenchmarkRunner` implemented |

#### Step 3.1 — Before removing each xfail mark, verify the issue is done

```bash
# Confirm the file currently has XFAIL results (not ERROR)
pytest -v tests/unit/strategies/test_position_targets_hardcoding.py --tb=short 2>&1 \
    | grep -E "XFAIL|XPASS|ERROR|PASSED|FAILED"
# Must show XFAIL or XPASS — never ERROR (ERROR means collection crash, not a known failure)
```

If `ERROR` appears, the file has an import problem that must be fixed before touching the xfail mark.

#### Step 3.2 — After removing a single xfail mark

```bash
pytest -v tests/unit/strategies/test_position_targets_hardcoding.py --tb=short 2>&1 \
    | grep -E "PASSED|FAILED|ERROR"
```

**Pass criterion:** All tests in the file show `PASSED`. Zero `FAILED`, zero `ERROR`.

#### Step 3.3 — Full suite check after all xfail marks removed

```bash
pytest --tb=short -q 2>&1 | tail -5
```

**Pass criteria:**
- Exit code 0
- Zero `FAILED`, zero `ERROR`, zero `XFAIL` (none remaining)
- Collected count equals or exceeds baseline (xfail tests that now PASS still count)

#### Step 3.4 — Confirm no stale xfail marks anywhere in the test suite

```bash
grep -rn "pytestmark.*xfail\|pytest.mark.xfail" tests/ --include="*.py" \
    | grep -v __pycache__
# Expected: no output — all xfail marks removed
```

**What counts as a regression:** Any test in these 5 files that fails (`FAILED`) after xfail removal. `XPASS` before removal was the signal that the underlying issue was already fixed; a `FAILED` after removal means the production fix is incomplete.

---

### Phase 4 — Coverage configuration, `fail_under`, and BaseTestCase removal

**Goal:** `pyproject.toml` gains `[tool.coverage.run]` and `[tool.coverage.report]` with `fail_under = 70`; `tests/test_base.py` is deleted; `tests/__init__.py` no longer imports from it; all 4 `ConfigManager()` call sites in `tests/test_data_api.py` (lines 203, 217, 233, 246) are replaced with `get_settings()`-compatible construction.

#### Step 4.1 — Verify BaseTestCase consumers are migrated before deletion

```bash
grep -rn "from test_base import\|import BaseTestCase\|from tests.test_base import" \
    tests/ --include="*.py" | grep -v __pycache__
# Expected: no matches
# Also check tests/__init__.py explicitly:
grep "test_base" tests/__init__.py
# Expected: no matches
```

Do not delete `test_base.py` until this step passes cleanly.

#### Step 4.2 — Verify ConfigManager() call sites in test files are gone

```bash
grep -rn "ConfigManager()" tests/ --include="*.py" | grep -v __pycache__
# Expected: no matches
# (The 4 sites in tests/test_data_api.py must be replaced; unit/config/test_config_consolidation.py
#  references ConfigManager() in string literals / test assertions — those are intentional and OK)
```

Disambiguate: string/comment references vs. live instantiations:

```bash
grep -rn "ConfigManager()" tests/ --include="*.py" | grep -v __pycache__ \
    | grep -v "\"ConfigManager()" | grep -v "'ConfigManager()"
# Expected: no matches
```

#### Step 4.3 — Confirm coverage config is present in pyproject.toml

```bash
grep -A 10 "\[tool.coverage" pyproject.toml
# Expected: sections [tool.coverage.run] and [tool.coverage.report] with fail_under = 70
```

#### Step 4.4 — Run coverage with the new config and verify the gate

```bash
pytest --cov=. --cov-report=term-missing --cov-fail-under=70 -q 2>&1 | tail -20
```

**Pass criteria:**
- Exit code 0 (which means both tests pass AND coverage ≥ 70%)
- "Required test coverage of 70% reached" message in output
- Zero `FAILED`, zero `ERROR`

**Fail criterion:** Exit code 2 (coverage below threshold). If coverage is below 70%, this is a configuration problem (wrong `source` in `[tool.coverage.run]`, or `omit` excluding too much), not a test failure.

#### Step 4.5 — Delete test_base.py and confirm no import errors

```bash
# Delete the file
rm tests/test_base.py

# Immediately re-collect to surface any broken imports
pytest --collect-only -q 2>&1 | grep -E "ERROR|ImportError|ModuleNotFoundError"
# Expected: no matches
```

**What counts as a regression:** Any `ImportError` or `ModuleNotFoundError` after deletion. Any test count drop (all BaseTestCase consumers must have been migrated in previous steps).

---

## Section 3: Final Acceptance Gate

Run this sequence on the final refactor branch. **All commands must exit 0.**

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Collect: must match or exceed baseline, no collection errors
pytest --collect-only --strict-markers -q 2>/dev/null | tail -1

# 2. Full suite: zero failures, zero errors, strict markers enforced
pytest --strict-markers --tb=short -q

# 3. Marker completeness: every test reachable by the three top-level markers
TOTAL=$(pytest --collect-only -q 2>/dev/null | tail -1 | awk '{print $1}')
MARKED=$(pytest -m "unit or integration or property" --collect-only -q 2>/dev/null | tail -1 | awk '{print $1}')
[ "$TOTAL" = "$MARKED" ] || { echo "FAIL: $((TOTAL - MARKED)) unmarked tests"; exit 1; }

# 4. No stale xfail marks
XFAIL_COUNT=$(grep -rn "pytestmark.*xfail\|pytest.mark.xfail" tests/ --include="*.py" \
    | grep -v __pycache__ | wc -l)
[ "$XFAIL_COUNT" -eq 0 ] || { echo "FAIL: $XFAIL_COUNT xfail marks remain"; exit 1; }

# 5. No root-level test files
ROOT_FILES=$(ls tests/test_*.py 2>/dev/null | wc -l)
[ "$ROOT_FILES" -eq 0 ] || { echo "FAIL: $ROOT_FILES root test files remain"; exit 1; }

# 6. No sys.path.insert hacks (module-level)
# Exclude the one inside test_utils_coverage.py which is inside a function body
SYSPATH=$(grep -rn "^sys.path.insert" tests/ --include="*.py" | grep -v __pycache__ | wc -l)
[ "$SYSPATH" -eq 0 ] || { echo "FAIL: $SYSPATH module-level sys.path.insert lines remain"; exit 1; }

# 7. No live ConfigManager() instantiation in test files
CM=$(grep -rn "ConfigManager()" tests/ --include="*.py" | grep -v __pycache__ \
    | grep -v "\"ConfigManager()" | grep -v "'ConfigManager()" | wc -l)
[ "$CM" -eq 0 ] || { echo "FAIL: $CM live ConfigManager() call sites in tests"; exit 1; }

# 8. test_base.py deleted
[ ! -f tests/test_base.py ] || { echo "FAIL: tests/test_base.py still exists"; exit 1; }

# 9. Coverage gate
pytest --cov=. --cov-report=term-missing --cov-fail-under=70 -q

echo ""
echo "✓ All acceptance gates passed — refactor PR is mergeable"
```

If every step in this script exits 0, the PR is mergeable.

---

## Appendix: Edge Cases and Codebase-Specific Gotchas

### A. `tests/__init__.py` is a live import, not dead code

`tests/__init__.py` re-exports `BaseTestCase`, `TestDataGenerator`, and `run_test_suite` from `test_base.py`. Deleting `test_base.py` without updating `__init__.py` will cause an `ImportError` on the entire `tests` package. This will manifest as **all tests failing to collect** — not a single test failure but a total collection crash. Update `tests/__init__.py` to an empty file (or remove the imports) as part of Phase 2 before `test_base.py` is deleted.

### B. `strict=False` on all xfail files means XPASS is silent today

The 5 xfail files use `strict=False`, so if an underlying issue gets fixed before Phase 3, the tests will silently show `XPASS` without failing the suite. The Phase 3 gate in Step 3.3 explicitly checks for zero remaining `XFAIL` — but also run `grep -rn "XPASS" /tmp/pytest_output.txt` to detect stealth passes that indicate early issue resolution.

### C. `test_utils_coverage.py` has a legitimate `sys.path.insert` inside a test

`tests/unit/utils/test_utils_coverage.py` line 431 contains `sys.path.insert(0, root)` **inside a test function body** — it is testing path manipulation behavior, not a module-level import hack. The final acceptance gate uses `^sys.path.insert` (anchored to start of line) to exclude this. Do not remove it.

### D. `pytest.ini` `pythonpath = . tests` makes `sys.path.insert` redundant

The three root files that have module-level `sys.path.insert` (`test_f811_regressions.py`, `test_sprint7_regressions.py`, `test_sprint8_regressions.py`) were written before `pythonpath` was added to `pytest.ini`. They will work without the hack. After merging these files into `unit/`, simply delete those lines.

### E. `DeprecationWarning` from `ConfigManager()` in production code

`draft_loading_service.py` emits a `DeprecationWarning` when tests exercise it. This is tracked in issue #393 and is **out of scope for this refactor**. The Phase 0 baseline captures the exact failure count under `-W error::DeprecationWarning`. Do not use `-W error::DeprecationWarning` in any phase gate — it would erroneously block the refactor on an unrelated issue.

### F. Conftest fixture shadowing during Phase 2

While root files and `unit/classes/conftest.py` coexist, there are two `sample_players` fixtures (11-player root version vs 14-player classes version). This is fine during migration. Once root files are removed, the `unit/classes/conftest.py` version shadows the root — verify that `configured_draft` in tests that previously used the 11-player set still works after the root fixture takes over. Per ADR-010 §3, the root fixture will be expanded to 14 players; confirm that no test performs `assert len(sample_players) == 11`.

### G. Coverage source must be scoped correctly

`[tool.coverage.run]` `source` should point to the production packages (`api`, `classes`, `cli`, `config`, `data`, `services`, `strategies`, `utils`), not to `tests/`, `lab/`, or `venv/`. An incorrect `source` configuration will produce inflated or deflated coverage numbers. If the Phase 4 coverage gate fails unexpectedly, inspect the `[tool.coverage.run]` `omit` list for accidental exclusions of production modules.
