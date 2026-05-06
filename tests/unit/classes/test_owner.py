"""Tests for Owner class."""
from unittest.mock import MagicMock

from classes.owner import Owner


def _make_owner(is_human=True):
    return Owner(owner_id="o1", name="Alice", email="alice@example.com", is_human=is_human)


def _make_team_with_roster(players=None, position_limits=None):
    team = MagicMock()
    team.roster = players or []
    team.position_limits = position_limits or {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DST": 1}
    return team


class TestOwnerInit:
    def test_defaults(self):
        owner = Owner(owner_id="o1", name="Bob")
        assert owner.is_human is True
        assert owner.email is None
        assert owner.team is None
        assert owner.draft_history == []

    def test_with_email_and_ai(self):
        owner = Owner(owner_id="o2", name="AI", is_human=False)
        assert owner.is_human is False


class TestOwnerPreferences:
    def setup_method(self):
        self.owner = _make_owner()

    def test_update_known_preference(self):
        self.owner.update_preferences(risk_tolerance=0.8)
        assert self.owner.preferences["risk_tolerance"] == 0.8

    def test_update_unknown_preference_ignored(self):
        self.owner.update_preferences(nonexistent_key="value")
        assert "nonexistent_key" not in self.owner.preferences

    def test_get_risk_tolerance(self):
        assert self.owner.get_risk_tolerance() == 0.5

    def test_get_position_priorities(self):
        prio = self.owner.get_position_priorities()
        assert "QB" in prio

    def test_get_max_bid_percentage(self):
        assert self.owner.get_max_bid_percentage() == 0.3


class TestTargetAndAvoidPlayers:
    def setup_method(self):
        self.owner = _make_owner()

    def test_add_target_player(self):
        self.owner.add_target_player("p1")
        assert "p1" in self.owner.preferences["target_players"]

    def test_add_target_player_no_duplicate(self):
        self.owner.add_target_player("p1")
        self.owner.add_target_player("p1")
        assert self.owner.preferences["target_players"].count("p1") == 1

    def test_remove_target_player(self):
        self.owner.add_target_player("p1")
        self.owner.remove_target_player("p1")
        assert "p1" not in self.owner.preferences["target_players"]

    def test_remove_target_player_not_in_list(self):
        # Should not raise
        self.owner.remove_target_player("nonexistent")

    def test_is_target_player(self):
        self.owner.add_target_player("p1")
        assert self.owner.is_target_player("p1") is True
        assert self.owner.is_target_player("p2") is False

    def test_add_avoid_player(self):
        self.owner.add_avoid_player("p1")
        assert "p1" in self.owner.preferences["avoid_players"]

    def test_add_avoid_player_no_duplicate(self):
        self.owner.add_avoid_player("p1")
        self.owner.add_avoid_player("p1")
        assert self.owner.preferences["avoid_players"].count("p1") == 1

    def test_remove_avoid_player(self):
        self.owner.add_avoid_player("p1")
        self.owner.remove_avoid_player("p1")
        assert "p1" not in self.owner.preferences["avoid_players"]

    def test_remove_avoid_player_not_in_list(self):
        self.owner.remove_avoid_player("nonexistent")

    def test_is_avoid_player(self):
        self.owner.add_avoid_player("p1")
        assert self.owner.is_avoid_player("p1") is True
        assert self.owner.is_avoid_player("p2") is False


class TestDraftHistory:
    def setup_method(self):
        self.owner = _make_owner()

    def test_add_draft_action(self):
        self.owner.add_draft_action({"type": "bid", "amount": 10})
        assert len(self.owner.draft_history) == 1

    def test_get_draft_summary_empty(self):
        summary = self.owner.get_draft_summary()
        assert summary["total_actions"] == 0
        assert summary["successful_bids"] == 0
        assert summary["average_bid"] == 0

    def test_get_draft_summary_with_bids(self):
        self.owner.add_draft_action({"type": "bid", "amount": 20, "successful": True})
        self.owner.add_draft_action({"type": "bid", "amount": 10, "successful": True})
        self.owner.add_draft_action({"type": "bid", "amount": 5, "successful": False})
        summary = self.owner.get_draft_summary()
        assert summary["successful_bids"] == 2
        assert summary["total_spent"] == 30
        assert summary["average_bid"] == 15.0


class TestTeamAssignment:
    def setup_method(self):
        self.owner = _make_owner()

    def test_assign_and_get_team(self):
        team = MagicMock()
        self.owner.assign_team(team)
        assert self.owner.get_team() is team
        assert self.owner.has_team() is True

    def test_has_team_without_team(self):
        assert self.owner.has_team() is False

    def test_get_roster_spots_no_team(self):
        assert self.owner.get_roster_spots() == []

    def test_get_available_roster_spots_no_team(self):
        assert self.owner.get_available_roster_spots() == {}

    def test_get_roster_spots_with_team(self):
        player = MagicMock()
        player.position = "QB"
        team = _make_team_with_roster(players=[player])
        self.owner.assign_team(team)
        spots = self.owner.get_roster_spots()
        assert any(s["is_filled"] for s in spots)
        assert any(not s["is_filled"] for s in spots)

    def test_get_available_roster_spots_with_team(self):
        player = MagicMock()
        player.position = "QB"
        team = _make_team_with_roster(players=[player])
        self.owner.assign_team(team)
        available = self.owner.get_available_roster_spots()
        assert available["QB"] == 0  # filled
        assert available["RB"] == 2  # empty


class TestOwnerStrAndRepr:
    def test_str_human(self):
        owner = _make_owner(is_human=True)
        assert "Human" in str(owner)

    def test_str_ai(self):
        owner = _make_owner(is_human=False)
        assert "AI" in str(owner)

    def test_repr(self):
        owner = _make_owner()
        assert "Owner" in repr(owner)
        assert "o1" in repr(owner)


class TestOwnerToDict:
    def test_to_dict_structure(self):
        owner = _make_owner()
        d = owner.to_dict()
        assert d["owner_id"] == "o1"
        assert d["name"] == "Alice"
        assert "has_team" in d
