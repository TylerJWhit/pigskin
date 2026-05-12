"""Property-based tests: DraftSetup — bidirectionality and participant invariants.

Track F — Issue #330

Sprint 10 · sprint/10 branch
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from classes.draft_setup import DraftSetup
from tests.property.conftest import _ALPHANUM, _LETTERS_SPACE


# ---------------------------------------------------------------------------
# Composite strategy for participant dicts
# ---------------------------------------------------------------------------

@st.composite
def participant_dict(draw, owner_id: str | None = None) -> dict:
    oid = owner_id or draw(st.text(min_size=1, max_size=16, alphabet=_ALPHANUM))
    name = draw(
        st.text(min_size=1, max_size=40, alphabet=_LETTERS_SPACE).filter(
            lambda n: n.strip() != ""
        )
    )
    team_name = draw(
        st.text(min_size=1, max_size=40, alphabet=_LETTERS_SPACE).filter(
            lambda n: n.strip() != ""
        )
    )
    return {"owner_id": oid, "owner_name": name, "team_name": team_name}


@st.composite
def participant_list(draw, min_size: int = 2, max_size: int = 8) -> list[dict]:
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    ids = draw(
        st.lists(
            st.text(min_size=1, max_size=16, alphabet=_ALPHANUM),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    parts = []
    for oid in ids:
        parts.append(draw(participant_dict(owner_id=oid)))
    return parts


# ---------------------------------------------------------------------------
# Property 1 — create_owner_with_team establishes bidirectionality
# ---------------------------------------------------------------------------

@given(
    owner_id=st.text(min_size=1, max_size=16, alphabet=_ALPHANUM),
    budget=st.floats(min_value=10.0, max_value=500.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50)
def test_create_owner_with_team_bidirectionality(owner_id, budget):
    """After create_owner_with_team, owner.get_team() is the created team."""
    owner, team = DraftSetup.create_owner_with_team(
        owner_id=owner_id,
        owner_name="Test Owner",
        team_name="Test Team",
        budget=budget,
    )

    assert owner.get_team() is team
    assert owner.has_team() is True
    assert team.owner_id == owner.owner_id


# ---------------------------------------------------------------------------
# Property 2 — all teams initialized with the given budget
# ---------------------------------------------------------------------------

@given(
    n_participants=st.integers(min_value=2, max_value=8),
    budget=st.integers(min_value=10, max_value=500),
)
@settings(max_examples=50)
def test_all_teams_get_same_budget(n_participants, budget):
    """Every team in the returned draft has budget == budget_per_team.

    Team.budget is stored as int, so we use integer budgets here to
    avoid implicit truncation masking the actual budget value.
    """
    participants = [
        {"owner_id": f"o{i}", "owner_name": f"Owner {i}", "team_name": f"Team {i}"}
        for i in range(n_participants)
    ]
    draft = DraftSetup.setup_draft_with_participants(
        draft_name="test",
        participants=participants,
        budget_per_team=float(budget),
    )

    for team in draft.teams:
        assert team.budget == budget
        assert team.initial_budget == budget


# ---------------------------------------------------------------------------
# Property 3 — no duplicate owner_ids in the returned draft
# ---------------------------------------------------------------------------

@given(n_participants=st.integers(min_value=2, max_value=10))
@settings(max_examples=50)
def test_no_duplicate_owner_ids(n_participants):
    """setup_draft_with_participants never produces duplicate owner_ids."""
    participants = [
        {"owner_id": f"owner_{i}", "owner_name": f"Name {i}", "team_name": f"Team {i}"}
        for i in range(n_participants)
    ]
    draft = DraftSetup.setup_draft_with_participants(
        draft_name="test",
        participants=participants,
    )

    owner_ids = [o.owner_id for o in draft.owners]
    assert len(owner_ids) == len(set(owner_ids))


# ---------------------------------------------------------------------------
# Property 4 — owner_id matches between owner and team for every participant
# ---------------------------------------------------------------------------

@given(n_participants=st.integers(min_value=2, max_value=8))
@settings(max_examples=50)
def test_owner_team_id_consistency(n_participants):
    """For every owner in the draft, the linked team has matching owner_id."""
    participants = [
        {"owner_id": f"owner_{i}", "owner_name": f"Name {i}", "team_name": f"Team {i}"}
        for i in range(n_participants)
    ]
    draft = DraftSetup.setup_draft_with_participants(
        draft_name="test",
        participants=participants,
    )

    for owner in draft.owners:
        if owner.has_team():
            assert owner.get_team().owner_id == owner.owner_id


# ---------------------------------------------------------------------------
# Property 5 — budget preserved through create_owner_with_team round-trip
# ---------------------------------------------------------------------------

@given(
    owner_id=st.text(min_size=1, max_size=16, alphabet=_ALPHANUM),
    budget=st.integers(min_value=10, max_value=1000),
)
@settings(max_examples=50)
def test_budget_preserved(owner_id, budget):
    """The team returned by create_owner_with_team has budget == supplied budget."""
    owner, team = DraftSetup.create_owner_with_team(
        owner_id=owner_id,
        owner_name="Owner",
        team_name="Team",
        budget=float(budget),
    )
    assert team.budget == float(budget)
    assert team.initial_budget == float(budget)
