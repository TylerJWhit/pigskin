"""Multi-level budget constraint assertions (#241)."""

import unittest
from classes.team import Team
from classes.player import Player
from strategies.value_based_strategy import ValueBasedStrategy


class TestMultilevelBudgetConstraints(unittest.TestCase):

    def _make_team(self, budget=10, roster_filled=10):
        team = Team("t", "o", "Test Team", budget)
        for i in range(roster_filled):
            team.roster.append(Player(f"r{i}", f"R{i}", "WR", "XX"))
        return team

    def test_max_bid_leaves_budget_for_remaining_slots(self):
        team = self._make_team(budget=10, roster_filled=10)
        strategy = ValueBasedStrategy()
        max_bid = strategy.calculate_max_bid(team, team.budget)
        remaining_slots = 15 - len(team.roster) - 1  # slots after buying current
        self.assertLessEqual(max_bid, team.budget - remaining_slots)

    def test_enforce_budget_constraint_caps_bid(self):
        team = self._make_team(budget=10, roster_filled=10)
        strategy = ValueBasedStrategy()
        high_bid = 8.0  # would leave only $2 for 4 remaining slots
        constrained = strategy._enforce_budget_constraint(high_bid, team, team.budget)
        remaining = 15 - len(team.roster) - 1
        self.assertLessEqual(constrained, team.budget - remaining)

    def test_calculate_bid_with_constraints_within_budget(self):
        team = self._make_team(budget=10, roster_filled=10)
        strategy = ValueBasedStrategy()
        player = Player("pp", "Test Player", "QB", "TEST",
                        auction_value=15.0, projected_points=200.0)

        class _Owner:
            risk_tolerance = 0.7
            position_preferences = {}

        bid = strategy.calculate_bid_with_constraints(
            player, team, _Owner(), 1.0, team.budget, []
        )
        self.assertGreaterEqual(bid, 0)
        self.assertLessEqual(bid, team.budget)

    def test_budget_per_remaining_slot_stays_positive(self):
        team = self._make_team(budget=10, roster_filled=10)
        remaining_slots = 15 - len(team.roster)
        self.assertGreater(remaining_slots, 0)
        budget_per_slot = team.budget / remaining_slots
        self.assertGreaterEqual(budget_per_slot, 1.0)


if __name__ == "__main__":
    unittest.main()
