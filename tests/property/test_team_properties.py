"""Property-based tests: team roster and budget invariants.

Track B — Issue #315

Sprint 10 · sprint/10 branch
"""

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tests.property.conftest import draft_player, draft_team


# ---------------------------------------------------------------------------
# Property 1 — add then remove is a no-op
# ---------------------------------------------------------------------------


@given(team=draft_team(), player=draft_player(), price=st.integers(min_value=1, max_value=50))
@settings(max_examples=50)
def test_add_remove_is_noop(team, player, price):
    """add_player(p, price) followed by remove_player(p) leaves team in original state."""
    assume(price <= team.budget)
    team.roster_config = {player.position: 2}
    team.position_limits = {player.position: 2}

    budget_before = team.budget
    roster_len_before = len(team.roster)

    added = team.add_player(player, price)
    assume(added)

    team.remove_player(player)

    assert team.budget == budget_before
    assert len(team.roster) == roster_len_before


# ---------------------------------------------------------------------------
# Property 2 — budget invariant after adding players
# ---------------------------------------------------------------------------


@given(
    initial_budget=st.integers(min_value=10, max_value=500),
    prices=st.lists(st.integers(min_value=1, max_value=10), min_size=1, max_size=6),
)
@settings(max_examples=50)
def test_budget_invariant_after_add(initial_budget, prices):
    """team.budget == initial_budget - sum(drafted prices) always."""
    from classes.team import Team
    from classes.player import Player

    positions = ["QB", "RB", "WR", "TE", "K", "DST"]
    team = Team("t", "o", "Test", initial_budget)

    for i, price in enumerate(prices):
        if price > team.budget:
            break
        p = Player(f"p{i}", f"Player {i}", positions[i % len(positions)], "NFL")
        team.add_player(p, price)

    total_in_roster = sum(
        int(p.draft_price) for p in team.roster if p.draft_price is not None
    )
    assert team.budget == team.initial_budget - total_in_roster


# ---------------------------------------------------------------------------
# Property 3 — roster count is bounded by position limits
# ---------------------------------------------------------------------------


@given(
    team=draft_team(),
    players=st.lists(draft_player(), min_size=1, max_size=25),
)
@settings(max_examples=50)
def test_roster_count_bounded(team, players):
    """len(team.roster) never exceeds the sum of all position limits."""
    max_slots = sum(team.position_limits.values())
    for p in players:
        if team.budget < 1:
            break
        team.add_player(p, 1)

    assert len(team.roster) <= max_slots


# ---------------------------------------------------------------------------
# Property 4 — no duplicate players on roster
# ---------------------------------------------------------------------------


@given(
    team=draft_team(),
    player=draft_player(),
)
@settings(max_examples=50)
def test_no_duplicate_players(team, player):
    """Adding the same player twice results in at most one entry in team.roster."""
    assume(team.budget >= 2)
    team.roster_config = {player.position: 2}
    team.position_limits = {player.position: 2}

    team.add_player(player, 1)
    team.add_player(player, 1)

    occurrences = sum(1 for p in team.roster if p.player_id == player.player_id)
    assert occurrences <= 1


# ---------------------------------------------------------------------------
# Property 5 — get_state round-trips key fields
# ---------------------------------------------------------------------------


@given(team=draft_team())
@settings(max_examples=50)
def test_to_dict_round_trips(team):
    """get_state() captures all scalar fields and they can reconstruct the team."""
    from classes.team import Team

    state = team.get_state()
    reconstructed = Team(
        team_id=state.team_id,
        owner_id=state.owner_id,
        team_name=state.team_name,
        budget=state.budget,
    )
    reconstructed.initial_budget = state.initial_budget

    assert reconstructed.team_id == team.team_id
    assert reconstructed.owner_id == team.owner_id
    assert reconstructed.team_name == team.team_name
    assert reconstructed.budget == team.budget
    assert reconstructed.initial_budget == team.initial_budget
