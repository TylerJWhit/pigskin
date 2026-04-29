# ADR-001: Mono-Repo Package Structure (pigskin-core / pigskin-app / pigskin-lab)

**Status:** Accepted
**Date:** 2026-04-28
**Reviewed:** 2026-04-28
**Author:** Architecture Agent (via Orchestrator)
**Reviewer:** Architecture Agent
**Deciders:** Engineering team

---

## Context

The current repository is a single flat project mixing:
- Core domain models (`classes/`, `config/`, `strategies/`)
- A CLI interface (`cli/`)
- A simulation/tournament engine (`services/tournament_service.py`, `classes/tournament.py`)
- An external API integration (`api/sleeper_api.py`)
- An unimplemented web UI (referenced in issues but absent from workspace)
- A GridironSage AI strategy skeleton (originally `strategies/alphazero/` — issue #55, now replaced)

Two product goals have been identified:
1. **Production App** (`pigskin-app`): An end-user tool providing live draft tracking and bid recommendations via a documented REST API and web UI.
2. **Research Lab** (`pigskin-lab`): A permanent, continuously-improving strategy research environment where new strategies are developed, benchmarked, and promoted to production.

These two products have incompatible runtime characteristics: the app needs low-latency inference and a stable API contract; the lab needs to run long simulation batches, experiment freely with strategy variants, and maintain historical benchmark results.

### Options Considered

| Option | Description | Key Risk |
|--------|-------------|----------|
| A — Two separate repos | `pigskin` (app) + `pigskin-lab` (research) | Shared `classes/` drifts out of sync; bug fixes must be cherry-picked across repos |
| B — Mono-repo, flat | Everything in one repo, no package boundaries | No enforcement of API contract; lab code can import app internals |
| **C — Mono-repo, packages** | One repo, three logical packages: `core/`, `app/`, `lab/` | Slightly more complex local dev setup; recommended |
| D — Published PyPI core | `pigskin-core` published to PyPI; app and lab install it | Overhead of versioning and publishing; unnecessary for a single-team project |

---

## Decision

**Option C: Mono-repo with three explicit packages.**

```
pigskin/                        ← existing repo root
├── core/                       ← pigskin-core (shared, versioned)
│   ├── classes/                ← Player, Team, Draft, Auction, Tournament
│   ├── config/                 ← ConfigManager, DraftConfig
│   └── strategies/
│       └── base_strategy.py    ← abstract base + interface ONLY
│
├── app/                        ← pigskin-app (production product)
│   ├── api/                    ← REST API (FastAPI, public, versioned at /api/v1/)
│   ├── services/               ← business logic wrapping core
│   ├── strategies/             ← production strategy (single promoted winner)
│   ├── ui/                     ← web frontend (HTTP-only; no direct Python imports)
│   └── integrations/           ← Sleeper API, future third-party adapters
│
└── lab/                        ← pigskin-lab (research, never deployed to users)
    ├── strategies/             ← all experimental strategy variants
    ├── gridiron_sage/          ← training, self-play, MCTS (GridironSage AI strategy)
    ├── simulation/             ← tournament runner, scenario generator
    ├── benchmarks/             ← strategy comparison harness
    ├── promotion/              ← gate evaluation + report generator
    ├── results_db/             ← SQLite — historical benchmark results
    └── experiments/            ← named experiments with config + results
```

Each package has its own `pyproject.toml` and is installable independently. The root `pyproject.toml` declares a workspace. In local dev, all three are installed in editable mode (`pip install -e core/ -e app/ -e lab/`).

---

## Consequences

### Positive
- **No code drift**: Both `app/` and `lab/` import from the same `core/` source of truth. A fix to `classes/auction.py` is immediately available to both.
- **Enforced API boundary**: The `ui/` layer can only reach `app/api/` via HTTP — no accidental direct imports of domain objects in templates.
- **Lab freedom**: `lab/strategies/` can hold 15+ experimental strategies without polluting the production codebase.
- **Strategy promotion is explicit**: Promoting a strategy requires a PR that modifies `app/strategies/` — not a config flag or environment variable.

### Negative
- **Migration cost**: Existing flat structure must be reorganized. All import paths change. This is a Sprint 5 item — do not restructure while Sprint 3 P0 bugs are open.
- **Local dev setup is slightly more complex**: Developers must install three packages. A `make dev-install` target in the Makefile mitigates this.
- **CI pipelines multiply**: Each package needs its own lint/test gate. See ADR-002 for CI implications.

### Constraints
- **Do not begin migration until Sprint 3 is complete (420/420 tests passing)**
- `core/classes/`, `core/config/` are the highest-churn modules in the codebase — stabilize them first

---

---

## Critical Thinking Review (Architecture Agent — 2026-04-28)

### Assumptions Examined

1. **"Option C is clearly best"** — The mono-repo with packages is the right call for a single-team project. Two repos (Option A) creates real drift risk given that `classes/auction.py` and `classes/draft.py` have been high-churn hotspots. Option D (published PyPI core) is over-engineered. The assumption holds.

2. **"All 15+ strategies go to `lab/strategies/`"** — The ADR places only the `base_strategy.py` interface in `core/`. Every concrete strategy (including the current production-quality ones like `EliteHybridStrategy`, `EnhancedVORStrategy`) moves to `lab/strategies/`. This is correct but is a notable consequence: the initial production app will have **no promoted strategy** until the first gate evaluation passes. The team must plan for a "bootstrap" production strategy on day one of migration.

3. **"Migration is safe to defer to Sprint 5"** — Confirmed. The ADR explicitly gates migration on 420/420 tests passing. Given that `core/classes/` is the highest-churn zone, stabilizing first is correct.

4. **"pip workspace for editable installs"** — The ADR recommends `pip install -e core/ -e app/ -e lab/`. This works with Python 3.21+/pip 21.3+ (PEP 660 editable installs via pyproject.toml). Requires `flit-core` or `hatchling` as the build backend — **not** `setuptools` unless using the legacy `setup.py` path. The current `setup.py` must be replaced with `pyproject.toml` per package during migration.

### Risks

- **Import path churn**: Every `from classes.auction import Auction` becomes `from pigskin_core.classes.auction import Auction`. This touches every test file and service. Recommend a `rope`-assisted refactor or `sed` batch rename, not manual edits.
- **Bootstrap production strategy gap**: On the first day of migration, `app/strategies/` is empty. Define a bootstrap strategy (recommend: copy of `EliteHybridStrategy` or `EnhancedVORStrategy` as the initial production winner, bypassing the gate for the first promotion only, with explicit team sign-off).
- **Python version floor**: The `pyproject.toml` workspace approach requires Python ≥ 3.8 (editable installs via PEP 660). The current `setup.py` must be migrated. Confirm minimum Python version in CI.
- **GridironSage migration**: `strategies/gridiron_sage_strategy.py` moves to `lab/gridiron_sage/` (issue #55). This is correctly noted in the layout. Ensure the migration issue (#55) explicitly references ADR-001 as the structural authority.

### Alternative Considered and Rejected

A two-package split (core + app, with lab as a folder in app/) was considered. Rejected because it conflates production runtime with research tooling — the key failure mode is a researcher importing an unstable `lab` dependency in `app/` accidentally.

---

## Review Checklist (Resolved)

- [x] **FastAPI confirmed for `app/api/`** — ADR-002 accepted in this sprint (2026-04-28). FastAPI with versioned REST + WebSocket is the selected design.
- [x] **SQLite confirmed for `lab/results_db/`** — ADR-004 accepted in this sprint (2026-04-28). SQLite with WAL mode + Alembic migrations.
- [x] **`core/` version tagging convention defined** — See below.
- [ ] **Update `AGENT_MANAGER.md`** — Deferred to Sprint 5, immediately before migration begins.

### Core Version Tagging Convention

`core/` uses **CalVer with a build counter**: `YYYY.MM.patch`

- Example: `2026.05.0` → first release in May 2026; `2026.05.1` → first patch.
- Breaking changes (API removals, signature changes): increment the month component and document in `core/CHANGELOG.md`.
- Tags in git: `core/v2026.05.0` (prefixed to avoid collision with app/lab tags which use `app/vX.Y.Z` and `lab/vX.Y.Z`).
- The version is declared in `core/pyproject.toml` and exposed as `pigskin_core.__version__`.

### Bootstrap Production Strategy Decision

On the day migration begins, `app/strategies/production_strategy.py` is populated by copying `EnhancedVORStrategy` from `lab/strategies/` as the baseline. This single exception to the promotion gate is recorded as a manual promotion entry in `lab/results_db/promotions` with `promoted_by = 'bootstrap'` and no benchmark run ID. All subsequent promotions must pass the gate (ADR-003).
