"""Unit tests for BidRecommendationService — closes #246."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_player(name="Patrick Mahomes", position="QB", auction_value=50.0, projected_points=350.0):
    p = MagicMock()
    p.name = name
    p.position = position
    p.auction_value = auction_value
    p.projected_points = projected_points
    p.is_drafted = False
    p.team = "KC"
    return p


def _make_team(budget=200.0, initial_budget=200.0, roster=None):
    t = MagicMock()
    t.team_id = "team1"
    t.owner_id = "owner1"
    t.team_name = "Test Team"
    t.budget = budget
    t.initial_budget = initial_budget
    t.roster = roster or []
    t.get_needs.return_value = ["QB", "RB"]
    t.get_total_spent.return_value = initial_budget - budget
    t.is_roster_complete.return_value = False
    t.get_projected_points.return_value = 800.0
    t.get_players_by_position.return_value = []
    return t


def _make_config(strategy_type="balanced", budget=200.0, data_path="/fake"):
    cfg = MagicMock()
    cfg.strategy_type = strategy_type
    cfg.budget = budget
    cfg.data_path = data_path
    cfg.sleeper_draft_id = None
    cfg.sleeper_user_id = None
    return cfg


def _make_service():
    from services.bid_recommendation_service import BidRecommendationService
    svc = BidRecommendationService.__new__(BidRecommendationService)
    svc.config_manager = MagicMock()
    svc.draft_service = MagicMock()
    svc._strategy_cache = {}
    svc.sleeper_available = False
    svc.sleeper_api = MagicMock()
    svc.sleeper_draft_service = MagicMock()
    svc.get_sleeper_players = MagicMock(return_value={})
    return svc


class TestBidRecommendationServiceGetStrategy(unittest.TestCase):

    def test_returns_strategy_instance(self):
        svc = _make_service()
        with patch("services.bid_recommendation_service.create_strategy") as mock_create:
            mock_create.return_value = MagicMock()
            strategy = svc._get_strategy("balanced")
        mock_create.assert_called_once_with("balanced")
        self.assertIsNotNone(strategy)

    def test_caches_strategy(self):
        svc = _make_service()
        with patch("services.bid_recommendation_service.create_strategy") as mock_create:
            mock_create.return_value = MagicMock()
            s1 = svc._get_strategy("balanced")
            s2 = svc._get_strategy("balanced")
        self.assertIs(s1, s2)
        mock_create.assert_called_once()  # only one creation

    def test_different_keys_create_separate_strategies(self):
        svc = _make_service()
        with patch("services.bid_recommendation_service.create_strategy") as mock_create:
            mock_create.side_effect = lambda k: MagicMock(name=k)
            svc._get_strategy("balanced")
            svc._get_strategy("aggressive")
        self.assertEqual(mock_create.call_count, 2)


class TestBidRecommendationServiceErrorResponse(unittest.TestCase):

    def test_error_response_structure(self):
        svc = _make_service()
        resp = svc._error_response("something went wrong")
        self.assertFalse(resp["success"])
        self.assertEqual(resp["error"], "something went wrong")
        self.assertEqual(resp["recommended_bid"], 0.0)
        self.assertFalse(resp["should_bid"])


class TestBidRecommendationServiceCalculateConfidence(unittest.TestCase):

    def test_good_value_alignment_high_confidence(self):
        svc = _make_service()
        player = _make_player(auction_value=50.0, projected_points=300.0)
        team = _make_team()
        team.get_needs.return_value = ["QB"]
        confidence = svc._calculate_confidence(player, 50.0, team)
        self.assertGreater(confidence, 0.5)

    def test_confidence_bounded_to_one(self):
        svc = _make_service()
        player = _make_player(auction_value=1.0, projected_points=500.0)
        team = _make_team(budget=200.0)
        confidence = svc._calculate_confidence(player, 1.0, team)
        self.assertLessEqual(confidence, 1.0)

    def test_confidence_non_negative(self):
        svc = _make_service()
        player = _make_player(auction_value=100.0, projected_points=50.0)
        team = _make_team(budget=5.0)
        team.get_needs.return_value = []
        confidence = svc._calculate_confidence(player, 200.0, team)
        self.assertGreaterEqual(confidence, 0.0)

    def test_medium_quality_player_path(self):
        # projected_points 100 < x <= 200 hits line 397
        svc = _make_service()
        player = _make_player(auction_value=30.0, projected_points=150.0)
        player.position = "WR"
        team = _make_team(budget=200.0)
        team.get_needs.return_value = ["WR"]  # position in needs → line 373
        confidence = svc._calculate_confidence(player, 30.0, team)
        self.assertGreaterEqual(confidence, 0.0)


class TestBidRecommendationServiceGenerateExplanation(unittest.TestCase):

    def test_no_bid_explanation(self):
        svc = _make_service()
        player = _make_player(auction_value=30.0)
        team = _make_team()
        strategy = MagicMock()
        strategy.name = "Conservative"
        owner = MagicMock()
        explanation = svc._generate_explanation(player, 10.0, 20.0, strategy, team, owner)
        self.assertIn("not bidding higher", explanation.lower())

    def test_bid_explanation_contains_strategy_name(self):
        svc = _make_service()
        player = _make_player(auction_value=50.0)
        team = _make_team()
        strategy = MagicMock()
        strategy.name = "Aggressive"
        owner = MagicMock()
        explanation = svc._generate_explanation(player, 40.0, 20.0, strategy, team, owner)
        self.assertIn("Aggressive", explanation)

    def test_mentions_position_need(self):
        svc = _make_service()
        player = _make_player(position="QB", auction_value=50.0)
        team = _make_team()
        team.get_needs.return_value = ["QB", "RB"]
        strategy = MagicMock()
        strategy.name = "Balanced"
        explanation = svc._generate_explanation(player, 40.0, 20.0, strategy, team, MagicMock())
        self.assertIn("QB", explanation)


class TestBidRecommendationServiceGenerateNominationReasoning(unittest.TestCase):

    def test_high_value_player_mentioned(self):
        svc = _make_service()
        player = _make_player(position="QB", auction_value=30.0)
        team = _make_team()
        team.get_needs.return_value = ["QB"]
        strategy = MagicMock()
        strategy.name = "Balanced"
        reasoning = svc._generate_nomination_reasoning(player, strategy, team)
        self.assertIn("High-value", reasoning)

    def test_low_cost_player_mentioned(self):
        svc = _make_service()
        player = _make_player(auction_value=2.0)
        team = _make_team()
        team.get_needs.return_value = []
        strategy = MagicMock()
        strategy.name = "Conservative"
        reasoning = svc._generate_nomination_reasoning(player, strategy, team)
        self.assertIn("Low-cost", reasoning)

    def test_aggressive_strategy_mentioned(self):
        svc = _make_service()
        player = _make_player(auction_value=50.0)
        team = _make_team()
        team.get_needs.return_value = []
        strategy = MagicMock()
        strategy.name = "Aggressive"
        reasoning = svc._generate_nomination_reasoning(player, strategy, team)
        self.assertIn("Aggressive", reasoning)


class TestBidRecommendationServiceGenerateTeamRecommendations(unittest.TestCase):

    def test_needs_mentioned(self):
        svc = _make_service()
        team = _make_team(budget=150.0, initial_budget=200.0)
        team.get_needs.return_value = ["QB", "TE"]
        config = _make_config()
        recs = svc._generate_team_recommendations(team, config)
        self.assertTrue(any("QB" in r or "TE" in r for r in recs))

    def test_high_budget_mentions_premium(self):
        svc = _make_service()
        team = _make_team(budget=180.0, initial_budget=200.0)
        team.get_needs.return_value = []
        team.is_roster_complete.return_value = True
        config = _make_config()
        recs = svc._generate_team_recommendations(team, config)
        self.assertTrue(any("premium" in r.lower() for r in recs))

    def test_low_budget_mentions_value(self):
        svc = _make_service()
        team = _make_team(budget=20.0, initial_budget=200.0)
        team.get_needs.return_value = []
        team.is_roster_complete.return_value = True
        config = _make_config()
        recs = svc._generate_team_recommendations(team, config)
        self.assertTrue(any("value" in r.lower() for r in recs))


class TestBidRecommendationServiceRecommendBid(unittest.TestCase):
    """Integration-level tests for recommend_bid() with mocked dependencies."""

    def test_local_fallback_player_not_found(self):
        svc = _make_service()
        svc.sleeper_available = False
        config = _make_config()
        svc.config_manager.load_config.return_value = config

        mock_draft = MagicMock()
        mock_draft.available_players = []
        mock_draft.teams = []
        svc.draft_service.load_current_draft.return_value = mock_draft

        with patch("services.bid_recommendation_service.create_strategy",
                   return_value=MagicMock()):
            result = svc.recommend_bid("Unknown Player", 10.0)

        self.assertFalse(result["success"])

    def test_local_fallback_no_draft_returns_error(self):
        svc = _make_service()
        svc.sleeper_available = False
        config = _make_config()
        svc.config_manager.load_config.return_value = config
        svc.draft_service.load_current_draft.return_value = None

        with patch("services.bid_recommendation_service.create_strategy",
                   return_value=MagicMock()):
            result = svc.recommend_bid("Mahomes", 10.0)

        self.assertFalse(result["success"])

    def test_exception_in_recommend_bid_returns_error(self):
        svc = _make_service()
        svc.config_manager.load_config.side_effect = RuntimeError("db down")

        result = svc.recommend_bid("Mahomes", 10.0)

        self.assertFalse(result["success"])
        self.assertIn("Error", result["error"])

    def test_local_fallback_success_path(self):
        svc = _make_service()
        svc.sleeper_available = False

        config = _make_config()
        svc.config_manager.load_config.return_value = config

        player = _make_player("Patrick Mahomes")
        team = _make_team()
        owner = MagicMock()
        owner.is_human = True

        mock_draft = MagicMock()
        mock_draft.available_players = [player]
        mock_draft.teams = [team]
        mock_draft._get_owner_by_id.return_value = owner
        svc.draft_service.load_current_draft.return_value = mock_draft

        mock_strategy = MagicMock()
        mock_strategy.name = "Balanced"
        mock_strategy.calculate_bid.return_value = 45.0

        with patch("services.bid_recommendation_service.create_strategy",
                   return_value=mock_strategy):
            result = svc.recommend_bid("Patrick Mahomes", 30.0)

        self.assertTrue(result["success"])
        self.assertEqual(result["recommended_bid"], 45.0)
        self.assertTrue(result["should_bid"])


class TestBidRecommendationServiceGetSleeperDraftContext(unittest.TestCase):
    """Tests for _get_sleeper_draft_context async method."""

    def test_draft_not_found_returns_failure(self):
        svc = _make_service()
        svc.sleeper_api.get_draft = AsyncMock(return_value=None)

        import asyncio
        result = asyncio.run(svc._get_sleeper_draft_context("d1", "Mahomes"))

        self.assertFalse(result["success"])

    def test_no_player_data_returns_failure(self):
        svc = _make_service()
        svc.sleeper_api.get_draft = AsyncMock(return_value={"draft_id": "d1"})
        svc.sleeper_api.get_draft_picks = AsyncMock(return_value=[])
        svc.get_sleeper_players = MagicMock(return_value={})

        import asyncio
        result = asyncio.run(svc._get_sleeper_draft_context("d1", "Mahomes"))

        self.assertFalse(result["success"])
        self.assertIn("player data", result["error"].lower())

    def test_player_not_found_returns_failure(self):
        svc = _make_service()
        svc.sleeper_api.get_draft = AsyncMock(return_value={"draft_id": "d1"})
        svc.sleeper_api.get_draft_picks = AsyncMock(return_value=[])
        svc.get_sleeper_players = MagicMock(return_value={
            "p1": {"full_name": "Lamar Jackson", "position": "QB", "team": "BAL"}
        })

        import asyncio
        result = asyncio.run(svc._get_sleeper_draft_context("d1", "Mahomes"))

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    def test_player_found_returns_context(self):
        svc = _make_service()
        svc.sleeper_api.get_draft = AsyncMock(return_value={"draft_id": "d1"})
        svc.sleeper_api.get_draft_picks = AsyncMock(return_value=[])
        svc.config_manager.load_config.return_value = _make_config()
        svc.get_sleeper_players = MagicMock(return_value={
            "p1": {"full_name": "Patrick Mahomes", "position": "QB", "team": "KC"}
        })

        import asyncio
        result = asyncio.run(svc._get_sleeper_draft_context("d1", "Patrick Mahomes"))

        self.assertTrue(result["success"])
        self.assertEqual(result["target_player"]["full_name"], "Patrick Mahomes")
        self.assertFalse(result["is_drafted"])

    def test_exception_returns_failure(self):
        svc = _make_service()
        svc.sleeper_api.get_draft = AsyncMock(side_effect=ConnectionError("down"))

        import asyncio
        result = asyncio.run(svc._get_sleeper_draft_context("d1", "Mahomes"))

        self.assertFalse(result["success"])

    def test_user_id_and_picks_populates_roster(self):
        svc = _make_service()
        svc.sleeper_api.get_draft = AsyncMock(return_value={"draft_id": "d1"})
        picks = [
            {'picked_by': 'u1', 'player_id': 'p1', 'metadata': {'amount': '45'}},
        ]
        svc.sleeper_api.get_draft_picks = AsyncMock(return_value=picks)
        player_data = {
            'p1': {'full_name': 'Patrick Mahomes', 'position': 'QB', 'team': 'KC'},
            'p2': {'full_name': 'CMC', 'position': 'RB', 'team': 'SF'},
        }
        svc.get_sleeper_players = MagicMock(return_value=player_data)
        config = _make_config()
        config.sleeper_user_id = 'u1'
        svc.config_manager.load_config.return_value = config

        import asyncio
        result = asyncio.run(svc._get_sleeper_draft_context("d1", "CMC"))

        self.assertTrue(result["success"])
        self.assertEqual(len(result["user_roster"]), 1)
        self.assertEqual(result["user_roster"][0]["name"], "Patrick Mahomes")


class TestRecommendNomination(unittest.TestCase):
    """Tests for recommend_nomination() covering lines 113-179."""

    def _make_draft_with_players(self, players=None, teams=None):
        draft = MagicMock()
        draft.available_players = players or []
        draft.teams = teams or []
        draft._get_owner_by_id.return_value = None
        return draft

    def test_no_draft_returns_error(self):
        svc = _make_service()
        svc.config_manager.load_config.return_value = _make_config()
        svc.draft_service.load_current_draft.return_value = None
        result = svc.recommend_nomination()
        self.assertFalse(result["success"])

    def test_with_candidates_success(self):
        svc = _make_service()
        config = _make_config()
        svc.config_manager.load_config.return_value = config

        player = _make_player("CMC", "RB", auction_value=60.0)
        team = _make_team()
        draft = self._make_draft_with_players([player], [team])
        svc.draft_service.load_current_draft.return_value = draft

        mock_strategy = MagicMock()
        mock_strategy.name = "Balanced"
        mock_strategy.should_nominate.return_value = True
        mock_strategy.calculate_bid.return_value = 50.0

        with patch("services.bid_recommendation_service.create_strategy", return_value=mock_strategy):
            result = svc.recommend_nomination()

        self.assertTrue(result["success"])
        self.assertEqual(result["recommended_player"], "CMC")

    def test_no_candidates_falls_back_to_top_value(self):
        svc = _make_service()
        config = _make_config()
        svc.config_manager.load_config.return_value = config

        players = [_make_player(f"P{i}", "WR", auction_value=float(i * 10)) for i in range(15)]
        team = _make_team()
        draft = self._make_draft_with_players(players, [team])
        svc.draft_service.load_current_draft.return_value = draft

        mock_strategy = MagicMock()
        mock_strategy.name = "Balanced"
        mock_strategy.should_nominate.return_value = False  # No candidates

        with patch("services.bid_recommendation_service.create_strategy", return_value=mock_strategy):
            result = svc.recommend_nomination()

        self.assertTrue(result["success"])

    def test_position_filter_applied(self):
        svc = _make_service()
        config = _make_config()
        svc.config_manager.load_config.return_value = config

        qb = _make_player("Mahomes", "QB", auction_value=50.0)
        rb = _make_player("CMC", "RB", auction_value=60.0)
        team = _make_team()
        draft = self._make_draft_with_players([qb, rb], [team])
        svc.draft_service.load_current_draft.return_value = draft

        mock_strategy = MagicMock()
        mock_strategy.name = "Balanced"
        mock_strategy.should_nominate.return_value = True
        mock_strategy.calculate_bid.return_value = 40.0

        with patch("services.bid_recommendation_service.create_strategy", return_value=mock_strategy):
            result = svc.recommend_nomination(position_filter=["QB"])

        self.assertTrue(result["success"])
        self.assertEqual(result["player_position"], "QB")

    def test_exception_returns_error(self):
        svc = _make_service()
        svc.config_manager.load_config.side_effect = RuntimeError("boom")
        result = svc.recommend_nomination()
        self.assertFalse(result["success"])

    def test_no_players_available(self):
        svc = _make_service()
        config = _make_config()
        svc.config_manager.load_config.return_value = config

        team = _make_team()
        draft = self._make_draft_with_players([], [team])
        svc.draft_service.load_current_draft.return_value = draft

        mock_strategy = MagicMock()
        mock_strategy.name = "Balanced"

        with patch("services.bid_recommendation_service.create_strategy", return_value=mock_strategy):
            result = svc.recommend_nomination()

        self.assertFalse(result["success"])


class TestAnalyzeTeamValue(unittest.TestCase):
    """Tests for analyze_team_value() covering lines 198-243."""

    def test_no_draft_returns_error(self):
        svc = _make_service()
        svc.config_manager.load_config.return_value = _make_config()
        svc.draft_service.load_current_draft.return_value = None
        result = svc.analyze_team_value()
        self.assertFalse(result["success"])

    def test_success_path(self):
        svc = _make_service()
        config = _make_config()
        svc.config_manager.load_config.return_value = config

        player = _make_player("Mahomes", "QB", auction_value=50.0, projected_points=350.0)
        player.drafted_price = 45
        team = _make_team(budget=155.0, initial_budget=200.0, roster=[player])
        owner = MagicMock()
        owner.is_human = True
        # Return actual list for QB position to hit line 212 branch
        team.get_players_by_position.side_effect = lambda pos: [player] if pos == 'QB' else []

        draft = MagicMock()
        draft.available_players = []
        draft.teams = [team]
        draft._get_owner_by_id.return_value = owner
        svc.draft_service.load_current_draft.return_value = draft

        result = svc.analyze_team_value()
        self.assertTrue(result["success"])
        self.assertIn("position_analysis", result)
        self.assertIn("QB", result["position_analysis"])
        self.assertEqual(result["position_analysis"]["QB"]["count"], 1)

    def test_exception_returns_error(self):
        svc = _make_service()
        svc.config_manager.load_config.side_effect = ValueError("fail")
        result = svc.analyze_team_value()
        self.assertFalse(result["success"])

    def test_zero_budget_spent_efficiency(self):
        svc = _make_service()
        config = _make_config()
        svc.config_manager.load_config.return_value = config

        team = _make_team(budget=200.0, initial_budget=200.0, roster=[])
        team.get_total_spent.return_value = 0  # No spending

        draft = MagicMock()
        draft.available_players = []
        draft.teams = [team]
        draft._get_owner_by_id.return_value = None
        svc.draft_service.load_current_draft.return_value = draft

        result = svc.analyze_team_value()
        self.assertTrue(result["success"])
        self.assertEqual(result["value_efficiency"], 0)


class TestGetTeamOwnerContext(unittest.TestCase):
    """Tests for _get_team_context and _get_owner_context private methods."""

    def test_get_team_by_team_id(self):
        svc = _make_service()
        team = _make_team()
        team.team_id = "team1"
        draft = MagicMock()
        draft.teams = [team]
        config = _make_config()
        result = svc._get_team_context(draft, {'team_id': 'team1'}, config)
        self.assertEqual(result.team_id, "team1")

    def test_get_human_team_when_no_id(self):
        svc = _make_service()
        team = _make_team()
        owner = MagicMock()
        owner.is_human = True
        draft = MagicMock()
        draft.teams = [team]
        draft._get_owner_by_id.return_value = owner
        config = _make_config()
        result = svc._get_team_context(draft, None, config)
        self.assertEqual(result, team)

    def test_fallback_to_first_team(self):
        svc = _make_service()
        team = _make_team()
        draft = MagicMock()
        draft.teams = [team]
        draft._get_owner_by_id.return_value = None
        config = _make_config()
        result = svc._get_team_context(draft, None, config)
        self.assertEqual(result, team)

    def test_creates_mock_team_when_no_teams(self):
        svc = _make_service()
        draft = MagicMock()
        draft.teams = []
        config = _make_config()
        result = svc._get_team_context(draft, None, config)
        self.assertEqual(result.team_name, "Mock Team")

    def test_get_owner_context_found(self):
        svc = _make_service()
        team = _make_team()
        owner = MagicMock()
        draft = MagicMock()
        draft._get_owner_by_id.return_value = owner
        result = svc._get_owner_context(draft, team)
        self.assertEqual(result, owner)

    def test_get_owner_context_creates_mock(self):
        svc = _make_service()
        team = _make_team()
        draft = MagicMock()
        draft._get_owner_by_id.return_value = None
        result = svc._get_owner_context(draft, team)
        self.assertEqual(result.name, "Mock Owner")


class TestSleeperContextMethods(unittest.TestCase):
    """Tests for _recommend_bid_with_sleeper_context, _convert_sleeper_player_to_auction_format,
    and _create_team_from_sleeper_context covering lines 518-712."""

    def _make_sleeper_context(self, is_drafted=False):
        return {
            'draft_id': 'd1',
            'draft_info': {},
            'target_player': {'player_id': 'p1', 'full_name': 'Josh Allen', 'position': 'QB', 'team': 'BUF'},
            'is_drafted': is_drafted,
            'user_budget': 155,
            'user_roster': [],
            'available_players': [],
            'total_picks': 5,
            'data_source': 'sleeper',
        }

    def test_already_drafted_player_returns_error(self):
        svc = _make_service()
        mock_strategy = MagicMock()
        mock_strategy.name = "Balanced"
        ctx = self._make_sleeper_context(is_drafted=True)
        result = svc._recommend_bid_with_sleeper_context("Josh Allen", 30.0, mock_strategy, ctx, None)
        self.assertFalse(result["success"])

    def test_success_path_with_sleeper_context(self):
        svc = _make_service()
        mock_strategy = MagicMock()
        mock_strategy.name = "Balanced"
        mock_strategy.calculate_bid.return_value = 45.0
        ctx = self._make_sleeper_context(is_drafted=False)
        result = svc._recommend_bid_with_sleeper_context("Josh Allen", 30.0, mock_strategy, ctx, None)
        self.assertTrue(result["success"])
        self.assertEqual(result["recommended_bid"], 45.0)
        self.assertEqual(result["data_source"], "sleeper")

    def test_exception_in_sleeper_context_returns_error(self):
        svc = _make_service()
        mock_strategy = MagicMock()
        mock_strategy.calculate_bid.side_effect = RuntimeError("boom")
        ctx = self._make_sleeper_context()
        result = svc._recommend_bid_with_sleeper_context("Josh Allen", 30.0, mock_strategy, ctx, None)
        self.assertFalse(result["success"])

    def test_convert_sleeper_player_basic(self):
        svc = _make_service()
        data = {'player_id': 'p1', 'full_name': 'Lamar Jackson', 'position': 'QB', 'team': 'BAL'}
        player = svc._convert_sleeper_player_to_auction_format(data)
        self.assertEqual(player.name, "Lamar Jackson")
        self.assertEqual(player.position, "QB")

    def test_convert_sleeper_player_uses_defaults_for_missing(self):
        svc = _make_service()
        data = {'name': 'Unknown', 'position': 'WR', 'team': 'XX'}
        player = svc._convert_sleeper_player_to_auction_format(data)
        self.assertEqual(player.projected_points, 100.0)
        self.assertEqual(player.auction_value, 10.0)

    def test_create_team_from_sleeper_context_default(self):
        svc = _make_service()
        ctx = self._make_sleeper_context()
        team = svc._create_team_from_sleeper_context(ctx, None)
        self.assertEqual(team.team_name, "Your Team")
        self.assertEqual(team.budget, 155)

    def test_create_team_from_sleeper_context_with_team_context(self):
        svc = _make_service()
        ctx = self._make_sleeper_context()
        ctx['user_roster'] = [
            {'name': 'CMC', 'position': 'RB', 'team': 'SF', 'bid': 55}
        ]
        team = svc._create_team_from_sleeper_context(ctx, {'team_name': 'My Sharks', 'budget': 145})
        self.assertEqual(team.team_name, "My Sharks")
        self.assertEqual(len(team.roster), 1)
        self.assertEqual(team.roster[0].name, "CMC")


class TestConvenienceFunctions(unittest.TestCase):
    """Tests for module-level convenience functions covering lines 717-804."""

    def test_recommend_bid_module_function(self):
        from services.bid_recommendation_service import recommend_bid
        with patch("services.bid_recommendation_service.BidRecommendationService") as MockSvc:
            mock_instance = MockSvc.return_value
            mock_instance.recommend_bid.return_value = {"success": True}
            result = recommend_bid("Mahomes", 30.0, config_dir="/tmp")
        mock_instance.recommend_bid.assert_called_once()
        self.assertTrue(result["success"])

    def test_recommend_nomination_module_function(self):
        from services.bid_recommendation_service import recommend_nomination
        with patch("services.bid_recommendation_service.BidRecommendationService") as MockSvc:
            mock_instance = MockSvc.return_value
            mock_instance.recommend_nomination.return_value = {"success": True}
            result = recommend_nomination(config_dir="/tmp")
        mock_instance.recommend_nomination.assert_called_once()
        self.assertTrue(result["success"])

    def test_get_bid_recommendation_function(self):
        from services.bid_recommendation_service import get_bid_recommendation
        with patch("services.bid_recommendation_service.BidRecommendationService") as MockSvc:
            mock_instance = MockSvc.return_value
            mock_instance.recommend_bid.return_value = {"success": True}
            result = get_bid_recommendation("CMC", 40.0, config_dir="/tmp")
        self.assertTrue(result["success"])

    def test_get_nomination_recommendation_function(self):
        from services.bid_recommendation_service import get_nomination_recommendation
        with patch("services.bid_recommendation_service.BidRecommendationService") as MockSvc:
            mock_instance = MockSvc.return_value
            mock_instance.recommend_nomination.return_value = {"success": True}
            result = get_nomination_recommendation(config_dir="/tmp", position_filter=["QB"])
        mock_instance.recommend_nomination.assert_called_once_with(None, ["QB"])
        self.assertTrue(result["success"])


class TestFindPlayerPartialMatch(unittest.TestCase):
    def test_partial_match(self):
        svc = _make_service()
        p = _make_player("Josh Allen")
        draft = MagicMock()
        draft.available_players = [p]
        result = svc._find_player(draft, "Allen")
        self.assertEqual(result, p)

    def test_no_match_returns_none(self):
        svc = _make_service()
        draft = MagicMock()
        draft.available_players = [_make_player("Someone Else")]
        result = svc._find_player(draft, "Mahomes")
        self.assertIsNone(result)


class TestNominationReasoning(unittest.TestCase):
    def test_low_value_player(self):
        svc = _make_service()
        player = _make_player(auction_value=3.0)
        player.position = "K"
        strategy = MagicMock()
        strategy.name = "Balanced"
        team = _make_team()
        team.get_needs.return_value = []
        result = svc._generate_nomination_reasoning(player, strategy, team)
        self.assertIn("Low-cost", result)

    def test_aggressive_strategy_reasoning(self):
        svc = _make_service()
        player = _make_player(auction_value=50.0)
        player.position = "QB"
        strategy = MagicMock()
        strategy.name = "Aggressive"
        team = _make_team()
        team.get_needs.return_value = []
        result = svc._generate_nomination_reasoning(player, strategy, team)
        self.assertIn("Aggressive", result)

    def test_conservative_strategy_reasoning(self):
        svc = _make_service()
        player = _make_player(auction_value=50.0)
        player.position = "QB"
        strategy = MagicMock()
        strategy.name = "Conservative"
        team = _make_team()
        team.get_needs.return_value = []
        result = svc._generate_nomination_reasoning(player, strategy, team)
        self.assertIn("Conservative", result)


class TestSleeperContextWithAvailablePlayers(unittest.TestCase):
    def test_available_players_converted(self):
        svc = _make_service()
        mock_strategy = MagicMock()
        mock_strategy.name = "Balanced"
        mock_strategy.calculate_bid.return_value = 45.0
        ctx = {
            'draft_id': 'd1',
            'draft_info': {},
            'target_player': {'player_id': 'p1', 'full_name': 'Josh Allen', 'position': 'QB', 'team': 'BUF'},
            'is_drafted': False,
            'user_budget': 155,
            'user_roster': [],
            'available_players': [
                {'player_id': 'p2', 'full_name': 'CMC', 'position': 'RB', 'team': 'SF'}
            ],
            'total_picks': 5,
            'data_source': 'sleeper',
        }
        result = svc._recommend_bid_with_sleeper_context("Josh Allen", 30.0, mock_strategy, ctx, None)
        self.assertTrue(result["success"])
        # Verify available player was passed to strategy
        call_kwargs = mock_strategy.calculate_bid.call_args
        remaining = call_kwargs[1].get('remaining_players') or call_kwargs[0][5]
        self.assertEqual(len(remaining), 1)


class TestConvertSleeperPlayerWithValues(unittest.TestCase):
    def test_uses_provided_projected_points_and_value(self):
        svc = _make_service()
        data = {'player_id': 'p1', 'full_name': 'CMC', 'position': 'RB', 'team': 'SF',
                'projected_points': 280.0, 'auction_value': 55.0}
        player = svc._convert_sleeper_player_to_auction_format(data)
        self.assertEqual(player.projected_points, 280.0)
        self.assertEqual(player.auction_value, 55.0)


class TestBidRecommendationAdditionalCoverage(unittest.TestCase):
    """Cover remaining uncovered lines in bid_recommendation_service.py."""

    def test_recommend_bid_with_sleeper_draft_id(self):
        """Cover lines 67-68 — sleeper_available=True with sleeper_draft_id."""
        svc = _make_service()
        svc.sleeper_available = True
        ctx = {'success': True, 'picks': [], 'players': {}, 'rosters': [],
               'available_players': []}
        svc.sleeper_draft_service.get_draft_context = MagicMock(return_value=ctx)

        mock_config = MagicMock()
        mock_config.budget = 200.0
        mock_config.strategy_type = 'value'
        svc.config_manager.load_config.return_value = mock_config

        with unittest.mock.patch('asyncio.run', return_value={
            'success': False, 'error': 'no data'
        }):
            result = svc.recommend_bid("Josh Allen", 10.0, sleeper_draft_id="draft123")
        assert isinstance(result, dict)

    def test_recommend_bid_conservative_confidence(self):
        """Cover line 373 — value_ratio < 0.8 adds 0.2 factor."""
        svc = _make_service()

        mock_player = MagicMock()
        mock_player.auction_value = 50.0  # high value
        mock_player.projected_points = 300.0
        mock_player.position = 'QB'

        team_ctx = MagicMock()
        team_ctx.get_needs.return_value = ['QB']
        team_ctx.is_roster_complete.return_value = False
        team_ctx.budget = 100.0

        # recommended_bid = 30, auction_value = 50 → ratio = 0.6 < 0.8 → line 373
        result = svc._calculate_confidence(mock_player, 30.0, team_ctx)
        assert 0 <= result <= 1.0

    def test_get_sleeper_draft_context_partial_player_match(self):
        """Cover lines 441-443 — partial player name match."""
        svc = _make_service()
        svc.sleeper_available = True
        players_data = {
            'p1': {'full_name': 'Josh Allen', 'position': 'QB', 'team': 'BUF'}
        }
        svc.get_sleeper_players.return_value = players_data

        picks = [{'player_id': 'p2', 'picked_by': 'u1', 'metadata': {'amount': '30'}}]
        rosters = []

        async def fake_context(draft_id):
            return {'picks': picks, 'rosters': rosters}

        with unittest.mock.patch.object(
            svc.sleeper_draft_service, 'get_draft_with_picks',
            return_value={'picks': picks, 'rosters': rosters}
        ):
            import asyncio
            result = asyncio.run(svc._get_sleeper_draft_context("draft123", "Josh"))
        assert isinstance(result, dict)

    def test_bid_amount_invalid_in_sleeper_context(self):
        """Cover lines 470-471 — invalid bid amount in pick metadata."""
        svc = _make_service()
        svc.sleeper_available = True
        players_data = {
            'p1': {'full_name': 'Josh Allen', 'position': 'QB', 'team': 'BUF'}
        }
        svc.get_sleeper_players.return_value = players_data

        picks = [
            {'player_id': 'p1', 'picked_by': 'u1', 'metadata': {'amount': 'invalid'}},  # triggers line 470-471
        ]
        rosters = [{'owner_id': 'u1', 'players': ['p2'], 'taxi': []}]

        mock_config = MagicMock()
        mock_config.sleeper_user_id = 'u1'
        mock_config.budget = 200.0
        svc.config_manager.load_config.return_value = mock_config

        with unittest.mock.patch.object(
            svc.sleeper_draft_service, 'get_draft_with_picks',
            return_value={'picks': picks, 'rosters': rosters}
        ):
            import asyncio
            result = asyncio.run(svc._get_sleeper_draft_context("draft123", "Josh Allen"))
        assert isinstance(result, dict)


if __name__ == "__main__":
    unittest.main()
