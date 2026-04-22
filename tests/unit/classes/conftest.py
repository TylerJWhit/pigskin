"""Shared fixtures for unit tests in tests/unit/classes/."""

import pytest
from classes.draft import Draft
from classes.team import Team
from classes.owner import Owner
from classes.player import Player


@pytest.fixture
def sample_players():
    """A minimal set of players covering all positions."""
    return [
        Player("qb1", "Josh Allen", "QB", "BUF", 350.0, 45.0, 12),
        Player("qb2", "Lamar Jackson", "QB", "BAL", 340.0, 43.0, 14),
        Player("rb1", "Christian McCaffrey", "RB", "SF", 320.0, 65.0, 9),
        Player("rb2", "Austin Ekeler", "RB", "LAC", 270.0, 45.0, 7),
        Player("rb3", "Derrick Henry", "RB", "TEN", 250.0, 38.0, 6),
        Player("rb4", "Saquon Barkley", "RB", "NYG", 265.0, 42.0, 13),
        Player("wr1", "Cooper Kupp", "WR", "LAR", 290.0, 58.0, 7),
        Player("wr2", "Davante Adams", "WR", "LV", 280.0, 55.0, 6),
        Player("wr3", "Tyreek Hill", "WR", "MIA", 275.0, 52.0, 10),
        Player("wr4", "Stefon Diggs", "WR", "BUF", 260.0, 48.0, 12),
        Player("te1", "Travis Kelce", "TE", "KC", 220.0, 38.0, 10),
        Player("te2", "Mark Andrews", "TE", "BAL", 200.0, 30.0, 14),
        Player("k1", "Justin Tucker", "K", "BAL", 130.0, 5.0, 14),
        Player("dst1", "Bills Defense", "DST", "BUF", 120.0, 8.0, 12),
    ]


@pytest.fixture
def sample_teams():
    """Two basic teams for testing."""
    return [
        Team("team1", "owner1", "Team Alpha", 200),
        Team("team2", "owner2", "Team Beta", 200),
    ]


@pytest.fixture
def sample_owners():
    """Three owners for testing."""
    return [
        Owner("owner1", "Alice"),
        Owner("owner2", "Bob"),
        Owner("owner3", "Carol"),
    ]


@pytest.fixture
def configured_draft(sample_teams, sample_owners, sample_players):
    """A fully configured draft with teams, owners, and players added."""
    draft = Draft(draft_id="test-draft-001", name="Test Draft", budget_per_team=200.0)
    for team in sample_teams:
        draft.add_team(team)
    for owner in sample_owners[:2]:
        draft.add_owner(owner)
    draft.add_players(sample_players)
    return draft


@pytest.fixture
def standard_roster_config():
    """Standard fantasy football roster configuration."""
    return {
        "QB": 2,
        "RB": 6,
        "WR": 6,
        "TE": 2,
        "K": 1,
        "DST": 1,
        "FLEX": 2,
    }


@pytest.fixture
def comprehensive_players():
    """Comprehensive player list (40+) indexed for realistic scenario tests.

    Indices used in test_team.py::test_team_in_realistic_auction_scenario:
      [4]  = QB (Burrow), [16] = RB (Kamara), [17] = RB (Jacobs),
      [25] = WR (Evans), [26] = WR (Hopkins), [33] = TE (Andrews)
    """
    players = []
    # QBs indices 0-9
    qb_data = [
        ("qb_a1", "Patrick Mahomes", "BUF", 380.0, 52.0, 10),
        ("qb_a2", "Josh Allen", "BUF", 360.0, 48.0, 12),
        ("qb_a3", "Lamar Jackson", "BAL", 355.0, 46.0, 14),
        ("qb_a4", "Justin Herbert", "LAC", 330.0, 38.0, 7),
        ("qb_a5", "Joe Burrow", "CIN", 325.0, 36.0, 10),  # index 4
        ("qb_a6", "Jalen Hurts", "PHI", 320.0, 35.0, 5),
        ("qb_a7", "Kyler Murray", "ARI", 300.0, 30.0, 13),
        ("qb_a8", "Dak Prescott", "DAL", 295.0, 28.0, 9),
        ("qb_a9", "Tua Tagovailoa", "MIA", 280.0, 25.0, 10),
        ("qb_a10", "Trevor Lawrence", "JAX", 270.0, 22.0, 11),
    ]
    for pid, name, team, pts, val, bye in qb_data:
        players.append(Player(pid, name, "QB", team, pts, val, bye))

    # RBs indices 10-19
    rb_data = [
        ("rb_a1", "Christian McCaffrey", "SF", 340.0, 70.0, 9),
        ("rb_a2", "Austin Ekeler", "LAC", 290.0, 52.0, 7),
        ("rb_a3", "Derrick Henry", "TEN", 275.0, 46.0, 6),
        ("rb_a4", "Saquon Barkley", "NYG", 270.0, 44.0, 13),
        ("rb_a5", "Tony Pollard", "DAL", 260.0, 40.0, 9),
        ("rb_a6", "Josh Jacobs", "LV", 255.0, 38.0, 6),
        ("rb_a7", "Alvin Kamara", "NO", 250.0, 36.0, 11),  # index 16
        ("rb_a8", "Josh Jacobs2", "LV", 245.0, 34.0, 6),   # index 17
        ("rb_a9", "Dameon Pierce", "HOU", 235.0, 30.0, 7),
        ("rb_a10", "Miles Sanders", "PHI", 225.0, 26.0, 5),
    ]
    for pid, name, team, pts, val, bye in rb_data:
        players.append(Player(pid, name, "RB", team, pts, val, bye))

    # WRs indices 20-29
    wr_data = [
        ("wr_a1", "Cooper Kupp", "LAR", 310.0, 62.0, 7),
        ("wr_a2", "Davante Adams", "LV", 295.0, 58.0, 6),
        ("wr_a3", "Tyreek Hill", "MIA", 290.0, 55.0, 10),
        ("wr_a4", "Stefon Diggs", "BUF", 280.0, 52.0, 12),
        ("wr_a5", "DeAndre Hopkins", "ARI", 265.0, 46.0, 13),
        ("wr_a6", "Mike Evans", "TB", 260.0, 44.0, 11),    # index 25
        ("wr_a7", "DeAndre Hopkins2", "ARI", 255.0, 42.0, 13),  # index 26
        ("wr_a8", "CeeDee Lamb", "DAL", 250.0, 40.0, 9),
        ("wr_a9", "DK Metcalf", "SEA", 245.0, 38.0, 11),
        ("wr_a10", "Terry McLaurin", "WAS", 235.0, 34.0, 14),
    ]
    for pid, name, team, pts, val, bye in wr_data:
        players.append(Player(pid, name, "WR", team, pts, val, bye))

    # TEs indices 30-39
    te_data = [
        ("te_a1", "Travis Kelce", "KC", 240.0, 42.0, 10),
        ("te_a2", "Mark Andrews", "BAL", 220.0, 36.0, 14),
        ("te_a3", "T.J. Hockenson", "MIN", 200.0, 30.0, 13),
        ("te_a4", "Kyle Pitts", "ATL", 195.0, 28.0, 11),
        ("te_a5", "Dalton Schultz", "DAL", 180.0, 22.0, 9),
        ("te_a6", "Pat Freiermuth", "PIT", 175.0, 20.0, 9),
        ("te_a7", "Cole Kmet", "CHI", 170.0, 18.0, 14),
        ("te_a8", "Mark Andrews2", "BAL", 165.0, 16.0, 14),  # index 33
        ("te_a9", "Dawson Knox", "BUF", 160.0, 14.0, 12),
        ("te_a10", "Mike Gesicki", "MIA", 155.0, 12.0, 10),
    ]
    for pid, name, team, pts, val, bye in te_data:
        players.append(Player(pid, name, "TE", team, pts, val, bye))

    # Ks and DSTs indices 40+
    players.append(Player("k_a1", "Justin Tucker", "K", "BAL", 140.0, 6.0, 14))
    players.append(Player("k_a2", "Evan McPherson", "K", "CIN", 130.0, 5.0, 10))
    players.append(Player("dst_a1", "Bills Defense", "DST", "BUF", 130.0, 9.0, 12))
    players.append(Player("dst_a2", "Cowboys Defense", "DST", "DAL", 120.0, 7.0, 9))

    return players
