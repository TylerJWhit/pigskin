"""Sprint 9 QA tests — Issue #118: owner.to_dict() embeds raw Pydantic objects.

These tests FAIL before the fix and PASS after.
"""

import json
import pytest

from classes.owner import Owner
from classes.team import Team
from classes.player import Player


def _owner_with_rostered_player() -> Owner:
    """Return an Owner with a Team that has one player on the roster."""
    owner = Owner("o1", "Alice")
    team = Team("t1", "o1", "Alice FC", budget=200)
    player = Player("p1", "Travis Kelce", "TE", "KC", projected_points=220.0, auction_value=38.0)
    team.add_player(player, 38)
    owner.assign_team(team)
    return owner


class TestIssue118OwnerToDictJsonSerializable:
    """Issue #118 — to_dict places raw Player Pydantic objects under roster_spots."""

    def test_to_dict_is_json_serializable(self):
        """json.dumps(owner.to_dict()) must not raise TypeError."""
        owner = _owner_with_rostered_player()
        try:
            json.dumps(owner.to_dict())
        except TypeError as exc:
            pytest.fail(
                f"owner.to_dict() is not JSON-serializable: {exc}. "
                "Issue #118: get_roster_spots() returns raw Player objects."
            )

    def test_roster_spot_player_is_not_raw_pydantic_object(self):
        """Each filled roster_spot should not contain a raw Pydantic Player object."""
        owner = _owner_with_rostered_player()
        d = owner.to_dict()
        for spot in d.get("roster_spots", []):
            if spot.get("is_filled"):
                player_val = spot.get("player")
                # Raw Pydantic models expose __fields__; a serialized dict does not
                assert not hasattr(player_val, "__fields__"), (
                    f"roster_spot['player'] is a raw Pydantic object ({type(player_val).__name__}). "
                    "Issue #118: owner.to_dict() must serialize Player to a plain dict."
                )

    def test_no_team_owner_to_dict_is_json_serializable(self):
        """Owner without a team must be JSON-serializable (baseline, expected PASS)."""
        owner = Owner("o2", "Bob")
        result = json.dumps(owner.to_dict())  # Must not raise
        assert isinstance(result, str)

    def test_roster_spots_player_has_expected_keys_when_serialized(self):
        """Once fixed, filled roster spot's player value should be a dict with 'player_id'."""
        owner = _owner_with_rostered_player()
        d = owner.to_dict()
        filled_spots = [s for s in d.get("roster_spots", []) if s.get("is_filled")]
        assert filled_spots, "Expected at least one filled roster spot"
        for spot in filled_spots:
            player_val = spot.get("player")
            # After fix, player_val should be a plain dict
            assert isinstance(player_val, dict), (
                f"Expected player to be a dict after fix, got {type(player_val).__name__}. "
                "Issue #118 still present."
            )
            assert "player_id" in player_val
