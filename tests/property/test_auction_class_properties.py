"""Property-based tests: Auction class — Vickrey pricing and sealed-bid invariants.

Track F — Issue #329

Sprint 10 · sprint/10 branch
"""

from __future__ import annotations

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from classes.auction import Auction
from classes.draft import Draft
from classes.player import Player
from classes.team import Team
from classes.owner import Owner
from tests.property.conftest import draft_player


# ---------------------------------------------------------------------------
# Helper: build a started draft + Auction
# ---------------------------------------------------------------------------

def _make_auction(n_teams: int = 3, budget: int = 200, n_players: int = 30) -> Auction:
    draft = Draft(name="test", budget_per_team=budget, roster_size=6, num_teams=n_teams)
    for i in range(n_teams):
        team = Team(f"team{i}", f"owner{i}", f"Team{i}", budget=budget)
        owner = Owner(f"owner{i}", f"Owner{i}")
        draft.add_team(team, owner)
    players = [
        Player(f"p{j}", f"Player{j}", ["QB", "RB", "WR", "TE"][j % 4], "NFL",
               auction_value=float(j % 50))
        for j in range(n_players)
    ]
    draft.add_players(players)
    draft.start_draft()
    return Auction(draft=draft)


# ---------------------------------------------------------------------------
# Property 1 — Vickrey: winner pays second-highest + 1 (single winner case)
# ---------------------------------------------------------------------------

@given(
    bids=st.dictionaries(
        keys=st.text(min_size=1, max_size=8),
        values=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=6,
    )
)
@settings(max_examples=100)
def test_vickrey_price_second_highest_plus_one(bids):
    """When there is a clear single top bidder, winner pays 2nd-highest + 1."""
    auction = _make_auction()
    sorted_vals = sorted(bids.values(), reverse=True)
    assume(sorted_vals[0] != sorted_vals[1])  # no tie at the top

    winner_id, price = auction._determine_auction_winner(bids)

    # Winner must have submitted the top bid
    assert bids[winner_id] == sorted_vals[0]
    # Price must equal second-highest + 1
    assert abs(price - (sorted_vals[1] + 1.0)) < 1e-9


# ---------------------------------------------------------------------------
# Property 2 — Vickrey: single bidder pays their own bid
# ---------------------------------------------------------------------------

@given(
    team_id=st.text(min_size=1, max_size=8),
    bid=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50)
def test_vickrey_single_bidder_pays_own_bid(team_id, bid):
    """When only one team bids, they win and pay their own bid."""
    auction = _make_auction()
    winner_id, price = auction._determine_auction_winner({team_id: bid})

    assert winner_id == team_id
    assert abs(price - bid) < 1e-9


# ---------------------------------------------------------------------------
# Property 3 — empty bids returns no winner
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=10)
def test_no_bids_returns_no_winner(_):
    """_determine_auction_winner({}) returns (None, 0.0)."""
    auction = _make_auction()
    winner_id, price = auction._determine_auction_winner({})
    assert winner_id is None
    assert price == 0.0


# ---------------------------------------------------------------------------
# Property 4 — tie-breaking: winner is one of the tied teams
# ---------------------------------------------------------------------------

@given(
    tied_ids=st.lists(
        st.text(min_size=1, max_size=8),
        min_size=2, max_size=5, unique=True
    ),
    tied_bid=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50)
def test_tie_winner_belongs_to_tied_set(tied_ids, tied_bid):
    """When multiple teams share the top bid, the winner is one of them."""
    auction = _make_auction()
    bids = {tid: tied_bid for tid in tied_ids}
    winner_id, _ = auction._determine_auction_winner(bids)
    assert winner_id in tied_ids


# ---------------------------------------------------------------------------
# Property 5 — team receives player only if budget allows
# ---------------------------------------------------------------------------

@given(
    player=draft_player(),
    budget=st.integers(min_value=1, max_value=200),
    price=st.integers(min_value=1, max_value=300),
)
@settings(max_examples=50)
def test_award_player_respects_budget(player, budget, price):
    """_award_player_to_team only adds player to team when price ≤ budget."""
    auction = _make_auction(budget=budget)
    team = auction.draft.teams[0]
    # Reset budget to the drawn value
    team.budget = budget
    team.initial_budget = budget
    team.roster_config = {player.position: 5}
    team.position_limits = {player.position: 5}

    # Ensure player is in available list
    if player not in auction.draft.available_players:
        auction.draft.available_players.append(player)

    before_roster = len(team.roster)
    auction._award_player_to_team(player, team.owner_id, float(price))

    if price <= budget:
        # Player should be on roster
        assert len(team.roster) == before_roster + 1
    else:
        # Budget exceeded — no change
        assert len(team.roster) == before_roster


# ---------------------------------------------------------------------------
# Property 6 — player moves from available to drafted after nominate_player
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=20, deadline=None)
def test_nominate_player_removes_from_available(_):
    """nominate_player() removes the player from draft.available_players."""
    auction = _make_auction(n_teams=2, budget=200, n_players=10)
    player = auction.draft.available_players[0]
    before = len(auction.draft.available_players)

    auction.nominate_player(player, "owner0", initial_bid=1.0)

    assert player not in auction.draft.available_players
    assert len(auction.draft.available_players) == before - 1
    assert player in auction.draft.drafted_players


# ---------------------------------------------------------------------------
# Property 7 — on_auction_completed fires exactly once per nominate_player
# ---------------------------------------------------------------------------

@given(st.just(None))
@settings(max_examples=20, deadline=None)
def test_auction_completed_callback_fires_once(_):
    """on_auction_completed callback fires exactly once per nomination.

    Teams need a calculate_bid method so _collect_sealed_bids returns bids;
    without bids the winner is None and _award_player_to_team (which fires
    the callback) is never reached.
    """
    auction = _make_auction(n_teams=2, budget=200, n_players=10)

    # Give every team a callable bid so bids are collected
    for team in auction.draft.teams:
        team.calculate_bid = lambda **kwargs: 10.0  # noqa: E731

    calls = []
    auction.on_auction_completed.append(lambda p, t, price: calls.append(1))

    player = auction.draft.available_players[0]
    auction.nominate_player(player, "owner0", initial_bid=1.0)

    assert len(calls) == 1
