"""CI integration smoke test for the property test infrastructure.

This test must pass before any Track B–E stubs are implemented.
It confirms that:
  - hypothesis is importable
  - the conftest composite strategies generate valid objects
  - pytest discovers tests/property/ correctly
"""

from hypothesis import given, settings

from tests.property.conftest import draft_player, draft_team, draft_state


@given(player=draft_player())
@settings(max_examples=10)
def test_draft_player_strategy_produces_valid_player(player):
    """draft_player() always produces a Player with required fields."""
    assert player.player_id
    assert player.name.strip()
    assert player.position in ("QB", "RB", "WR", "TE", "K", "DST")
    assert player.projected_points >= 0.0
    assert player.auction_value >= 0.0


@given(team=draft_team())
@settings(max_examples=10)
def test_draft_team_strategy_produces_valid_team(team):
    """draft_team() always produces a Team with non-negative budget and empty roster."""
    assert team.budget >= 10
    assert len(team.roster) == 0


@given(state=draft_state())
@settings(max_examples=5)
def test_draft_state_strategy_produces_valid_state(state):
    """draft_state() always produces a (teams, players) tuple with consistent sizes."""
    teams, players = state
    assert len(teams) >= 2
    assert len(players) >= len(teams)
