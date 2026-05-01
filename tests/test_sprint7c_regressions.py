"""
Sprint 7 QA Phase 2 regression tests — bid_recommendation_service hardcoded values.

Issues:
  #126 — _convert_sleeper_player_to_auction_format uses hardcoded projected_points/auction_value
  #128 — _get_sleeper_draft_context uses user_budget = 200 unconditionally
"""
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# #128 — user_budget hardcoded to 200, ignores config.budget
# ---------------------------------------------------------------------------

class TestUserBudgetFromConfig(unittest.TestCase):
    """#128: _get_sleeper_draft_context must read user_budget from config.budget."""

    def _make_service(self, budget):
        from services.bid_recommendation_service import BidRecommendationService
        config = MagicMock()
        config.budget = budget
        config.sleeper_user_id = None  # skip pick processing
        config_manager = MagicMock()
        config_manager.load_config.return_value = config
        svc = BidRecommendationService.__new__(BidRecommendationService)
        svc.config_manager = config_manager
        svc.sleeper_api = MagicMock()
        return svc

    def _mock_sleeper_api(self, svc, player_name="Test Player"):
        """Set up minimal Sleeper API mocks so _get_sleeper_draft_context reaches budget."""
        player_id = "p1"
        svc.sleeper_api.get_draft.return_value = {
            'type': 'auction', 'status': 'in_progress'
        }
        svc.sleeper_api.get_draft_picks.return_value = []
        svc.get_sleeper_players = MagicMock(return_value={
            player_id: {
                'full_name': player_name,
                'position': 'QB',
                'team': 'KC',
            }
        })

    def test_budget_500_league_uses_500(self):
        """A $500 league must get user_budget=500, not 200."""
        svc = self._make_service(budget=500)
        self._mock_sleeper_api(svc)

        result = svc._get_sleeper_draft_context("draft123", "Test Player")

        self.assertTrue(result.get('success'), f"Expected success, got: {result}")
        self.assertEqual(
            result['user_budget'], 500,
            "user_budget must come from config.budget (500), not hardcoded 200"
        )

    def test_budget_100_league_uses_100(self):
        """A $100 league must get user_budget=100."""
        svc = self._make_service(budget=100)
        self._mock_sleeper_api(svc)

        result = svc._get_sleeper_draft_context("draft123", "Test Player")

        self.assertTrue(result.get('success'), f"Expected success, got: {result}")
        self.assertEqual(
            result['user_budget'], 100,
            "user_budget must come from config.budget (100), not hardcoded 200"
        )

    def test_default_budget_200_still_works(self):
        """Standard $200 league still gets 200 when config.budget == 200."""
        svc = self._make_service(budget=200)
        self._mock_sleeper_api(svc)

        result = svc._get_sleeper_draft_context("draft123", "Test Player")

        self.assertTrue(result.get('success'), f"Expected success, got: {result}")
        self.assertEqual(result['user_budget'], 200)


# ---------------------------------------------------------------------------
# #126 — _convert_sleeper_player_to_auction_format uses hardcoded projections
# ---------------------------------------------------------------------------

class TestConvertSleeperPlayerProjections(unittest.TestCase):
    """#126: _convert_sleeper_player_to_auction_format must use actual data,
    falling back to defaults only when data is absent."""

    def _make_service(self):
        from services.bid_recommendation_service import BidRecommendationService
        svc = BidRecommendationService.__new__(BidRecommendationService)
        return svc

    def test_actual_projected_points_used(self):
        """When sleeper_player has projected_points, that value must be used."""
        svc = self._make_service()
        sleeper_player = {
            'player_id': 'p1',
            'full_name': 'Patrick Mahomes',
            'position': 'QB',
            'team': 'KC',
            'projected_points': 350.5,
            'auction_value': 55.0,
        }
        player = svc._convert_sleeper_player_to_auction_format(sleeper_player)
        self.assertAlmostEqual(
            player.projected_points, 350.5,
            places=1,
            msg="projected_points must reflect actual Sleeper data, not hardcoded 100.0"
        )

    def test_actual_auction_value_used(self):
        """When sleeper_player has auction_value, that value must be used."""
        svc = self._make_service()
        sleeper_player = {
            'player_id': 'p1',
            'full_name': 'Justin Jefferson',
            'position': 'WR',
            'team': 'MIN',
            'projected_points': 280.0,
            'auction_value': 62.0,
        }
        player = svc._convert_sleeper_player_to_auction_format(sleeper_player)
        self.assertAlmostEqual(
            player.auction_value, 62.0,
            places=1,
            msg="auction_value must reflect actual Sleeper data, not hardcoded 10.0"
        )

    def test_default_projected_points_when_absent(self):
        """When projected_points is absent from Sleeper data, fallback to 100.0."""
        svc = self._make_service()
        sleeper_player = {
            'player_id': 'p2',
            'full_name': 'Unknown Kicker',
            'position': 'K',
            'team': 'NYJ',
        }
        player = svc._convert_sleeper_player_to_auction_format(sleeper_player)
        self.assertAlmostEqual(player.projected_points, 100.0, places=1)

    def test_default_auction_value_when_absent(self):
        """When auction_value is absent, fallback to 10.0."""
        svc = self._make_service()
        sleeper_player = {
            'player_id': 'p3',
            'full_name': 'No Value Player',
            'position': 'DST',
            'team': 'CHI',
        }
        player = svc._convert_sleeper_player_to_auction_format(sleeper_player)
        self.assertAlmostEqual(player.auction_value, 10.0, places=1)

    def test_zero_value_uses_default_not_zero(self):
        """Falsy 0 should fall back to defaults (use 'or' fallback semantics)."""
        svc = self._make_service()
        sleeper_player = {
            'player_id': 'p4',
            'full_name': 'Practice Squad',
            'position': 'RB',
            'team': 'UNK',
            'projected_points': 0,
            'auction_value': 0,
        }
        player = svc._convert_sleeper_player_to_auction_format(sleeper_player)
        # 0 is falsy — fallback to defaults as per issue recommendation
        self.assertAlmostEqual(player.projected_points, 100.0, places=1)
        self.assertAlmostEqual(player.auction_value, 10.0, places=1)


if __name__ == '__main__':
    unittest.main()
