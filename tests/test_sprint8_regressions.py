"""Sprint 8 — QA Agent Phase 1 regression tests.

These tests are intentionally written to FAIL against the current codebase,
documenting the precise expected behaviour for each P1 bug.  Backend Agent must
make all tests pass without breaking any previously-passing tests.

Track A — API:
    #94  SleeperAPI._make_request: json.JSONDecodeError not caught — raw exception
         bubbles up instead of being wrapped in SleeperAPIError.
    #95  SleeperAPI.search_players / get_player_by_name: both inject `player_id`
         directly into the caller's dict, mutating shared state.

Track B — Services & Classes:
    #111 Team._can_fit_in_roster_structure: the QB-bench constraint (≤1 QB on
         bench) is dead code — it lives after an unconditional `return False`
         and never executes.
    #127 BidRecommendationService._get_sleeper_draft_context: `target_player =
         player_data` is a reference copy; the subsequent `target_player[
         'player_id'] = player_id` mutates the caller's shared players_data dict.
    #129 DraftLoadingService._calculate_position_limits: FLEX spots are added to
         RB, WR, *and* TE starting counts independently — 1 FLEX spot inflates
         total capacity by 3 instead of 1.
    #130 DraftLoadingService.get_draft_status: calls `os.path.exists(config.
         data_path)` without guarding against `data_path is None` → TypeError.

Track C — Strategies:
    #143 AdaptiveStrategy / AggressiveStrategy: the `if position_priority >= 2.0`
         mandatory-bid branch is unreachable because _calculate_position_priority
         caps its return value at 1.0 via `min(1.0, …)`.
    #145 AggressiveStrategy.calculate_bid: `remaining_budget / team.initial_budget`
         is unguarded — ZeroDivisionError when initial_budget == 0.
    #146 SigmoidStrategy._calculate_budget_pressure: `remaining_budget /
         team.initial_budget` and `len(team.roster) / sum(team.roster_requirements
         .values())` are both unguarded — ZeroDivisionError on edge-case teams.
    #147 VorStrategy.calculate_bid: local variable `vor_scaling_factor = 0.25`
         shadows `self._vor_scaling_factor`, so subclass overrides are ignored.

Track D — CLI & Utils:
    #156 cli/commands.py: a large block of code lives after an unconditional
         `return` inside _run_elimination_rounds — dead, unreachable, misleading.
    #157 utils/path_utils.py: get_data_file("data/sheets/x.csv") silently returns
         data/data/sheets/x.csv; the doubled prefix is not caught.
    #158 cli/main.py: handle_tournament_command calls int() on raw args without a
         try/except — ValueError on non-numeric input crashes the CLI.
    #159 cli/main.py: _display_ping_results accesses result['tests'] without
         guard — KeyError if 'tests' key is absent (e.g. on error responses).
    #161 cli/commands.py: run_elimination_tournament hard-codes the strategy list
         instead of reading list(AVAILABLE_STRATEGIES.keys()).
"""

import asyncio
import json
import os
import sys
import unittest
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classes.player import Player
from classes.team import Team


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_player(player_id: str, position: str = "QB", name: Optional[str] = None,
                 auction_value: float = 20.0, projected_points: float = 15.0) -> Player:
    return Player(
        player_id=player_id,
        name=name or f"Player {player_id}",
        position=position,
        team="KC",
        projected_points=projected_points,
        auction_value=auction_value,
    )


def _make_team(budget: int = 200, roster_config: Optional[dict] = None) -> Team:
    cfg = roster_config or {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}
    return Team("t1", "o1", "TestTeam", budget=budget, roster_config=cfg)


# ===========================================================================
# Track A — #94  SleeperAPI JSONDecodeError not caught
# ===========================================================================

class TestSleeperAPIJSONDecodeError(unittest.TestCase):
    """#94 — _make_request must wrap json.JSONDecodeError in SleeperAPIError."""

    def test_json_decode_error_raises_sleeper_api_error(self):
        """When response.json() raises JSONDecodeError a SleeperAPIError must be raised."""
        from api.sleeper_api import SleeperAPI, SleeperAPIError

        api = SleeperAPI()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with self.assertRaises(SleeperAPIError,
                                   msg="JSONDecodeError from response.json() must be wrapped "
                                       "in SleeperAPIError, not propagated raw"):
                asyncio.run(api._make_request("/test"))


# ===========================================================================
# Track A — #95  Shared-dict mutation in search_players / get_player_by_name
# ===========================================================================

class TestSleeperAPISharedDictMutation(unittest.TestCase):
    """#95 — search_players and get_player_by_name must not mutate input dicts."""

    def _players_data(self) -> dict:
        return {
            "p1": {
                "full_name": "Patrick Mahomes",
                "first_name": "Patrick",
                "last_name": "Mahomes",
                "position": "QB",
            },
            "p2": {
                "full_name": "Tyreek Hill",
                "first_name": "Tyreek",
                "last_name": "Hill",
                "position": "WR",
            },
        }

    def test_search_players_does_not_inject_player_id_into_source(self):
        """search_players must return copies, not mutate the source dict entries."""
        from api.sleeper_api import SleeperAPI

        api = SleeperAPI()
        data = self._players_data()
        original_keys = {k: frozenset(v.keys()) for k, v in data.items()}

        api.search_players("Patrick", data)

        for pid, keys_before in original_keys.items():
            self.assertEqual(
                frozenset(data[pid].keys()), keys_before,
                f"search_players mutated source entry '{pid}': "
                f"injected keys {frozenset(data[pid].keys()) - keys_before}",
            )

    def test_get_player_by_name_does_not_inject_player_id_into_source(self):
        """get_player_by_name must return a copy, not mutate the source dict entry."""
        from api.sleeper_api import SleeperAPI

        api = SleeperAPI()
        data = self._players_data()
        original_keys = {k: frozenset(v.keys()) for k, v in data.items()}

        api.get_player_by_name("Patrick Mahomes", data)

        for pid, keys_before in original_keys.items():
            self.assertEqual(
                frozenset(data[pid].keys()), keys_before,
                f"get_player_by_name mutated source entry '{pid}': "
                f"injected keys {frozenset(data[pid].keys()) - keys_before}",
            )

    def test_search_results_contain_player_id(self):
        """search_players results must still include player_id (via copy, not mutation)."""
        from api.sleeper_api import SleeperAPI

        api = SleeperAPI()
        data = self._players_data()
        results = api.search_players("Patrick", data)

        self.assertTrue(len(results) > 0, "Expected at least one result for 'Patrick'")
        for result in results:
            self.assertIn("player_id", result, "Result dict must contain player_id")


# ===========================================================================
# Track B — #111  QB bench constraint is dead code
# ===========================================================================

class TestTeamQBBenchConstraint(unittest.TestCase):
    """#111 — Only 1 QB should be allowed on bench; constraint is currently dead code."""

    def test_third_qb_rejected_from_bench(self):
        """After starter + 1 bench QB, a 3rd QB must be rejected.

        roster_config = {QB:1, RB:2, WR:3, TE:1, K:1, DST:1, BN:3}
        Sequence:
          qb1 → fills QB starter slot   (ok)
          qb2 → fills 1 BN slot         (ok — 0 QBs were on bench before)
          qb3 → must be rejected        (1 QB already on bench; limit is 1)
        """
        roster_config = {
            "QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DST": 1, "BN": 3,
        }
        team = Team("t1", "o1", "TestTeam", budget=200, roster_config=roster_config)

        qb1 = _make_player("qb1", "QB", "QB Starter", auction_value=30.0)
        qb2 = _make_player("qb2", "QB", "QB Backup", auction_value=10.0)
        qb3 = _make_player("qb3", "QB", "QB Third",  auction_value=5.0)

        self.assertTrue(team.add_player(qb1, 30), "First QB (starter) should be added")
        self.assertTrue(team.add_player(qb2, 10), "Second QB (bench) should be added")

        result = team.add_player(qb3, 5)
        self.assertFalse(
            result,
            "Third QB must be REJECTED — only 1 QB allowed on bench, "
            "but dead code prevents this constraint from firing",
        )


# ===========================================================================
# Track B — #127  BidRecommendationService cache mutation
# ===========================================================================

class TestBidRecommendationServiceCacheMutation(unittest.TestCase):
    """#127 — _get_sleeper_draft_context must not mutate the shared players_data cache."""

    def _players_data(self) -> dict:
        return {
            "p_mahomes": {
                "full_name": "Patrick Mahomes",
                "position": "QB",
                "team": "KC",
                # player_id intentionally absent — represents a clean cache entry
            },
            "p_hill": {
                "full_name": "Tyreek Hill",
                "position": "WR",
                "team": "MIA",
            },
        }

    def test_player_cache_not_mutated_after_context_fetch(self):
        """After _get_sleeper_draft_context, source cache entries must be unchanged."""
        from services.bid_recommendation_service import BidRecommendationService

        players_data = self._players_data()
        original_keys = {k: frozenset(v.keys()) for k, v in players_data.items()}

        service = BidRecommendationService.__new__(BidRecommendationService)
        service.config_manager = MagicMock()
        service.config_manager.load_config.return_value = MagicMock(
            sleeper_user_id=None, budget=200
        )

        mock_api = AsyncMock()
        mock_api.get_draft = AsyncMock(return_value={"draft_id": "d1", "league_id": "l1"})
        mock_api.get_draft_picks = AsyncMock(return_value=[])
        service.sleeper_api = mock_api
        service.get_sleeper_players = MagicMock(return_value=players_data)

        asyncio.run(service._get_sleeper_draft_context("d1", "Patrick Mahomes"))

        for pid, keys_before in original_keys.items():
            self.assertEqual(
                frozenset(players_data[pid].keys()), keys_before,
                f"Cache entry '{pid}' was mutated: "
                f"injected keys {frozenset(players_data[pid].keys()) - keys_before}",
            )


# ===========================================================================
# Track B — #129  FLEX triple-counted in _calculate_position_limits
# ===========================================================================

class TestDraftLoadingFLEXTripleCounting(unittest.TestCase):
    """#129 — DraftLoadingService._calculate_position_limits: FLEX counted 3 times."""

    def test_flex_spot_not_triple_counted(self):
        """With 1 FLEX spot, the total RB+WR+TE capacity must equal
        RB_starters + WR_starters + TE_starters + 1, not +3."""
        from services.draft_loading_service import DraftLoadingService

        service = DraftLoadingService.__new__(DraftLoadingService)

        # No bench (BN=0) to isolate FLEX-only inflation.
        roster_positions = {
            "QB": 1, "RB": 2, "WR": 2, "TE": 1,
            "K": 1, "DST": 1, "FLEX": 1, "BN": 0,
        }
        limits = service._calculate_position_limits(roster_positions)

        rb = limits.get("RB", 0)
        wr = limits.get("WR", 0)
        te = limits.get("TE", 0)
        total_flex_eligible = rb + wr + te

        # Correct: 2 + 2 + 1 + 1 (FLEX) = 6
        # Buggy:   3 + 3 + 2        = 8   (FLEX counted once per position)
        self.assertLessEqual(
            total_flex_eligible, 6,
            f"FLEX triple-counted: RB({rb})+WR({wr})+TE({te})={total_flex_eligible}; "
            f"expected ≤ 6 with 1 FLEX spot",
        )


# ===========================================================================
# Track B — #130  get_draft_status crashes when data_path is None
# ===========================================================================

class TestGetDraftStatusNoneDataPath(unittest.TestCase):
    """#130 — get_draft_status must not raise TypeError when data_path is None."""

    def test_no_type_error_when_data_path_is_none(self):
        from services.draft_loading_service import DraftLoadingService

        mock_config = MagicMock()
        mock_config.data_path = None          # Trigger condition
        mock_config.data_source = "fantasypros"
        mock_config.num_teams = 10
        mock_config.budget = 200
        mock_config.sleeper_draft_id = None

        service = DraftLoadingService.__new__(DraftLoadingService)
        service.config_manager = MagicMock()
        service.config_manager.load_config.return_value = mock_config

        # load_current_draft is not under test here — stub it out
        with patch.object(service, "load_current_draft", return_value=None):
            try:
                result = service.get_draft_status()
            except TypeError as exc:
                self.fail(
                    f"get_draft_status raised TypeError when data_path=None: {exc}"
                )

        self.assertIn("config_loaded", result)


# ===========================================================================
# Track C — #143  Mandatory K/DST bid boost (dead branch position_priority >= 2.0)
# ===========================================================================

class TestMandatoryPositionBidBoost(unittest.TestCase):
    """#143 — position_priority >= 2.0 branch is dead; urgently-needed K/DST bids
    are not boosted.  After fix the tests below must pass."""

    def _team_needing_k(self) -> Team:
        """Full roster except K — K slot is the last critical need."""
        team = _make_team(budget=50,
                          roster_config={"QB": 1, "RB": 2, "WR": 2, "TE": 1,
                                         "K": 1, "DST": 1})
        for i, pos in enumerate(["QB", "RB", "RB", "WR", "WR", "TE", "DST"]):
            team.add_player(_make_player(f"p{i}", pos, auction_value=10.0), 1)
        return team

    def test_adaptive_strategy_boosts_bid_for_urgently_needed_k(self):
        """AdaptiveStrategy must apply mandatory-bid boost when K is the last need.

        With current code the branch `if position_priority >= 2.0` is never
        reached (max priority = 1.0), so the boost never fires.
        Expected: bid > min(10.0, budget * 0.1) when K is urgently needed.
        """
        from strategies.adaptive_strategy import AdaptiveStrategy

        strategy = AdaptiveStrategy()
        team = self._team_needing_k()
        owner = MagicMock()
        owner.get_risk_tolerance.return_value = 0.7

        k_player = _make_player("k1", "K", "Justin Tucker", auction_value=8.0,
                                projected_points=10.0)
        bid = strategy.calculate_bid(k_player, team, owner, 1.0, team.budget, [k_player])

        mandatory_minimum = min(10.0, team.budget * 0.1)
        self.assertGreater(
            bid, mandatory_minimum,
            f"AdaptiveStrategy K bid ({bid}) must exceed mandatory minimum "
            f"({mandatory_minimum}) when K is last urgent need",
        )

    def test_aggressive_strategy_boosts_bid_for_urgently_needed_k(self):
        """AggressiveStrategy: same mandatory-bid branch check."""
        from strategies.aggressive_strategy import AggressiveStrategy

        strategy = AggressiveStrategy()
        team = self._team_needing_k()
        owner = MagicMock()
        owner.get_risk_tolerance.return_value = 0.7

        k_player = _make_player("k1", "K", "Justin Tucker", auction_value=8.0,
                                projected_points=10.0)
        bid = strategy.calculate_bid(k_player, team, owner, 1.0, team.budget, [k_player])

        mandatory_minimum = min(15.0, team.budget * 0.15)
        self.assertGreater(
            bid, mandatory_minimum,
            f"AggressiveStrategy K bid ({bid}) must exceed mandatory minimum "
            f"({mandatory_minimum}) when K is last urgent need",
        )


# ===========================================================================
# Track C — #145  AggressiveStrategy unguarded initial_budget
# ===========================================================================

class TestAggressiveStrategyInitialBudgetGuard(unittest.TestCase):
    """#145 — calculate_bid must not crash when team.initial_budget is 0 or missing."""

    def test_no_zero_division_when_initial_budget_is_zero(self):
        from strategies.aggressive_strategy import AggressiveStrategy

        strategy = AggressiveStrategy()
        team = MagicMock()
        team.initial_budget = 0
        team.budget = 0
        team.roster = []
        team.roster_config = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}
        team.roster_requirements = team.roster_config.copy()
        team.get_needs.return_value = ["K"]
        team.get_remaining_roster_slots.return_value = 1
        team.enforce_budget_constraint.return_value = 0
        team.calculate_position_priority.return_value = 0.5

        owner = MagicMock()
        player = _make_player("k1", "K")

        try:
            strategy.calculate_bid(player, team, owner, 1.0, 0.0, [player])
        except ZeroDivisionError:
            self.fail(
                "AggressiveStrategy.calculate_bid raised ZeroDivisionError "
                "when team.initial_budget == 0"
            )

    def test_no_attribute_error_when_initial_budget_missing(self):
        from strategies.aggressive_strategy import AggressiveStrategy

        strategy = AggressiveStrategy()
        # MagicMock with spec=[] means NO attributes exist
        team = MagicMock(spec=[])
        owner = MagicMock()
        player = _make_player("p1", "QB", auction_value=25.0)

        try:
            strategy.calculate_bid(player, team, owner, 1.0, 50.0, [player])
        except AttributeError as exc:
            self.fail(
                f"AggressiveStrategy.calculate_bid raised AttributeError "
                f"when team lacks initial_budget: {exc}"
            )


# ===========================================================================
# Track C — #146  SigmoidStrategy unguarded attributes
# ===========================================================================

class TestSigmoidStrategyUnguardedAttributes(unittest.TestCase):
    """#146 — SigmoidStrategy must not crash on zero initial_budget or empty requirements."""

    def test_no_zero_division_when_initial_budget_is_zero(self):
        from strategies.sigmoid_strategy import SigmoidStrategy

        strategy = SigmoidStrategy()
        team = _make_team(budget=0)
        team.initial_budget = 0    # Override after construction

        owner = MagicMock()
        owner.get_risk_tolerance.return_value = 0.7
        player = _make_player("p1", "QB", auction_value=25.0)

        try:
            strategy.calculate_bid(player, team, owner, 1.0, 0.0, [player])
        except ZeroDivisionError:
            self.fail(
                "SigmoidStrategy.calculate_bid raised ZeroDivisionError "
                "when team.initial_budget == 0"
            )

    def test_no_zero_division_when_roster_requirements_empty(self):
        from strategies.sigmoid_strategy import SigmoidStrategy

        strategy = SigmoidStrategy()
        team = MagicMock()
        team.initial_budget = 200
        team.budget = 200
        team.roster = []
        team.roster_config = {}
        team.roster_requirements = {}     # sum({}.values()) == 0 → ZeroDivisionError
        team.get_needs.return_value = []
        team.get_remaining_roster_slots.return_value = 0
        team.enforce_budget_constraint.return_value = 1
        team.calculate_position_priority.return_value = 0.5

        owner = MagicMock()
        owner.get_risk_tolerance.return_value = 0.7
        player = _make_player("p1", "QB", auction_value=25.0)

        try:
            strategy.calculate_bid(player, team, owner, 1.0, 200.0, [player])
        except ZeroDivisionError:
            self.fail(
                "SigmoidStrategy.calculate_bid raised ZeroDivisionError "
                "when roster_requirements is empty"
            )


# ===========================================================================
# Track C — #147  VorStrategy local var shadows self._vor_scaling_factor
# ===========================================================================

class TestVorStrategyScalingFactorShadowing(unittest.TestCase):
    """#147 — calculate_bid local `vor_scaling_factor = 0.25` shadows the instance
    attribute; subclass overrides are silently discarded."""

    def test_subclass_vor_scaling_factor_is_respected(self):
        """A subclass setting _vor_scaling_factor=10.0 must produce a higher bid
        than the default 0.25 factor.  Currently FAILS because the local variable
        always wins."""
        from strategies.vor_strategy import VorStrategy

        class HighScaleVorStrategy(VorStrategy):
            def __init__(self):
                super().__init__()
                self._vor_scaling_factor = 10.0  # 40× the default

        default_strategy = VorStrategy()
        high_strategy = HighScaleVorStrategy()

        # Confirm the subclass attribute is actually set
        self.assertEqual(
            high_strategy._vor_scaling_factor, 10.0,
            "Subclass _vor_scaling_factor must be 10.0 after __init__",
        )

        team = MagicMock()
        team.budget = 200
        team.initial_budget = 200
        team.roster = []
        team.roster_config = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}
        team.roster_requirements = team.roster_config.copy()
        team.get_needs.return_value = ["QB"]
        team.get_remaining_roster_slots.return_value = 6
        team.enforce_budget_constraint.side_effect = lambda bid, *a, **kw: int(bid)
        team.calculate_position_priority.return_value = 0.8

        owner = MagicMock()
        owner.get_risk_tolerance.return_value = 0.7

        player = _make_player("p1", "QB", "Patrick Mahomes",
                              auction_value=50.0, projected_points=300.0)
        player.vor = 50.0   # must be positive to reach the scaling-factor code path
        remaining = [player]

        default_bid = default_strategy.calculate_bid(
            player, team, owner, 1.0, 200.0, remaining
        )
        high_bid = high_strategy.calculate_bid(
            player, team, owner, 1.0, 200.0, remaining
        )

        self.assertGreater(
            high_bid, default_bid,
            f"Custom _vor_scaling_factor (10.0) should produce a higher bid than "
            f"the default (0.25), but got high={high_bid}, default={default_bid}.  "
            f"The local variable `vor_scaling_factor = 0.25` is shadowing the "
            f"instance attribute.",
        )


# ===========================================================================
# Track D — #157  get_data_file doubles data/ path segment
# ===========================================================================

class TestGetDataFileDoubledPath(unittest.TestCase):
    """#157 — get_data_file("data/sheets/x.csv") silently returns data/data/sheets/x.csv."""

    def test_data_prefix_not_doubled_in_returned_path(self):
        """get_data_file must not produce a path containing data/data/."""
        from utils.path_utils import get_data_file

        # Callers occasionally pass the full relative path including "data/".
        # The function prepends get_data_dir() (which already ends in "data"),
        # silently doubling the prefix.
        try:
            result = get_data_file("data/sheets/players.csv")
            self.assertNotIn(
                "data/data",
                str(result),
                f"get_data_file doubled the data/ prefix: got {result}",
            )
        except ValueError:
            pass  # Also acceptable — explicit rejection of a doubled prefix


# ===========================================================================
# Track D — #158  handle_tournament_command unhandled ValueError on non-numeric args
# ===========================================================================

class TestHandleTournamentCommandNonNumericArgs(unittest.TestCase):
    """#158 — handle_tournament_command must not crash on non-numeric arguments."""

    def _make_cli(self):
        from cli.main import AuctionDraftCLI
        cli = AuctionDraftCLI.__new__(AuctionDraftCLI)
        cli.command_processor = MagicMock()
        cli.command_processor.run_elimination_tournament.return_value = {
            "success": True,
            "tournament_winner": "value",
            "total_rounds": 1,
        }
        return cli

    def test_non_numeric_rounds_returns_error_code_not_exception(self):
        """Passing a non-numeric rounds argument must return 1, not raise ValueError."""
        cli = self._make_cli()
        try:
            return_code = cli.handle_tournament_command(["not_a_number"])
        except ValueError as exc:
            self.fail(
                f"handle_tournament_command raised ValueError on non-numeric arg: {exc}"
            )
        self.assertNotEqual(return_code, None)

    def test_non_numeric_teams_per_draft_returns_error_code_not_exception(self):
        """Non-numeric teams_per_draft arg must not raise ValueError."""
        cli = self._make_cli()
        try:
            cli.handle_tournament_command(["10", "not_a_number"])
        except ValueError as exc:
            self.fail(
                f"handle_tournament_command raised ValueError on non-numeric "
                f"teams_per_draft: {exc}"
            )


# ===========================================================================
# Track D — #159  _display_ping_results KeyError when 'tests' key missing
# ===========================================================================

class TestDisplayPingResultsMissingTestsKey(unittest.TestCase):
    """#159 — _display_ping_results must not raise KeyError when 'tests' is absent."""

    def _make_cli(self):
        from cli.main import AuctionDraftCLI
        cli = AuctionDraftCLI.__new__(AuctionDraftCLI)
        return cli

    def test_no_key_error_when_tests_key_absent(self):
        """Error response without 'tests' key must not crash _display_ping_results."""
        cli = self._make_cli()
        error_result = {
            "success": False,
            "error": "Connection timed out",
            "overall_status": "UNHEALTHY",
            "summary": "API unreachable",
        }
        try:
            cli._display_ping_results(error_result)
        except KeyError as exc:
            self.fail(
                f"_display_ping_results raised KeyError({exc}) when 'tests' key "
                f"was absent from the result dict"
            )

    def test_no_key_error_on_completely_empty_result(self):
        """Completely empty result dict must not crash _display_ping_results."""
        cli = self._make_cli()
        try:
            cli._display_ping_results({})
        except KeyError as exc:
            self.fail(
                f"_display_ping_results raised KeyError({exc}) on empty result dict"
            )


# ===========================================================================
# Track D — #161  run_elimination_tournament uses hardcoded strategy list
# ===========================================================================

class TestRunEliminationTournamentUsesAvailableStrategies(unittest.TestCase):
    """#161 — run_elimination_tournament must use AVAILABLE_STRATEGIES, not a hardcoded list."""

    def test_dynamically_added_strategy_included_in_tournament(self):
        """A strategy added to AVAILABLE_STRATEGIES at runtime must appear in the
        strategy list passed to _run_elimination_rounds.

        Currently FAILS because run_elimination_tournament has its own hardcoded list.
        """
        from strategies import AVAILABLE_STRATEGIES
        from cli.commands import CommandProcessor

        sentinel_key = "_qa_sentinel_strategy_xyz_"

        # Record which strategies _run_elimination_rounds is called with
        captured: list = []

        def capture(strategies, *args, **kwargs):
            captured.extend(strategies)
            return {"success": True, "tournament_winner": strategies[0], "total_rounds": 1}

        proc = CommandProcessor.__new__(CommandProcessor)
        proc.config_manager = MagicMock()

        mock_strategy_cls = MagicMock(return_value=MagicMock())

        with patch.dict(AVAILABLE_STRATEGIES, {sentinel_key: mock_strategy_cls}):
            with patch.object(proc, "_run_elimination_rounds", side_effect=capture):
                proc.run_elimination_tournament(rounds_per_group=1, teams_per_draft=2)

        self.assertIn(
            sentinel_key, captured,
            f"run_elimination_tournament used a hardcoded strategy list and did not "
            f"include the dynamically-registered strategy '{sentinel_key}'.  "
            f"Fix: replace the hardcoded list with list(AVAILABLE_STRATEGIES.keys()).",
        )


# ===========================================================================
# Track D — #156  Dead code after return in _run_elimination_rounds
# ===========================================================================

class TestRunEliminationRoundsDeadCode(unittest.TestCase):
    """#156 — dead code block after unconditional `return` must be removed.

    The dead block references `AVAILABLE_STRATEGIES` and prints to stdout; after
    the fix it should be absent.  This test verifies the method returns the
    expected structure without printing unexpected 'comprehensive tournament'
    messages.
    """

    def test_elimination_rounds_returns_correct_structure(self):
        """_run_elimination_rounds must return {success, tournament_winner, total_rounds}."""
        from cli.commands import CommandProcessor
        import io

        proc = CommandProcessor.__new__(CommandProcessor)
        proc.config_manager = MagicMock()

        def fake_draft(strategies, verbose=False):
            return {
                "success": True,
                "strategy_results": {s: float(i * 10) for i, s in enumerate(strategies)},
            }

        with patch.object(proc, "_run_elimination_draft", side_effect=fake_draft):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                result = proc._run_elimination_rounds(
                    ["value", "aggressive"], rounds_per_group=1,
                    teams_per_draft=2, verbose=False,
                )
                output = mock_out.getvalue()

        self.assertIn("success", result)
        self.assertTrue(result["success"])
        self.assertIn("tournament_winner", result)
        # The dead block would print "Starting comprehensive tournament with statistical testing..."
        self.assertNotIn(
            "Starting comprehensive tournament with statistical testing",
            output,
            "Dead code after `return` is somehow executing and printing to stdout",
        )


if __name__ == "__main__":
    unittest.main()
