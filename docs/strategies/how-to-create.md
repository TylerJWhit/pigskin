# How to Create a New Strategy

This guide walks through adding a strategy from scratch so it works end-to-end: lab experiments, simulations, and the CLI.

---

## Prerequisites

- Python ≥ 3.10, project venv activated (`source venv/bin/activate`)
- Familiarity with `strategies/base_strategy.py` — read it before writing your own
- A clear idea of the bidding logic you want to implement

---

## Step 1 — Create `strategies/my_strategy.py`

All strategies inherit from `Strategy` (alias for `BaseStrategy`).

```python
# strategies/my_strategy.py
"""One-line summary of the strategy."""

from typing import List, TYPE_CHECKING
from .base_strategy import Strategy

if TYPE_CHECKING:
    from classes.player import Player
    from classes.team import Team
    from classes.owner import Owner


class MyStrategy(Strategy):
    """Short description used in catalog and CLI output."""

    def __init__(self, aggression: float = 1.0):
        """
        Args:
            aggression: Scales bid relative to base value (0.5 – 1.5).
        """
        super().__init__(
            "My Strategy",          # Human-readable name
            f"Description with aggression={aggression:.1f}"
        )
        self.aggression = aggression

    def calculate_bid(
        self,
        player: "Player",
        team: "Team",
        owner: "Owner",
        current_bid: float,
        remaining_budget: float,
        remaining_players: List["Player"],
    ) -> float:
        """Return the bid amount, or 0.0 to pass."""
        # Guard: always reserve $1 per unfilled roster slot
        slots_left = self._get_remaining_roster_slots(team)
        if remaining_budget <= slots_left + 3:
            return max(current_bid + 1, 1.0)

        position_priority = self._calculate_position_priority(player, team)
        if position_priority <= 0.1:
            return 0.0

        player_value = self._get_player_value(player, default=10.0)
        max_bid = self.calculate_max_bid(team, remaining_budget)

        bid = min(player_value * self.aggression * position_priority, max_bid)
        if bid <= current_bid:
            return 0.0

        return self._enforce_budget_constraint(bid, team, remaining_budget)
```

### Key helpers available from `BaseStrategy`

| Helper | What it does |
|--------|--------------|
| `self._get_player_value(player, default)` | Returns `auction_value` (falls back to `projected_points`) |
| `self._calculate_position_priority(player, team)` | 0.0 – 1.0 based on roster needs |
| `self._calculate_position_urgency(player, team)` | Urgency multiplier as roster fills |
| `self._get_remaining_roster_slots(team)` | Count of unfilled mandatory slots |
| `self.calculate_max_bid(team, remaining_budget)` | Safe max spend respecting roster completion |
| `self._enforce_budget_constraint(bid, team, budget)` | Clamps bid so team can still complete roster |
| `self._calculate_budget_reservation(team, budget)` | Minimum $$ to hold for remaining slots |

---

## Step 2 — Register in `strategies/__init__.py`

Open `strategies/__init__.py` and add in two places:

```python
# 1. Import at the top (keep alphabetical within the section)
from .my_strategy import MyStrategy

# 2. Add to AVAILABLE_STRATEGIES dict
AVAILABLE_STRATEGIES = {
    ...
    'my_strategy': MyStrategy,   # ← new entry
}

# 3. Add to __all__
__all__ = [
    ...
    'MyStrategy',
]
```

Verify it's visible:

```bash
python -c "from strategies import AVAILABLE_STRATEGIES; print('my_strategy' in AVAILABLE_STRATEGIES)"
# True
```

---

## Step 3 — Add unit tests in `tests/unit/strategies/`

Create `tests/unit/strategies/test_my_strategy.py`:

```python
"""Unit tests for MyStrategy."""

import pytest
from strategies.my_strategy import MyStrategy
from unittest.mock import MagicMock


def _make_player(auction_value: float = 20.0, position: str = "RB"):
    p = MagicMock()
    p.auction_value = auction_value
    p.position = position
    return p


def _make_team(needs=("RB",), roster_len=0, initial_budget=200.0):
    t = MagicMock()
    t.get_needs.return_value = list(needs)
    t.roster = [MagicMock()] * roster_len
    t.roster_requirements = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}
    t.initial_budget = initial_budget
    return t


class TestMyStrategy:
    def test_passes_when_budget_is_low(self):
        s = MyStrategy()
        player = _make_player(20.0)
        team = _make_team()
        bid = s.calculate_bid(player, team, MagicMock(), 0.0, 5.0, [])
        # With almost no budget left, strategy should not overbid
        assert bid <= 5.0

    def test_bids_above_current_for_needed_position(self):
        s = MyStrategy(aggression=1.0)
        player = _make_player(20.0, "RB")
        team = _make_team(needs=["RB"])
        bid = s.calculate_bid(player, team, MagicMock(), 5.0, 150.0, [])
        assert bid > 5.0

    def test_passes_for_unwanted_position(self):
        s = MyStrategy()
        player = _make_player(20.0, "QB")
        team = _make_team(needs=[])  # team needs nothing
        bid = s.calculate_bid(player, team, MagicMock(), 0.0, 150.0, [])
        assert bid == 0.0

    def test_never_exceeds_remaining_budget(self):
        s = MyStrategy(aggression=2.0)  # deliberately over-aggressive
        player = _make_player(100.0, "RB")
        team = _make_team(needs=["RB"])
        remaining = 50.0
        bid = s.calculate_bid(player, team, MagicMock(), 0.0, remaining, [])
        assert bid <= remaining
```

Run just your new tests:

```bash
pytest tests/unit/strategies/test_my_strategy.py -v
```

---

## Step 4 — Add property tests in `tests/property/`

Property tests catch edge cases your unit tests won't imagine.  
Add `tests/property/test_my_strategy_properties.py`:

```python
"""Property-based tests for MyStrategy (Hypothesis)."""

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from unittest.mock import MagicMock

from strategies.my_strategy import MyStrategy


def _make_team(needs, roster_len, initial_budget):
    t = MagicMock()
    t.get_needs.return_value = needs
    t.roster = [MagicMock()] * roster_len
    t.roster_requirements = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}
    t.initial_budget = max(initial_budget, 1.0)
    return t


@given(
    auction_value=st.floats(min_value=1.0, max_value=200.0, allow_nan=False),
    current_bid=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    remaining_budget=st.floats(min_value=1.0, max_value=400.0, allow_nan=False),
    aggression=st.floats(min_value=0.1, max_value=3.0, allow_nan=False),
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=200)
def test_bid_never_exceeds_remaining_budget(auction_value, current_bid, remaining_budget, aggression):
    """Invariant: bid must never exceed remaining_budget."""
    s = MyStrategy(aggression=aggression)
    player = MagicMock()
    player.auction_value = auction_value
    player.position = "RB"
    team = _make_team(["RB"], roster_len=0, initial_budget=200.0)

    bid = s.calculate_bid(player, team, MagicMock(), current_bid, remaining_budget, [])
    assert bid <= remaining_budget, f"bid {bid} > budget {remaining_budget}"


@given(
    auction_value=st.floats(min_value=1.0, max_value=200.0, allow_nan=False),
    remaining_budget=st.floats(min_value=1.0, max_value=400.0, allow_nan=False),
)
@settings(max_examples=100)
def test_bid_is_non_negative(auction_value, remaining_budget):
    """Invariant: bid must be ≥ 0."""
    s = MyStrategy()
    player = MagicMock()
    player.auction_value = auction_value
    player.position = "WR"
    team = _make_team(["WR"], roster_len=1, initial_budget=200.0)

    bid = s.calculate_bid(player, team, MagicMock(), 0.0, remaining_budget, [])
    assert bid >= 0.0
```

Run property tests:

```bash
pytest tests/property/test_my_strategy_properties.py -v
```

---

## Step 5 — Test in the lab

Create an experiment config at `lab/experiments/my_experiment.yaml`:

```yaml
name: my_strategy_baseline
description: First run of MyStrategy against existing strategies

strategies:
  - my_strategy
  - balanced
  - vor
  - aggressive

num_simulations: 500
num_teams: 10
budget: 200

metrics:
  - win_rate
  - avg_score
  - budget_efficiency
```

Run it:

```bash
python -m lab.simulation.runner --experiment lab/experiments/my_experiment.yaml
```

Results land in `lab/results_db/`. Compare with:

```bash
python -m lab.eval.compare_strategies --experiment my_strategy_baseline
```

---

## Step 6 — Update the strategy catalog

Add your strategy to [docs/strategies/catalog.md](catalog.md) following the existing table format.  
Include: key, class name, description, key parameters with defaults, and best-use guidance.

---

## Checklist

- [ ] `strategies/my_strategy.py` created, inherits `Strategy`
- [ ] `calculate_bid()` always returns `0.0 ≤ bid ≤ remaining_budget`
- [ ] Registered in `AVAILABLE_STRATEGIES` and `__all__`
- [ ] `create_strategy("my_strategy")` works without errors
- [ ] Unit tests in `tests/unit/strategies/test_my_strategy.py` — all pass
- [ ] Property tests in `tests/property/test_my_strategy_properties.py` — all pass
- [ ] Lab experiment YAML created and at least one simulation run completed
- [ ] `docs/strategies/catalog.md` updated

---

## Common Pitfalls

| Problem | Fix |
|---------|-----|
| `bid > remaining_budget` | Always call `_enforce_budget_constraint()` before returning |
| `ZeroDivisionError` on `initial_budget` | Guard: `initial_budget = getattr(team, 'initial_budget', None) or remaining_budget or 1` |
| Strategy never bids | Check `_calculate_position_priority()` — returns 0.0 when position slot is full |
| Strategy overbids on K/DST | These positions need special handling; see `AggressiveStrategy.calculate_bid()` for the pattern |
| Import error in `__init__.py` | Ensure class name in import matches exactly what's defined in the module |
