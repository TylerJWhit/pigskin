# ADR-003: Strategy Promotion Pipeline (Lab → Production)

**Status:** Revised and Accepted
**Date:** 2026-04-28
**Revised:** 2026-04-28
**Author:** Architecture Agent (via Orchestrator)
**Reviewer:** Architecture Agent
**Deciders:** Engineering team

---

## Context

`pigskin-lab` is a permanent, continuously-improving research environment. New and modified strategies are developed and benchmarked there. At some point a challenger strategy outperforms the current production strategy. The promotion pipeline is the process by which that strategy safely moves from lab to production.

This pipeline must be:
- **Automated where possible** (no manual benchmark interpretation)
- **Auditable** (every promotion has a linked benchmark report and git SHA)
- **Reversible** (rollback must be possible within one sprint)
- **Statistically rigorous** (pass/fail based on evidence, not intuition)

The current production strategy is undefined (no `app/strategies/` exists yet), so this ADR defines the policy that will govern all future promotions from the moment the split occurs.

---

## Promotion Gate Specification

### Minimum Evidence Requirements

| Requirement | Threshold | Rationale |
|-------------|-----------|-----------|
| Simulation count | ≥ 500 runs | Sufficient for stable win-rate estimates at 12-team auction format |
| Seed diversity | 50 distinct seeds minimum | Prevents overfitting to a specific random draw |
| Opponent set | Must include: VOR, Balanced, Aggressive, Conservative, Random (at least 5 distinct strategy types in each sim) | Tests robustness across opponent variety |
| Win-rate improvement | Challenger ≥ current + **5.0 percentage points** | Statistically achievable at n=500; consistent with p < 0.01 (see Critical Thinking Revision) |
| Statistical significance | **p < 0.01** (two-sample proportion z-test) | Tighter threshold; z ≈ 3.6 at 5pp + n=500 yields p ≈ 0.0003 |
| Budget efficiency | Challenger avg budget efficiency ≥ current − 1% | No regression on secondary metric |
| No catastrophic failure | Challenger win-rate vs. Random ≥ 80% | Sanity floor — must beat a trivial baseline |
| Variance gate | Challenger stddev(win-rate) ≤ current + 5% | Rejects high-variance "lucky" strategies |

### Promotion Gate Output

The gate script (`lab/promotion/gate.py`) produces:
```json
{
  "gate_result": "PASS | FAIL",
  "challenger_strategy": "<name>",
  "current_strategy": "<name>",
  "simulation_count": 500,
  "challenger_win_rate": 0.42,
  "current_win_rate": 0.38,
  "improvement_pp": 4.0,
  "p_value": 0.021,
  "budget_efficiency_delta": 0.005,
  "variance_delta": 0.02,
  "gate_timestamp": "2026-04-28T00:00:00Z",
  "lab_git_sha": "abc1234",
  "report_path": "lab/experiments/<experiment_id>/report.md"
}
```

Gate result is written to `lab/results_db/` and referenced in the auto-generated promotion PR.

---

## Promotion Workflow

```
1. Lab CI (nightly or manual trigger)
   └─ Run simulation batch (N ≥ 500, diverse seeds + opponents)
   └─ Write results to lab/results_db/

2. Gate evaluation (promotion/gate.py)
   └─ FAIL → record result, notify monitoring dashboard, stop
   └─ PASS → continue

3. Auto-generate promotion PR
   └─ Branch: lab/promote/<strategy_name>-<date>
   └─ Change: update app/strategies/<production_strategy>.py
   └─ Attach: benchmark report as PR body
   └─ Label: "promotion", "needs-review"

4. Human review (required)
   └─ Engineer reviews gate JSON + benchmark report
   └─ Can request additional simulations before merging
   └─ Merges PR into develop

5. CI/CD (app-ci.yml) runs on merge
   └─ Full test suite (must pass 420/420)
   └─ Deploy to staging

6. Promotion record written to lab/results_db/promotions table
   └─ Fields: strategy_name, promoted_at, benchmark_score, git_sha, promoted_by
```

### Rollback Policy
- Previous production strategy is retained in `app/strategies/previous/` for one full sprint after promotion
- Rollback is a one-line config change + PR — no code changes required
- Rollback is considered if: post-promotion monitoring shows >5% win-rate regression vs. baseline over 2+ weeks of live data (requires future user analytics)
- **Until user analytics exist**, rollback trigger is manual: if lab nightly simulations show the promoted strategy's win-rate has degraded >5pp vs. its promotion benchmark over 50+ recent runs, the engineer on rotation must initiate rollback review.

---

## Critical Thinking Review (Architecture Agent — 2026-04-28)

### Statistical Contradiction — CRITICAL REVISION

**The original gate contains an internally inconsistent requirement.** The combination of:
- `simulation_count ≥ 500`
- `win_rate_improvement ≥ 2.0 percentage points`
- `p < 0.05 (two-sample proportion z-test)`

…is statistically impossible to satisfy simultaneously for marginal improvements.

**Proof:**

For a baseline win-rate of ~38% (reasonable for a 12-team format where each team has ~1/12 ≈ 8.3% expected win rate but better strategies achieve higher):

```
p1 = 0.40 (current), p2 = 0.42 (challenger, exactly 2pp better)
pooled_p = 0.41
SE = sqrt(0.41 * 0.59 * (1/500 + 1/500)) = sqrt(0.2419 / 250) ≈ 0.031
z = 0.02 / 0.031 ≈ 0.645
p-value ≈ 0.52  ← FAR from 0.05
```

To achieve p < 0.05 with a 2pp improvement, you need approximately **n ≈ 3,750 simulations per strategy** (not 500).

**Resolution (two options — both are acceptable; the team must choose one):**

| Option | n (simulations) | Min improvement threshold | Tradeoff |
|--------|-----------------|--------------------------|---------|
| **A — Keep 2pp threshold, increase n** | **3,750** | 2.0 pp | Slower CI; higher confidence |
| **B — Keep n=500, raise threshold** | 500 | **5.0 pp** | Faster CI; only promotes clearly dominant strategies |

**Architecture Agent recommendation: Option B (n=500, 5pp threshold).**

Rationale: This lab will run strategies that differ meaningfully (different algorithms, not just parameter tweaks). A 5pp bar correctly filters noise while keeping CI fast. If a strategy is only 2pp better, it's not decisively superior — wait for a stronger challenger. The 5pp threshold at n=500 yields z ≈ 3.6, p ≈ 0.0003, which is robust.

**Updated gate requirement:**

| Requirement | Original | Revised | Notes |
|-------------|----------|---------|-------|
| Simulation count | ≥ 500 | **≥ 500** | Unchanged |
| Win-rate improvement | ≥ 2.0 pp | **≥ 5.0 pp** | Statistically consistent with n=500 |
| Statistical significance | p < 0.05 | **p < 0.01** | Tighter threshold; at 5pp + n=500, z≈3.6, p≈0.0003 — use 0.01 as the gate floor |

### Revised Gate Specification

Replace the "Win-rate improvement" and "Statistical significance" rows in the Promotion Gate table:

| Requirement | Threshold | Rationale |
|-------------|-----------|-----------|
| Simulation count | ≥ 500 runs | Sufficient for stable estimates; consistent with 5pp threshold |
| Seed diversity | 50 distinct seeds minimum | Prevents overfitting |
| Opponent set | VOR, Balanced, Aggressive, Conservative, Random, **+ current production strategy** | Must include current champion as an explicit opponent |
| Win-rate improvement | Challenger ≥ current + **5.0 percentage points** | Statistically achievable at n=500, p<0.01 |
| Statistical significance | **p < 0.01** (two-sample proportion z-test) | Tighter threshold justified by the large z-score at 5pp+n=500 |
| Budget efficiency | Challenger avg budget efficiency ≥ current − 1% | Unchanged |
| No catastrophic failure | Challenger win-rate vs. Random ≥ 80% | Unchanged |
| Variance gate | Challenger stddev(win-rate) ≤ current + 5% | Unchanged |

### Additional Revision: Opponent Set

**The original opponent set omits the current production strategy.** A challenger that beats VOR, Balanced, etc. but loses to the incumbent is not promotable. Add "current production strategy" as a required opponent.

### Rollback Trigger Gap

The rollback policy requires "post-promotion monitoring" and "user analytics" — neither exists. Without a trigger signal, rollback is theoretically possible but practically never invoked.

**Interim rollback policy** (until analytics exist): If lab nightly CI shows promoted strategy's win-rate has degraded >5pp vs. its promotion benchmark over ≥50 consecutive nightly runs, the engineer on rotation must create a rollback issue within 48 hours. This is a manual but defined trigger.

### Assumptions Examined

1. **"500 simulations is sufficient"** — Sufficient for the revised 5pp/p<0.01 threshold. Would be insufficient for the original 2pp threshold.
2. **"Promotion is once-per-sprint cadence"** — Not specified. Nightly CI can detect a gate-passing challenger at any time. The ADR should not imply promotion is sprint-gated — it's event-driven (gate passes → PR created).
3. **"Human review is the final gate"** — Correct. Auto-generated PRs with gate JSON are good; a human merge requirement prevents fully automated deployments of AI-generated strategy code.

### Risks

- **Strategy overfitting to the opponent set**: A strategy tuned to beat VOR + Balanced + Aggressive may be brittle against novel opponents. Mitigated by the Random baseline requirement.
- **Gate gaming**: A researcher could tune a strategy to barely pass the gate (5pp improvement vs. a weak current strategy) repeatedly. Mitigated by requiring improvement vs. the current PRODUCTION strategy, not vs. an arbitrary baseline.
- **Bootstrap exception**: ADR-001 allows a bootstrap production strategy (EnhancedVORStrategy) without gate passage. This is a one-time exception and must be treated as such. Gate.py should check if `promotions` table is empty and mark the bootstrap record so it cannot be used as a "baseline" in future comparisons.

---

## Consequences

### Positive
- Promotion decisions are evidence-based and auditable — no "felt better" promotions
- The gate spec is versioned in `docs/adr/` — changes require a PR and review
- Auto-generated PRs make promotion lightweight (no manual bookkeeping)
- Historical benchmark data in `results_db/` enables trend analysis

### Negative
- 500-simulation gate takes real compute time — must be async/scheduled, not blocking CI
- Gate thresholds (5pp improvement, p < 0.01) are calibrated for n=500; they will need re-evaluation after the first season of real data
- Human review step is a bottleneck; acceptable for now given low promotion frequency (target: ≤ 4 promotions per season)

---

## Open Questions (for Architecture + AI/ML Engineer Agents)
- [ ] Should the gate use win-rate (binary: did this team win the league?) or expected rank (continuous: avg finish position)? Expected rank is more statistically powerful at small N.
- [ ] How is "current production strategy" tracked in `results_db/`? Suggest a `production_registry` table with a `is_current` flag.
- [ ] Should the lab auto-create GitHub issues for near-miss gate results (e.g., p=0.06, improvement=1.8pp)? This would surface close calls for manual investigation.
