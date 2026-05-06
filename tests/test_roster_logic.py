"""Roster configuration and slot logic assertions (#241 - convert module-level script)."""

import unittest
from classes.team import Team
from classes.player import Player


ROSTER_CONFIG = {
    "QB": 1, "RB": 2, "WR": 2, "TE": 1,
    "FLEX": 2, "K": 1, "DST": 1, "BN": 5
}
TOTAL_SLOTS = sum(ROSTER_CONFIG.values())


class TestRosterLogic(unittest.TestCase):

    def _make_team(self):
        return Team("t", "o", "Test Team", roster_config=ROSTER_CONFIG)

    def _players(self):
        return [
            Player("1", "Josh Allen", "QB", "BUF"),
            Player("2", "Bijan Robinson", "RB", "ATL"),
            Player("3", "Saquon Barkley", "RB", "PHI"),
            Player("4", "Ja'Marr Chase", "WR", "CIN"),
            Player("5", "CeeDee Lamb", "WR", "DAL"),
            Player("6", "Brock Bowers", "TE", "LV"),
            Player("7", "Brandon Aubrey", "K", "DAL"),
            Player("8", "Buffalo Bills", "DST", "BUF"),
            Player("9", "De Von Achane", "RB", "MIA"),
            Player("10", "Amon Ra St Brown", "WR", "DET"),
            Player("11", "Travis Kelce", "TE", "KC"),
            Player("12", "Cooper Kupp", "WR", "LAR"),
            Player("13", "Joe Burrow", "QB", "CIN"),
            Player("14", "Kenneth Walker", "RB", "SEA"),
            Player("15", "Mike Evans", "WR", "TB"),
        ]

    def test_roster_config_is_set(self):
        team = self._make_team()
        self.assertEqual(team.roster_config, ROSTER_CONFIG)

    def test_total_roster_slots_matches_config(self):
        self.assertEqual(TOTAL_SLOTS, 15)

    def test_can_add_up_to_total_slots(self):
        team = self._make_team()
        players = self._players()
        added = 0
        for p in players:
            if team.add_player(p, 1):
                added += 1
        self.assertEqual(len(team.roster), added)
        self.assertLessEqual(len(team.roster), TOTAL_SLOTS)

    def test_roster_does_not_exceed_total_slots(self):
        team = self._make_team()
        for p in self._players():
            team.add_player(p, 1)
        self.assertLessEqual(len(team.roster), TOTAL_SLOTS)

    def test_budget_decreases_by_bid_amount(self):
        team = self._make_team()
        initial_budget = team.budget
        team.add_player(Player("p1", "Test QB", "QB", "XX"), 15)
        self.assertEqual(team.budget, initial_budget - 15)

    def test_get_remaining_roster_slots_decrements_on_add(self):
        team = self._make_team()
        before = team.get_remaining_roster_slots()
        team.add_player(Player("p1", "Test QB", "QB", "XX"), 5)
        after = team.get_remaining_roster_slots()
        self.assertEqual(after, before - 1)


if __name__ == "__main__":
    unittest.main()
