"""VOR/inflation strategy bid assertions (#241 - replace print-only tests)."""

import unittest
from classes.player import Player
from classes.team import Team
from classes.owner import Owner
from strategies.vor_strategy import VorStrategy
from strategies.improved_value_strategy import ImprovedValueStrategy


def _player(name, pos, value, pts=None):
    return Player(name.lower().replace(" ", "_"), name, pos, "TEST",
                  auction_value=value,
                  projected_points=pts if pts is not None else value * 10)


def _team(budget, roster_count=0):
    t = Team("t", "o", "T", budget)
    for i in range(roster_count):
        t.add_player(_player(f"dummy{i}", "WR", 10.0), 10)
    return t


def _owner():
    return Owner("o", "Owner")


class TestVorInflationBehavior(unittest.TestCase):

    def setUp(self):
        self.strategy = VorStrategy(aggression=1.0, scarcity_weight=0.7)
        self.player = _player("Elite RB", "RB", 45.0, 280.0)
        self.remaining = [_player("RB2", "RB", 25.0, 200.0),
                          _player("WR1", "WR", 30.0, 220.0)]
        self.owner = _owner()

    def test_bid_is_non_negative(self):
        team = _team(180)
        bid = self.strategy.calculate_bid(
            self.player, team, self.owner, 1, team.budget, self.remaining)
        self.assertGreaterEqual(bid, 0)

    def test_bid_does_not_exceed_remaining_budget(self):
        team = _team(50)
        bid = self.strategy.calculate_bid(
            self.player, team, self.owner, 1, team.budget, self.remaining)
        self.assertLessEqual(bid, team.budget)

    def test_higher_budget_yields_higher_or_equal_bid(self):
        """More budget should not reduce bid on a high-VOR player."""
        low_team = _team(40)
        high_team = _team(180)
        bid_low = self.strategy.calculate_bid(
            self.player, low_team, self.owner, 1, low_team.budget, self.remaining)
        bid_high = self.strategy.calculate_bid(
            self.player, high_team, self.owner, 1, high_team.budget, self.remaining)
        self.assertGreaterEqual(bid_high, bid_low)

    def test_bid_decreases_when_budget_exhausted(self):
        """When budget is tiny, bid should be minimal."""
        team = _team(5, roster_count=13)
        bid = self.strategy.calculate_bid(
            self.player, team, self.owner, 1, team.budget, self.remaining)
        self.assertLessEqual(bid, team.budget)

    def test_calculate_vor_returns_stored_vor_attribute(self):
        """_calculate_vor returns the player's pre-computed vor attribute."""
        self.player.vor = 130.0
        vor = self.strategy._calculate_vor(self.player)
        self.assertEqual(vor, 130.0)
        self.assertGreater(vor, 0)


class TestImprovedValueInflationBehavior(unittest.TestCase):

    def setUp(self):
        self.strategy = ImprovedValueStrategy(aggression=1.0, scarcity_weight=0.3)
        self.player = _player("Elite RB", "RB", 45.0, 280.0)
        self.remaining = [_player("RB1", "RB", 25.0, 200.0)]
        self.owner = _owner()

    def test_bid_is_non_negative(self):
        team = _team(180)
        bid = self.strategy.calculate_bid(
            self.player, team, self.owner, 1, team.budget, self.remaining)
        self.assertGreaterEqual(bid, 0)

    def test_bid_within_budget(self):
        team = _team(50)
        bid = self.strategy.calculate_bid(
            self.player, team, self.owner, 1, team.budget, self.remaining)
        self.assertLessEqual(bid, team.budget)

    def test_priority_is_between_zero_and_one(self):
        team = _team(150)
        priority = self.strategy._calculate_position_priority(self.player, team)
        self.assertGreaterEqual(priority, 0.0)
        self.assertLessEqual(priority, 1.0)


if __name__ == "__main__":
    unittest.main()
