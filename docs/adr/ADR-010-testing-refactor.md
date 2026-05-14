# ADR-010: Testing Infrastructure Refactor

**Date:** 2026-05-13  
**Status:** Proposed  
**Supersedes:** (none — first architectural specification for the test suite)  
**Affected sprints:** Sprint 13 → Sprint 15

---

## 1. ADR Header

### Title
Consolidate and refactor the test suite: eliminate sprint-labeled duplication, establish a stable directory hierarchy, define fixture ownership, introduce a coverage toolchain, and harden marker discipline.

### Context
The test suite has grown organically across twelve sprints. The result is structural debt in three forms:

1. **Directory duplication.** Twenty-eight root-level test files shadow `unit/` subdirectories that already own those domains. Sprint-labeled suffixes (`_sprint9.py`) further fragment coverage for the same modules.
2. **Fixture drift.** `tests/conftest.py` and `tests/unit/classes/conftest.py` define overlapping `sample_players` / `configured_draft` fixtures with subtly different shapes (11-player set vs. 14-player set; 2-owner vs. 6-owner). `BaseTestCase` in `test_base.py` duplicates fixture construction in an `unittest` idiom that does not compose with pytest parametrize or Hypothesis.
3. **Toolchain gaps.** `pyproject.toml` has no `[tool.coverage.*]` sections. `pytest.ini` has no `addopts`. The `make coverage` Makefile target inlines coverage flags directly into the shell command, making them invisible to IDEs and pre-commit hooks. The Makefile `help` text advertises an 85% gate while the inline flag enforces 90% — a silent inconsistency.

### Decision
Restructure `tests/` into four stable subdirectories (`unit/`, `integration/`, `property/`, and root infrastructure). Eliminate sprint-labeled file variants by merging them into their canonical counterparts. Migrate all coverage and pytest configuration into `pyproject.toml`. Adopt a three-phase `fail_under` ramp (70 → 85 → 90).

### Consequences

**Positive**
- Single authoritative file per production module; no sprint-suffix lookup required
- Fixture conflicts resolved through explicit scope and override rules
- `pyproject.toml` becomes the single source of truth for coverage config — IDE, CLI, and CI read the same values
- `make test` and `make coverage` produce consistent results regardless of execution context
- `--strict-markers` prevents undeclared marker typos from silently passing

**Negative / Risks**
- Large move-and-merge operation risks transient CI failure if done as a single PR; see §7 for sequenced migration
- Sprint regression test classes inherit from `unittest.TestCase`; merge targets must preserve `unittest`-compatible assertions or convert them to bare `assert` statements
- The `property` marker is declared in `pytest.ini` but is absent from `REQUIRED_MARKS` in `test_pytest_marks.py`; this gap must be closed during migration (Phase 1)

---

## 2. Target Directory Tree

The tree below shows the **desired state** after the refactor.  
`[M]` = merge of two or more existing files.  
`[←]` = moved from root `tests/` without structural change.  
`[N]` = new file (infrastructure only, not a test file).  
Files without annotation already exist at the shown path.

```
tests/
│
├── conftest.py                         # root scope — canonical shared fixtures (§3)
├── pytest.ini                          # retained; addopts + markers updated (§6)
├── __init__.py
│
├── integration/                        # NEW subtree — replaces test_integration.py
│   ├── __init__.py                     [N]
│   ├── conftest.py                     [N]  real HTTP client, temp DB, env overrides
│   ├── test_api_integration.py         [←] from test_integration.py + test_data_api.py (API routes)
│   ├── test_draft_end_to_end.py        [←] from test_project.py (end-to-end simulation)
│   └── test_ping.py                    [←] from test_ping_format.py
│
├── unit/
│   ├── __init__.py
│   ├── conftest.py                     [N]  unit-scope helpers: mock_config, patch_settings
│   ├── test_pytest_marks.py            [M]  add 'property' to REQUIRED_MARKS
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── test_auth.py
│   │   ├── test_api_key_security.py
│   │   ├── test_recommend_bid.py
│   │   ├── test_schemas.py
│   │   └── test_sleeper_api.py
│   │
│   ├── classes/
│   │   ├── __init__.py
│   │   ├── conftest.py                 [M]  keep existing; remove sample_players/configured_draft
│   │   │                                    (root conftest becomes canonical for those)
│   │   ├── test_auction.py             [M]  test_auction.py
│   │   │                                    + test_auction_sprint9.py      (§115)
│   │   │                                    + test_auction_budget.py       (root)
│   │   │                                    + test_auction_enforcement.py  (root)
│   │   │                                    + test_budget_violation.py     (root)
│   │   │                                    + test_multilevel_constraints.py (root)
│   │   │                                    + test_integer_budgets.py      (root, auction portion)
│   │   │                                    + F811 auction regression      (from test_f811_regressions.py)
│   │   │                                    + Sprint 7b auction regression (from test_sprint7b_regressions.py)
│   │   ├── test_draft.py
│   │   ├── test_draft_setup.py         [M]  test_draft_setup.py
│   │   │                                    + test_draft_setup_layering.py (§358)
│   │   │                                    + test_roster_logic.py        (root)
│   │   ├── test_owner.py               [M]  test_owner.py + test_owner_sprint9.py (§118)
│   │   ├── test_player.py              [M]  test_player.py + test_player_sprint9.py (§120)
│   │   ├── test_strategy.py            [←]  from test_classes.py (classes/strategy.py tests)
│   │   ├── test_team.py                [M]  test_team.py + test_team_sprint9.py (§117)
│   │   └── test_tournament.py          [M]  test_tournament.py
│   │                                        + test_tournament_sprint9.py  (§119)
│   │                                        + Sprint 7 tournament regressions (#116, #113)
│   │                                        + Sprint 7b regressions       (#114, #110, #112)
│   │
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── test_cli_season_default.py
│   │   ├── test_commands.py            [M]  test_commands.py + test_commands_decomposition.py (§366)
│   │   └── test_main.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── test_config_manager.py      [M]  test_config_manager.py
│   │   │                                    + test_config_manager_sprint9.py (#163, #164)
│   │   │                                    + test_config_consolidation.py  (#359)
│   │   │                                    + Sprint 7c config regression   (from test_sprint7c_regressions.py)
│   │   └── test_settings.py            [←]  from test_settings_sprint9.py (#162)
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   └── test_fantasypros_loader.py  [M]  test_fantasypros_loader.py
│   │                                        + test_fantasypros_loader_sprint9.py (#167, #166)
│   │                                        + test_fantasypros_loader_security.py (#165)
│   │                                        + test_fantasypros.py          (root)
│   │                                        + test_data_api.py             (root, data-loader portion)
│   │
│   ├── lab/
│   │   ├── __init__.py
│   │   ├── test_auction_replay.py
│   │   ├── test_experiment_config.py
│   │   ├── test_gridiron_sage.py       [←]  from root test_gridiron_sage.py
│   │   ├── test_lab_ci_pipeline.py
│   │   ├── test_lab_results_db.py      [←]  from root test_lab_results_db.py
│   │   ├── test_simulation_runner.py   [M]  test_simulation_runner.py
│   │   │                                    + test_lab_simulation_runner.py (root, #257)
│   │   └── test_sleeper_auction_scraper.py [M] test_sleeper_auction_scraper.py
│   │                                        + test_lab_sleeper_scraper.py  (root, #235)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── test_bid_recommendation_service.py [M] test_bid_recommendation_service.py
│   │   │                                          + test_bid_recommendation_service_sprint9.py
│   │   │                                          + Sprint 8 BRS regression (#246 cache mutation)
│   │   ├── test_draft_loading_service.py      [M] test_draft_loading_service.py
│   │   │                                          + Sprint 7b regression    (#131 no-timer-threads)
│   │   │                                          + Sprint 8 regressions    (#FLEX triple-count, #data-path)
│   │   ├── test_sleeper_draft_service.py      [M] test_sleeper_draft_service.py
│   │   │                                          + test_sleeper_draft_service_sprint9.py
│   │   └── test_tournament_service.py         [M] test_tournament_service.py
│   │                                              + test_tournament_service_security.py (#133)
│   │                                              + test_tournament_service_sprint9.py
│   │                                              + Sprint 7 regression     (#132 KeyError)
│   │                                              + Sprint 8 regression     (#elimination-tournament)
│   │
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── test_base_strategy.py       [M]  test_base_strategy.py
│   │   │                                    + Sprint 7 regression  (#144 kwargs forwarding)
│   │   │                                    + F811 base_strategy   (from test_f811_regressions.py)
│   │   │                                    + Sprint 8 regressions (#aggressive-guard, #sigmoid-attrs)
│   │   ├── test_position_targets_hardcoding.py
│   │   ├── test_spending_strategy_analyzer.py
│   │   ├── test_strategy_config.py
│   │   ├── test_strategy_coverage.py   [M]  test_strategy_coverage.py
│   │   │                                    + test_strategies.py   (root)
│   │   │                                    + test_strategy_bids.py (root)
│   │   │                                    + test_market_inflation.py  (root)
│   │   │                                    + test_inflation_behavior.py (root)
│   │   │                                    + Sprint 8 regressions (#vor-scaling-factor, #mandatory-pos)
│   │   ├── test_strategy_registration.py
│   │   └── test_vor_strategy.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── test_cheatsheet_parser.py   [←]  from test_cheatsheet_parser_sprint9.py (#168)
│       ├── test_market_tracker.py      [←]  from test_market_tracker_sprint9.py (#169)
│       ├── test_print_module.py
│       ├── test_sleeper_cache.py       [←]  from test_sleeper_cache_sprint9.py (#170)
│       └── test_utils_coverage.py
│
└── property/
    ├── __init__.py
    ├── conftest.py                     # existing — Hypothesis profiles + composite strategies
    ├── test_api_deps_properties.py
    ├── test_auction_class_properties.py
    ├── test_auction_properties.py
    ├── test_base_strategy_properties.py
    ├── test_bid_recommendation_service_properties.py
    ├── test_cheatsheet_parser_properties.py
    ├── test_config_properties.py
    ├── test_data_properties.py
    ├── test_draft_loading_service_properties.py
    ├── test_draft_properties.py
    ├── test_draft_setup_properties.py
    ├── test_owner_properties.py
    ├── test_path_utils_properties.py
    ├── test_placeholder.py
    ├── test_recommend_schema_properties.py
    ├── test_sigmoid_strategy_properties.py
    ├── test_simulation_runner_properties.py
    ├── test_sleeper_cache_properties.py
    ├── test_spending_analyzer_properties.py
    ├── test_strategy_properties.py
    ├── test_strategy_registry_properties.py
    ├── test_team_properties.py
    ├── test_tournament_properties.py
    ├── test_tournament_service_properties.py
    └── test_vor_strategy_properties.py
```

### File count reconciliation

| Area | Before | After (target) | Change |
|---|---|---|---|
| `tests/` root test files | 28 | 0 (all migrated) | −28 |
| `tests/unit/` (all subdirs) | 56 | 43 | −13 (sprint merges) |
| `tests/integration/` | 0 | 3 | +3 |
| `tests/property/` | 25 | 25 | 0 |
| Infrastructure (`__init__`, `conftest`) | 7 | 11 | +4 |
| **Total test files** | **108** | **71** | **−37** |

The 37-file reduction comes entirely from merging sprint-labeled variants into canonical files; no tests are deleted.

---

## 3. Fixture Hierarchy Design

### Scope resolution order

pytest resolves fixtures nearest-first: a local conftest shadows a parent conftest fixture of the same name. The design below assigns each fixture to the highest scope at which it is _universally_ needed, preventing leakage upward.

```
tests/conftest.py                    ← widest scope (root)
  └── tests/unit/conftest.py         ← unit scope
        └── tests/unit/classes/conftest.py  ← classes scope
  └── tests/integration/conftest.py  ← integration scope
  └── tests/property/conftest.py     ← property scope
```

### `tests/conftest.py` — Root scope

Owns **domain data factories** needed by unit, integration, and property tests alike.

| Fixture | Type | Scope | Notes |
|---|---|---|---|
| `sample_player` | `Player` | `function` | Single RB; position/budget defaults |
| `sample_players` | `list[Player]` | `function` | 11-player set (QB×1, RB×4, WR×3, TE×1, K×1, DST×1) — **canonical**; `unit/classes/conftest.py` currently uses 14; resolve by adopting the 14-player set here and retiring the local override |
| `sample_team` | `Team` | `function` | Budget=200 |
| `sample_teams` | `list[Team]` | `function` | Two teams |
| `sample_owner` | `Owner` | `function` | Single owner |
| `sample_owners` | `list[Owner]` | `function` | Six owners (Alice–Frank); expand root from 2 to 6 to match the richer `classes/conftest.py` set |
| `configured_draft` | `Draft` | `function` | Fully assembled: 2 teams, 2 owners, all 14 players |
| `standard_roster_config` | `dict` | `session` | `{QB:1, RB:2, WR:3, TE:1, K:1, DST:1, FLEX:2}` — add FLEX |

**`BaseTestCase` / `TestDataGenerator` pattern mapping:**

`test_base.py::BaseTestCase.setUp` builds `self.test_config` and exposes `create_mock_player` / `create_mock_team` helpers. These map to named fixtures as follows:

| `BaseTestCase` pattern | Target fixture | Location |
|---|---|---|
| `self.test_config` | `default_draft_config` | `tests/conftest.py` |
| `create_mock_player(...)` | `sample_player` (parametrized via factory fixture) | `tests/conftest.py` |
| `create_mock_team(...)` | `sample_team` | `tests/conftest.py` |
| `TestDataGenerator` | Hypothesis strategies in `tests/property/conftest.py` | existing |

`test_base.py` itself is **retired** after migration; no new `unittest.TestCase` subclass infrastructure is added.

### `tests/unit/conftest.py` — Unit scope (new)

Owns **mock/patch helpers** that are only meaningful in isolated unit tests — not in integration or property tests.

| Fixture | Type | Scope | Purpose |
|---|---|---|---|
| `mock_config` | `MagicMock` | `function` | Pre-wired `ConfigManager` mock; eliminates the repeated `patch('config.config_manager.load_config')` boilerplate in `test_vor_strategy.py` and 9 other files |
| `mock_settings` | `MagicMock` | `function` | Pre-wired `get_settings()` mock |
| `mock_sleeper_client` | `MagicMock` | `function` | HTTP-level mock for SleeperAPI calls |
| `patch_env_testing` | `None` | `session` | `autouse=True`; ensures `TESTING=true` is set for the entire unit run (currently done via `os.environ.setdefault` in root conftest — move the `autouse` session fixture here so integration tests can override it) |

### `tests/unit/classes/conftest.py` — Classes scope (existing, trimmed)

After the root conftest absorbs the canonical `sample_players` / `configured_draft` / `sample_owners`, this conftest retains only fixtures that are **specific to class-layer tests**:

| Fixture | Retain? | Notes |
|---|---|---|
| `sample_players` | **Remove** — defer to root conftest | Conflict resolved by root winning |
| `sample_teams` | **Remove** — defer to root conftest | |
| `sample_owners` | **Remove** — defer to root conftest | |
| `configured_draft` | **Remove** — defer to root conftest | |
| `standard_roster_config` | **Remove** — defer to root conftest | |
| `comprehensive_players` | **Keep** | 44-player list; only used in `test_team.py` realistic scenario |

The resulting `unit/classes/conftest.py` will be ≤30 lines.

### `tests/integration/conftest.py` — Integration scope (new)

| Fixture | Type | Scope | Purpose |
|---|---|---|---|
| `test_client` | `httpx.AsyncClient` | `function` | Real FastAPI `TestClient` for route-level tests |
| `temp_db` | `AsyncSession` | `function` | In-memory SQLite; `aiosqlite` backend |
| `api_key_header` | `dict` | `session` | `{"X-API-Key": os.environ["PIGSKIN_API_KEY"]}` |

### `tests/property/conftest.py` — Property scope (existing, unchanged)

Already well-structured with Hypothesis profiles and composite strategies (`draft_player`, `draft_team`, `draft_state`). No changes required; see §7 Phase 0 for the one gap to close (adding `draft_state`).

---

## 4. Naming Convention Rules

### 4.1 Test files

| Rule | Pattern | Example |
|---|---|---|
| Mirror the production module name | `test_<module>.py` | `test_tournament_service.py` |
| One file per production module | No suffixes | ~~`test_auction_sprint9.py`~~ |
| Security tests co-located | Not a separate `_security.py` file; use a `TestSecurity*` class inside the canonical file | `test_tournament_service.py::TestSecurityCWDPath` |
| Integration test files describe the interaction, not the module | `test_<scenario>.py` | `test_draft_end_to_end.py` |
| Property test files use `_properties` suffix | `test_<module>_properties.py` | `test_auction_properties.py` |

**Prohibited patterns:**
- `test_<module>_sprint<N>.py` — sprint-labeled variants
- `test_<module>_v2.py` — versioned variants
- `test_<module>_security.py` — security as a separate top-level file

### 4.2 Test classes

| Rule | Pattern | Example |
|---|---|---|
| Group by behavior cluster | `Test<FeatureOrConcept>` | `TestBudgetEnforcement` |
| Security tests use explicit prefix | `TestSecurity<Concept>` | `TestSecurityPathTraversal` |
| Regression tests reference the issue | `TestIssue<N><ShortName>` | `TestIssue116IndependentStrategyInstances` |
| No `Base` prefix unless it is genuinely abstract | `TestBase...` reserved for helpers with no test methods | — |

**Do not use** `unittest.TestCase` for new tests. Existing `unittest.TestCase` subclasses migrated from sprint regression files may be left as-is for the duration of the migration sprint; conversion to plain pytest classes is a follow-up.

### 4.3 Test functions

| Rule | Pattern | Example |
|---|---|---|
| State what is asserted | `test_<thing>_<condition>_<expected>` | `test_bid_exceeds_budget_raises_value_error` |
| Parametrized tests describe the variant | `test_<thing>[<id>]` via `pytest.mark.parametrize` ids | `test_strategy_bid[aggressive]` |
| Do not use `test_it_works` or `test_happy_path` | — | ~~`test_it_works`~~ |

### 4.4 Fixture names

| Rule | Pattern | Example |
|---|---|---|
| Noun phrases, snake_case | `<noun_phrase>` | `sample_player`, `configured_draft` |
| Factory fixtures (return a callable) | `make_<noun>` | `make_player`, `make_draft` |
| Mock fixtures | `mock_<dependency>` | `mock_config`, `mock_sleeper_client` |
| Patch fixtures (no return value) | `patch_<target>` | `patch_env_testing` |
| Do not expose fixtures as class methods or `setUp` | — | ~~`self.create_mock_player()`~~ |

### 4.5 Conftest placement

| Fixture needed by | Conftest location |
|---|---|
| All test types (unit, integration, property) | `tests/conftest.py` |
| Unit tests only | `tests/unit/conftest.py` |
| A single unit subdirectory | `tests/unit/<subdir>/conftest.py` |
| Integration tests only | `tests/integration/conftest.py` |
| Property tests only | `tests/property/conftest.py` |

**Rule:** A fixture must live in the _shallowest_ conftest where it is needed. Do not duplicate a root-scope fixture in a subdirectory conftest unless explicitly overriding it for that scope.

---

## 5. Marker Taxonomy

### 5.1 Marker registry (target `pytest.ini`)

```ini
markers =
    unit: isolated test; no I/O, no network, all external deps mocked
    integration: real I/O; database, HTTP, filesystem, or multi-component
    property: Hypothesis-driven generative test
    slow: runtime >2 s on reference hardware; deselect in fast-feedback loops
    performance: benchmarks and latency assertions; always deselect in unit run
    simulation: runs a full tournament/draft simulation loop (stochastic, heavier than unit)
    ml: requires torch/numpy/ML dependencies; skip if environment lacks them
```

### 5.2 Decision table

| Test characteristics | Marker(s) to apply |
|---|---|
| Calls no I/O, all deps mocked/patched | `unit` |
| Uses `hypothesis.given` | `property` |
| Hits a real database or spawns real HTTP | `integration` |
| Runs a full `Tournament.run()` or `Draft.run()` loop | `simulation` |
| Typically runs in >2 s (including `simulation` tests) | `slow` _(in addition to primary marker)_ |
| Asserts on wall-clock latency or memory usage | `performance` |
| Imports `torch`, `numpy`, or lab ML modules | `ml` |

**`slow` is always additive** — it is never the only marker on a test. A simulation test that takes 3 s should be marked `@pytest.mark.simulation` and `@pytest.mark.slow`.

### 5.3 `xfail` discipline

`pytestmark = pytest.mark.xfail(...)` at module level is currently used in `unit/strategies/` to gate acceptance criteria for open issues. The rules:

| Condition | Action |
|---|---|
| Issue is open; feature is not yet implemented | `@pytest.mark.xfail(strict=False, reason="Closes #N — <title>")` |
| Issue is closed; all tests pass | Remove `xfail` in the same PR that closes the issue |
| Test unexpectedly passes (`XPASS`) | CI fails if `strict=True`; investigate before removing xfail |
| Module-level `pytestmark` xfail | Allowed only when _every_ test in the file is blocked by the same issue |

### 5.4 CI marker filter profiles

| Profile | Command fragment | When used |
|---|---|---|
| Fast feedback (pre-commit) | `-m "unit and not slow"` | Local pre-commit hook |
| Full unit gate | `-m "unit or property"` | PR CI |
| Nightly | _(no -m filter)_ | Scheduled CI run |
| Lab bench | `-m "simulation or performance"` | `make lab-bench` |

---

## 6. Coverage Toolchain Design

### 6.1 `[tool.coverage.run]` — add to `pyproject.toml`

```toml
[tool.coverage.run]
source = [
    "api",
    "classes",
    "cli",
    "config",
    "data",
    "services",
    "strategies",
    "utils",
]
omit = [
    "*/venv/*",
    "*/pigskin_auction_draft.egg-info/*",
    "lab/*",
    "tests/*",
    "setup.py",
    "run_tests.py",
]
branch = true
```

**Rationale for `branch = true`:** The strategy bid logic contains many short-circuit branches (`if remaining_budget < 1: return 1`). Line-only coverage would pass at 90% while missing entire conditional paths. Branch coverage exposes this.

`lab/` is excluded because it lives in a separate `pyproject.toml` with its own coverage lifecycle.

### 6.2 `[tool.coverage.report]` — add to `pyproject.toml`

```toml
[tool.coverage.report]
show_missing = true
skip_covered = false
skip_empty = true
precision = 1
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@(abc\\.)?abstractmethod",
    "if __name__ == ['\"]__main__['\"]:",
]
```

`skip_covered = false` is intentional: hiding 100%-covered files masks regressions when a file is later edited but the test is not updated.

### 6.3 `pytest.ini addopts`

Replace the current (empty) `addopts` with:

```ini
[pytest]
addopts =
    -ra
    --strict-markers
    --tb=short
    --timeout=60
```

| Flag | Purpose |
|---|---|
| `-ra` | Print a short summary for all non-passing outcomes (xfail, xpass, skip, error) |
| `--strict-markers` | Fail on any undeclared marker; enforces the taxonomy in §5 |
| `--tb=short` | Readable tracebacks without full frame noise |
| `--timeout=60` | Kill runaway tests; `pytest-timeout` already installed |

Coverage flags are **not** added to `addopts`. They belong in `make coverage` so that `make test` (the fast feedback loop) does not pay the coverage instrumentation overhead.

### 6.4 `make test` and `make coverage` invocations

**`make test`** — fast, no coverage instrumentation:

```makefile
test:
	pytest -m "unit or property" -q
```

**`make test-all`** — full suite including integration and simulation:

```makefile
test-all:
	pytest -q
```

**`make coverage`** — coverage-gated run:

```makefile
coverage:
	pytest \
	  --cov \
	  --cov-report=term-missing \
	  --cov-report=xml:coverage.xml \
	  --cov-fail-under=$(COVERAGE_GATE) \
	  -q
```

With a Makefile variable:

```makefile
COVERAGE_GATE ?= 85
```

The default is 85. CI overrides via environment variable: `make coverage COVERAGE_GATE=90`.

### 6.5 `fail_under` ramp

| Sprint | Gate | Rationale |
|---|---|---|
| Sprint 13 (migration) | **70** | Stabilize the structure; do not regress existing coverage |
| Sprint 14 | **85** | Close known zero-coverage modules (config, cli); `make coverage` Makefile help text already advertises 85% |
| Sprint 15 | **90** | Match the inline value currently in the Makefile `coverage` target; all strategy branches covered |

The ramp is enforced by updating `COVERAGE_GATE` in the Makefile and committing the change in the sprint-start PR. CI reads the committed value.

**Known coverage gaps to close on the path to 90%:**
- `strategies/`: currently guarded by `xfail`; as issues resolve, test activation will raise coverage naturally
- `config/`: `ConfigManager` deprecation sweep (issue #393) will add tests for every instantiation site
- `cli/commands/`: decomposition (#366) acceptance tests are already written but `xfail`-guarded
- `api/schemas/`: `test_schemas.py` exists but covers only the schema models, not route handlers

---

## 7. Migration Sequencing

The migration must never leave CI red for longer than one PR cycle. The following phases are designed to be independently mergeable.

### Phase 0 — Toolchain bootstrapping _(no test movement)_

**Goal:** Install coverage config and `addopts` before touching any test file.

1. Add `[tool.coverage.run]` and `[tool.coverage.report]` to `pyproject.toml` with `fail_under` at current measured baseline (record it first with `pytest --cov -q 2>&1 | tail -1`).
2. Update `pytest.ini addopts` with `-ra --strict-markers --tb=short --timeout=60`.
3. Add `property` to `REQUIRED_MARKS` in `tests/unit/test_pytest_marks.py`.
4. Update Makefile `test` and `coverage` targets to the forms in §6.4.
5. Set `COVERAGE_GATE = 70` in Makefile.

**Risk:** `--strict-markers` will fail if any test file uses an undeclared marker. Run `pytest --collect-only -q 2>&1 | grep "PytestUnknownMarkWarning"` before merging to confirm zero warnings.

**Dependencies:** None. Can be done in a single PR.

---

### Phase 1 — Root-level sprint regression consolidation _(highest duplication density)_

**Goal:** Eliminate the 4 sprint regression files at `tests/test_sprint*.py`.

**Order of merges within Phase 1:**

1. `test_sprint7_regressions.py` → distribute test classes to:
   - `unit/classes/test_tournament.py` (issues #116, #113)
   - `unit/services/test_tournament_service.py` (issue #132)
   - `unit/strategies/test_base_strategy.py` (issue #144)

2. `test_sprint7b_regressions.py` → distribute to:
   - `unit/classes/test_player.py` (#114)
   - `unit/classes/test_auction.py` (#110)
   - `unit/classes/test_team.py` (#112)
   - `unit/services/test_draft_loading_service.py` (#131)

3. `test_sprint7c_regressions.py` → distribute to:
   - `unit/config/test_config_manager.py` (`TestUserBudgetFromConfig`)
   - `unit/data/test_fantasypros_loader.py` (`TestConvertSleeperPlayerProjections`)

4. `test_sprint8_regressions.py` → distribute to:
   - `unit/api/test_sleeper_api.py` (JSONDecodeError, shared-dict mutation)
   - `unit/classes/test_team.py` (QB bench constraint)
   - `unit/services/test_bid_recommendation_service.py` (cache mutation)
   - `unit/services/test_draft_loading_service.py` (FLEX triple-count, data-path bug)
   - `unit/services/test_tournament_service.py` (elimination tournament)
   - `unit/strategies/test_base_strategy.py` (aggressive-guard, sigmoid-attrs)
   - `unit/strategies/test_vor_strategy.py` (scaling-factor shadowing)
   - `unit/strategies/test_strategy_coverage.py` (mandatory position bid boost)
   - `unit/cli/test_main.py` (handle-tournament non-numeric args)
   - `unit/api/test_schemas.py` (display-ping-results missing tests key)

**Constraint:** Do not delete source files until the destination file's test count has been verified by CI. Use `git mv` to preserve history; the merge itself is a code edit.

**Dependencies:** Phase 0 must be complete (strict-markers must pass before new files land).

---

### Phase 2 — Unit sprint9 suffix merges _(lower risk; in-place)_

**Goal:** Eliminate `_sprint9.py` files within `unit/`.

Each merge is a straightforward append: copy test classes from the sprint9 file into the canonical file, then delete the sprint9 file. No fixture changes needed (both files already use the same conftest).

**Safe merge order** (lowest coupling to highest):

1. `unit/utils/*_sprint9.py` → three canonical files (no conftest changes)
2. `unit/config/*_sprint9.py` → `test_config_manager.py`, `test_settings.py`
3. `unit/data/test_fantasypros_loader_sprint9.py` → `test_fantasypros_loader.py`
4. `unit/services/*_sprint9.py` → three canonical files
5. `unit/classes/*_sprint9.py` → five canonical files

**Dependencies:** Phase 1 must be complete so sprint7/8 merges do not conflict with sprint9 merges in the same file.

---

### Phase 3 — Root-level misc migration _(highest churn risk)_

**Goal:** Move the 16 remaining root-level test files to their `unit/` destinations.

**Sub-phases:**

**3a — Lab files** (lowest blast radius; lab tests are already `xfail`-guarded or isolated):
- `test_gridiron_sage.py` → `unit/lab/`
- `test_lab_results_db.py` → `unit/lab/`
- `test_lab_simulation_runner.py` → merge into `unit/lab/test_simulation_runner.py`
- `test_lab_sleeper_scraper.py` → merge into `unit/lab/test_sleeper_auction_scraper.py`

**3b — Data and API** (no strategy dependencies):
- `test_fantasypros.py` → merge into `unit/data/test_fantasypros_loader.py`
- `test_data_api.py` → split: data-loader assertions → `unit/data/`; route assertions → `integration/test_api_integration.py`
- `test_ping_format.py` → `integration/test_ping.py`

**3c — Strategy and budget** (many files, same target):
- `test_auction_budget.py`, `test_auction_enforcement.py`, `test_budget_violation.py`, `test_multilevel_constraints.py`, `test_integer_budgets.py` → merge into `unit/classes/test_auction.py`
- `test_strategies.py`, `test_strategy_bids.py`, `test_market_inflation.py`, `test_inflation_behavior.py` → merge into `unit/strategies/test_strategy_coverage.py`

**3d — Omnibus files** (highest cognitive load; do last):
- `test_classes.py` — scan and distribute by class touched
- `test_services.py` — scan and distribute by service touched
- `test_f811_regressions.py` → split: auction → `unit/classes/test_auction.py`; base_strategy → `unit/strategies/test_base_strategy.py`
- `test_integration.py` → `integration/test_draft_end_to_end.py`
- `test_project.py` → `integration/test_draft_end_to_end.py`
- `test_runner.py` → **delete** (runner scaffolding; no test content)
- `test_base.py` → **delete** after all `BaseTestCase` subclasses are migrated

**Dependencies:** Phase 2 complete; root conftest fixture expansion (§3) must precede 3c/3d since those files use `BaseTestCase.setUp` patterns that will be replaced by root fixtures.

---

### Phase 4 — Conftest consolidation _(final polish)_

**Goal:** Apply the fixture hierarchy design from §3.

1. Expand `tests/conftest.py`: canonical 14-player set, 6-owner set, `FLEX`-inclusive roster config.
2. Create `tests/unit/conftest.py` with `mock_config`, `mock_settings`, `mock_sleeper_client`, `patch_env_testing`.
3. Trim `tests/unit/classes/conftest.py` to `comprehensive_players` only.
4. Create `tests/integration/conftest.py` with `test_client`, `temp_db`, `api_key_header`.
5. Set `COVERAGE_GATE = 85` in Makefile; verify CI passes.

**Dependencies:** Phase 3 complete; all test files have been moved and use root fixtures.

---

### Phase 5 — Coverage ramp to 90 _(future sprint)_

Not a structural change. Activities:

- Resolve xfail-guarded strategies (issues #151, #153, #213–217)
- Complete `ConfigManager` deprecation sweep (#393)
- Fill `cli/commands/` gap after decomposition (#366)
- Set `COVERAGE_GATE = 90`

---

### Dependency graph summary

```
Phase 0 (toolchain)
    └── Phase 1 (sprint7/8 regression merges)
            └── Phase 2 (sprint9 merges)
                    └── Phase 3 (root misc → unit/)
                            └── Phase 4 (conftest consolidation)
                                    └── Phase 5 (coverage ramp, future sprint)
```

Each phase is independently CI-green. No phase requires a force-push or skipping of test gates.

---

## Appendix A — Files retired (no content to migrate)

| File | Reason |
|---|---|
| `tests/test_runner.py` | Runner scaffolding only; no test assertions |
| `tests/test_base.py` | `BaseTestCase` patterns replaced by named fixtures in §3 |
| `tests/test_project.py` | Superseded by `integration/test_draft_end_to_end.py` |
| `run_tests.py` (root) | Superseded by `pytest` invocation in Makefile |

---

## Appendix B — Open questions deferred to implementation

1. **`unittest.TestCase` migration policy.** Sprint regression classes (`TestIndependentStrategyInstances`, etc.) use `self.assert*` methods. The decision of whether to convert them to plain `assert` statements during the merge (preferred) or leave them as-is (safe but inconsistent) is left to the implementing engineer. Converting them simplifies fixture injection but risks subtle behavioral differences in error reporting.

2. **`test_classes.py` and `test_services.py` content.** These files were created early in the project and may contain broad smoke tests that overlap significantly with the canonical unit files. A content audit is required before the Phase 3d merge; they may be deleteable rather than mergeable.

3. **`property` marker on Hypothesis tests.** Currently `tests/property/` files do not uniformly apply `@pytest.mark.property`. The Phase 0 toolchain work should include adding `pytestmark = pytest.mark.property` to each file in `tests/property/` as a block change — this is mechanical and low-risk.
