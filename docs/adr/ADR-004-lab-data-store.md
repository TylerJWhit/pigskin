# ADR-004: Lab Data Store (SQLite for Benchmark Results)

**Status:** Revised and Accepted
**Date:** 2026-04-28
**Revised:** 2026-04-28
**Author:** Architecture Agent (via Orchestrator)
**Reviewer:** Architecture Agent
**Deciders:** Engineering team

---

## Context

`pigskin-lab` is a permanent research environment that runs simulation batches continuously. Results must be persisted so that:
- Promotion gate comparisons use historical baselines (not re-computed each time)
- Strategy improvement trends are visible over weeks/seasons
- Promotion decisions are auditable with linked benchmark data

The lab is single-team (one developer or small group), not a multi-tenant SaaS. Concurrency requirements are modest.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| Files (JSON/CSV in `results/`) | Zero setup; current approach | Not queryable; no transactions; easy corruption; no trend analysis |
| **SQLite** | Zero-server setup; file-based (version-controllable schema); full SQL; sufficient for single-writer workload | Not suitable if parallel simulation workers write simultaneously (WAL mode mitigates this) |
| PostgreSQL | Full concurrency; better for parallel writes | Requires a running server; overkill for single-developer research tool |
| DuckDB | Columnar; excellent analytics queries | Less mature tooling; unusual dependency |

---

## Decision

**SQLite with WAL mode, accessed via SQLAlchemy (async with aiosqlite).**

WAL (Write-Ahead Logging) mode allows concurrent reads during writes and reduces write contention enough for the lab's parallel simulation workers (typically 4–8 processes writing results independently).

If the lab ever scales to >20 concurrent simulation workers, revisit this decision and migrate to PostgreSQL.

### Schema

```sql
-- Benchmark runs (one row per full simulation batch)
CREATE TABLE benchmark_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id   TEXT NOT NULL,          -- human-readable name, e.g. "vor_v2_vs_field"
    run_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lab_git_sha     TEXT NOT NULL,
    core_version    TEXT NOT NULL,
    simulation_count INTEGER NOT NULL,
    seed_list       TEXT,                   -- JSON array of seeds used
    opponent_set    TEXT NOT NULL,          -- JSON array of strategy names
    config_snapshot TEXT                    -- JSON snapshot of DraftConfig used
);

-- Per-strategy results within a run
CREATE TABLE strategy_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES benchmark_runs(id),
    strategy_name   TEXT NOT NULL,
    win_rate        REAL NOT NULL,
    win_rate_stddev REAL,
    avg_rank        REAL,
    avg_budget_efficiency REAL,
    p_value_vs_current REAL,               -- NULL if no current production strategy
    gate_result     TEXT,                  -- 'PASS', 'FAIL', 'NOT_EVALUATED'
    raw_results     TEXT                   -- JSON array of per-simulation outcomes
);

-- Promotion history
CREATE TABLE promotions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    promoted_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    strategy_name       TEXT NOT NULL,
    benchmark_run_id    INTEGER NOT NULL REFERENCES benchmark_runs(id),
    win_rate_at_promotion REAL NOT NULL,
    improvement_pp      REAL NOT NULL,
    p_value             REAL NOT NULL,
    app_git_sha         TEXT,              -- SHA of the app PR merge commit
    promoted_by         TEXT,             -- GitHub username or 'auto'
    is_current          INTEGER NOT NULL DEFAULT 1,  -- 1 = currently in production
    rolled_back_at      TIMESTAMP         -- NULL unless rolled back
);

-- Indices
CREATE INDEX idx_benchmark_runs_experiment ON benchmark_runs(experiment_id);
CREATE INDEX idx_strategy_results_run ON strategy_results(run_id);
CREATE INDEX idx_strategy_results_name ON strategy_results(strategy_name);
CREATE INDEX idx_promotions_current ON promotions(is_current);
```

### File Location
- Database file: `lab/results_db/pigskin_lab.db`
- Schema migrations: `lab/results_db/migrations/` (use Alembic)
- Tracked in `.gitignore` (data only); schema + migrations ARE tracked in git

---

## Consequences

### Positive
- No server setup required — works immediately on any developer machine
- Schema migrations via Alembic give a versioned change history
- WAL mode handles the parallel simulation writer scenario
- Full SQL enables trend queries: `SELECT strategy_name, AVG(win_rate) FROM strategy_results GROUP BY strategy_name ORDER BY 2 DESC`

### Negative
- SQLite file is binary — not human-readable in git diff
- If simulation workers are distributed across machines (future scale), SQLite becomes a blocker; plan PostgreSQL migration path
- Alembic adds a dev dependency and migration discipline requirement

---

## Migration Path to PostgreSQL (if needed)
- SQLAlchemy abstraction means connection string is the only change
- Schema is already Postgres-compatible (no SQLite-specific types)
- Migration trigger: >20 concurrent simulation workers OR distributed lab compute
---

## Critical Thinking Review (Architecture Agent — 2026-04-28)

### Three Schema Issues Requiring Revision

#### Issue 1: `is_current` Flag Invariant — Data Integrity Risk

**Problem:** `is_current INTEGER NOT NULL DEFAULT 1` means every new row inserted into `promotions` sets `is_current=1`. The application is responsible for setting all other rows to `is_current=0` on each new promotion. This invariant is not enforced by the schema. If the update step is skipped (bug, crash, partial write), multiple rows show `is_current=1`, and the system has no authoritative current strategy.

**Fix:** Replace the `is_current` column with a dedicated `current_production` view backed by a partial update, or use a single-row "current promotion" tracking table. Simplest approach: use a SQLite trigger.

Add to schema migrations:

```sql
-- Enforce: at most one row has is_current=1 at any time
-- When a new promotion is marked current, all others are automatically cleared.
CREATE TRIGGER enforce_single_current_promotion
    AFTER INSERT ON promotions
    WHEN NEW.is_current = 1
BEGIN
    UPDATE promotions SET is_current = 0
    WHERE id != NEW.id AND is_current = 1;
END;

CREATE TRIGGER enforce_single_current_on_update
    AFTER UPDATE OF is_current ON promotions
    WHEN NEW.is_current = 1
BEGIN
    UPDATE promotions SET is_current = 0
    WHERE id != NEW.id AND is_current = 1;
END;
```

This makes the invariant database-enforced, not application-enforced.

#### Issue 2: SQLite Version Constraint — `json_extract()` Required

**Problem:** `seed_list TEXT` stores a JSON array (e.g., `"[1, 42, 99, ...]"`). The schema has no index on seed values, and `json_extract()` is required to query them. SQLite's JSON functions (`json_extract`, `json_each`) were available since 3.9.0 (2015) but `json_each` as a table-valued function requires SQLite 3.38.0 (2022-02-22).

**Fix:** Document the minimum SQLite version requirement and add a startup check.

```python
# lab/results_db/db.py — add version check on connection init
import sqlite3
MIN_SQLITE_VERSION = (3, 38, 0)
conn_version = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
if conn_version < MIN_SQLITE_VERSION:
    raise RuntimeError(
        f"SQLite {sqlite3.sqlite_version} < 3.38.0 required for json_each() support. "
        "Upgrade SQLite or use seed_list queries via application-level JSON parsing."
    )
```

Add to `docs/adr/ADR-004`: minimum SQLite version = **3.38.0**.

If the runtime SQLite is older (possible on older Ubuntu/Debian), fall back to application-level seed filtering (load all rows, parse `seed_list` in Python). This fallback must be documented.

#### Issue 3: `config_snapshot` Nullability

**Problem:** `config_snapshot TEXT` is nullable with no documented semantics for NULL. If a benchmark run doesn't record its config snapshot, that run cannot be reproduced. For a promotion audit, this is a gap — the gate report references `config_snapshot` but it may be absent.

**Fix:** Make `config_snapshot NOT NULL` in new migrations. Existing NULL rows (from any runs before this schema change) get a sentinel value: `config_snapshot = '{"note": "config not captured — pre-schema-revision run"}'`.

Add to Alembic migration:

```sql
UPDATE benchmark_runs SET config_snapshot = '{"note":"config not captured"}' WHERE config_snapshot IS NULL;
ALTER TABLE benchmark_runs RENAME COLUMN config_snapshot TO config_snapshot_old;
-- (SQLite does not support ALTER COLUMN; use recreate pattern)
```

Alembic's `op.execute()` with the recreate pattern handles this for SQLite.

### Revised Schema Additions

The schema from the Decision section is accepted with these additions:

```sql
-- Add after the promotions table definition:
CREATE TRIGGER enforce_single_current_promotion
    AFTER INSERT ON promotions
    WHEN NEW.is_current = 1
BEGIN
    UPDATE promotions SET is_current = 0 WHERE id != NEW.id AND is_current = 1;
END;

CREATE TRIGGER enforce_single_current_on_update
    AFTER UPDATE OF is_current ON promotions
    WHEN NEW.is_current = 1
BEGIN
    UPDATE promotions SET is_current = 0 WHERE id != NEW.id AND is_current = 1;
END;
```

`config_snapshot` is `NOT NULL` going forward. `seed_list` remains `TEXT` (nullable acceptable — not all runs enumerate seeds explicitly).

### Assumptions Examined

1. **"WAL mode is sufficient for 4-8 parallel simulation workers"** — Correct. SQLite WAL allows concurrent reads and one writer at a time. With multiprocessing workers, each process serializes writes. At 4-8 processes, write contention is occasional and brief (a single result row per simulation end). This is fine.

2. **"SQLAlchemy async with aiosqlite is the right ORM choice"** — Correct for the asyncio FastAPI environment. However, lab simulation workers are NOT async — they're multiprocessing workers running sync code. The lab write path should use sync SQLAlchemy (not aiosqlite) for simulation workers, and async SQLAlchemy (with aiosqlite) only for the FastAPI read endpoints. Document this split.

3. **"Schema is Postgres-compatible"** — Mostly true, but `INTEGER PRIMARY KEY AUTOINCREMENT` is SQLite-specific. PostgreSQL uses `SERIAL` or `BIGSERIAL`. The migration path should document the one-time schema translation step (Alembic env.py switch + schema re-creation in Postgres).

### Risks

- **`is_current` flag corruption on crash** — Resolved by trigger above.
- **SQLite version on CI/prod** — Ubuntu 22.04 ships SQLite 3.37.2 (just below 3.38.0). Ubuntu 24.04 ships 3.45.x. Confirm CI uses Ubuntu 24.04 or install SQLite from source in CI.
- **Alembic discipline**: SQLite's limited `ALTER TABLE` support means many schema changes require the table-recreate pattern. Engineers must use `op.execute()` directly for these, not Alembic's `op.alter_column()`. Document this constraint in `lab/results_db/migrations/README.md`.
- **Bootstrap promotion record** (from ADR-001/ADR-003): The bootstrap record has `benchmark_run_id = NULL`. The foreign key `NOT NULL REFERENCES benchmark_runs(id)` in the schema will REJECT this. Either: (a) create a sentinel `benchmark_runs` row for the bootstrap case, or (b) relax the FK to nullable for the promotions table with a CHECK constraint ensuring non-bootstrap rows have a non-null FK. **Recommendation: (a) — create a bootstrap benchmark_runs row.**