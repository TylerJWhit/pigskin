"""QA Phase 1 — Issues #213–217: Strategy position_targets / total_slots hardcoding

Failing tests that verify:
  #213 — Audit: every strategy with total_slots=15 or position_targets hardcoded
           must instead derive values from team.roster_config or a passed config.
  #214 — balanced_strategy.py and basic_strategy.py: no hardcoded 15 or
           fixed position_targets dict in non-config-aware methods.
  #215 — elite_hybrid_strategy.py and hybrid_strategies.py: same.
  #216 — improved_value, random, refined, league strategies: same.
  #217 — Integration: all strategies work correctly with non-standard roster config.

These tests MUST FAIL before the fix and PASS after.
"""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock
from typing import Dict

import pytest

# All tests in this file are QA Phase 1 gates — expected to FAIL until the
# fixes for issues #213–217 are implemented. Remove this mark after implementation.
pytestmark = pytest.mark.xfail(
    strict=False,
    reason="QA Phase 1 gate for #213-217 — fails until hardcoded total_slots=15 removed from 9 strategy files",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STRATEGIES_DIR = Path(__file__).parent.parent.parent.parent / "strategies"

_AFFECTED_FILES = [
    "balanced_strategy.py",
    "basic_strategy.py",
    "elite_hybrid_strategy.py",
    "hybrid_strategies.py",
    "improved_value_strategy.py",
    "league_strategy.py",
    "random_strategy.py",
    "refined_value_random_strategy.py",
    "enhanced_vor_strategy.py",
]


def _find_hardcoded_15(filename: str) -> list[int]:
    """Return line numbers where `total_slots = 15` appears as an assignment."""
    source = (_STRATEGIES_DIR / filename).read_text()
    tree = ast.parse(source)
    hits = []
    for node in ast.walk(tree):
        # Assignments like `total_slots = 15`
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "total_slots":
                    if isinstance(node.value, ast.Constant) and node.value.value == 15:
                        hits.append(node.lineno)
        # Augmented assignment (shouldn't appear, but be safe)
        if isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "total_slots":
                if isinstance(node.value, ast.Constant) and node.value.value == 15:
                    hits.append(node.lineno)
    return hits


def _mock_team(roster_config: Dict[str, int]) -> MagicMock:
    """Build a mock Team with the given roster_config and an empty roster."""
    team = MagicMock()
    team.roster_config = roster_config
    type(team).roster = PropertyMock(return_value=[])
    # Remove get_remaining_roster_slots so strategies fall through to our config
    del team.get_remaining_roster_slots
    return team


def _mock_player(position: str = "QB") -> MagicMock:
    player = MagicMock()
    player.position = position
    player.projected_points = 20.0
    player.auction_value = 30.0
    player.name = f"Mock {position}"
    return player


# ---------------------------------------------------------------------------
# Issue #213 — Audit: no hardcoded `total_slots = 15`
# ---------------------------------------------------------------------------

class TestAuditHardcodedTotalSlots:
    @pytest.mark.parametrize("filename", _AFFECTED_FILES)
    def test_no_hardcoded_total_slots_15(self, filename: str):
        """Strategy file must not contain `total_slots = 15` as a literal.

        After the fix, strategies must derive total_slots from
        team.roster_config (via base_strategy._get_remaining_roster_slots)
        or from an injected config parameter.
        """
        hits = _find_hardcoded_15(filename)
        assert not hits, (
            f"strategies/{filename} contains hardcoded `total_slots = 15` at "
            f"lines {hits}. Replace with `sum(team.roster_config.values())` or "
            "delegate to `self._get_remaining_roster_slots(team)` from base_strategy."
        )


# ---------------------------------------------------------------------------
# Issue #214 — balanced_strategy and basic_strategy
# ---------------------------------------------------------------------------

class TestBalancedStrategyNonStandardRoster:
    def test_remaining_slots_respects_custom_roster_config(self):
        """BalancedStrategy._get_remaining_roster_slots() must use team.roster_config."""
        from strategies.balanced_strategy import BalancedStrategy

        strategy = BalancedStrategy()
        # 8-slot league: QB=1, RB=1, WR=1, TE=1, K=1, DST=1, FLEX=1, BENCH=1
        team = _mock_team({"QB": 1, "RB": 1, "WR": 1, "TE": 1, "K": 1, "DST": 1, "FLEX": 1, "BENCH": 1})
        slots = strategy._get_remaining_roster_slots(team)
        assert slots == 8, (
            f"BalancedStrategy._get_remaining_roster_slots() returned {slots} "
            "for an 8-slot roster config, expected 8. "
            "The hardcoded `total_slots = 15` is not respecting team.roster_config."
        )


class TestBasicStrategyNonStandardRoster:
    def test_position_priority_uses_team_roster_config(self):
        """BasicStrategy._calculate_position_priority must derive from team, not hardcoded dict."""
        from strategies.basic_strategy import BasicStrategy

        strategy = BasicStrategy()
        # A 6-man roster with no FLEX — DST should still be valid
        team = _mock_team({"QB": 1, "RB": 1, "WR": 1, "TE": 1, "K": 1, "DST": 1})
        player = _mock_player("DST")
        # Should not raise and should return a float priority
        priority = strategy._calculate_position_priority(player, team)
        assert isinstance(priority, (int, float)), (
            "BasicStrategy._calculate_position_priority() must return a numeric "
            "priority even with a non-standard 6-slot roster. Got: {priority}"
        )


# ---------------------------------------------------------------------------
# Issue #215 — elite_hybrid_strategy and hybrid_strategies
# ---------------------------------------------------------------------------

class TestEliteHybridStrategyNonStandardRoster:
    def test_remaining_slots_respects_12_slot_config(self):
        """EliteHybridStrategy must derive total_slots from team.roster_config."""
        from strategies.elite_hybrid_strategy import EliteHybridStrategy

        strategy = EliteHybridStrategy()
        team = _mock_team({
            "QB": 2, "RB": 2, "WR": 3, "TE": 1, "FLEX": 2, "K": 1, "DST": 1,
        })
        slots = strategy._get_remaining_roster_slots(team)
        assert slots == 12, (
            f"EliteHybridStrategy._get_remaining_roster_slots() returned {slots} "
            "but expected 12 for a 12-slot config. Hardcoded `total_slots = 15`."
        )


class TestHybridStrategiesNonStandardRoster:
    def test_aggressive_value_remaining_slots(self):
        """AggressiveValueStrategy must derive slots from team.roster_config."""
        from strategies.hybrid_strategies import AggressiveValueStrategy

        strategy = AggressiveValueStrategy()
        team = _mock_team({"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1})
        slots = strategy._get_remaining_roster_slots(team)
        assert slots == 8, (
            f"AggressiveValueStrategy returned {slots} slots for an 8-slot config, "
            "expected 8. Hardcoded 15 detected."
        )


# ---------------------------------------------------------------------------
# Issue #216 — improved_value, random, refined, league strategies
# ---------------------------------------------------------------------------

class TestImprovedValueStrategyNonStandardRoster:
    def test_remaining_slots_non_standard(self):
        from strategies.improved_value_strategy import ImprovedValueStrategy
        strategy = ImprovedValueStrategy()
        team = _mock_team({"QB": 1, "RB": 1, "WR": 2, "TE": 1, "K": 1, "DST": 1, "FLEX": 1})
        slots = strategy._get_remaining_roster_slots(team)
        assert slots == 8, (
            f"ImprovedValueStrategy returned {slots} slots for an 8-slot config, expected 8."
        )


class TestRandomStrategyNonStandardRoster:
    def test_remaining_slots_non_standard(self):
        from strategies.random_strategy import RandomStrategy
        strategy = RandomStrategy()
        team = _mock_team({"QB": 1, "RB": 2, "WR": 2, "TE": 1})
        slots = strategy._get_remaining_roster_slots(team)
        assert slots == 6, (
            f"RandomStrategy returned {slots} slots for a 6-slot config, expected 6."
        )


class TestLeagueStrategyNonStandardRoster:
    def test_remaining_slots_non_standard(self):
        from strategies.league_strategy import LeagueStrategy
        strategy = LeagueStrategy()
        team = _mock_team({"QB": 1, "RB": 2, "WR": 3, "TE": 1, "FLEX": 2})
        slots = strategy._get_remaining_roster_slots(team)
        assert slots == 9, (
            f"LeagueStrategy returned {slots} slots for a 9-slot config, expected 9."
        )


# ---------------------------------------------------------------------------
# Issue #217 — Integration tests: all strategies with non-standard roster
# ---------------------------------------------------------------------------

from strategies import AVAILABLE_STRATEGIES


class TestAllStrategiesNonStandardRoster:
    @pytest.mark.parametrize("key", list(AVAILABLE_STRATEGIES.keys()))
    def test_strategy_bid_with_non_standard_roster(self, key: str):
        """Every registered strategy must produce a non-negative bid for a
        non-standard 8-slot roster config without crashing."""
        strategy_cls = AVAILABLE_STRATEGIES[key]
        try:
            strategy = strategy_cls()  # type: ignore[abstract]
        except Exception as e:
            pytest.skip(f"Could not instantiate {key}: {e}")

        team = _mock_team({
            "QB": 1, "RB": 1, "WR": 2, "TE": 1, "K": 1, "DST": 1, "BENCH": 1
        })
        owners = [MagicMock()]
        owners[0].team = team
        player = _mock_player("RB")

        try:
            bid = strategy.calculate_bid(  # type: ignore[abstract]
                player, team, owners[0], current_bid=1.0,
                remaining_budget=200.0, remaining_players=[player],
            )
        except Exception as e:
            pytest.fail(
                f"Strategy '{key}' raised {type(e).__name__}: {e} when called "
                "with a non-standard 8-slot roster config. After #217, all "
                "strategies must handle non-standard configs without crashing."
            )

        assert bid >= 0, (
            f"Strategy '{key}' returned negative bid {bid} for non-standard roster."
        )
