"""Budget enforcement assertions (#241 - replace print-only test)."""

import unittest
from classes.team import Team
from classes.player import Player
from strategies.value_based_strategy import ValueBasedStrategy


class TestAuctionBudgetEnforcement(unittest.TestCase):

    def _make_team(self, budget=200):
        roster_config = {"QB": 1, "RB": 2, "WR": 2, "TE": 1,
                         "FLEX": 2, "K": 1, "DST": 1, "BN": 5}
        return Team("t1", "o1", "Team 1", budget, roster_config)

    def test_budget_never_negative_after_purchases(self):
        team = self._make_team(200)
        strategy = ValueBasedStrategy()
        team.set_strategy(strategy)
        players_to_buy = [
            Player(f"p{i}", f"Player{i}", "RB", "KC", auction_value=20.0)
            for i in range(5)
        ]
        for player in players_to_buy:
            team.add_player(player, 20)
        self.assertGreaterEqual(team.budget, 0)

    def test_can_still_complete_roster_after_spending(self):
        """After buying some players, remaining budget must cover remaining slots."""
        roster_config = {"QB": 1, "RB": 2, "WR": 2, "TE": 1,
                         "FLEX": 2, "K": 1, "DST": 1, "BN": 5}
        team = Team("t1", "o1", "Team 1", 200, roster_config)
        total_slots = sum(roster_config.values())

        # Buy 5 expensive players
        for i in range(5):
            p = Player(f"p{i}", f"Player{i}", "RB", "KC")
            team.add_player(p, 30)

        remaining_slots = total_slots - len(team.roster)
        self.assertGreaterEqual(
            team.budget, remaining_slots,
            f"Budget ${team.budget} cannot cover {remaining_slots} remaining slots"
        )

    def test_strategy_max_bid_respects_remaining_slots(self):
        roster_config = {"QB": 1, "RB": 2, "WR": 2, "TE": 1,
                         "FLEX": 2, "K": 1, "DST": 1, "BN": 5}
        team = Team("t1", "o1", "Team 1", 10, roster_config)
        # Fill 10 of 15 slots (5 remain)
        for i in range(10):
            team.roster.append(Player(f"r{i}", f"R{i}", "WR", "XX"))

        strategy = ValueBasedStrategy()
        max_bid = strategy.calculate_max_bid(team, team.budget)
        remaining_slots = sum(roster_config.values()) - len(team.roster) - 1
        self.assertLessEqual(max_bid, team.budget - remaining_slots)


if __name__ == "__main__":
    unittest.main()
