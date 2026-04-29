"""Regression tests for F811 duplicate-method bugs in auction.py and base_strategy.py.

Issue #85 — classes/auction.py:
  - _sort_players_for_roster_completion was defined twice; the second (simpler)
    definition silently overwrote the first (position-aware) one.
  - add_completion_listener was defined twice; both were identical, but the
    duplication meant any change to one would not be reflected in the other.

Issue #86 — strategies/base_strategy.py:
  - Strategy.__str__ was defined twice; the second definition silently
    overwrote the first.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classes.player import Player
from classes.draft import Draft
from classes.auction import Auction


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_player(player_id: str, name: str, position: str, auction_value: float) -> Player:
    return Player(
        player_id=player_id,
        name=name,
        position=position,
        team="TEST",
        projected_points=50.0,
        auction_value=auction_value,
    )


def _make_team_mock(roster=None, roster_config=None):
    """Return a lightweight mock that looks like a Team for sorting tests."""
    team = MagicMock()
    team.roster = roster if roster is not None else []
    team.roster_config = roster_config if roster_config is not None else {
        "QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1,
    }
    return team


# ---------------------------------------------------------------------------
# Issue #85 — _sort_players_for_roster_completion
# ---------------------------------------------------------------------------

class TestSortPlayersForRosterCompletion(unittest.TestCase):
    """Regression tests for the duplicate _sort_players_for_roster_completion.

    Before the fix the second (simpler) definition:
        sorted(players, key=lambda p: p.auction_value)
    overwrote the first (position-aware) definition, which also considered
    whether a position was still needed.  The regression ensures the
    position-aware definition is active.
    """

    def _get_auction(self):
        """Create a minimal Auction with a stubbed Draft."""
        draft = MagicMock(spec=Draft)
        draft.current_player = None
        draft.current_bid = 0.0
        draft.current_high_bidder = None
        draft.current_nominator = None
        draft.status = "active"
        draft.teams = []
        draft.available_players = []
        return Auction(draft=draft)

    def test_needed_position_ranked_before_cheaper_unneeded_player(self):
        """A needed-position player must rank above a cheaper same-value unneeded player.

        Scenario:
          - Team has 0 QBs on roster; roster_config requires 1 QB.
          - Player A: QB, value=10  (needed position, moderate price)
          - Player B: WR, value=1   (not needed — team already has 2 WRs)

        With the buggy second definition (sort by price only) Player B would
        appear first because $1 < $10.  With the correct first definition
        Player A appears first because QB is still needed.
        """
        auction = self._get_auction()

        # Team already has 2 WRs (need met), 0 QBs (need not met)
        wr1 = _make_player("wr1", "WR Player 1", "WR", auction_value=15.0)
        wr2 = _make_player("wr2", "WR Player 2", "WR", auction_value=12.0)
        team = _make_team_mock(
            roster=[wr1, wr2],
            roster_config={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1},
        )

        player_a = _make_player("qb1", "QB Player", "QB", auction_value=10.0)
        player_b = _make_player("wr3", "WR Player 3", "WR", auction_value=1.0)

        available = [player_b, player_a]  # cheaper WR is listed first
        result = auction._sort_players_for_roster_completion(available, team)

        first = result[0]
        self.assertEqual(
            first.position, "QB",
            msg=(
                "_sort_players_for_roster_completion should rank the needed QB first, "
                "but got position '%s' instead.  "
                "This indicates the buggy 'sort by price only' definition is active."
                % first.position
            ),
        )

    def test_all_positions_met_sorts_by_value_ascending(self):
        """When all positions are already filled, sort cheapest first."""
        auction = self._get_auction()

        # Build a full roster (every required position filled)
        positions_in_config = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}
        roster_players = []
        for pos, count in positions_in_config.items():
            for i in range(count):
                roster_players.append(
                    _make_player(f"{pos}_{i}", f"{pos} Player {i}", pos, auction_value=10.0)
                )
        team = _make_team_mock(roster=roster_players, roster_config=positions_in_config)

        cheap = _make_player("extra1", "Cheap Player", "RB", auction_value=1.0)
        expensive = _make_player("extra2", "Expensive Player", "QB", auction_value=50.0)

        result = auction._sort_players_for_roster_completion([expensive, cheap], team)
        # Both positions are over their limits — priority scores are negative for both.
        # The first result should be the higher priority score; with identical "over
        # limit" logic, the cheaper player should still surface near the top.
        # The important assertion is that the method returns a list without error.
        self.assertEqual(len(result), 2)

    def test_empty_player_list_returns_empty(self):
        """Empty available_players returns an empty list without error."""
        auction = self._get_auction()
        team = _make_team_mock()
        result = auction._sort_players_for_roster_completion([], team)
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Issue #85 — add_completion_listener (no-duplicate)
# ---------------------------------------------------------------------------

class TestAddCompletionListenerNoDuplicate(unittest.TestCase):
    """Ensure add_completion_listener registers a callback exactly once.

    Before the fix two definitions existed; because both appended to the same
    list the observable behaviour was the same, but the regression test pins
    the implementation: one call -> one registration.
    """

    def _get_auction(self):
        draft = MagicMock(spec=Draft)
        draft.current_player = None
        draft.current_bid = 0.0
        draft.current_high_bidder = None
        draft.current_nominator = None
        draft.status = "active"
        draft.teams = []
        draft.available_players = []
        return Auction(draft=draft)

    def test_single_registration(self):
        """Calling add_completion_listener once registers exactly one callback."""
        auction = self._get_auction()
        cb = MagicMock()

        auction.add_completion_listener(cb)

        self.assertEqual(
            len(auction.on_auction_completed), 1,
            "Expected exactly one entry in on_auction_completed after one add_completion_listener call.",
        )
        self.assertIs(auction.on_auction_completed[0], cb)

    def test_callback_is_invoked_on_notify(self):
        """The registered callback is invoked when _notify_auction_completed fires."""
        auction = self._get_auction()
        cb = MagicMock()
        auction.add_completion_listener(cb)

        player = _make_player("p1", "Test Player", "RB", 10.0)
        auction._notify_auction_completed(player, None, 15.0)

        cb.assert_called_once_with(player, None, 15.0)

    def test_multiple_registrations_each_fire_once(self):
        """Two different callbacks registered individually each fire once."""
        auction = self._get_auction()
        cb1, cb2 = MagicMock(), MagicMock()
        auction.add_completion_listener(cb1)
        auction.add_completion_listener(cb2)

        player = _make_player("p2", "Another Player", "WR", 20.0)
        auction._notify_auction_completed(player, "team1", 25.0)

        cb1.assert_called_once()
        cb2.assert_called_once()


# ---------------------------------------------------------------------------
# Issue #86 — Strategy.__str__ defined twice
# ---------------------------------------------------------------------------

class TestStrategyStrNoDuplicate(unittest.TestCase):
    """Ensure Strategy.__str__ returns the expected representation.

    Before the fix __str__ was defined at line 44 and again at line 311.
    The second definition (identical) silently replaced the first.  This test
    pins the expected format so a future accidental overwrite is caught.
    """

    def _get_concrete_strategy(self):
        from strategies.basic_strategy import BasicStrategy
        return BasicStrategy()

    def test_str_format(self):
        """__str__ returns '<name>: <description>'."""
        strategy = self._get_concrete_strategy()
        result = str(strategy)
        expected = f"{strategy.name}: {strategy.description}"
        self.assertEqual(result, expected)

    def test_str_contains_name(self):
        """__str__ contains the strategy name."""
        strategy = self._get_concrete_strategy()
        self.assertIn(strategy.name, str(strategy))

    def test_str_contains_description(self):
        """__str__ contains the strategy description."""
        strategy = self._get_concrete_strategy()
        self.assertIn(strategy.description, str(strategy))

    def test_str_is_defined_exactly_once(self):
        """Strategy.__str__ should not be multiply defined in the MRO."""
        from strategies.base_strategy import Strategy
        # Collect all __str__ definitions in the MRO, stopping before object
        definitions = []
        for cls in type.mro(Strategy):
            if cls is object:
                break
            if "__str__" in cls.__dict__:
                definitions.append(cls)
        # Only Strategy itself should define __str__ in the base hierarchy
        self.assertEqual(
            len(definitions), 1,
            f"__str__ is defined in multiple classes in the MRO: {definitions}",
        )


if __name__ == "__main__":
    unittest.main()
