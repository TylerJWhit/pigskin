"""Shared pytest fixtures for the pigskin test suite.

Provides common Player, Team, Owner, and Draft fixtures to reduce
boilerplate duplication across test files.
"""
import os

# Mark this process as a test environment so create_app() does not raise
# RuntimeError for a missing PIGSKIN_API_KEY (see api/main.py).
os.environ.setdefault("TESTING", "true")

import pytest

from classes.player import Player
from classes.team import Team
from classes.owner import Owner
from classes.draft import Draft


@pytest.fixture
def sample_player():
    """A single standard RB player."""
    return Player("player_1", "Test Player", "RB", "SEA", projected_points=150.0, auction_value=20.0)


@pytest.fixture
def sample_players():
    """A minimal set of players covering all common positions."""
    return [
        Player("qb1", "Josh Allen", "QB", "BUF", 350.0, 45.0, 12),
        Player("rb1", "Christian McCaffrey", "RB", "SF", 320.0, 65.0, 9),
        Player("rb2", "Austin Ekeler", "RB", "LAC", 270.0, 45.0, 7),
        Player("rb3", "Derrick Henry", "RB", "TEN", 250.0, 38.0, 6),
        Player("rb4", "Saquon Barkley", "RB", "NYG", 265.0, 42.0, 13),
        Player("wr1", "Cooper Kupp", "WR", "LAR", 290.0, 58.0, 7),
        Player("wr2", "Davante Adams", "WR", "LV", 280.0, 55.0, 6),
        Player("wr3", "Tyreek Hill", "WR", "MIA", 275.0, 52.0, 10),
        Player("te1", "Travis Kelce", "TE", "KC", 220.0, 38.0, 10),
        Player("k1", "Justin Tucker", "K", "BAL", 130.0, 5.0, 14),
        Player("dst1", "Bills Defense", "DST", "BUF", 120.0, 8.0, 12),
    ]


@pytest.fixture
def sample_team():
    """A single team with standard budget."""
    return Team("team_1", "owner_1", "Test Team", 200)


@pytest.fixture
def sample_teams():
    """Two teams for testing interactions."""
    return [
        Team("team_1", "owner_1", "Team Alpha", 200),
        Team("team_2", "owner_2", "Team Beta", 200),
    ]


@pytest.fixture
def sample_owner():
    """A single owner."""
    return Owner("owner_1", "Test Owner")


@pytest.fixture
def sample_owners():
    """Two owners for testing."""
    return [
        Owner("owner_1", "Alice"),
        Owner("owner_2", "Bob"),
    ]


@pytest.fixture
def configured_draft(sample_teams, sample_owners, sample_players):
    """A fully configured Draft with teams, owners, and players."""
    draft = Draft(draft_id="test-draft-001", name="Test Draft", budget_per_team=200.0)
    for team in sample_teams:
        draft.add_team(team)
    for owner in sample_owners:
        draft.add_owner(owner)
    draft.add_players(sample_players)
    return draft


@pytest.fixture
def standard_roster_config():
    """Standard 10-team fantasy football roster configuration."""
    return {
        "QB": 1,
        "RB": 2,
        "WR": 3,
        "TE": 1,
        "K": 1,
        "DST": 1,
    }
