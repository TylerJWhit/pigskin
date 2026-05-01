"""Sprint 7 Track B: regression tests for P1 bugs #114, #110, #112, #131.

Written as QA Phase 1 (failing tests that define the contract) before fixes
are implemented. All tests must pass after the corresponding fixes are applied.

#114 — classes/player.py: Player.__init__ default name='' raises ValidationError
#110 — classes/draft.py: complete_auction ignores add_player return value
#112 — classes/team.py: is_roster_complete / get_needs use hardcoded positions
#131 — services/draft_loading_service.py: Auction ctor no longer starts timers
        (verified resolved by sealed-bid refactor — tests confirm no threads)
"""

import threading
import unittest

from classes.player import Player
from classes.team import Team
from classes.draft import Draft
from classes.owner import Owner


# ---------------------------------------------------------------------------
# #114 — Player default name validation
# ---------------------------------------------------------------------------

class TestPlayerDefaultName(unittest.TestCase):
    """#114: Player(player_id='x') must NOT raise ValidationError."""

    def test_player_default_construction_no_exception(self):
        """Calling Player(player_id='x') with no name must not raise."""
        try:
            p = Player(player_id="test-id-001")
        except Exception as e:
            self.fail(
                f"Player(player_id='test-id-001') raised {type(e).__name__}: {e}"
            )

    def test_player_default_name_is_non_empty_string(self):
        """The default name must satisfy min_length=1."""
        p = Player(player_id="test-id-002")
        self.assertIsInstance(p.name, str)
        self.assertGreater(len(p.name), 0, "Default name must not be empty")

    def test_player_explicit_name_preserved(self):
        """Explicit name is still stored correctly."""
        p = Player(player_id="test-id-003", name="Patrick Mahomes")
        self.assertEqual(p.name, "Patrick Mahomes")


# ---------------------------------------------------------------------------
# #110 — complete_auction ignores add_player return value
# ---------------------------------------------------------------------------

class TestCompleteAuctionChecksAddPlayer(unittest.TestCase):
    """#110: When add_player returns False, player must NOT be removed from
    available_players (player stays in the pool; transaction not recorded)."""

    def _make_draft_with_player(self):
        draft = Draft(draft_id="d-110", num_teams=2, budget_per_team=50)
        owner = Owner(owner_id="o1", name="Owner 1", is_human=False)
        owner2 = Owner(owner_id="o2", name="Owner 2", is_human=False)
        team = Team(team_id="t1", owner_id="o1", team_name="Team 1", budget=50)
        team2 = Team(team_id="t2", owner_id="o2", team_name="Team 2", budget=50)
        draft.add_owner(owner)
        draft.add_owner(owner2)
        draft.add_team(team)
        draft.add_team(team2)
        player = Player(player_id="p1", name="Test Player", position="QB",
                        projected_points=20.0, auction_value=10.0)
        draft.add_players([player])
        draft.start_draft()
        return draft, player, team

    def test_player_not_removed_when_add_player_fails(self):
        """If add_player returns False (budget 0), player stays in available_players."""
        draft, player, team = self._make_draft_with_player()

        # Drain the team's budget so add_player will reject the player
        team.budget = 0.0

        # Manually set auction state to simulate a completed auction
        draft.current_player = player
        draft.current_high_bidder = "o1"
        draft.current_bid = 10.0

        players_before = len(draft.available_players)

        # complete_auction should detect the failure and NOT remove the player
        try:
            draft.complete_auction()
        except Exception:
            pass  # Some implementations may raise; what matters is pool integrity

        # Player must still be in available_players if add_player returned False
        result = team.add_player(player, 10.0)
        if not result:
            # add_player does return False — verify player was NOT removed
            self.assertIn(
                player,
                draft.available_players,
                "Player must stay in available_players when add_player fails"
            )

    def test_player_added_to_team_on_success(self):
        """On a successful complete_auction, player IS removed and added to team."""
        draft, player, team = self._make_draft_with_player()

        draft.current_player = player
        draft.current_high_bidder = "o1"
        draft.current_bid = 5.0

        draft.complete_auction()

        self.assertIn(player, team.roster, "Player should be on winning team")
        self.assertNotIn(player, draft.available_players,
                         "Player should be removed from available pool")


# ---------------------------------------------------------------------------
# #112 — Team.is_roster_complete / get_needs use hardcoded positions
# ---------------------------------------------------------------------------

class TestTeamRosterConfigRespected(unittest.TestCase):
    """#112: is_roster_complete and get_needs must use self.roster_config,
    not hardcoded positions."""

    def _make_player(self, pid, pos):
        return Player(player_id=pid, name=f"Player {pid}", position=pos,
                      projected_points=10.0, auction_value=10.0)

    def test_is_roster_complete_2qb_league(self):
        """In a 2-QB league, roster is not complete with only 1 QB."""
        roster_config = {'QB': 2, 'RB': 2, 'WR': 3, 'TE': 1, 'K': 1, 'DST': 1}
        team = Team(team_id="t1", owner_id="o1", team_name="T1",
                    budget=200, roster_config=roster_config)

        # Add exactly the default-hardcoded 1 QB + remaining positions
        team.roster = [
            self._make_player("qb1", "QB"),
            self._make_player("rb1", "RB"),
            self._make_player("rb2", "RB"),
            self._make_player("wr1", "WR"),
            self._make_player("wr2", "WR"),
            self._make_player("wr3", "WR"),
            self._make_player("te1", "TE"),
            self._make_player("k1", "K"),
            self._make_player("dst1", "DST"),
        ]

        # With hardcoded check: is_roster_complete would return True (1 QB meets QB:1)
        # With roster_config check: must return False (needs 2 QBs per roster_config)
        self.assertFalse(
            team.is_roster_complete(),
            "2-QB league must require 2 QBs; roster_config must override hardcoded QB:1"
        )

    def test_is_roster_complete_true_when_config_satisfied(self):
        """Roster is complete when all roster_config requirements are met."""
        roster_config = {'QB': 1, 'RB': 1, 'WR': 1}
        team = Team(team_id="t2", owner_id="o2", team_name="T2",
                    budget=200, roster_config=roster_config)
        team.roster = [
            self._make_player("qb1", "QB"),
            self._make_player("rb1", "RB"),
            self._make_player("wr1", "WR"),
        ]
        self.assertTrue(team.is_roster_complete())

    def test_get_needs_uses_roster_config(self):
        """get_needs returns positions from roster_config, not hardcoded defaults."""
        # Minimal 1-position league
        roster_config = {'QB': 2}
        team = Team(team_id="t3", owner_id="o3", team_name="T3",
                    budget=200, roster_config=roster_config)
        team.roster = [self._make_player("qb1", "QB")]

        needs = team.get_needs()
        self.assertEqual(
            needs.count("QB"), 1,
            "get_needs should report 1 missing QB when roster_config requires 2"
        )
        # Should NOT include RB/WR/TE/K/DST from hardcoded defaults
        for pos in ["RB", "WR", "TE", "K", "DST"]:
            self.assertNotIn(
                pos, needs,
                f"get_needs must not include '{pos}' when not in roster_config"
            )

    def test_default_roster_config_unchanged(self):
        """Team with no explicit roster_config still behaves correctly (regression)."""
        team = Team(team_id="t4", owner_id="o4", team_name="T4", budget=200)
        # No players — needs should list the defaults
        needs = team.get_needs()
        self.assertIn("QB", needs)
        self.assertIn("RB", needs)


# ---------------------------------------------------------------------------
# #131 — draft_loading_service Auction ctor no longer starts timers
# ---------------------------------------------------------------------------

class TestDraftLoadingServiceNoTimerThreads(unittest.TestCase):
    """#131: Confirmed resolved by sealed-bid refactor. Verify no background
    threads are started when Auction is instantiated."""

    def test_auction_init_starts_no_extra_threads(self):
        """Auction() must not spawn background threads."""
        from classes.auction import Auction

        draft = Draft(draft_id="d-131", num_teams=2, budget_per_team=200)
        owner = Owner(owner_id="o1", name="Owner 1", is_human=False)
        owner2 = Owner(owner_id="o2", name="Owner 2", is_human=False)
        team = Team(team_id="t1", owner_id="o1", team_name="T1", budget=200)
        team2 = Team(team_id="t2", owner_id="o2", team_name="T2", budget=200)
        draft.add_owner(owner)
        draft.add_owner(owner2)
        draft.add_team(team)
        draft.add_team(team2)
        draft.start_draft()

        threads_before = threading.active_count()
        auction = Auction(draft)
        threads_after = threading.active_count()

        self.assertEqual(
            threads_before, threads_after,
            f"Auction() must not start background threads "
            f"(before={threads_before}, after={threads_after})"
        )


if __name__ == "__main__":
    unittest.main()
