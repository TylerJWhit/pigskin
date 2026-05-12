"""Property-based tests: auction bid invariants.

Track B — Issue #315
The real budget-enforcement point is Team.add_player (Auction.place_bid is a
legacy stub that always returns False). These properties test the core invariant
that drives every auction: money paid for drafted players must stay within the
team's initial budget.

Sprint 10 · sprint/10 branch
"""

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tests.property.conftest import draft_player, draft_team


# ---------------------------------------------------------------------------
# Property 1 — valid bids never violate budget
# ---------------------------------------------------------------------------


@given(
    team=draft_team(),
    player=draft_player(),
    bid_fraction=st.floats(min_value=0.01, max_value=1.0, allow_nan=False),
)
@settings(max_examples=50)
def test_bid_bounded_by_budget(team, player, bid_fraction):
    """add_player with any 1 <= amount <= remaining_budget never leaves budget < 0.

    Invariant:
        forall team, player, amount where 1 <= amount <= team.budget:
            after add_player(player, amount): team.budget >= 0
    """
    assume(team.budget >= 1)
    amount = max(1, int(bid_fraction * team.budget))
    amount = min(amount, team.budget)
    team.add_player(player, amount)
    assert team.budget >= 0


# ---------------------------------------------------------------------------
# Property 2 — overbids are always rejected
# ---------------------------------------------------------------------------


@given(
    team=draft_team(),
    player=draft_player(),
    overage=st.integers(min_value=1, max_value=1000),
)
@settings(max_examples=50)
def test_overbid_always_rejected(team, player, overage):
    """add_player with amount > remaining_budget always returns False.

    Invariant:
        forall team, player, overage > 0:
            add_player(team.budget + overage) returns False and budget unchanged
    """
    overbid = team.budget + overage
    budget_before = team.budget
    result = team.add_player(player, overbid)
    assert result is False
    assert team.budget == budget_before


# ---------------------------------------------------------------------------
# Property 3 — bidding exactly the budget succeeds and drains it to zero
# ---------------------------------------------------------------------------


@given(team=draft_team(), player=draft_player())
@settings(max_examples=50)
def test_bid_at_exactly_budget(team, player):
    """add_player with price == team.budget succeeds and leaves team.budget == 0.

    Assumes team has at least $1 and a free roster slot for the player's position.

    Invariant:
        forall team with budget >= 1, player with a free position slot:
            add_player(player, budget) is True and team.budget == 0
    """
    assume(team.budget >= 1)
    # Ensure the team has a slot for this position by clearing roster and resetting config
    team.roster_config = {player.position: 1}
    team.position_limits = {player.position: 1}
    result = team.add_player(player, team.budget)
    assert result is True
    assert team.budget == 0


# ---------------------------------------------------------------------------
# Property 4 — sequential valid bids maintain the budget invariant
# ---------------------------------------------------------------------------


@given(
    initial_budget=st.integers(min_value=10, max_value=500),
    n_bids=st.integers(min_value=1, max_value=6),
)
@settings(max_examples=50)
def test_sequential_bids_maintain_budget(initial_budget, n_bids):
    """Any sequence of valid bids keeps sum(paid prices) <= initial_budget.

    Invariant:
        forall initial_budget, sequence of add_player calls where each price <= current budget:
            initial_budget - team.budget == sum of accepted prices
    """
    from classes.team import Team
    from classes.player import Player

    team = Team("t", "o", "Test", initial_budget)
    positions = ["QB", "RB", "WR", "TE", "K", "DST", "RB", "WR"]
    total_paid = 0

    for i in range(n_bids):
        if team.budget < 1:
            break
        bid = max(1, team.budget // (n_bids - i))
        bid = min(bid, team.budget)
        p = Player(f"p{i}", f"Player {i}", positions[i % len(positions)], "NFL")
        if team.add_player(p, bid):
            total_paid += bid

    assert team.initial_budget - team.budget == total_paid
    assert total_paid <= initial_budget


# ---------------------------------------------------------------------------
# Property 5 — team state reads are idempotent
# ---------------------------------------------------------------------------


@given(team=draft_team())
@settings(max_examples=50)
def test_auction_state_idempotent(team):
    """Calling get_state() twice without mutations returns equal TeamState objects.

    Invariant:
        forall team:
            team.get_state() == team.get_state()  (no side effects)
    """
    s1 = team.get_state()
    s2 = team.get_state()
    assert s1 == s2
    assert s1.team_id == s2.team_id
    assert s1.budget == s2.budget
    assert s1.roster_player_ids == s2.roster_player_ids

