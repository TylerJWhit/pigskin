"""Tests for Player class."""
import pytest
from classes.player import Player


def _make_player(**kwargs):
    defaults = dict(
        player_id="p1",
        name="Test Player",
        position="QB",
        auction_value=30.0,
        projected_points=300.0,
        bye_week=5,
        nfl_team="KC"
    )
    defaults.update(kwargs)
    return Player(**defaults)


class TestPlayerInit:
    def test_basic_creation(self):
        p = _make_player()
        assert p.player_id == "p1"
        assert p.name == "Test Player"
        assert p.position == "QB"

    def test_default_is_not_drafted(self):
        p = _make_player()
        assert p.is_drafted is False
        assert p.drafted_price is None
        assert p.drafted_by is None

    def test_team_alias(self):
        p = _make_player()
        assert p.team == p.nfl_team == "KC"


class TestPlayerValidation:
    def test_invalid_bye_week_zero_raises(self):
        with pytest.raises(Exception):
            _make_player(bye_week=0)

    def test_player_id_none_raises(self):
        with pytest.raises(Exception):
            # Pydantic validator on player_id
            Player(
                player_id=None,  # type: ignore
                name="Test",
                position="QB",
                auction_value=10.0,
                projected_points=100.0,
                bye_week=5
            )


class TestMarkAsDrafted:
    def test_mark_as_drafted(self):
        p = _make_player()
        p.mark_as_drafted(50.0, "owner1")
        assert p.is_drafted is True
        assert p.drafted_price == 50.0
        assert p.drafted_by == "owner1"
        assert p.draft_price == 50.0


class TestGetValueOverReplacement:
    def test_positive_vor(self):
        p = _make_player(projected_points=300.0)
        assert p.get_value_over_replacement(200.0) == 100.0

    def test_negative_vor_returns_zero(self):
        p = _make_player(projected_points=100.0)
        assert p.get_value_over_replacement(200.0) == 0


class TestStrAndRepr:
    def test_str(self):
        p = _make_player(name="Patrick Mahomes", position="QB", nfl_team="KC")
        result = str(p)
        assert "Patrick Mahomes" in result
        assert "QB" in result

    def test_repr(self):
        p = _make_player()
        result = repr(p)
        assert "Player" in result
        assert "p1" in result

    def test_hash(self):
        p1 = _make_player()
        p2 = _make_player()
        assert hash(p1) == hash(p2)


class TestToDict:
    def test_to_dict_structure(self):
        p = _make_player()
        d = p.to_dict()
        assert d["player_id"] == "p1"
        assert d["name"] == "Test Player"
        assert "team" in d
        assert "projected_points" in d
        assert "is_drafted" in d
