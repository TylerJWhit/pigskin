"""Failing tests for strategy registration — acceptance criteria for issues #151 and #153.

Issue #151: InflationAwareVorStrategy must be registered under the canonical key
            'inflation_aware_vor' in AVAILABLE_STRATEGIES (currently 'inflation_vor').

Issue #153: InflationAwareVorStrategy._calculate_inflation_factor() hard-codes
            standard_budget_per_slot = 200 / 15, which breaks non-standard leagues.
            The constructor must accept `budget` and `roster_size` parameters and
            use them in the inflation calculation.
"""

from unittest.mock import MagicMock

from strategies import AVAILABLE_STRATEGIES, create_strategy
from strategies.enhanced_vor_strategy import InflationAwareVorStrategy


# ---------------------------------------------------------------------------
# Issue #151 — Registration key
# ---------------------------------------------------------------------------

class TestInflationAwareVorStrategyRegistration:
    """InflationAwareVorStrategy must be accessible as 'inflation_aware_vor'."""

    def test_inflation_aware_vor_key_in_available_strategies(self):
        """'inflation_aware_vor' must be a key in AVAILABLE_STRATEGIES (issue #151).

        Currently the key is 'inflation_vor', so this test fails.
        """
        assert "inflation_aware_vor" in AVAILABLE_STRATEGIES, (
            "'inflation_aware_vor' is not registered in AVAILABLE_STRATEGIES.  "
            f"Current keys: {list(AVAILABLE_STRATEGIES.keys())}"
        )

    def test_create_strategy_returns_inflation_aware_vor_instance(self):
        """create_strategy('inflation_aware_vor') must return an InflationAwareVorStrategy."""
        strategy = create_strategy("inflation_aware_vor")
        assert isinstance(strategy, InflationAwareVorStrategy), (
            f"Expected InflationAwareVorStrategy, got {type(strategy)}"
        )

    def test_inflation_aware_vor_name_attribute(self):
        """The registered strategy instance must have name == 'inflation_aware_vor'."""
        strategy = create_strategy("inflation_aware_vor")
        assert strategy.name == "inflation_aware_vor", (
            f"Expected strategy.name='inflation_aware_vor', got '{strategy.name}'"
        )


# ---------------------------------------------------------------------------
# Issue #153 — Custom budget and roster_size
# ---------------------------------------------------------------------------

class TestInflationAwareVorStrategyCustomBudget:
    """InflationAwareVorStrategy must accept and use custom budget / roster_size.

    The hard-coded `standard_budget_per_slot = 200 / 15` inside
    _calculate_inflation_factor() must be replaced by values derived from the
    constructor arguments `budget` and `roster_size`.
    """

    def test_constructor_accepts_budget_kwarg(self):
        """InflationAwareVorStrategy(budget=100) must not raise TypeError (issue #153)."""
        strategy = InflationAwareVorStrategy(budget=100)
        assert strategy is not None

    def test_constructor_accepts_roster_size_kwarg(self):
        """InflationAwareVorStrategy(roster_size=20) must not raise TypeError (issue #153)."""
        strategy = InflationAwareVorStrategy(roster_size=20)
        assert strategy is not None

    def test_constructor_stores_budget(self):
        """Constructed instance must expose the custom budget."""
        strategy = InflationAwareVorStrategy(budget=100, roster_size=20)
        assert strategy.budget == 100

    def test_constructor_stores_roster_size(self):
        """Constructed instance must expose the custom roster_size."""
        strategy = InflationAwareVorStrategy(budget=100, roster_size=20)
        assert strategy.roster_size == 20

    def test_inflation_factor_uses_custom_budget_and_roster_size(self):
        """_calculate_inflation_factor() must use instance budget/roster_size, not 200/15.

        With budget=100 and roster_size=10 the standard_budget_per_slot is 10.0.
        With budget=200 and roster_size=15 the standard_budget_per_slot is ~13.33.
        The two instances must produce different inflation factors when given the
        same team situation, proving the calculation is parameterised.
        """
        # Two teams, each with $50 remaining and 5 roster slots left.
        def _make_team(remaining_budget: float, roster_size: int):
            team = MagicMock()
            team.budget = remaining_budget
            team.roster = [MagicMock()] * (roster_size - 5)  # 5 slots still open
            return team

        strategy_small = InflationAwareVorStrategy(budget=100, roster_size=10)
        strategy_standard = InflationAwareVorStrategy(budget=200, roster_size=15)

        teams = [_make_team(50, 10), _make_team(50, 10)]
        remaining = []  # not used in the inflation calc itself

        factor_small = strategy_small._calculate_inflation_factor(teams, remaining)
        factor_standard = strategy_standard._calculate_inflation_factor(teams, remaining)

        assert factor_small != factor_standard, (
            "Inflation factors are identical despite different budget/roster_size "
            "configurations — the hardcoded 200/15 constant has not been removed."
        )

    def test_default_budget_and_roster_size_match_standard_league(self):
        """Default InflationAwareVorStrategy() must default to budget=200, roster_size=15."""
        strategy = InflationAwareVorStrategy()
        assert strategy.budget == 200
        assert strategy.roster_size == 15
