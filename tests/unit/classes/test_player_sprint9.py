"""Sprint 9 QA tests — Issue #120: player.to_dict() omits the vor field.

These tests FAIL before the fix and PASS after.
"""

from classes.player import Player


class TestIssue120PlayerToDictVorField:
    """Issue #120 — to_dict() silently drops the vor field."""

    def test_to_dict_includes_vor_key(self):
        """to_dict() must include the 'vor' key."""
        player = Player("p1", "Patrick Mahomes", "QB", "KC", projected_points=400.0, auction_value=55.0)
        d = player.to_dict()
        assert "vor" in d, (
            f"Expected 'vor' key in player.to_dict(), but keys were: {list(d.keys())}. "
            "Issue #120: to_dict() omits the vor field."
        )

    def test_to_dict_vor_reflects_set_value(self):
        """to_dict() must return the correct vor value when vor is non-zero."""
        player = Player(
            "p2", "Justin Jefferson", "WR", "MIN",
            projected_points=320.0, auction_value=52.0,
            vor=42.5
        )
        d = player.to_dict()
        assert "vor" in d, (
            "Issue #120: 'vor' key missing from to_dict() output."
        )
        assert d["vor"] == 42.5, (
            f"Expected vor=42.5, got {d.get('vor')}. "
            "Issue #120: vor value incorrect or not included."
        )

    def test_to_dict_vor_default_is_zero(self):
        """When vor is not explicitly set, to_dict() should include 'vor': 0.0."""
        player = Player("p3", "Tyreek Hill", "WR", "MIA", projected_points=300.0, auction_value=48.0)
        d = player.to_dict()
        assert "vor" in d, "Issue #120: 'vor' key missing from to_dict()."
        assert d["vor"] == 0.0, f"Expected default vor=0.0, got {d.get('vor')}"

    def test_to_dict_still_includes_existing_fields(self):
        """Sanity: to_dict() must still contain all pre-existing keys (baseline)."""
        player = Player("p4", "Travis Kelce", "TE", "KC", projected_points=220.0, auction_value=38.0)
        d = player.to_dict()
        expected_keys = {"player_id", "name", "position", "team", "projected_points",
                         "auction_value", "bye_week", "is_drafted", "drafted_price", "drafted_by"}
        for key in expected_keys:
            assert key in d, f"Existing key '{key}' missing from to_dict() — regression risk"
