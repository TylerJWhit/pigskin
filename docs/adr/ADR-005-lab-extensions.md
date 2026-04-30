# ADR-005: lab/ Package Extensions and data/ Module Placement

- **Status:** Accepted
- **Date:** 2026-04-30
- **Author:** Research Agent (Sprint 6)
- **Related:** ADR-001 (repo structure), #193, #186, #192

---

## Context

ADR-001 defines the initial `lab/` package structure with seven subdirectories.
Sprint 6 research (Initiative 1 — auction backtest, Initiative 2 — player projection)
identified three structural gaps that must be resolved before implementation can begin:

1. `lab/data/` — needed for auction data ingestion (`sleeper_auction_scraper.py`) and
   projection snapshots (`projections/`)
2. `lab/backtest/` — needed for the value-efficiency replay harness (`auction_replay.py`)
3. `lab/eval/` — needed for the projection accuracy evaluator (`projection_accuracy.py`)

Additionally, ADR-001 never assigned `data/fantasypros_loader.py` (core domain) to a package.
This gap blocks the `data/projections/` work in Initiative 2.

---

## Decision

### 1. Extend `lab/` with three new subdirectories

```
lab/
├── ...  (all ADR-001 directories unchanged)
├── data/                     ← NEW — auction scraper + projection snapshots
│   ├── __init__.py
│   └── sleeper_auction_scraper.py   (tracked by #192 / initiative A4)
├── backtest/                 ← NEW — value-efficiency replay harness
│   ├── __init__.py
│   └── auction_replay.py            (tracked by initiative A5)
└── eval/                     ← NEW — projection accuracy evaluator
    ├── __init__.py
    └── projection_accuracy.py       (tracked by initiative B5)
```

All three directories are **lab-only** — they have no production consumers.

### 2. Keep `data/` module at root (shared, versioned)

`data/fantasypros_loader.py` produces `Player` objects consumed by:
- `services/bid_recommendation_service.py` (production)
- `tests/` (production test suite)
- `lab/strategies/` (experimental)

**Decision:** `data/` stays at the repository root as a shared module.
It is not promoted into `lab/` because production services depend on it.

When the mono-repo migration (#176) completes, `data/` will become `core/data/`.
Until then, it is imported as `from data import ...`.

**`lab/data/` is separate**: it holds lab-specific data ingestion tools that have
no production consumers and must not be confused with the core `data/` module.

---

## Consequences

### Positive
- Clear separation between production data loading (`data/`) and lab ingestion (`lab/data/`)
- Initiative 1 and 2 implementation issues now have canonical home directories
- No production breakage risk from `lab/` churn

### Negative / Risks
- Two `data`-named directories at different paths require developer discipline to distinguish
- Import path `from lab.data import ...` must not shadow root `from data import ...`
  → mitigation: `lab/data/__init__.py` never re-exports from root `data/`

### Neutral
- `lab/pyproject.toml` declares `pigskin-lab` as a separate installable package;
  `lab/data/` is included automatically by the `find: where=["."]` directive

---

## Updated Full lab/ Structure

```
lab/
├── pyproject.toml
├── README.md
├── __init__.py
├── strategies/           # experimental strategies
├── gridiron_sage/        # GridironSage MCTS
├── simulation/           # tournament runner
├── benchmarks/           # strategy comparison
├── promotion/            # gate evaluation
├── results_db/           # SQLite + Alembic
├── experiments/          # named experiment configs
├── data/                 # auction scraper + projection snapshots  ← ADR-005
├── backtest/             # replay harness                          ← ADR-005
└── eval/                 # projection accuracy evaluator           ← ADR-005
```
