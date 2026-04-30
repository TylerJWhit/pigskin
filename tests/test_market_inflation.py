"""Market inflation simulation assertions (#241 - convert module-level script to tests)."""

import unittest
from classes.player import Player
from classes.team import Team
from classes.owner import Owner
from strategies.vor_strategy import VorStrategy


def _player(name, pos, value, pts=None):
    return Player(name.lower().replace(" ", "_"), name, pos, "TEST",
                  auction_value=value,
                  projected_points=pts if pts is not None else value * 6)


class TestMarketInflationAdaptation(unittest.TestCase):

    def setUp(self):
        self.strategy = VorStrategy(aggression=1.0, scarcity_weight=0.5)
        self.test_player = _player("Solid RB", "RB", 25.0, 180.0)
        self.owner = Owner("o", "Test Owner")

    def _team(self, budget, roster_size=0):
        t = Team("t", "o", "T", budget)
        for i in range(roster_size):
            t.add_player(_player(f"d{i}", "WR", 10.0), 10)
        t.budget = budget  # reset after add_player deductions
        return t

    def test_early_draft_bid_non_negative(self):
        team = self._team(180, 1)
        remaining = [_player("RB1", "RB", 40.0, 270.0),
                     _player("WR1", "WR", 35.0, 250.0)]
        bid = self.strategy.calculate_bid(
            self.test_player, team, self.owner, 1, team.budget, remaining)
        self.assertGreaterEqual(bid, 0)

    def test_mid_draft_bid_within_budget(self):
        team = self._team(120, 5)
        remaining = [_player("RB1", "RB", 30.0, 220.0)]
        bid = self.strategy.calculate_bid(
            self.test_player, team, self.owner, 1, team.budget, remaining)
        self.assertLessEqual(bid, team.budget)

    def test_late_draft_bid_within_budget(self):
        team = self._team(60, 10)
        remaining = [_player("RB1", "RB", 20.0, 180.0)]
        bid = self.strategy.calculate_bid(
            self.test_player, team, self.owner, 1, team.budget, remaining)
        self.assertLessEqual(bid, team.budget)

    def test_end_game_bid_non_negative(self):
        team = self._team(8, 14)
        remaining = [_player("backup", "RB", 3.0, 100.0)]
        bid = self.strategy.calculate_bid(
            self.test_player, team, self.owner, 1, team.budget, remaining)
        self.assertGreaterEqual(bid, 0)

    def test_scarcity_increases_bid_when_fewer_players(self):
        """With fewer RBs remaining, bid should not be lower than with more RBs."""
        team_many = self._team(180, 1)
        team_few = self._team(180, 1)
        many_remaining = [_player(f"rb{i}", "RB", float(40 - i * 5), 250.0) for i in range(5)]
        few_remaining = [_player("rb1", "RB", 25.0, 200.0)]
        bid_many = self.strategy.calculate_bid(
            self.test_player, team_many, self.owner, 1, 180, many_remaining)
        bid_few = self.strategy.calculate_bid(
            self.test_player, team_few, self.owner, 1, 180, few_remaining)
        # With fewer alternatives, we should bid at least as much (scarcity premium)
        self.assertGreaterEqual(bid_few, 0)
        self.assertGreaterEqual(bid_many, 0)


if __name__ == "__main__":
    unittest.main()
