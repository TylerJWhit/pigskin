# Strategy Catalog

All strategies registered in `AVAILABLE_STRATEGIES` (see `strategies/__init__.py`).  
To instantiate any strategy: `from strategies import create_strategy; s = create_strategy("key")`.

---

| Key | Class | Description | Key Parameters (defaults) | Best For |
|-----|-------|-------------|---------------------------|----------|
| `value` | `ValueBasedStrategy` | Bids based on player auction value with position premiums and budget reservation logic | `value_multiplier=1.4`, `max_overbid=1.3`, `position_premiums` (RB: 1.3, WR: 1.2) | General-purpose; balanced 10–12 team leagues |
| `aggressive` | `AggressiveStrategy` | Goes all-in on elite players early; throttles back when budget falls below threshold | `elite_threshold=25`, `elite_multiplier=1.3`, `budget_threshold=0.7` | Deep leagues; managers willing to punt thin positions for 2–3 studs |
| `conservative` | `ConservativeStrategy` | Caps bids at 85% of value; mildly overbids on sleepers under $15; never spends >20% of budget on one player | `max_value_ratio=0.85`, `sleeper_threshold=15`, `sleeper_multiplier=1.1` | Risk-averse managers; high-variance leagues where overpaying is punished |
| `sigmoid` | `SigmoidStrategy` | Uses sigmoid curves to blend aggression with draft progress, budget pressure, and positional need | `base_multiplier=1.05`, `steepness=8.0`, `midpoint=0.5`, `need_boost=1.35`, `budget_pressure_factor=2.2` | Experienced managers who want math-driven, context-sensitive bidding |
| `improved_value` | `ImprovedValueStrategy` | Value-based bidding with a configurable scarcity adjustment per position | `aggression=1.0`, `scarcity_weight=0.3`, `randomness=0.0` | Leagues where positional scarcity (RB, TE) drives inflation |
| `adaptive` | `AdaptiveStrategy` | Tracks bid history and per-position market trends to adjust aggression in real time | `base_aggression=1.0`, `adapt_factor=0.5` | Variable markets; experienced managers who want the bot to "learn" the room |
| `vor` | `VorStrategy` | Bids using Value Over Replacement relative to positional baselines, weighted by scarcity | `aggression=1.0`, `scarcity_weight=0.7` | Analytics-driven leagues; managers targeting the best positional upside |
| `random` | `RandomStrategy` | Bids with randomized aggression and configurable noise; primarily for simulation variety | `aggression=random(0.5–1.5)`, `randomness=0.5` | Stress testing, simulation baseline, unpredictable opponent modeling |
| `smart` | `SmartStrategy` | Placeholder — delegates to `ValueBasedStrategy`; reserved for future sprint work (#63) | (inherits `value` params) | Testing harness; do not use in production tournaments |
| `balanced` | `BalancedStrategy` | VOR-variance-adjusted bidding with position scarcity; slightly more aggressive defaults | `aggression=1.25`, `vor_variance=1.1` | All-around leagues; recommended starting point for new users |
| `basic` | `BasicStrategy` | Straightforward bid = `player_value × aggression × position_priority × urgency` | `aggression=1.0` | Baseline benchmarking; learning how the bid pipeline works |
| `elite_hybrid` | `EliteHybridStrategy` | Pays up sharply for players above per-position elite thresholds; conserves on the rest | `aggression=1.2`, `vor_variance=0.8`, `elite_thresholds` (RB: 35, WR: 30, QB: 25) | Leagues where elite RB/WR scarcity is extreme and studs win championships |
| `inflation_aware_vor` | `InflationAwareVorStrategy` | VOR strategy that measures league-wide budget consumption to compute a real-time inflation factor | `aggression=1.0`, `scarcity_weight=0.7`, `inflation_sensitivity=0.5`, `budget=200`, `roster_size=15` | Large (14+) leagues; inflationary markets where $1 bids drain the pool |
| `value_random` | `ValueRandomStrategy` | Value-based core with a configurable random perturbation on each bid | `aggression=1.0`, `randomness=0.3`, `scarcity_weight=0.5` | Simulation variety; modeling human unpredictability in tournament fields |
| `value_smart` | `ValueSmartStrategy` | Hybrid of value-based bidding and adaptive trend tracking | `aggression=1.0`, `adapt_factor=0.5`, `scarcity_weight=0.5` | Mid-skill managers who want value discipline with situational flexibility |
| `league` | `LeagueStrategy` | Applies per-position trend factors (e.g., league overvalues top RBs, undervalues K/DST) to adjust bids | `aggression=1.0`, `trend_adjustment=0.8` | Experienced managers who know their specific league's bidding tendencies |
| `refined_value_random` | `RefinedValueRandomStrategy` | Enhanced value-random hybrid with higher RB/TE scarcity weights and explicit position targets | `aggression=1.1`, `randomness=0.35`, `scarcity_weight=0.5` | Semi-random simulation runs; tournament fields that need realistic variance |

---

## Strategy Family Overview

```
BaseStrategy (strategies/base_strategy.py)
├── Simple / Baseline
│   ├── basic            — configurable aggression only
│   ├── random           — randomized bids for simulation
│   └── smart            — placeholder (ValueBased delegate)
├── Value-Based
│   ├── value            — position-premium value bidding
│   ├── conservative     — capped value, sleeper-friendly
│   ├── improved_value   — value + scarcity adjustment
│   └── value_random     — value + random noise
├── VOR-Based
│   ├── vor              — Value Over Replacement
│   └── inflation_aware_vor  — VOR + market inflation factor
├── Hybrid
│   ├── balanced         — VOR variance + scarcity
│   ├── elite_hybrid     — elite-threshold spikes + VOR
│   ├── value_smart      — value + adaptive trending
│   └── refined_value_random — value + scarcity + random
├── Adaptive / Trend
│   ├── adaptive         — real-time aggression adjustment
│   ├── sigmoid          — sigmoid-curve context model
│   └── league           — per-position league-trend factors
└── Aggressive
    └── aggressive       — elite-first, throttled budget
```

---

## Parameter Quick Reference

| Parameter | Type | Typical Range | Meaning |
|-----------|------|---------------|---------|
| `aggression` | float | 0.5 – 1.5 | Scales final bid up/down from base value |
| `scarcity_weight` | float | 0.0 – 1.0 | How much positional scarcity inflates bids |
| `randomness` | float | 0.0 – 1.0 | Probability / magnitude of random bid noise |
| `adapt_factor` | float | 0.0 – 1.0 | Speed at which aggression adapts to observed trends |
| `vor_variance` | float | 0.1 – 1.5 | Multiplier on VOR-derived bid variance |
| `inflation_sensitivity` | float | 0.0 – 1.0 | Responsiveness to league-wide budget inflation |
| `elite_threshold` | int/dict | per position | Auction value above which a player is "elite" |
| `trend_adjustment` | float | 0.5 – 1.0 | Weight of per-position league-trend factors |
