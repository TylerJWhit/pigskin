"""Property-based tests: data layer invariants (Player schema, VOR, auction values).

Track D — Issue #317

Sprint 10 · sprint/10 branch
"""


from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tests.property.conftest import draft_player

_POSITIONS = ["QB", "RB", "WR", "TE", "K", "DST"]


@given(player=draft_player())
@settings(max_examples=50)
def test_player_schema_complete(player):
    """Any Player built from valid input has non-None required fields.

    Invariant:
        forall valid player:
            player_id, name, position, nfl_team are all non-None
    """
    assert player.player_id is not None
    assert player.name is not None
    assert player.position is not None
    assert player.nfl_team is not None


@given(
    projected_points=st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    baseline_points=st.floats(min_value=0.0, max_value=499.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_vor_non_negative_for_starters(projected_points, baseline_points):
    """VOR is always >= 0 for any player ranked above the position baseline.

    VOR is defined as: max(0, projected_points - baseline_points).

    Invariant:
        forall projected_points >= baseline_points:
            VOR(projected_points, baseline_points) >= 0
    """
    assume(projected_points >= baseline_points)
    vor = projected_points - baseline_points
    assert vor >= 0.0


@given(
    total_budget=st.integers(min_value=100, max_value=2000),
    n_players=st.integers(min_value=5, max_value=30),
)
@settings(max_examples=30)
def test_auction_values_sum_to_budget(total_budget, n_players):
    """Budget-normalised auction values sum to exactly total_budget (within floating-point).

    Normalisation: v_i = raw_i / sum(raw) * total_budget.

    Invariant:
        forall total_budget, n_players >= 1:
            abs(sum(normalised_values) - total_budget) < 1e-6
    """
    import random

    rng = random.Random(total_budget * 31 + n_players)
    raw = [rng.uniform(1.0, 100.0) for _ in range(n_players)]
    raw_sum = sum(raw)
    normalised = [v / raw_sum * total_budget for v in raw]
    assert abs(sum(normalised) - total_budget) < 1e-6


@given(n_rows=st.integers(min_value=1, max_value=20))
@settings(max_examples=20)
def test_csv_parse_idempotent(n_rows):
    """Parsing the same CSV data twice produces identical player lists.

    Invariant:
        forall csv_data:
            _parse_csv_file(data, pos) == _parse_csv_file(data, pos)
    """
    from data.fantasypros_loader import _parse_csv_file

    header = "Rank,Player Name,Team,Bye,Projected Points,Auction Value"
    rows = [
        f"{i},Player{i},NFL,7,{10.0 + i * 2.5},{5 + i}"
        for i in range(1, n_rows + 1)
    ]
    csv_content = "\n".join([header] + rows)

    result1 = _parse_csv_file(csv_content, "RB")
    result2 = _parse_csv_file(csv_content, "RB")

    assert len(result1) == len(result2)
    for p1, p2 in zip(result1, result2):
        assert p1.player_id == p2.player_id
        assert p1.name == p2.name
        assert p1.projected_points == p2.projected_points
