"""Sprint 9 QA tests — Issue #117: remove_player doesn't reset draft_price alias.

These tests FAIL before the fix and PASS after.
"""

from classes.team import Team
from classes.player import Player


def _make_team(budget: int = 200) -> Team:
    return Team("t1", "o1", "Team Alpha", budget=budget)


def _make_player(player_id: str = "p1") -> Player:
    return Player(player_id, "John Doe", "QB", "BUF", projected_points=300.0, auction_value=40.0)


class TestIssue117RemovePlayerDraftPriceAlias:
    """Issue #117 — remove_player resets drafted_price but NOT draft_price alias."""

    def test_draft_price_is_none_after_remove_player(self):
        """draft_price alias must be None after remove_player."""
        team = _make_team()
        player = _make_player()
        team.add_player(player, 40)

        assert player.draft_price == 40, "Precondition: draft_price set after add_player"

        team.remove_player(player)

        # BUG: remove_player sets drafted_price=None but leaves draft_price unchanged
        assert player.draft_price is None, (
            f"Expected draft_price to be None after remove_player, got {player.draft_price}. "
            "Issue #117: remove_player does not reset draft_price alias."
        )

    def test_drafted_price_is_none_after_remove_player(self):
        """drafted_price must also be None after remove_player (sanity check)."""
        team = _make_team()
        player = _make_player()
        team.add_player(player, 40)
        team.remove_player(player)
        assert player.drafted_price is None

    def test_both_aliases_cleared_after_remove(self):
        """Both draft_price and drafted_price must be None — they must not diverge."""
        team = _make_team()
        player = _make_player("p2")
        team.add_player(player, 35)

        team.remove_player(player)

        # This directly documents the divergence introduced by the bug:
        assert player.draft_price is None, (
            f"draft_price={player.draft_price} diverged from "
            f"drafted_price={player.drafted_price} after remove_player. "
            "Issue #117 still present."
        )
        assert player.drafted_price is None

    def test_is_drafted_reset_after_remove_player(self):
        """is_drafted flag should be False after remove_player (baseline)."""
        team = _make_team()
        player = _make_player()
        team.add_player(player, 40)
        team.remove_player(player)
        assert player.is_drafted is False

    def test_budget_restored_after_remove_player(self):
        """Team budget should be restored after remove_player (baseline)."""
        team = _make_team(budget=200)
        player = _make_player()
        team.add_player(player, 40)
        assert team.budget == 160
        team.remove_player(player)
        assert team.budget == 200
