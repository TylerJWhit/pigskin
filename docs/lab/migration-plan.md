# Mono-Repo Migration Plan

**Authority:** ADR-001 (Accepted 2026-04-28)
**Status:** Approved for planning; execution gated on Sprint 3 completion
**Sprint target:** Sprint 5
**Author:** Git Workflow Agent (2026-04-29)

---

## Pre-Migration Gate

Both constraints are **confirmed satisfied as of 2026-04-29**:

| Constraint | Status |
|-----------|--------|
| Test suite at 420/420 passing | ✅ Confirmed |
| Sprint 3 complete | ✅ Confirmed |

Do **not** begin any directory moves until these remain satisfied on the migration branch immediately before each step.

---

## 1. Current Structure

The repository is a single flat project — all modules at root level with no package boundaries:

```
pigskin/                    ← repo root
├── api/                    ← Sleeper API integration
├── classes/                ← core domain models (Player, Team, Draft, Auction, Tournament)
├── cli/                    ← command-line interface
├── config/                 ← ConfigManager, config.json
├── data/                   ← FantasyPros loader, VOR calculations
├── services/               ← business logic (bid_recommendation, draft_loading, sleeper_draft, tournament)
├── strategies/             ← all strategies (15+), including gridiron_sage_strategy.py
├── tests/                  ← test suite
├── utils/                  ← shared utilities
├── docs/                   ← documentation
├── setup.py                ← single package config
└── requirements*.txt       ← flat dependency list
```

**Problems with the current structure (per ADR-001):**
- Production app code and research experiment code live in the same namespace
- Lab strategies pollute the production package
- No enforced API boundary between UI and domain models
- GridironSage strategy (`strategies/gridiron_sage_strategy.py`) mixed with stable production strategies
- `setup.py` cannot express the three-package workspace relationship

---

## 2. Target Structure (ADR-001 Decision C)

```
pigskin/                        ← repo root
├── core/                       ← pigskin-core (shared, versioned — CalVer YYYY.MM.patch)
│   ├── pyproject.toml
│   ├── classes/                ← Player, Team, Draft, Auction, Tournament
│   ├── config/                 ← ConfigManager, DraftConfig
│   └── strategies/
│       └── base_strategy.py    ← abstract base + interface ONLY
│
├── app/                        ← pigskin-app (production product)
│   ├── pyproject.toml
│   ├── api/                    ← REST API (FastAPI, versioned at /api/v1/)
│   ├── services/               ← business logic wrapping core
│   ├── strategies/             ← single promoted production strategy
│   ├── ui/                     ← web frontend (HTTP-only)
│   └── integrations/           ← Sleeper API, future adapters
│
├── lab/                        ← pigskin-lab (research, never deployed)
│   ├── pyproject.toml
│   ├── strategies/             ← all experimental strategy variants
│   ├── gridiron_sage/          ← training, self-play, MCTS (from strategies/gridiron_sage_strategy.py)
│   ├── simulation/             ← tournament runner, scenario generator
│   ├── benchmarks/             ← strategy comparison harness
│   ├── promotion/              ← gate evaluation + report generator
│   ├── results_db/             ← SQLite — historical benchmark results
│   └── experiments/            ← named experiments with config + results
│
├── tests/                      ← test suite (covers all three packages)
├── docs/                       ← documentation (this file, ADRs, etc.)
├── pyproject.toml              ← root workspace declaring core/, app/, lab/
├── Makefile                    ← includes `make dev-install`
└── requirements*.txt           ← kept for legacy CI; superseded by pyproject.toml
```

**Import namespace changes:**

| Before | After |
|--------|-------|
| `from classes.auction import Auction` | `from pigskin_core.classes.auction import Auction` |
| `from strategies.base_strategy import BaseStrategy` | `from pigskin_core.strategies.base_strategy import BaseStrategy` |
| `from config.config_manager import ConfigManager` | `from pigskin_core.config.config_manager import ConfigManager` |
| `from services.bid_recommendation_service import ...` | `from pigskin_app.services.bid_recommendation_service import ...` |
| `from api.sleeper_api import SleeperAPI` | `from pigskin_app.integrations.sleeper_api import SleeperAPI` |
| `from strategies.enhanced_vor_strategy import ...` | `from pigskin_lab.strategies.enhanced_vor_strategy import ...` |

---

## 3. Migration Sequence

Each step must be executed on its own feature branch, pass the full test suite, and be merged before the next step begins.

### Step 0 — Scaffold pyproject.toml files (no file moves)

**Branch:** `chore/mono-repo-scaffold`

1. Create `core/pyproject.toml` declaring package `pigskin-core` with an empty `src/` layout
2. Create `app/pyproject.toml` declaring package `pigskin-app`, declaring `pigskin-core` as a dependency
3. Create `lab/pyproject.toml` declaring package `pigskin-lab`, declaring `pigskin-core` as a dependency
4. Create root `pyproject.toml` workspace entry pointing to `core/`, `app/`, `lab/`
5. Verify `make dev-install` succeeds (installs all three editable packages)
6. Run `python -m pytest tests/` — must pass 420/420 before merging

**Verification gate:** `python -m pytest tests/ -q` exits 0

---

### Step 1 — Migrate `core/` (classes, config, base_strategy)

**Branch:** `feat/mono-repo-core`

Move these directories under `core/`:

```
classes/         →  core/classes/
config/          →  core/config/
strategies/base_strategy.py  →  core/strategies/base_strategy.py
```

**Import path update** — run the sed script template (see §4) for `pigskin_core`.

**Verification gate:** `python -m pytest tests/ -q` exits 0

---

### Step 2 — Migrate `app/` (services, api/integrations, production strategy)

**Branch:** `feat/mono-repo-app`

Move these directories under `app/`:

```
services/        →  app/services/
api/             →  app/integrations/
cli/             →  app/cli/
```

Populate bootstrap production strategy (ADR-001 §Bootstrap):

```
strategies/enhanced_vor_strategy.py  →  app/strategies/production_strategy.py
```

Record bootstrap promotion in `lab/results_db/promotions` with `promoted_by = 'bootstrap'`.

**Import path update** — run the sed script template for `pigskin_app`.

**Verification gate:** `python -m pytest tests/ -q` exits 0

---

### Step 3 — Migrate `lab/` (all experimental strategies, gridiron_sage, simulation)

**Branch:** `feat/mono-repo-lab`

Move these directories under `lab/`:

```
strategies/      →  lab/strategies/     (all concrete strategies except base_strategy.py)
strategies/gridiron_sage_strategy.py  →  lab/gridiron_sage/
```

Stub out remaining lab directories (empty `__init__.py` + README):

```
lab/simulation/
lab/benchmarks/
lab/promotion/
lab/results_db/
lab/experiments/
```

**Import path update** — run the sed script template for `pigskin_lab`.

**Verification gate:** `python -m pytest tests/ -q` exits 0

---

### Step 4 — Remove legacy root-level modules and `setup.py`

**Branch:** `chore/mono-repo-cleanup`

1. Delete `setup.py` (replaced by `pyproject.toml` workspace)
2. Update `requirements*.txt` to reference workspace packages
3. Update CI workflows to use `make dev-install` instead of `pip install -r requirements.txt`
4. Update `INSTALL.md` with new dev setup instructions

**Verification gate:** `python -m pytest tests/ -q` exits 0; `make ci` exits 0

---

## 4. Import Path Changes — Scripted, Not Manual

**All import path changes must be applied with the script below, not by hand editing files.**

### sed batch rename template

```bash
#!/usr/bin/env bash
# scripts/migrate_imports.sh
# Usage: bash scripts/migrate_imports.sh <package> <step>
#   package: core | app | lab
#   step:    1 | 2 | 3
set -euo pipefail

TARGET_FILES=$(find . -name "*.py" \
    -not -path "./venv/*" \
    -not -path "./.git/*" \
    -not -path "./pigskin_auction_draft.egg-info/*")

migrate_core() {
    echo "$TARGET_FILES" | xargs sed -i \
        -e 's/from classes\./from pigskin_core.classes./g' \
        -e 's/import classes\./import pigskin_core.classes./g' \
        -e 's/from config\.config_manager/from pigskin_core.config.config_manager/g' \
        -e 's/from config\./from pigskin_core.config./g' \
        -e 's/from strategies\.base_strategy/from pigskin_core.strategies.base_strategy/g'
}

migrate_app() {
    echo "$TARGET_FILES" | xargs sed -i \
        -e 's/from services\./from pigskin_app.services./g' \
        -e 's/from api\./from pigskin_app.integrations./g' \
        -e 's/from cli\./from pigskin_app.cli./g'
}

migrate_lab() {
    echo "$TARGET_FILES" | xargs sed -i \
        -e 's/from strategies\./from pigskin_lab.strategies./g' \
        -e 's/import strategies\./import pigskin_lab.strategies./g'
}

case "$1" in
    core) migrate_core ;;
    app)  migrate_app ;;
    lab)  migrate_lab ;;
    *) echo "Usage: $0 <core|app|lab>"; exit 1 ;;
esac

echo "Import migration for '$1' complete. Run: python -m pytest tests/ -q"
```

### rope-based alternative (recommended for complex renames)

For cases where sed produces false positives (e.g., a local variable named `classes`), use `rope`:

```bash
pip install rope
python - <<'EOF'
from rope.base.project import Project
from rope.refactor.rename import Rename

project = Project('.')
# Example: rename module 'classes' to 'pigskin_core.classes'
# Use rope's find_occurrences + rename for each affected module
# See: https://rope.readthedocs.io/en/latest/overview.html
EOF
```

The rope approach is slower but semantically correct. Use rope for Step 1 (core), which has the most cross-cutting imports.

---

## 5. Verification Gate

At **every step** in §3, before opening the merge PR, the following must all pass:

```bash
# 1. Full test suite
python -m pytest tests/ -q --timeout=60
# Exit code must be 0; all 420 tests must pass

# 2. Lint
make lint

# 3. Type check
make typecheck

# 4. dev-install still works
make dev-install
```

If any gate fails, **do not proceed to the next step**. Open a `fix/<slug>` branch off the migration branch, fix the issue, and re-run the full gate before merging.

---

## 6. Branching Model for This Migration

### Branch hierarchy

```
main  ──────────────────────────────────────────●── (tagged release post-migration)
        \                                      /
         mono-repo-migration  ──●──●──●──●──●  (integration branch; never pushed to main mid-migration)
               \      \      \      \
                step0  step1  step2  step3      (short-lived feature branches)
```

### Feature branch naming convention

| Step | Branch name |
|------|-------------|
| 0 — Scaffold pyproject.toml | `chore/mono-repo-scaffold` |
| 1 — Migrate core | `feat/mono-repo-core` |
| 2 — Migrate app | `feat/mono-repo-app` |
| 3 — Migrate lab | `feat/mono-repo-lab` |
| 4 — Cleanup | `chore/mono-repo-cleanup` |
| Import fix (if needed) | `fix/mono-repo-imports-<module>` |

### Integration branch

Create `mono-repo-migration` off `main` at the start of Sprint 5. All step branches are opened against `mono-repo-migration`, not `main`.

`mono-repo-migration` → `main` is a single final PR, reviewed and approved by at least one team member, after Step 4 gates pass.

### PR strategy

- Each step branch opens a PR against `mono-repo-migration`
- PR body must include: files moved, import rename script run, test gate result (paste `pytest` summary)
- No step PR may be merged until its verification gate passes (§5)
- `mono-repo-migration` → `main` PR requires Architecture or PM sign-off per ADR-003

### Lab promotion branch convention (post-migration)

```
lab/promote/<strategy-slug>-<YYYY-MM-DD>
```

Example: `lab/promote/enhanced-vor-v3-2026-06-01`

Lab promotion PRs must target `main` and require:
1. Gate evaluation report attached (from `make lab-gate STRATEGY=<name>`)
2. Explicit Architecture review — lab + app changes need separate reviewer sign-off (one reviewer per package touched)

### Cross-package PR policy

| PR touches | Reviewer requirement |
|-----------|---------------------|
| `core/` only | 1 reviewer |
| `app/` only | 1 reviewer |
| `lab/` only | 1 reviewer |
| `core/` + `app/` | 1 reviewer (single PR acceptable) |
| `lab/` + `app/` | 2 reviewers — one per package |
| All three packages | 2 reviewers + Architecture sign-off |

---

## 7. `make dev-install` Target

The Makefile `dev-install` target installs all three packages in editable mode for local development:

```makefile
dev-install:
    @echo "Installing all packages in editable (dev) mode..."
    pip install -e core/ -e app/ -e lab/
    @echo "dev-install complete. All three packages (pigskin-core, pigskin-app, pigskin-lab) are active."
```

This target is **pre-migration safe**: it will fail gracefully until the `core/`, `app/`, and `lab/` directories contain valid `pyproject.toml` files (Step 0). Until then, `make install` remains the correct command for the current flat structure.

---

## 8. Rollback Plan

If migration causes test breakage that cannot be resolved within the current sprint:

### Per-step rollback

Each step branch is short-lived and not yet merged to `main`. If a step's verification gate fails and cannot be fixed quickly:

```bash
# Abandon the step branch
git checkout mono-repo-migration
git branch -D feat/mono-repo-<step>

# If the step was already merged to mono-repo-migration, revert the merge commit
git revert -m 1 <merge-commit-sha>
git push origin mono-repo-migration
```

`main` is never touched until the full migration completes, so rollback never requires touching `main`.

### Full migration rollback

If `mono-repo-migration` itself is merged to `main` and then found to be broken:

```bash
# Create a revert PR
git checkout main
git revert -m 1 <mono-repo-migration-merge-sha>
git push origin revert/mono-repo-migration
# Open PR: revert/mono-repo-migration → main
```

### Import path rollback

If import path changes cause runtime errors not caught by tests, run the inverse sed:

```bash
# Reverse core migration
find . -name "*.py" -not -path "./venv/*" | xargs sed -i \
    -e 's/from pigskin_core\.classes\./from classes./g' \
    -e 's/from pigskin_core\.config\./from config./g' \
    -e 's/from pigskin_core\.strategies\.base_strategy/from strategies.base_strategy/g'
```

Mirror inverse scripts must be written **before** running the forward migration scripts, and committed to `scripts/rollback_imports.sh`.

---

## Appendix: pyproject.toml Workspace Setup

Root `pyproject.toml` (PEP 517/518 workspace — requires pip ≥ 21.3):

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.workspace]
packages = ["core", "app", "lab"]
```

`core/pyproject.toml` (example):

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pigskin-core"
version = "2026.05.0"
requires-python = ">=3.8"
dependencies = []

[tool.hatch.build.targets.wheel]
packages = ["classes", "config", "strategies"]
```

`app/pyproject.toml` and `lab/pyproject.toml` follow the same pattern, declaring `pigskin-core` as a dependency.

---

*This document is approved for planning. Execution begins in Sprint 5 after team review of this plan.*
