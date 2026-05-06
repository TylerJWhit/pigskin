"""Budget constraint assertions in auction scenarios (#241)."""

import unittest
from classes.team import Team
from classes.player import Player
from strategies.value_based_strategy import ValueBasedStrategy
from strategies.basic_strategy import BasicStrategy


class TestBudgetConstraintInAuction(unittest.TestCase):

    def _roster_config(self):
        return {"QB": 1, "RB": 2, "WR": 2, "TE": 1,
                "FLEX": 2, "K": 1, "DST": 1, "BN": 5}

    def test_budget_never_goes_below_zero(self):
        rc = self._roster_config()
        team = Team("t", "o", "T", 200, rc)
        for i in range(10):
            team.add_player(Player(f"p{i}", f"P{i}", "RB", "X"), 15)
        self.assertGreaterEqual(team.budget, 0)

    def test_budget_per_remaining_slot_maintained(self):
        rc = self._roster_config()
        total_slots = sum(rc.values())
        team = Team("t", "o", "T", 200, rc)
        for i in range(5):
            team.add_player(Player(f"p{i}", f"P{i}", "WR", "X"), 20)

        remaining_slots = total_slots - len(team.roster)
        self.assertGreaterEqual(
            team.budget, remaining_slots,
            "Team must retain at least $1 per remaining roster slot"
        )

    def test_calculate_max_bid_returns_non_negative(self):
        rc = self._roster_config()
        team = Team("t", "o", "T", 50, rc)
        strategy = ValueBasedStrategy()
        max_bid = strategy.calculate_max_bid(team, team.budget)
        self.assertGreaterEqual(max_bid, 0)

    def test_two_strategies_both_maintain_budget_invariant(self):
        rc = self._roster_config()
        for StratCls in (ValueBasedStrategy, BasicStrategy):
            team = Team("t", "o", "T", 200, rc)
            team.set_strategy(StratCls())
            for i in range(8):
                team.add_player(Player(f"p{i}", f"P{i}", "WR", "X"), 18)
            self.assertGreaterEqual(team.budget, 0, f"{StratCls.__name__} led to negative budget")


if __name__ == "__main__":
    unittest.main()
