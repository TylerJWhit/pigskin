"""Property-based tests: Draft class state machine and auction invariants.

Track F — Issue #328

Sprint 10 · sprint/10 branch
"""

from __future__ import annotations

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from classes.draft import Draft
from classes.player import Player
from classes.team import Team
from classes.owner import Owner


# ---------------------------------------------------------------------------
# Helper: build a minimal 2-team draft with players ready to start
# ---------------------------------------------------------------------------

def _make_started_draft(n_players: int = 20) -> Draft:
    """Return a started 2-team draft pre-loaded with n_players."""
    draft = Draft(name="test", budget_per_team=200.0, roster_size=6, num_teams=2)
    for i in range(2):
        team = Team(f"team{i}", f"owner{i}", f"Team {i}", budget=200)
        owner = Owner(f"owner{i}", f"Owner {i}")
        draft.add_team(team, owner)
    players = [
        Player(f"p{j}", f"Player {j}", ["QB", "RB", "WR", "TE"][j % 4], "NFL")
        for j in range(n_players)
    ]
    draft.add_players(players)
    draft.start_draft()
    return draft


# ---------------------------------------------------------------------------
# Property 1 — state machine: only valid transitions
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=10)
def test_draft_starts_in_created_status(_):
    """A freshly constructed Draft is always in 'created' status."""
    draft = Draft()
    assert draft.status == "created"


@given(st.just(None))
@settings(max_examples=10)
def test_start_draft_transitions_to_started(_):
    """start_draft() moves status from 'created' to 'started'."""
    draft = Draft(num_teams=2, budget_per_team=100, roster_size=4)
    for i in range(2):
        team = Team(f"t{i}", f"o{i}", f"Team{i}", budget=100)
        owner = Owner(f"o{i}", f"Owner{i}")
        draft.add_team(team, owner)
    players = [Player(f"p{j}", f"P{j}", "RB", "NFL") for j in range(12)]
    draft.add_players(players)
    draft.start_draft()
    assert draft.status == "started"


@given(st.just(None))
@settings(max_examples=10)
def test_status_cannot_go_backwards(_):
    """Once 'started', calling start_draft() again raises ValueError."""
    draft = _make_started_draft()
    try:
        draft.start_draft()
        assert False, "Expected ValueError"
    except ValueError:
        pass  # correct
    assert draft.status in ("started", "paused", "completed")


# ---------------------------------------------------------------------------
# Property 2 — nominator rotation is cyclic
# ---------------------------------------------------------------------------

@given(n_advances=st.integers(min_value=1, max_value=50))
@settings(max_examples=50)
def test_nominator_rotation_is_cyclic(n_advances):
    """After num_teams advances the index returns to its starting value."""
    draft = _make_started_draft()
    num_teams = len(draft.teams)
    start_index = draft.current_nominator_index

    for _ in range(num_teams * n_advances):
        draft._advance_nominator()

    assert draft.current_nominator_index == start_index


@given(n_advances=st.integers(min_value=0, max_value=100))
@settings(max_examples=50)
def test_nominator_index_always_valid(n_advances):
    """current_nominator_index is always in [0, len(teams) - 1]."""
    draft = _make_started_draft()
    for _ in range(n_advances):
        draft._advance_nominator()

    assert 0 <= draft.current_nominator_index < len(draft.teams)


# ---------------------------------------------------------------------------
# Property 3 — bid monotonicity
# ---------------------------------------------------------------------------

@given(
    first_bid=st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    low_bid_delta=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50)
def test_place_bid_rejects_non_increasing(first_bid, low_bid_delta):
    """place_bid returns False if bid_amount <= current_bid."""
    draft = _make_started_draft()
    player = draft.available_players[0]
    draft.nominate_player(player, "owner0", initial_bid=first_bid)

    low_bid = first_bid - low_bid_delta  # always ≤ current bid
    result = draft.place_bid("owner1", low_bid)
    assert result is False


@given(
    first_bid=st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    increment=st.floats(min_value=0.01, max_value=50.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50)
def test_place_bid_accepts_higher(first_bid, increment):
    """place_bid returns True when bid_amount > current_bid and team has budget."""
    assume(first_bid + increment <= 200.0)
    draft = _make_started_draft()
    player = draft.available_players[0]
    draft.nominate_player(player, "owner0", initial_bid=first_bid)

    result = draft.place_bid("owner1", first_bid + increment)
    assert result is True
    assert draft.current_bid == first_bid + increment


# ---------------------------------------------------------------------------
# Property 4 — auction resolution moves player between pools
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=20)
def test_complete_auction_moves_player(_):
    """complete_auction() removes player from available and adds to drafted."""
    draft = _make_started_draft()
    player = draft.available_players[0]
    before_available = len(draft.available_players)
    before_drafted = len(draft.drafted_players)

    draft.nominate_player(player, "owner0", initial_bid=1.0)
    draft.place_bid("owner1", 2.0)
    draft.complete_auction()

    # Player moved pools (or auction was voided — either way it left available)
    assert len(draft.available_players) == before_available - 1
    assert len(draft.drafted_players) == before_drafted + 1


# ---------------------------------------------------------------------------
# Property 5 — team count never exceeds num_teams cap
# ---------------------------------------------------------------------------

@given(extra=st.integers(min_value=1, max_value=10))
@settings(max_examples=50)
def test_team_count_capped(extra):
    """Adding more than num_teams teams raises ValueError."""
    num_teams = 2
    draft = Draft(num_teams=num_teams, budget_per_team=100, roster_size=4)
    for i in range(num_teams):
        draft.add_team(Team(f"t{i}", f"o{i}", f"Team{i}", budget=100))

    for i in range(extra):
        try:
            draft.add_team(Team(f"extra{i}", f"eo{i}", f"Extra{i}", budget=100))
            assert False, "Expected ValueError"
        except ValueError:
            pass

    assert len(draft.teams) == num_teams


# ---------------------------------------------------------------------------
# Property 6 — get_leaderboard returns all teams sorted descending
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=20)
def test_leaderboard_ordering(_):
    """get_leaderboard() returns team dicts in descending projected_points order."""
    draft = _make_started_draft()
    leaderboard = draft.get_leaderboard()  # returns List[Dict]
    assert len(leaderboard) == len(draft.teams)
    for i in range(len(leaderboard) - 1):
        pts_a = leaderboard[i]["projected_points"]
        pts_b = leaderboard[i + 1]["projected_points"]
        assert pts_a >= pts_b
