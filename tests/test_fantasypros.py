"""Tests for FantasyPros data loading (#241 - replace vacuous print-only tests)."""

import os
import unittest
from data import FantasyProsLoader, load_fantasypros_players, get_position_rankings

_DATA_FILES_PRESENT = os.path.exists(os.path.join("data", "sheets", "QB.csv"))


class TestFantasyProsLoader(unittest.TestCase):

    def test_loader_instantiates(self):
        loader = FantasyProsLoader()
        self.assertIsNotNone(loader)

    def test_get_data_summary_returns_dict(self):
        loader = FantasyProsLoader()
        summary = loader.get_data_summary()
        self.assertIsInstance(summary, dict)

    @unittest.skipUnless(_DATA_FILES_PRESENT, "data/sheets CSV files not present")
    def test_load_position_data_returns_list_for_each_position(self):
        loader = FantasyProsLoader()
        for pos in ["QB", "RB", "WR", "TE", "K", "DST"]:
            players = loader.load_position_data(pos)
            self.assertIsInstance(players, list)

    def test_load_fantasypros_players_returns_list(self):
        players = load_fantasypros_players()
        self.assertIsInstance(players, list)

    @unittest.skipUnless(_DATA_FILES_PRESENT, "data/sheets CSV files not present")
    def test_get_position_rankings_returns_list(self):
        rankings = get_position_rankings("QB", top_n=5)
        self.assertIsInstance(rankings, list)

    def test_player_objects_have_required_attributes(self):
        players = load_fantasypros_players()
        for p in players[:10]:
            self.assertTrue(hasattr(p, "name"))
            self.assertTrue(hasattr(p, "position"))
            self.assertTrue(hasattr(p, "auction_value"))


if __name__ == "__main__":
    unittest.main()
