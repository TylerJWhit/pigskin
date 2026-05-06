# pigskin-lab Continuous Improvement Loop — Design

**Status:** Draft  
**Issue:** [LAB-1] #78  
**Author:** AI/ML Engineer  
**Date:** 2026-04-29  
**References:** ADR-001 (repo structure), ADR-003 (promotion gate), ADR-004 (lab data store)

---

## Critical Thinking Review (AI/ML Engineer — 2026-04-29)

Before committing to this design, the following assumptions and risks are made explicit.

### Assumptions Examined

1. **"50-iteration MCTS produces a reliable tournament signal."**  
   At 50 iterations the UCB tree search has visited a very small portion of the game tree for a 12-team auction with 200+ players. Strategies may appear equivalent at this resolution. **Assumption: partially valid.** The cap exists to prevent hanging in multi-team simulations (noted in agent instructions). The signal will be noisy for fine-grained comparisons. The n=500 batch requirement in ADR-003 compensates by averaging over noise.

2. **"GridironSage will eventually outperform hand-crafted strategies."**  
   There is no evidence yet for this in the 12-team auction format. Auction drafts have a complex combinatorial structure that may favor domain-knowledge strategies (VOR, EliteHybrid) over learned policies trained with limited self-play data. **Assumption: unverified.** The lab must be designed to hold GridironSage accountable to the same promotion gate as all other strategies — it receives no special promotion path.

3. **"SQLite WAL mode is sufficient for parallel lab workers."**  
   ADR-004 acknowledges the threshold is ~20 concurrent writers. The lab design targets 4–8 parallel simulation processes. **Assumption: valid** with retry-on-lock logic in the results writer.

4. **"Nightly CI is the right cadence."**  
   This assumes training + benchmark completes in < 8 hours. Early runs may not hit this. The design must support both nightly (CI-triggered) and manual-trigger modes.

### Alternative Perspective

The current framing optimizes for win-rate as the primary promotion signal. An alternative would be **strategic robustness** — promoting a strategy that wins across the widest opponent distribution, not just the one that achieves the highest peak win-rate against a fixed opponent set. This is a meaningful alternative that the gate's opponent-diversity requirement partially addresses, but the primary comparator (win-rate) still rewards peak performance over robustness. **The current design is reasonable for v1; robustness scoring should be considered for v2.**

### Key Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| 50-iter MCTS produces noisy tournament signal | Medium | n=500 batch averaging; variance gate in ADR-003 |
| GridironSage converges to local optimum, lab stalls | High | Human-trigger for new experiment configs; randomized opponent mix |
| Alert fatigue if gate FAILs nightly for months | Medium | Gate result trend dashboard; distinguish "no improvement" from "regression" |
| No production strategy on day-1 of migration | High | Bootstrap policy: EliteHybridStrategy is the initial `app/strategies/production.py` (see §6) |
| Budget-efficiency gate is only a regression guard, not a positive requirement | Low | A strategy that underspends to win more is a valid outcome in auction theory; flag in reports but do not auto-reject |
| SQLite WAL lock contention with 4–8 parallel writers | Low | Exponential backoff retry in results writer; max 3 retries |

### One Deeper Question

**How does the lab distinguish "better strategy" from "better opponent draw"?** If the 50 distinct seeds are drawn from the same distribution, a strategy that happens to excel at mid-market RB pricing could appear dominant in a run that over-samples that scenario. The seed list must be fixed across all benchmark runs for a given experiment (stored in `benchmark_runs.seed_list`) so that comparisons are apples-to-apples. This constraint is not made explicit in ADR-003 and should be enforced in the gate script.

---

## 1. Lab Architecture: The Continuous Improvement Loop

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          pigskin-lab CI loop                            │
│                                                                         │
│  ┌──────────────┐     ┌──────────────────┐     ┌─────────────────────┐ │
│  │  Experiment  │────▶│  Simulation Run  │────▶│   Gate Evaluation   │ │
│  │  Config      │     │  (N≥500 matches, │     │   (promotion/gate)  │ │
│  │  (YAML/JSON) │     │   MCTS 50-iter)  │     │                     │ │
│  └──────────────┘     └──────────────────┘     └──────────┬──────────┘ │
│                               │                           │             │
│                               ▼                           │             │
│                    ┌──────────────────┐                   │             │
│                    │  results_db/     │◀──────────────────┘             │
│                    │  pigskin_lab.db  │                                 │
│                    └──────────────────┘                                 │
│                               │                                         │
│                        PASS ──┼── FAIL                                  │
│                               │         │                               │
│                    ┌──────────▼──────┐  │  ┌────────────────────────┐  │
│                    │  Auto-generate  │  └─▶│  Record FAIL + notify  │  │
│                    │  Promotion PR   │     │  (no PR generated)     │  │
│                    └──────────┬──────┘     └────────────────────────┘  │
│                               │                                         │
└───────────────────────────────┼─────────────────────────────────────────┘
                                │
                    ┌───────────▼──────────┐
                    │   Human Review       │
                    │   Merge PR →         │
                    │   app/strategies/    │
                    └──────────────────────┘
```

### Loop Trigger Modes

| Mode | Trigger | Use Case |
|------|---------|----------|
| **Nightly CI** | GitHub Actions cron (`0 2 * * *`) | Steady-state improvement scanning |
| **Manual** | `gh workflow run lab-ci.yml` | After a new strategy is added to `lab/strategies/` |
| **GridironSage post-training** | Called by `lab/gridiron_sage/train.py` after a training cycle completes | Evaluate newly trained checkpoint against production |

The nightly CI run does **not** run training — it benchmarks whatever strategies are currently in `lab/strategies/` against the production strategy. Training is a separate, explicit workflow.

---

## 2. Strategy Lab Lifecycle

### States

```
NEW ──▶ CANDIDATE ──▶ BENCHMARKING ──▶ GATE ──▶ PROMOTED
                                          │
                                          └──▶ REJECTED (archived, not deleted)
```

| State | Location | Description |
|-------|----------|-------------|
| **NEW** | `lab/strategies/<name>.py` | Strategy added to lab; no benchmark data yet |
| **CANDIDATE** | `lab/strategies/<name>.py` | Manually designated for a benchmark run via `lab/experiments/<experiment_id>/config.json` |
| **BENCHMARKING** | `lab/results_db/` | Active simulation batch in progress |
| **GATE** | `lab/promotion/gate.py` output | Gate evaluation running; result pending |
| **PROMOTED** | `app/strategies/production.py` | Strategy is the current production strategy |
| **REJECTED** | `lab/strategies/<name>.py` (retained) | Gate FAIL; strategy stays in lab for further iteration |

### Lifecycle Steps

**Step 1 — Experiment Definition**

An experiment config is created in `lab/experiments/<experiment_id>/config.json`:

```json
{
  "experiment_id": "enhanced_vor_v3_vs_field",
  "challenger_strategy": "enhanced_vor_v3",
  "opponent_set": ["vor", "balanced", "aggressive", "conservative", "random"],
  "simulation_count": 500,
  "seed_list": [1001, 1002, ..., 1050],
  "mcts_iterations_per_match": 50,
  "draft_config": {
    "num_teams": 12,
    "budget": 200,
    "scoring_format": "half_ppr"
  }
}
```

The `seed_list` is fixed at experiment creation and stored in `benchmark_runs.seed_list`. The same seeds must be used if the experiment is re-run to ensure comparability.

**Step 2 — Simulation Run**

`lab/simulation/runner.py` executes the experiment config:
- Spawns up to 8 parallel worker processes (each writes to SQLite with WAL retry)
- Each match: 12-team auction, MCTS at 50 iterations, one challenger + 11 opponents drawn from the opponent set
- Results written to `strategy_results` table per batch

**Step 3 — Gate Evaluation**

`lab/promotion/gate.py` reads results from the DB, compares challenger vs. current production strategy:

| Criterion | Threshold | Source |
|-----------|-----------|--------|
| Simulation count | ≥ 500 | ADR-003 |
| Seed diversity | ≥ 50 distinct seeds | ADR-003 |
| Opponent set coverage | All 5 required types present | ADR-003 |
| Win-rate improvement | Challenger ≥ current + **5.0 pp** | ADR-003 (revised) |
| Statistical significance | p < 0.01 (two-sample proportion z-test) | ADR-003 |
| Budget efficiency | Challenger avg efficiency ≥ current − 1% | ADR-003 |
| Sanity floor | Win-rate vs. Random ≥ 80% | ADR-003 |
| Variance gate | Challenger σ(win-rate) ≤ current σ + 5% | ADR-003 |
| **Seed consistency** | Same `seed_list` used as registered at experiment creation | Lab design (not in ADR-003) |

**Step 4 — Promotion PR (PASS only)**

Gate emits a JSON result (schema from ADR-003). On PASS:
- Branch: `lab/promote/<strategy_name>-<YYYY-MM-DD>`
- Copies challenger strategy to `app/strategies/production.py`
- Moves previous production strategy to `app/strategies/previous/`
- PR body: gate JSON + benchmark report from `lab/experiments/<id>/report.md`
- Labels: `promotion`, `needs-review`

---

## 3. MCTS Tournament Configuration

### Two Modes — Never Mixed

| Mode | Iterations | Purpose | Location |
|------|-----------|---------|----------|
| **Tournament** | **50** (hard cap) | Lab benchmark matches, production inference | `lab/simulation/`, `app/` |
| **Training** | **800** | GridironSage self-play data generation | `lab/gridiron_sage/` |

The 50-iteration cap is enforced in code within the tournament runner. It must never be configurable via user-facing config for production paths — it is a hard constant. Training mode (800 iterations) is invoked only by the explicit `lab/gridiron_sage/train.py` script, never automatically by CI.

### MCTS Parameters

```json
{
  "tournament_mcts_iterations": 50,
  "training_mcts_iterations": 800,
  "c_puct": 1.4,
  "temperature_initial": 1.0,
  "temperature_final": 0.1,
  "temperature_decay_steps": 30,
  "neural_net_eval_cache": true
}
```

`temperature_initial` applies for the first `temperature_decay_steps` training games, then decays to `temperature_final`. Tournament mode always uses `temperature = 0` (greedy action selection — deterministic for reproducibility given fixed seeds).

---

## 4. Strategy Entry and Production Determination

### How New Strategies Enter the Lab

A strategy enters `lab/strategies/` by one of three paths:

| Path | Description | Review required? |
|------|-------------|-----------------|
| **Hand-authored** | Engineer writes a new Python strategy file | PR into `develop`; code review |
| **GridironSage checkpoint** | `lab/gridiron_sage/train.py` exports a checkpoint; `lab/promotion/checkpoint_to_strategy.py` wraps it as a `LabStrategy` | Automated; human reviews before designating as CANDIDATE |
| **Mutation experiment** | `lab/gridiron_sage/` generates strategy variants via hyperparameter sweep | Automated; only the Pareto-optimal variant is designated CANDIDATE |

Strategies in `lab/strategies/` are **never** directly importable by `app/`. The `core/strategies/base_strategy.py` interface is the only shared contract.

### How the Production Strategy is Determined

There is exactly **one** production strategy at any time: `app/strategies/production.py`. This file is updated **only** by a merged promotion PR. The determination is fully gate-controlled:

```
current production = last strategy to pass the gate AND have its promotion PR merged
```

On day-1 of migration (Sprint 5), the bootstrap production strategy is `EliteHybridStrategy` — it is the highest-performing hand-crafted strategy in the current `strategies/` directory and requires no gate evaluation for the initial placement. All subsequent changes to `app/strategies/production.py` require a passed gate.

---

## 5. Integration with ADR-003: Promotion Gate

The gate script `lab/promotion/gate.py` is the authoritative implementation of ADR-003. Key integration points:

### Statistical Test

```
Two-sample proportion z-test (one-tailed: challenger > current)

H₀: p_challenger ≤ p_current
H₁: p_challenger > p_current

z = (p̂₂ - p̂₁) / √(p̂_pool × (1 - p̂_pool) × (1/n₁ + 1/n₂))

where n₁ = n₂ = 500, reject H₀ if p < 0.01
```

At the required 5pp improvement with baseline ~35–40% win-rate, z ≈ 3.6 and p ≈ 0.0003 — well within the 0.01 threshold. The gate is internally consistent (per ADR-003 critical thinking revision).

### Gate Output → DB Write

The gate always writes a record to `strategy_results` regardless of PASS/FAIL:

```python
# lab/promotion/gate.py (pseudocode)
result = evaluate_gate(challenger, current, simulation_results)
db.write_gate_result(result)          # always write
if result.gate_result == "PASS":
    generate_promotion_pr(result)
else:
    notify_monitoring_dashboard(result)
```

Gate results are immutable once written. If an engineer disagrees with a FAIL, they run a new experiment (new `experiment_id`) — they do not amend existing records.

---

## 6. Integration with ADR-004: Lab Data Store

The SQLite database at `lab/results_db/pigskin_lab.db` uses the schema defined in ADR-004 verbatim. The lab design adds the following operational constraints not specified in the ADR:

### Write Path

All simulation workers write to the DB via a single shared writer module:

```
lab/results_db/writer.py
  └── write_simulation_result(run_id, strategy_name, outcome)
        └── retry up to 3× with exponential backoff on OperationalError (database is locked)
        └── raise after 3 failures (worker dies; run continues with other workers)
```

The `run_id` is created by the orchestrator before spawning workers and passed to each worker — workers never create their own `benchmark_runs` rows.

### Read Path (Gate)

The gate script reads via a synchronous SQLite connection (no aiosqlite needed — gate is single-threaded):

```sql
SELECT strategy_name, AVG(win_rate) AS mean_win_rate,
       AVG(win_rate_stddev) AS mean_stddev,
       AVG(avg_budget_efficiency) AS mean_budget_eff
FROM strategy_results
WHERE run_id = :run_id
GROUP BY strategy_name;
```

### Alembic Migrations

`lab/results_db/migrations/` uses Alembic with a single `env.py`. Schema changes are introduced as numbered migration scripts and applied by `lab CI` on startup before running any simulations.

---

## 7. Lab Directory Structure

```
lab/                                    ← pigskin-lab root package
│
├── pyproject.toml                      ← lab package manifest; depends on pigskin-core
│
├── gridiron_sage/                      ← GridironSage ML system (MCTS + dual-head neural network)
│   ├── __init__.py
│   ├── network.py                      ← Dual-head PyTorch model (policy + value heads)
│   ├── mcts.py                         ← MCTS implementation (50/800 iter modes)
│   ├── train.py                        ← Self-play training loop (800 iterations)
│   ├── self_play.py                    ← Game data generation
│   ├── replay_buffer.py                ← 50K experience FIFO buffer
│   ├── features.py                     ← 20-dim feature extractor (canonical)
│   └── checkpoint_to_strategy.py       ← Wrap trained checkpoint as LabStrategy
│
├── strategies/                         ← All experimental strategy variants
│   ├── __init__.py
│   ├── <strategy_name>.py              ← One file per strategy; inherits base_strategy
│   └── ...                             ← 17 current strategies migrate here from strategies/
│
├── simulation/                         ← Tournament runner for benchmark matches
│   ├── __init__.py
│   ├── runner.py                       ← Parallel simulation orchestrator (8 workers max)
│   ├── match.py                        ← Single 12-team auction match execution
│   └── scenario_generator.py          ← Draft config + player pool generation per seed
│
├── benchmarks/                         ← Strategy comparison harness
│   ├── __init__.py
│   ├── benchmark.py                    ← Run a full benchmark; calls runner + gate
│   └── report.py                       ← Generate Markdown benchmark report
│
├── promotion/                          ← Gate evaluation + PR generation
│   ├── __init__.py
│   ├── gate.py                         ← ADR-003 gate logic
│   └── pr_generator.py                 ← GitHub API: create promotion branch + PR
│
├── results_db/                         ← SQLite persistence (ADR-004)
│   ├── pigskin_lab.db                  ← .gitignore'd; data only
│   ├── schema.sql                      ← ADR-004 schema (tracked in git)
│   ├── writer.py                       ← Retry-safe write path
│   └── migrations/                     ← Alembic migration scripts
│       ├── env.py
│       └── versions/
│           └── 001_initial_schema.py
│
└── experiments/                        ← Named experiment configs + results
    └── <experiment_id>/
        ├── config.json                 ← Immutable after run starts
        └── report.md                   ← Auto-generated post-gate
```

### What Does NOT Live in `lab/`

- `app/strategies/production.py` — lives in `app/`; updated only by promotion PR
- `app/strategies/previous/` — previous production strategy; lives in `app/`
- `core/strategies/base_strategy.py` — abstract interface; lives in `core/`
- The current flat `strategies/` directory at the repo root — migrates to `lab/strategies/` in Sprint 5

---

## 8. Rollback Policy

Rollback policy is inherited from ADR-003 with one lab-specific addition:

### Trigger Conditions

| Condition | Source | Action |
|-----------|--------|--------|
| Post-promotion nightly CI shows promoted strategy's win-rate degraded > **5pp vs. its promotion benchmark** over ≥ **50 consecutive nightly runs** | Lab CI + results_db | Engineer on rotation initiates rollback review |
| Future: live user analytics show >5% win-rate regression vs. baseline over 2+ weeks | User analytics (not yet built) | Automatic rollback trigger (future) |

### Rollback Execution

1. Open a rollback PR: revert `app/strategies/production.py` to `app/strategies/previous/`
2. PR body must include the triggering gate result JSON and the run IDs of the 50 degraded CI runs
3. PR is fast-tracked — requires one human review, not two
4. After merge: `promotions.rolled_back_at` is updated for the affected promotion record
5. `app/strategies/previous/` is NOT auto-deleted after rollback — it becomes the new production until the next promotion cycle

### Rollback Is Not a Career Move

Rolling back is a normal, expected outcome. The CI dashboard should surface the "5pp regression over 50 runs" signal proactively — engineers should not need to manually query the DB to discover it.

### What "50 nightly runs" Means in Practice

With a nightly CI cadence, 50 runs ≈ 50 calendar days (≈7 weeks). This is a deliberately conservative window to avoid rollback thrashing on noisy results. If a catastrophic failure is observed (e.g., promoted strategy win-rate drops below the "sanity floor" of 80% vs. Random), rollback is immediate without waiting for 50 runs.

---

## 9. Open Questions (Cannot Resolve Alone)

The following questions require input from other agents or the engineering team before implementation begins.

| # | Question | Owner | Blocking? |
|---|----------|-------|-----------|
| 1 | **Bootstrap strategy**: Does `EliteHybridStrategy` need to pass the gate before being placed in `app/strategies/production.py` on migration day? Or is it exempt as the founding production strategy? | Architecture Agent / PM | Yes — affects Sprint 5 migration plan |
| 2 | **Seed list governance**: Who is responsible for generating and maintaining the canonical seed list? Should seeds be fixed forever or rotated per season? Rotating seeds breaks year-over-year comparability. | Architecture Agent | Yes — affects gate consistency |
| 3 | **GridironSage training cadence**: How often should training runs be triggered? A nightly training run + nightly benchmark run in the same 8-hour window may not be feasible on CI hardware. Is training triggered manually or on a weekly schedule? | AI/ML Engineer (self) + DevOps/PM | Yes — affects CI pipeline design |
| 4 | **Parallel worker count**: ADR-004 notes "typically 4–8 processes." Is there a CI runner resource constraint that sets this ceiling? The lab design assumes up to 8, but CI hardware may enforce fewer. | DevOps / PM | No — default to 4 if unknown |
| 5 | **`lab/results_db/pigskin_lab.db` backup policy**: The DB is `.gitignore`'d. If the CI runner is ephemeral, the DB is lost on every run. Is the DB stored on a persistent volume, or is it rebuilt from scratch each run? If ephemeral, the "historical trend" value of the DB is lost. | DevOps / PM | Yes — fundamental to the "permanent research environment" goal |
| 6 | **Promotion PR auto-merge**: Should the promotion PR be auto-merged if the gate passes and no reviewer requests changes within N days? Or is human review always required? ADR-003 says "human review required" but does not define a timeout. | PM / Architecture Agent | No — default to "always human" |
| 7 | **Strategy naming convention for `lab/strategies/`**: The current flat `strategies/` has 17 files with inconsistent naming (`elite_hybrid_strategy.py`, `improved_value_strategy.py`, etc.). Should the lab enforce a naming convention (e.g., `<family>_<variant>_v<N>.py`) before migration? | Architecture Agent | No — but should be decided in Sprint 5 |
| 8 | **`lab/` package and `app/` package on the same CI runner**: ADR-001 specifies three packages. Does the promotion gate run in the `lab` CI pipeline or the `app` CI pipeline? The gate writes to `lab/results_db/` (lab concern) but generates a PR that changes `app/strategies/` (app concern). | Architecture Agent | Yes — affects CI pipeline topology |

---

## 10. Summary of Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Single production strategy (`app/strategies/production.py`) | No config flags; promotion is a code change; git history is the audit trail |
| Bootstrap strategy = `EliteHybridStrategy` (pending Architecture approval) | Highest-performing current hand-crafted strategy; avoids "no production strategy on day 1" gap |
| Fixed seed list per experiment | Ensures gate comparisons are apples-to-apples; prevents seed-overfitting |
| MCTS tournament hard cap = 50 iterations | Inherited from agent constraints; encoded as a constant, not a config value |
| MCTS training cap = 800 iterations | Full depth for quality GridironSage self-play data; never triggered by CI automatically |
| GridironSage uses same promotion gate as all strategies | No special path; accountability over ML hype |
| Gate always writes to DB (PASS or FAIL) | Immutable audit log; trend visibility |
| `lab/results_db/pigskin_lab.db` requires persistent storage | Loss of DB = loss of historical trend data; must be addressed in CI infrastructure |
| Rollback trigger = 5pp regression over ≥50 nightly runs | Conservative window avoids noise-driven rollback thrashing |
| Catastrophic rollback bypass | < 80% win-rate vs. Random triggers immediate rollback without waiting for 50 runs |
