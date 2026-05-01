"""Sprint 7 — QA Agent Phase 1 regression tests.

Issue #116 — classes/tournament.py:
    Single strategy instance shared across multiple teams in _run_single_simulation.
    Mutable strategy state clobbered by interleaved calls from different teams.

Issue #113 — classes/tournament.py:
    Tournament.get_strategy_rankings() divides by zero when only one
    strategy config is present (len(self.strategy_configs) - 1 == 0).

Issue #132 — services/tournament_service.py:
    _analyze_tournament_results raises KeyError when a strategy's results dict
    does not contain 'points_std' (e.g. a strategy that completed zero
    simulations, so the key was never populated).

Issue #144 — strategies/base_strategy.py:
    __init_subclass__ wraps calculate_bid but the wrapper does not forward
    **kwargs to the original implementation.  Strategies that accept extra
    keyword arguments (e.g. InflationAwareVorStrategy) silently lose them.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classes.player import Player
from classes.tournament import Tournament


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

def _make_players(n: int = 30) -> list:
    positions = ["QB", "RB", "WR", "TE"]
    return [
        Player(
            player_id=f"p{i}",
            name=f"Player {i}",
            position=positions[i % len(positions)],
            team="XX",
            projected_points=float(300 - i),
            auction_value=float(60 - i),
        )
        for i in range(n)
    ]


def _make_tournament(num_simulations: int = 1, budget: float = 200.0) -> Tournament:
    t = Tournament(
        name="Regression Test Tournament",
        num_simulations=num_simulations,
        budget_per_team=budget,
        roster_size=9,
    )
    t.add_players(_make_players(30))
    return t


# ---------------------------------------------------------------------------
# #116 — Independent strategy instances per team
# ---------------------------------------------------------------------------

class TestIndependentStrategyInstances(unittest.TestCase):
    """Regression tests for #116.

    Each team in a simulation must receive its OWN strategy instance so
    that mutable state on one team cannot corrupt another team's decisions.
    """

    def test_multi_team_config_produces_distinct_instances(self):
        """When num_teams=2, the two teams must have different strategy object ids."""
        tournament = _make_tournament()
        tournament.add_strategy_config("basic", "Bot", num_teams=2)
        draft = tournament._run_single_simulation(0)
        self.assertIsNotNone(draft, "Simulation returned None unexpectedly")

        teams = draft.teams
        strategies = [t.strategy for t in teams if t.strategy is not None]

        self.assertGreaterEqual(len(strategies), 2, "Expected at least 2 teams with strategies")
        # All strategy ids must be distinct — no shared references
        strategy_ids = [id(s) for s in strategies]
        self.assertEqual(
            len(strategy_ids),
            len(set(strategy_ids)),
            "Two or more teams share the same strategy instance — #116 regression: "
            f"ids={strategy_ids}",
        )

    def test_strategy_state_mutation_does_not_leak_across_teams(self):
        """Mutating one team's strategy must not affect any other team's strategy."""
        tournament = _make_tournament()
        tournament.add_strategy_config("basic", "Bot", num_teams=3)
        draft = tournament._run_single_simulation(0)
        self.assertIsNotNone(draft)

        teams_with_strategies = [t for t in draft.teams if t.strategy is not None]
        self.assertGreaterEqual(len(teams_with_strategies), 2)

        # Mutate the first team's strategy
        first_strategy = teams_with_strategies[0].strategy
        first_strategy.set_parameter("_regression_marker", "team_0_only")

        # Other teams must NOT see this parameter
        for other_team in teams_with_strategies[1:]:
            marker = other_team.strategy.get_parameter("_regression_marker")
            self.assertIsNone(
                marker,
                f"Team {other_team.team_id} strategy reflects mutation from team 0 — "
                "shared strategy instance confirmed (#116 regression)",
            )


# ---------------------------------------------------------------------------
# #113 — get_strategy_rankings with single strategy config
# ---------------------------------------------------------------------------

class TestGetStrategyRankingsSingleStrategy(unittest.TestCase):
    """Regression tests for #113.

    get_strategy_rankings() must not raise ZeroDivisionError when only
    one strategy config is registered (len(strategy_configs) - 1 == 0).
    """

    def test_rankings_does_not_divide_by_zero_with_one_strategy(self):
        """get_strategy_rankings() with a single strategy must not raise ZeroDivisionError."""
        tournament = _make_tournament(num_simulations=2)
        tournament.add_strategy_config("basic", "BotA", num_teams=2)

        # Run the tournament to populate self.results
        try:
            tournament.run_tournament(parallel=False)
        except Exception:
            # If the tournament itself fails for another reason, we still want
            # to test the rankings method in isolation below
            pass

        # If results are empty (tournament failed), populate a minimal result
        # to isolate the division-by-zero path in get_strategy_rankings
        if not tournament.results:
            tournament.results["basic"] = {
                "simulations": 2,
                "wins": 1,
                "win_rate": 0.5,
                "avg_points": 400.0,
                "avg_spent": 180.0,
                "avg_remaining": 20.0,
                "avg_ranking": 1.0,
                "points_std": 10.0,
                "best_points": 450.0,
                "worst_points": 350.0,
                "median_ranking": 1.0,
            }

        try:
            rankings = tournament.get_strategy_rankings()
        except ZeroDivisionError as exc:
            self.fail(
                f"get_strategy_rankings() raised ZeroDivisionError with 1 strategy config "
                f"(#113 regression): {exc}"
            )

        self.assertIsInstance(rankings, list, "Rankings must be a list")

    def test_rankings_returns_list_for_single_strategy(self):
        """Rankings must contain the single strategy's entry."""
        tournament = _make_tournament()
        tournament.results["solo"] = {
            "simulations": 5,
            "wins": 3,
            "win_rate": 0.6,
            "avg_points": 500.0,
            "avg_spent": 190.0,
            "avg_remaining": 10.0,
            "avg_ranking": 1.0,
            "points_std": 20.0,
            "best_points": 550.0,
            "worst_points": 450.0,
            "median_ranking": 1.0,
        }
        tournament.strategy_configs = [{"strategy_type": "solo", "owner_name": "X", "num_teams": 1}]

        try:
            rankings = tournament.get_strategy_rankings()
        except ZeroDivisionError as exc:
            self.fail(f"ZeroDivisionError with single strategy (#113): {exc}")

        self.assertEqual(len(rankings), 1)
        self.assertEqual(rankings[0][0], "solo")


# ---------------------------------------------------------------------------
# #132 — _analyze_tournament_results does not raise on missing points_std
# ---------------------------------------------------------------------------

class TestAnalyzeTournamentResultsKeyError(unittest.TestCase):
    """Regression tests for #132.

    _analyze_tournament_results must not raise KeyError when a strategy's
    result dict is missing the 'points_std' key.
    """

    def _make_service_with_tournament(self, results_override: dict):
        """Return a TournamentService whose current_tournament has the given results."""
        from services.tournament_service import TournamentService
        service = TournamentService.__new__(TournamentService)
        service.current_tournament = type("FakeTournament", (), {})()

        def get_strategy_rankings():
            return [
                (name, {"composite_score": 50.0, "results": res})
                for name, res in results_override.items()
            ]

        service.current_tournament.get_strategy_rankings = get_strategy_rankings
        return service

    def test_no_keyerror_when_points_std_absent(self):
        """_analyze_tournament_results must not raise KeyError if points_std is absent."""
        from services.tournament_service import TournamentService

        # Results dict missing 'points_std' — simulates a strategy with 0 or 1 sims
        results_no_std = {
            "basic": {
                "simulations": 1,
                "wins": 1,
                "win_rate": 1.0,
                "avg_points": 400.0,
                "avg_spent": 180.0,
                "avg_remaining": 20.0,
                "avg_ranking": 1.0,
                "best_points": 400.0,
                "worst_points": 400.0,
                "median_ranking": 1.0,
                # NOTE: 'points_std' intentionally absent
            }
        }
        service = self._make_service_with_tournament(results_no_std)

        summary = {
            "completed_simulations": 1,
            "results": results_no_std,
        }

        try:
            analysis = service._analyze_tournament_results(summary)
        except KeyError as exc:
            self.fail(
                f"_analyze_tournament_results raised KeyError({exc}) "
                "when 'points_std' absent from results — #132 regression"
            )

        # most_consistent should be None or have a std_dev of 0 / float('inf')
        if analysis.get("most_consistent") is not None:
            self.assertIn(
                "std_dev",
                analysis["most_consistent"],
                "most_consistent entry must include std_dev even when original data lacked it",
            )

    def test_no_keyerror_with_normal_results(self):
        """_analyze_tournament_results must succeed with well-formed results."""
        results_full = {
            "basic": {
                "simulations": 5,
                "wins": 3,
                "win_rate": 0.6,
                "avg_points": 450.0,
                "avg_spent": 185.0,
                "avg_remaining": 15.0,
                "avg_ranking": 1.4,
                "points_std": 25.0,
                "best_points": 500.0,
                "worst_points": 400.0,
                "median_ranking": 1.0,
            }
        }
        service = self._make_service_with_tournament(results_full)

        summary = {
            "completed_simulations": 5,
            "results": results_full,
        }

        try:
            analysis = service._analyze_tournament_results(summary)
        except Exception as exc:
            self.fail(f"_analyze_tournament_results raised unexpectedly: {exc}")

        self.assertIsNotNone(analysis.get("most_consistent"))


# ---------------------------------------------------------------------------
# #144 — calculate_bid wrapper forwards **kwargs to the original method
# ---------------------------------------------------------------------------

class TestCalculateBidWrapperForwardsKwargs(unittest.TestCase):
    """Regression tests for #144.

    The __init_subclass__ wrapper around calculate_bid must forward **kwargs
    so that subclasses accepting additional keyword arguments receive them.
    """

    def _make_minimal_objects(self):
        """Return (player, team, owner) stubs sufficient for calculate_bid calls."""
        from unittest.mock import MagicMock
        player = MagicMock()
        player.position = "RB"
        player.projected_points = 200.0
        player.auction_value = 30.0

        team = MagicMock()
        team.budget = 200.0
        team.enforce_budget_constraint = None  # don't trigger constraint wrapper

        owner = MagicMock()
        return player, team, owner

    def test_inflation_aware_vor_does_not_raise_on_extra_kwargs(self):
        """InflationAwareVorStrategy.calculate_bid must accept **kwargs without TypeError."""
        from strategies.enhanced_vor_strategy import InflationAwareVorStrategy

        strategy = InflationAwareVorStrategy()
        player, team, owner = self._make_minimal_objects()

        try:
            result = strategy.calculate_bid(
                player, team, owner,
                current_bid=1,
                remaining_budget=200,
                remaining_players=[],
                extra_context={"inflation_factor": 1.1},  # extra kwarg
            )
        except TypeError as exc:
            self.fail(
                f"calculate_bid raised TypeError with extra **kwargs — "
                f"__init_subclass__ wrapper is dropping kwargs (#144 regression): {exc}"
            )

        self.assertIsInstance(result, (int, float), "calculate_bid must return a numeric type")

    def test_wrapper_does_not_discard_subclass_kwargs(self):
        """A custom strategy with **kwargs in calculate_bid must receive them."""
        from strategies.base_strategy import Strategy
        from unittest.mock import MagicMock

        received_kwargs = {}

        class KwargsCapturingStrategy(Strategy):
            def calculate_bid(self, player, team, owner, current_bid,
                              remaining_budget, remaining_players, **kwargs):
                received_kwargs.update(kwargs)
                return current_bid + 1

            def should_nominate(self, player, team, owner, remaining_budget):
                return True

        strategy = KwargsCapturingStrategy("test", "test strategy")
        player, team, owner = self._make_minimal_objects()

        strategy.calculate_bid(
            player, team, owner,
            current_bid=5,
            remaining_budget=200,
            remaining_players=[],
            custom_signal=42,
        )

        self.assertIn(
            "custom_signal",
            received_kwargs,
            "The __init_subclass__ wrapper swallowed 'custom_signal' kwargs — #144 regression",
        )
        self.assertEqual(received_kwargs["custom_signal"], 42)


if __name__ == "__main__":
    unittest.main()
