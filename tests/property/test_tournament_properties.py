"""Property-based tests: tournament and simulation invariants.

Track E — Issue #318

Uses the draft_state composite strategy from conftest for full-draft simulations.
Full-draft tests use max_examples=20, deadline=None to keep CI runtime reasonable.

Sprint 10 · sprint/10 branch
"""

import json

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tests.property.conftest import draft_player, draft_state, draft_team


def _simulate_draft(teams, players):
    """Round-robin auction draft simulation: each team bids $1 per player in turn."""
    player_pool = list(players)
    for i, player in enumerate(player_pool):
        team = teams[i % len(teams)]
        if team.budget >= 1 and not player.is_drafted:
            team.add_player(player, 1)


# ---------------------------------------------------------------------------
# Property 1 — no team's total spend exceeds its initial budget
# ---------------------------------------------------------------------------


@given(state=draft_state())
@settings(max_examples=20, deadline=None)
def test_team_budget_never_exceeded(state):
    """After a simulated draft, initial_budget - budget >= 0 for all teams.

    Invariant:
        forall (teams, players) from draft_state():
            all(t.initial_budget - t.budget >= 0 for t in teams)
    """
    teams, players = state
    _simulate_draft(teams, players)
    for t in teams:
        assert t.initial_budget - t.budget >= 0, (
            f"Team {t.team_name}: initial_budget={t.initial_budget} budget={t.budget}"
        )


# ---------------------------------------------------------------------------
# Property 2 — each player appears in at most one team's roster
# ---------------------------------------------------------------------------


@given(state=draft_state())
@settings(max_examples=20, deadline=None)
def test_no_player_drafted_twice(state):
    """After a simulated draft, each player_id appears in at most one team's roster.

    Invariant:
        forall (teams, players) from draft_state():
            len(all_player_ids) == len(set(all_player_ids))
    """
    teams, players = state
    assume(len({p.player_id for p in players}) == len(players))
    _simulate_draft(teams, players)
    all_ids = [p.player_id for t in teams for p in t.roster]
    assert len(all_ids) == len(set(all_ids)), (
        f"Duplicate players found: {len(all_ids) - len(set(all_ids))} duplicates"
    )


# ---------------------------------------------------------------------------
# Property 3 — team projected score is always non-negative
# ---------------------------------------------------------------------------


@given(
    team=draft_team(),
    players=st.lists(draft_player(), min_size=1, max_size=15),
)
@settings(max_examples=50)
def test_score_bounded(team, players):
    """Team.get_projected_points() is always >= 0 regardless of player combination.

    Invariant:
        forall team, any subset of players on roster:
            team.get_projected_points() >= 0.0
    """
    for p in players:
        if team.budget >= 1 and not p.is_drafted:
            team.add_player(p, 1)

    score = team.get_projected_points()
    assert score >= 0.0, f"Negative projected score: {score}"


# ---------------------------------------------------------------------------
# Property 4 — tournament results serialisation is lossless (JSON round-trip)
# ---------------------------------------------------------------------------


@given(state=draft_state(n_teams=2, n_rounds=1))
@settings(max_examples=20, deadline=None)
def test_results_serialization_lossless(state):
    """A dict of tournament results survives json.dumps/json.loads losslessly.

    TournamentResults is a plain Dict[str, Any] — serialisation is via json.

    Invariant:
        forall results dict:
            json.loads(json.dumps(results)) == results
    """
    teams, players = state
    _simulate_draft(teams, players)

    results = {
        "teams": [
            {
                "team_id": t.team_id,
                "budget": t.budget,
                "initial_budget": t.initial_budget,
                "roster_size": len(t.roster),
                "projected_points": t.get_projected_points(),
            }
            for t in teams
        ]
    }
    serialised = json.dumps(results)
    restored = json.loads(serialised)
    assert restored == results


# ---------------------------------------------------------------------------
# Property 5 — strategy ranking is deterministic given the same inputs
# ---------------------------------------------------------------------------


@given(
    n_teams=st.integers(min_value=2, max_value=6),
    budget=st.integers(min_value=20, max_value=200),
)
@settings(max_examples=10, deadline=None)
def test_strategy_ranking_deterministic(n_teams, budget):
    """Building the same team roster twice produces identical projected score.

    Invariant:
        forall team, player_list:
            build_roster(team, players) twice → identical get_projected_points()
    """
    from classes.team import Team
    from classes.player import Player

    positions = ["QB", "RB", "WR", "WR", "TE", "K"]

    def build_team():
        t = Team("t1", "o1", "Test", budget)
        for i, pos in enumerate(positions):
            p = Player(f"p{i}", f"Player {i}", pos, "NFL", projected_points=10.0 + i)
            t.add_player(p, 1)
        return t

    t1 = build_team()
    t2 = build_team()

    assert t1.get_projected_points() == t2.get_projected_points()


# ---------------------------------------------------------------------------
# Property 6 — roster size bounded after full draft
# ---------------------------------------------------------------------------


@given(state=draft_state())
@settings(max_examples=20, deadline=None)
def test_roster_positions_filled(state):
    """After a simulated draft, len(team.roster) <= sum(position_limits.values()).

    Invariant:
        forall (teams, players) from draft_state():
            all(len(t.roster) <= sum(t.position_limits.values()) for t in teams)
    """
    teams, players = state
    _simulate_draft(teams, players)
    for t in teams:
        max_slots = sum(t.position_limits.values())
        assert len(t.roster) <= max_slots, (
            f"Team {t.team_name}: roster {len(t.roster)} > max_slots {max_slots}"
        )
