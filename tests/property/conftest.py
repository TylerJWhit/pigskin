"""Shared Hypothesis composite strategies and settings profiles.

All tests/property/ modules import from here. The composite strategies
(draft_player, draft_team, draft_state) are the building blocks used
across every track (B–E).

Hypothesis settings profiles
------------------------------
* ``ci``      – max_examples=50, deadline=None  (used in GitHub Actions)
* ``dev``     – max_examples=200, deadline=None (local full runs)
* ``default`` – max_examples=100               (fallback)

Set the active profile via the HYPOTHESIS_PROFILE environment variable.
CI workflow sets ``HYPOTHESIS_PROFILE=ci``.
"""

from __future__ import annotations

import os

from hypothesis import HealthCheck, settings
from hypothesis import strategies as st

from classes.player import Player
from classes.team import Team

# ---------------------------------------------------------------------------
# Settings profiles
# ---------------------------------------------------------------------------
settings.register_profile(
    "ci",
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "dev",
    max_examples=200,
    deadline=None,
)
settings.register_profile(
    "default",
    max_examples=100,
    deadline=None,
)

settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

# ---------------------------------------------------------------------------
# Reusable constants
# ---------------------------------------------------------------------------
_POSITIONS = ["QB", "RB", "WR", "TE", "K", "DST"]

_ALPHANUM = st.characters(whitelist_categories=["Lu", "Ll", "Nd"])
_LETTERS_SPACE = st.characters(
    whitelist_categories=["Lu", "Ll"], whitelist_characters=" "
)
_UPPERCASE = st.characters(whitelist_categories=["Lu"])


# ---------------------------------------------------------------------------
# Composite strategies
# ---------------------------------------------------------------------------


@st.composite
def draft_player(draw, position: str | None = None) -> Player:
    """Generate a valid Player with plausible fantasy-football values.

    Args:
        position: Force a specific position string; drawn randomly if None.

    Returns:
        A Player instance with non-negative projected_points and auction_value.
    """
    pos = position or draw(st.sampled_from(_POSITIONS))
    player_id = draw(st.text(min_size=1, max_size=20, alphabet=_ALPHANUM))
    name = draw(
        st.text(min_size=1, max_size=40, alphabet=_LETTERS_SPACE).filter(
            lambda n: n.strip() != ""
        )
    )
    team_abbr = draw(st.text(min_size=2, max_size=4, alphabet=_UPPERCASE))
    projected = draw(
        st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False)
    )
    auction_val = draw(
        st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False)
    )
    return Player(
        player_id=player_id,
        name=name,
        position=pos,
        nfl_team=team_abbr,
        projected_points=projected,
        auction_value=auction_val,
    )


@st.composite
def draft_team(draw, budget: int | None = None) -> Team:
    """Generate a valid Team with a given or randomly drawn integer budget.

    Args:
        budget: Fixed budget; drawn from [10, 500] if None.

    Returns:
        A Team instance with a positive budget and empty roster.
    """
    b = budget if budget is not None else draw(st.integers(min_value=10, max_value=500))
    team_id = draw(st.text(min_size=1, max_size=20, alphabet=_ALPHANUM))
    owner_id = draw(st.text(min_size=1, max_size=20, alphabet=_ALPHANUM))
    team_name = draw(
        st.text(min_size=1, max_size=40, alphabet=_LETTERS_SPACE).filter(
            lambda n: n.strip() != ""
        )
    )
    return Team(
        team_id=team_id,
        owner_id=owner_id,
        team_name=team_name,
        budget=b,
    )


@st.composite
def draft_state(
    draw,
    n_teams: int | None = None,
    n_rounds: int | None = None,
) -> tuple[list[Team], list[Player]]:
    """Generate a plausible draft state as (teams, player_pool).

    The player pool contains 3× as many players as roster slots to allow
    realistic simulation tests without exhausting the supply.

    Args:
        n_teams:  Number of teams; drawn from [2, 12] if None.
        n_rounds: Rounds (≈ roster depth); drawn from [1, 5] if None.

    Returns:
        Tuple of (List[Team], List[Player]).
    """
    num_teams = n_teams or draw(st.integers(min_value=2, max_value=12))
    num_rounds = n_rounds or draw(st.integers(min_value=1, max_value=5))
    budget = draw(st.integers(min_value=num_rounds * 2, max_value=300))

    teams = [
        Team(
            team_id=f"team_{i}",
            owner_id=f"owner_{i}",
            team_name=f"Team {i}",
            budget=budget,
        )
        for i in range(num_teams)
    ]

    n_players = num_teams * num_rounds * 3
    players = draw(
        st.lists(draft_player(), min_size=n_players, max_size=n_players)
    )

    return teams, players
