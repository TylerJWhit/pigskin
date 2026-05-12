"""Property-based tests: config round-trip invariants.

Track D — Issue #317

Sprint 10 · sprint/10 branch
"""

from hypothesis import given, settings
from hypothesis import strategies as st


_ROSTER_POSITIONS = st.fixed_dictionaries(
    {
        "QB": st.integers(min_value=1, max_value=3),
        "RB": st.integers(min_value=2, max_value=8),
        "WR": st.integers(min_value=2, max_value=8),
        "TE": st.integers(min_value=1, max_value=3),
        "K": st.integers(min_value=0, max_value=2),
        "DST": st.integers(min_value=0, max_value=2),
        "FLEX": st.integers(min_value=0, max_value=4),
        "BENCH": st.integers(min_value=0, max_value=8),
    }
)

_draft_config_kwargs = st.fixed_dictionaries(
    {
        "budget": st.integers(min_value=1, max_value=1000),
        "num_teams": st.integers(min_value=2, max_value=20),
        "strategy_type": st.sampled_from(["value", "vor", "aggressive", "conservative"]),
        "refresh_interval": st.integers(min_value=5, max_value=300),
        "roster_positions": _ROSTER_POSITIONS,
    }
)


@given(kwargs=_draft_config_kwargs)
@settings(max_examples=50)
def test_draft_config_round_trip(kwargs):
    """DraftConfig.from_dict(cfg.to_dict()) equals cfg field-by-field.

    Invariant:
        forall valid DraftConfig cfg:
            DraftConfig.from_dict(cfg.to_dict()).budget == cfg.budget
            and all other scalar fields match
    """
    from config.config_manager import DraftConfig

    cfg = DraftConfig(**kwargs)
    d = cfg.to_dict()
    restored = DraftConfig.from_dict(d)

    assert restored.budget == cfg.budget
    assert restored.num_teams == cfg.num_teams
    assert restored.strategy_type == cfg.strategy_type
    assert restored.refresh_interval == cfg.refresh_interval
    assert restored.roster_positions == cfg.roster_positions


@given(n_calls=st.integers(min_value=2, max_value=10))
@settings(max_examples=20)
def test_settings_immutable_after_init(n_calls):
    """Calling get_settings() N times always returns the same cached object (is).

    Invariant:
        forall n >= 2:
            all get_settings() calls return the same object by identity
    """
    from config.settings import get_settings

    first = get_settings()
    for _ in range(n_calls - 1):
        assert get_settings() is first


@given(kwargs=_draft_config_kwargs)
@settings(max_examples=50)
def test_config_budget_non_negative(kwargs):
    """Any valid DraftConfig always has budget > 0.

    Invariant:
        forall valid DraftConfig cfg:  cfg.budget > 0
    """
    from config.config_manager import DraftConfig

    cfg = DraftConfig(**kwargs)
    assert cfg.budget > 0


@given(kwargs=_draft_config_kwargs)
@settings(max_examples=50)
def test_config_team_count_positive(kwargs):
    """Any valid DraftConfig always has num_teams >= 2.

    Invariant:
        forall valid DraftConfig cfg:  cfg.num_teams >= 2
    """
    from config.config_manager import DraftConfig

    cfg = DraftConfig(**kwargs)
    assert cfg.num_teams >= 2
