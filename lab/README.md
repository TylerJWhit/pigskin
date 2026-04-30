# pigskin-lab

Experimental research lab for auction strategy development, backtesting, and player projection work.

**This package is not production code.** It runs experiments and generates data that may be
promoted to the core `pigskin` package via the gate process in `lab/promotion/`.

## Structure

| Directory | Purpose | Tracking |
|-----------|---------|---------|
| `strategies/` | Experimental strategy implementations | #82 |
| `gridiron_sage/` | GridironSage MCTS training | #83 |
| `simulation/` | Tournament runner | #187 |
| `benchmarks/` | Strategy comparison harness | — |
| `promotion/` | Gate evaluation for production promotion | #80 |
| `results_db/` | SQLite results store + Alembic migrations | #79 |
| `experiments/` | Named experiment configuration files | — |
| `data/` | Auction data scraper, projection snapshots | #192 |
| `backtest/` | Value-efficiency replay harness | — |
| `eval/` | Projection accuracy evaluator | — |

## Usage

```bash
# Install in development mode alongside the core package
pip install -e .
```

## Architecture

See `docs/adr/ADR-001-repo-structure.md` and `docs/adr/ADR-005-lab-extensions.md` for
the full design rationale and package placement decisions.
