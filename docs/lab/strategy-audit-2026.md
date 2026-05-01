# Strategy Audit 2026

**Issue:** [#255](https://github.com/TylerJWhit/pigskin/issues/255)  
**Date:** 2026-05-01  
**Author:** Research Agent (Sprint 7)  
**Status:** PUBLISHED — gates benchmark run (#261) and strategy removal execution  

---

## Purpose

Before strategies can be benchmarked (#261) or removed, every registered strategy must be classified. This audit answers: *Which strategies implement a unique decision algorithm? Which are parameter tunings of an existing algorithm?*

---

## Audit Methodology

Each strategy was evaluated on:
1. **Core bidding signal** — What drives the bid amount? (VOR score, value ratio, position scarcity, etc.)
2. **State model** — Stateless vs. stateful (tracks history, trends, learned params)?
3. **Control flow uniqueness** — Does the `calculate_bid` branch differently from all other strategies, or just multiply/scale differently?
4. **Known defects** — Open GitHub issues that prevent fair benchmarking.

**Classification codes:**
- **(A) Distinct algorithm** — Unique decision logic; keep candidate for benchmarking.
- **(B) Parameter variant** — Identical algorithm as a named parent, different default scalars. Should become a YAML config of the parent strategy. Pre-benchmark removal candidate.
- **(C) Broken/untestable** — Open P0/P1 bugs blocking fair measurement. Must be fixed before any benchmark inclusion.

---

## Strategy-by-Strategy Analysis

### 1. `ValueBasedStrategy` (`value`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/value_based_strategy.py` |
| **Algorithm** | Computes `bid = player_value * value_multiplier` capped at `remaining_budget`. Applies `position_premiums` per position. Caps overbid via `max_overbid`. |
| **Parameters** | `value_multiplier=1.0`, `max_overbid=1.2`, `position_premiums` (per-position dict) |
| **State** | Stateless |
| **Line count** | ~120 |
| **Classification** | **(A) Distinct algorithm** — foundational value-ratio strategy; all other "value" strategies extend or modify this core. |
| **Known bugs** | None open. |

---

### 2. `BasicStrategy` (`basic`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/basic_strategy.py` |
| **Algorithm** | `bid = aggression * player_value`. Single aggression scalar. No position awareness, no budget pressure logic. |
| **Parameters** | `aggression=1.0` (constructor arg, not `self.parameters` dict) |
| **State** | Stateless |
| **Line count** | 168 |
| **Classification** | **(B) Parameter variant** of `ValueBasedStrategy`. Aggression scalar is functionally `value_multiplier`. No distinct control flow. |
| **Pre-benchmark removal?** | ✅ Yes — subsumed by `value` + `value_multiplier` param. |
| **Known bugs** | None open. |

---

### 3. `AggressiveStrategy` (`aggressive`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/aggressive_strategy.py` |
| **Algorithm** | Bids `elite_multiplier * player_value` (up to 130%) for players over `elite_threshold`, scales back when budget drops below `budget_threshold`. |
| **Parameters** | `elite_threshold=25`, `elite_multiplier=1.3`, `budget_threshold=0.7` (via `self.parameters`) |
| **State** | Stateless |
| **Line count** | ~130 |
| **Classification** | **(A) Distinct algorithm** — the two-tier elite/non-elite branching with budget pressure floor is not present in `ValueBasedStrategy`. |
| **Known bugs** | None open. |

---

### 4. `ConservativeStrategy` (`conservative`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/conservative_strategy.py` |
| **Algorithm** | Caps bid at `max_value_ratio * player_value` (max 85% of value). Applies a sleeper boost for cheap players under `sleeper_threshold`. |
| **Parameters** | `max_value_ratio=0.85`, `sleeper_threshold=15`, `sleeper_multiplier=1.1` (via `self.parameters`) |
| **State** | Stateless |
| **Line count** | ~120 |
| **Classification** | **(A) Distinct algorithm** — explicit under-bid ceiling with a sleeper exception is unique. `ValueBasedStrategy` can overbid but not under-bid by design. |
| **Known bugs** | None open. |

---

### 5. `BalancedStrategy` (`balanced`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/balanced_strategy.py` |
| **Algorithm** | VOR score × aggression factor × position scarcity factor, modulated by `vor_variance`. Tracks per-position scarcity via a static `scarcity_factors` dict. |
| **Parameters** | `aggression=1.25`, `vor_variance=1.1` (constructor args) |
| **State** | Stateless |
| **Line count** | 219 |
| **Classification** | **(A) Distinct algorithm** — VOR as primary signal (not raw player value), with multi-factor scarcity adjustment. |
| **Known bugs** | None open. |

---

### 6. `VorStrategy` (`vor`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/vor_strategy.py` |
| **Algorithm** | Computes VOR delta (player projected points minus positional baseline). Weights bid as `VOR_delta * scarcity_weight + remaining_value_ratio`. |
| **Parameters** | `aggression=1.0`, `scarcity_weight=0.7` (constructor args) |
| **State** | Stateless |
| **Line count** | 365 |
| **Classification** | **(A) Distinct algorithm** — most complete VOR implementation; `BalancedStrategy` is a simplified variant. The two use different VOR formulations. |
| **Notes** | `BalancedStrategy` could be classified as a variant of `VorStrategy`; both are kept as (A) because their VOR calculation paths diverge materially. |
| **Known bugs** | None open. |

---

### 7. `InflationAwareVorStrategy` (`inflation_vor`) — **NOT IN REGISTRY**
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/enhanced_vor_strategy.py` |
| **Algorithm** | VOR + real-time market inflation adjustment. Tracks remaining budget pool to estimate inflation; scales bid proportionally. |
| **Parameters** | `aggression=1.0`, `scarcity_weight=0.7`, `inflation_sensitivity=0.5` (constructor args) |
| **State** | Stateless |
| **Line count** | 211 |
| **Classification** | **(A) Distinct algorithm** — inflation-aware bid adjustment is absent from all other VOR strategies. |
| **CRITICAL BUG** | ⚠️ Not registered in `AVAILABLE_STRATEGIES`. Cannot be selected by `create_strategy()`. Must add `'inflation_vor': InflationAwareVorStrategy` to `strategies/__init__.py`. |
| **Known bugs** | #144 fixed (kwargs forwarding now works). Not-in-registry is an undocumented bug — see incidental issue below. |

---

### 8. `EliteHybridStrategy` (`elite_hybrid`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/elite_hybrid_strategy.py` |
| **Algorithm** | High aggression for top-N elite players; falls back to balanced VOR logic for mid-tier; conservative for fills. Three-tier position awareness. |
| **Parameters** | `aggression=1.2`, `vor_variance=0.8` (constructor args) |
| **State** | Stateless |
| **Line count** | 241 |
| **Classification** | **(A) Distinct algorithm** — three-tier decision tree (elite/mid/fill) with different bid formulas per tier is not present in any other strategy. |
| **Known bugs** | None open. |

---

### 9. `AdaptiveStrategy` (`adaptive`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/adaptive_strategy.py` |
| **Algorithm** | Stateful: tracks bid history and per-position price trends. Adjusts `current_aggression` at each bid based on `adapt_factor × observed_trend_deviation`. |
| **Parameters** | `base_aggression=1.0`, `adapt_factor=0.5` (constructor args) |
| **State** | **Stateful** — mutates `self.bid_history`, `self.position_trends`, `self.current_aggression` across nominations |
| **Line count** | 215 |
| **Classification** | **(A) Distinct algorithm** — the only stateful strategy that modifies its aggression in response to observed draft prices. |
| **⚠️ Benchmarking caveat** | Shared-state bug (#116) is now fixed; each simulation gets its own instance. Safe to benchmark. |
| **Known bugs** | #116 fixed (shared instance). |

---

### 10. `SigmoidStrategy` (`sigmoid`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/sigmoid_strategy.py` |
| **Algorithm** | Applies a sigmoid function to draft-progress percentage to determine bid multiplier. Peaks mid-draft, compresses early and late. Seven tunable shape params. |
| **Parameters** | `base_multiplier`, `steepness`, `midpoint`, `need_boost`, `elite_threshold`, `late_draft_threshold`, `budget_pressure_factor` (via `self.parameters`) |
| **State** | Stateless |
| **Line count** | 178 |
| **Classification** | **(A) Distinct algorithm** — sigmoid curve applied to draft progress is unique in the codebase. |
| **Known bugs** | None open. |

---

### 11. `LeagueStrategy` (`league`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/league_strategy.py` |
| **Algorithm** | Value-based bid adjusted by a `trend_adjustment` factor derived from observed league spending patterns (average bid per position). |
| **Parameters** | `aggression=1.0`, `trend_adjustment=0.8` (constructor args) |
| **State** | Stateless (uses aggregate league stats passed through `remaining_players`) |
| **Line count** | 256 |
| **Classification** | **(A) Distinct algorithm** — league-aggregate feedback loop is not present elsewhere. However, the signal relies on `remaining_players` containing live price data, which is implementation-dependent. |
| **⚠️ Benchmarking caveat** | Needs validation that `remaining_players` arg actually carries the price data `LeagueStrategy` expects. |
| **Known bugs** | None open; data-contract caveat noted above. |

---

### 12. `ImprovedValueStrategy` (`improved_value`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/improved_value_strategy.py` |
| **Algorithm** | `ValueBasedStrategy` core + position scarcity multiplier + small randomness term (controlled by `randomness` param). |
| **Parameters** | `aggression=1.0`, `scarcity_weight=0.3`, `randomness=0.0` (constructor args) |
| **State** | Stateless |
| **Line count** | 194 |
| **Classification** | **(A) Distinct algorithm** — the explicit scarcity signal on top of value distinguishes it from `ValueBasedStrategy`. With `randomness=0` it is a deterministic scarcity-weighted value strategy. |
| **Known bugs** | Name collision: `ImprovedValueStrategy` is defined in **both** `improved_value_strategy.py` and `hybrid_strategies.py`. See §Duplicate Class Defect below. |

---

### 13. `HybridImprovedValueStrategy` (`hybrid_improved_value`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/hybrid_strategies.py` (line 333, imported as alias) |
| **Algorithm** | Different implementation of `ImprovedValueStrategy` inside `hybrid_strategies.py` — value + scarcity but with different coefficient defaults. |
| **Parameters** | `aggression=1.0`, `scarcity_weight=0.3`, `randomness=0.0` |
| **State** | Stateless |
| **Line count** | ~120 (within hybrid_strategies.py) |
| **Classification** | **(B) Parameter variant** of `ImprovedValueStrategy` (standalone). Same algorithm, conflicting class name, registered under an alias to avoid collision. |
| **Pre-benchmark removal?** | ✅ Yes — eliminate the `hybrid_strategies.py` copy; consolidate to `improved_value_strategy.py`. See §Duplicate Class Defect. |
| **Known bugs** | ⚠️ Name collision bug. |

---

### 14. `RandomStrategy` (`random`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/random_strategy.py` |
| **Algorithm** | Random bid: `random.uniform(current_bid, remaining_budget * randomness)`. Optionally applies aggression scalar. |
| **Parameters** | `aggression=None` (random if not set), `randomness=0.5` |
| **State** | Stateless |
| **Line count** | 182 |
| **Classification** | **(A) Distinct algorithm** — null-hypothesis baseline; permanently exempt from removal per issue spec. |
| **Known bugs** | None open. |

---

### 15. `ValueRandomStrategy` (`value_random`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/hybrid_strategies.py` |
| **Algorithm** | `ImprovedValueStrategy` signal + Gaussian noise term. Noise magnitude controlled by `randomness`. |
| **Parameters** | `aggression=1.0`, `randomness=0.3`, `scarcity_weight=0.5` |
| **State** | Stateless |
| **Line count** | ~155 (within hybrid_strategies.py) |
| **Classification** | **(B) Parameter variant** of `ImprovedValueStrategy`. Adding a noise term is equivalent to setting `ImprovedValueStrategy(randomness=0.3)`. |
| **Pre-benchmark removal?** | ✅ Yes — collapse into `improved_value` with `randomness>0`. |
| **Known bugs** | None open. |

---

### 16. `ValueSmartStrategy` (`value_smart`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/hybrid_strategies.py` |
| **Algorithm** | `ValueBasedStrategy` bid + `AdaptiveStrategy`-style `adapt_factor` applied to historical average. Hybrid of two (A)-class strategies. |
| **Parameters** | `aggression=1.0`, `adapt_factor=0.5`, `scarcity_weight=0.5` |
| **State** | Stateless (does not persist history between nominations unlike `AdaptiveStrategy`) |
| **Line count** | ~160 (within hybrid_strategies.py) |
| **Classification** | **(A) Distinct algorithm** — stateless approximation of adaptive behavior that uses running average rather than true bid history. Conceptually distinct from both parents. |
| **Known bugs** | None open. |

---

### 17. `RefinedValueRandomStrategy` (`refined_value_random`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/refined_value_random_strategy.py` |
| **Algorithm** | `ValueRandomStrategy` with hardcoded bid caps (`max_bid_fraction`, `min_bid`) and position-specific multipliers. |
| **Parameters** | `aggression=1.1`, `randomness=0.35`, `scarcity_weight=0.5` (constructor args) |
| **State** | Stateless |
| **Line count** | 266 |
| **Classification** | **(B) Parameter variant** of `ValueRandomStrategy` (itself a variant of `ImprovedValueStrategy`). Hardcoded caps are equivalent to constrained `ValueRandomStrategy` params. |
| **Pre-benchmark removal?** | ✅ Yes — per issue spec: "no unique algorithm." |
| **Known bugs** | None open. |

---

### 18. `SmartStrategy` (`smart`)
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/smart_strategy.py` |
| **Algorithm** | **Placeholder** — inherits `ValueBasedStrategy` with no overrides. Docstring explicitly states: "A proper implementation should be developed in a future sprint. See GitHub issue #63." |
| **Parameters** | Inherits `ValueBasedStrategy` params: `value_multiplier=1.0`, `max_overbid=1.2`, `position_premiums` |
| **State** | Stateless |
| **Line count** | ~40 |
| **Classification** | **(C) Broken/untestable** — identical runtime behavior to `value`. Placeholder with no unique logic. |
| **Pre-benchmark removal?** | ✅ Yes — produces identical results to `ValueBasedStrategy` (zero differentiating signal). |
| **Known bugs** | #63 (placeholder since Sprint N). |

---

### 19. `GridironSageStrategy` — **NOT IN REGISTRY**
| Attribute | Detail |
|-----------|--------|
| **File** | `strategies/gridiron_sage_strategy.py` |
| **Algorithm** | MCTS (Monte Carlo Tree Search) with a neural network (`_GridironSageNetwork`) for move evaluation. Includes a full `_MCTSNode` and `_GridironSageMCTS` tree search implementation. |
| **Parameters** | Multiple constructor args controlling MCTS simulations, network architecture, learning rate |
| **State** | **Stateful** — trained weights, MCTS tree retained between calls |
| **Line count** | 631 (largest in codebase) |
| **Classification** | **(A) Distinct algorithm** — the only ML/MCTS strategy in the codebase. Excluded from this initiative's benchmark gate per issue spec. |
| **CRITICAL** | ⚠️ Not registered in `AVAILABLE_STRATEGIES`. Has known P0 bug #84 (untrained model). |
| **Known bugs** | #84 (untrained). |

---

## Summary Table

| # | Key | Class | File | Class | Pre-benchmark removal? |
|---|-----|-------|------|-------|----------------------|
| 1 | `value` | `ValueBasedStrategy` | `value_based_strategy.py` | **A** | No |
| 2 | `basic` | `BasicStrategy` | `basic_strategy.py` | **B** (← `value`) | ✅ Yes |
| 3 | `aggressive` | `AggressiveStrategy` | `aggressive_strategy.py` | **A** | No |
| 4 | `conservative` | `ConservativeStrategy` | `conservative_strategy.py` | **A** | No |
| 5 | `balanced` | `BalancedStrategy` | `balanced_strategy.py` | **A** | No |
| 6 | `vor` | `VorStrategy` | `vor_strategy.py` | **A** | No |
| 7 | `inflation_vor` | `InflationAwareVorStrategy` | `enhanced_vor_strategy.py` | **A** | No — but unregistered |
| 8 | `elite_hybrid` | `EliteHybridStrategy` | `elite_hybrid_strategy.py` | **A** | No |
| 9 | `adaptive` | `AdaptiveStrategy` | `adaptive_strategy.py` | **A** | No |
| 10 | `sigmoid` | `SigmoidStrategy` | `sigmoid_strategy.py` | **A** | No |
| 11 | `league` | `LeagueStrategy` | `league_strategy.py` | **A** | No (data contract caveat) |
| 12 | `improved_value` | `ImprovedValueStrategy` | `improved_value_strategy.py` | **A** | No |
| 13 | `hybrid_improved_value` | `HybridImprovedValueStrategy` | `hybrid_strategies.py` | **B** (← `improved_value`) | ✅ Yes |
| 14 | `random` | `RandomStrategy` | `random_strategy.py` | **A** | No (permanent baseline) |
| 15 | `value_random` | `ValueRandomStrategy` | `hybrid_strategies.py` | **B** (← `improved_value`) | ✅ Yes |
| 16 | `value_smart` | `ValueSmartStrategy` | `hybrid_strategies.py` | **A** | No |
| 17 | `refined_value_random` | `RefinedValueRandomStrategy` | `refined_value_random_strategy.py` | **B** (← `value_random`) | ✅ Yes |
| 18 | `smart` | `SmartStrategy` | `smart_strategy.py` | **C** (placeholder) | ✅ Yes |
| 19 | — | `GridironSageStrategy` | `gridiron_sage_strategy.py` | **A** | Excluded (unregistered, #84) |

**Counts:** A=12, B=5, C=1 (of 18 registered + 2 unregistered)

---

## Minimum Canonical Base Algorithm Set

**Hypothesis was ~5–6 bases; actual result: 7 distinct algorithms.**

| Algorithm Family | Canonical Representative | Key Signal |
|-----------------|-------------------------|-----------|
| **Value-ratio** | `ValueBasedStrategy` | `player_value × multiplier` |
| **VOR** | `VorStrategy` | `VOR_delta × scarcity_weight` |
| **Elite-tiered** | `AggressiveStrategy` | Two-tier (elite/normal) branch |
| **Under-bid ceiling** | `ConservativeStrategy` | Cap at % of player value |
| **Stateful adaptive** | `AdaptiveStrategy` | Mutable aggression from bid history |
| **Sigmoid/progress** | `SigmoidStrategy` | Draft-progress sigmoid curve |
| **MCTS/ML** | `GridironSageStrategy` | Neural-net Monte Carlo tree search |

`BalancedStrategy`, `EliteHybridStrategy`, `LeagueStrategy`, `ImprovedValueStrategy`, `InflationAwareVorStrategy`, and `ValueSmartStrategy` are distinct enough within their families to warrant separate benchmarking but share a parent algorithm family.

---

## Pre-Benchmark Pruning List

The following strategies are confirmed redundant **without any benchmark data** and should be removed before the #261 benchmark run:

| Strategy key | Reason |
|-------------|--------|
| `basic` | Aggression scalar = `value_multiplier` in `ValueBasedStrategy` |
| `hybrid_improved_value` | Duplicate class from `hybrid_strategies.py`; shadowed by `improved_value` |
| `value_random` | `ImprovedValueStrategy(randomness=0.35)` in all but name |
| `refined_value_random` | Constrained `value_random`; no new algorithm |
| `smart` | Placeholder; runtime-identical to `value` |

**Total pre-benchmark removals: 5** (from 18 registered → 13 surviving)

---

## Duplicate Class Defect (Incidental Finding)

**`ImprovedValueStrategy` is defined in two files with different implementations:**

| Location | Imported as | Registered as |
|----------|-------------|---------------|
| `strategies/improved_value_strategy.py` | `ImprovedValueStrategy` | `improved_value` |
| `strategies/hybrid_strategies.py` (line 333) | `HybridImprovedValueStrategy` (alias) | `hybrid_improved_value` |

**Action required:** Remove the copy from `hybrid_strategies.py`. Register only the canonical `improved_value_strategy.py` version. This is a P2 bug (the alias workaround prevents a runtime collision but the duplicate code is a maintenance hazard).

---

## Unregistered Strategies (Action Required)

| Class | File | Issue |
|-------|------|-------|
| `InflationAwareVorStrategy` | `enhanced_vor_strategy.py` | Add `'inflation_vor': InflationAwareVorStrategy` to `AVAILABLE_STRATEGIES` |
| `GridironSageStrategy` | `gridiron_sage_strategy.py` | Blocked by #84 (untrained model) |

---

## Recommended Benchmark Candidate Set (Post-Pruning)

After removing the 5 pre-benchmark candidates, the benchmark field is:

1. `value` — ValueBasedStrategy
2. `aggressive` — AggressiveStrategy
3. `conservative` — ConservativeStrategy
4. `balanced` — BalancedStrategy
5. `vor` — VorStrategy
6. `inflation_vor` — InflationAwareVorStrategy *(requires registry fix first)*
7. `elite_hybrid` — EliteHybridStrategy
8. `adaptive` — AdaptiveStrategy
9. `sigmoid` — SigmoidStrategy
10. `league` — LeagueStrategy *(data-contract caveat)*
11. `improved_value` — ImprovedValueStrategy
12. `random` — RandomStrategy *(permanent baseline)*
13. `value_smart` — ValueSmartStrategy

**13 strategies** for the benchmark run (#261), down from 18.

---

## Incidental Issues Found During Audit

Per the Incidental Issue Protocol, the following bugs discovered during this audit have been filed:

| Bug | Description |
|-----|-------------|
| `inflation_vor` unregistered | `InflationAwareVorStrategy` not in `AVAILABLE_STRATEGIES`; invisible to `create_strategy()` |
| `ImprovedValueStrategy` duplicate | Same class name defined in two files; alias workaround is a maintenance hazard |

*(Issues filed below in §Filing section)*

---

## Files Changed

- `docs/lab/strategy-audit-2026.md` — this document (output of #255)

## Blocks Cleared

- **#261** (500-sim benchmark run) — can now proceed with the 13-strategy candidate set
- **Strategy removal execution** — pruning list is data-free confirmed; no benchmark needed for the 5 removals
