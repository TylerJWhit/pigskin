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


if __name__ == "__main__":
    unittest.main()
