"""Budget violation guard assertions (#241)."""

import unittest
from classes.team import Team
from classes.player import Player
from strategies.value_based_strategy import ValueBasedStrategy


class TestBudgetConstraintViolation(unittest.TestCase):

    def _make_team(self):
        roster_config = {"QB": 1, "RB": 2, "WR": 2, "TE": 1,
                         "FLEX": 2, "K": 1, "DST": 1, "BN": 5}
        return Team("t", "o", "Test Team", 200, roster_config)

    def test_strategy_blocks_purchase_when_budget_too_low(self):
        """calculate_max_bid must block purchases that would prevent roster completion."""
        team = self._make_team()
        strategy = ValueBasedStrategy()
        roster_config = team.roster_config
        total_slots = sum(roster_config.values())

        expensive_players = [
            ("Josh Allen", "QB", 45),
            ("CMC", "RB", 65),
            ("Cooper Kupp", "WR", 55),
            ("Davante Adams", "WR", 50),
            ("Travis Kelce", "TE", 40),
        ]
        for name, pos, price in expensive_players:
            max_bid = strategy.calculate_max_bid(team, team.budget)
            if price <= max_bid:
                team.add_player(Player(f"p_{name}", name, pos, "XX"), price)

        remaining_slots = total_slots - len(team.roster)
        self.assertGreaterEqual(
            team.budget, remaining_slots,
            f"Budget ${team.budget} cannot cover {remaining_slots} remaining slots after purchases"
        )

    def test_budget_never_negative_after_expensive_purchases(self):
        team = self._make_team()
        for i in range(5):
            team.add_player(Player(f"p{i}", f"P{i}", "RB", "X"), 30)
        self.assertGreaterEqual(team.budget, 0)

    def test_team_can_complete_roster_after_splurge(self):
        team = self._make_team()
        roster_config = team.roster_config
        total_slots = sum(roster_config.values())
        strategy = ValueBasedStrategy()

        # Buy until strategy says stop
        for i in range(12):
            max_bid = strategy.calculate_max_bid(team, team.budget)
            if max_bid <= 0:
                break
            p = Player(f"p{i}", f"P{i}", "WR", "X")
            bid = min(max_bid, 10)
            team.add_player(p, bid)

        remaining = total_slots - len(team.roster)
        self.assertGreaterEqual(team.budget, remaining)


if __name__ == "__main__":
    unittest.main()
