"""Property-based tests: Owner class invariants.

Track F — Issue #327

Sprint 10 · sprint/10 branch
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from classes.owner import Owner
from tests.property.conftest import draft_team, _ALPHANUM, _LETTERS_SPACE


# ---------------------------------------------------------------------------
# Composite strategy for Owner instances
# ---------------------------------------------------------------------------

@st.composite
def draft_owner(draw, owner_id: str | None = None) -> Owner:
    """Generate a valid Owner with a random id and name."""
    oid = owner_id or draw(st.text(min_size=1, max_size=20, alphabet=_ALPHANUM))
    name = draw(
        st.text(min_size=1, max_size=40, alphabet=_LETTERS_SPACE).filter(
            lambda n: n.strip() != ""
        )
    )
    return Owner(owner_id=oid, name=name)


# ---------------------------------------------------------------------------
# Property 1 — target player deduplication
# ---------------------------------------------------------------------------

@given(owner=draft_owner(), player_id=st.text(min_size=1, max_size=20, alphabet=_ALPHANUM))
@settings(max_examples=50)
def test_add_target_player_deduplication(owner, player_id):
    """Adding the same player_id twice yields exactly one entry in target_players."""
    owner.add_target_player(player_id)
    owner.add_target_player(player_id)

    targets = owner.preferences["target_players"]
    assert targets.count(player_id) == 1


# ---------------------------------------------------------------------------
# Property 2 — avoid player deduplication
# ---------------------------------------------------------------------------

@given(owner=draft_owner(), player_id=st.text(min_size=1, max_size=20, alphabet=_ALPHANUM))
@settings(max_examples=50)
def test_add_avoid_player_deduplication(owner, player_id):
    """Adding the same player_id twice yields exactly one entry in avoid_players."""
    owner.add_avoid_player(player_id)
    owner.add_avoid_player(player_id)

    avoids = owner.preferences["avoid_players"]
    assert avoids.count(player_id) == 1


# ---------------------------------------------------------------------------
# Property 3 — risk tolerance bounds
# ---------------------------------------------------------------------------

@given(
    owner=draft_owner(),
    risk=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50)
def test_risk_tolerance_bounds(owner, risk):
    """get_risk_tolerance() always returns a value in [0.0, 1.0] after update."""
    owner.update_preferences(risk_tolerance=risk)
    result = owner.get_risk_tolerance()
    assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# Property 4 — draft history append-only
# ---------------------------------------------------------------------------

@given(
    owner=draft_owner(),
    n_actions=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=50)
def test_draft_history_append_only(owner, n_actions):
    """Each add_draft_action() appends exactly one entry; history never shrinks."""
    for i in range(n_actions):
        before = len(owner.draft_history)
        owner.add_draft_action({"action": "bid", "round": i})
        assert len(owner.draft_history) == before + 1


# ---------------------------------------------------------------------------
# Property 5 — owner↔team bidirectionality
# ---------------------------------------------------------------------------

@given(owner=draft_owner(), team=draft_team())
@settings(max_examples=50)
def test_assign_team_bidirectionality(owner, team):
    """After assign_team(t), owner.get_team() is t."""
    owner.assign_team(team)

    assert owner.get_team() is team
    assert owner.has_team() is True


# ---------------------------------------------------------------------------
# Property 6 — preference persistence across multiple reads
# ---------------------------------------------------------------------------

@given(
    owner=draft_owner(),
    max_bid_pct=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    n_reads=st.integers(min_value=2, max_value=10),
)
@settings(max_examples=50)
def test_preference_persistence(owner, max_bid_pct, n_reads):
    """update_preferences(max_bid_percentage=v) survives multiple reads."""
    owner.update_preferences(max_bid_percentage=max_bid_pct)
    for _ in range(n_reads):
        assert owner.get_max_bid_percentage() == max_bid_pct


# ---------------------------------------------------------------------------
# Property 7 — target/avoid lists are mutually independent
# ---------------------------------------------------------------------------

@given(
    owner=draft_owner(),
    player_id=st.text(min_size=1, max_size=20, alphabet=_ALPHANUM),
)
@settings(max_examples=50)
def test_target_avoid_independence(owner, player_id):
    """Adding a player to targets does not add them to avoids, and vice versa."""
    owner.add_target_player(player_id)
    assert not owner.is_avoid_player(player_id)

    owner2 = Owner(owner_id="o2", name="Other")
    owner2.add_avoid_player(player_id)
    assert not owner2.is_target_player(player_id)
