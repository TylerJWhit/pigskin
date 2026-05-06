"""Test cases for core classes (Player, Team, Owner, etc.)."""

import unittest

from test_base import BaseTestCase, TestDataGenerator


class TestPlayer(BaseTestCase):
    """Test Player class functionality."""
    
    def test_player_creation(self):
        """Test basic player creation."""
        player = self.create_mock_player()
        
        self.assertEqual(player.player_id, "test_player_1")
        self.assertEqual(player.name, "Test Player")
        self.assertEqual(player.position, "RB")
        self.assertEqual(player.team, "TEST")
        self.assertEqual(player.projected_points, 150.0)
        
    def test_player_auction_tracking(self):
        """Test auction-related tracking."""
        player = self.create_mock_player()
        
        # Test initial state
        self.assertFalse(player.is_drafted)
        self.assertIsNone(player.drafted_price)
        self.assertIsNone(player.drafted_by)
        
        # Test drafting
        player.mark_as_drafted(15.0, "test_owner_1")
        self.assertTrue(player.is_drafted)
        self.assertEqual(player.drafted_price, 15.0)
        self.assertEqual(player.drafted_by, "test_owner_1")
        
    def test_player_value_calculations(self):
        """Test value calculation methods."""
        player = self.create_mock_player(projected_points=200.0)
        
        # Test value over replacement
        vor = player.get_value_over_replacement(150.0)
        self.assertEqual(vor, 50.0)  # 200 - 150
        
        # Test with zero replacement value
        vor_zero = player.get_value_over_replacement(0.0)
        self.assertEqual(vor_zero, 200.0)
        
    def test_player_string_representation(self):
        """Test string representation of player."""
        player = self.create_mock_player()
        player_str = str(player)
        
        self.assertIn("Test Player", player_str)
        self.assertIn("RB", player_str)
        self.assertIn("TEST", player_str)


class TestTeam(BaseTestCase):
    """Test Team class functionality."""
    
    def test_team_creation(self):
        """Test basic team creation."""
        team = self.create_mock_team()
        
        self.assertEqual(team.team_name, "Test Team")
        self.assertEqual(team.budget, 200.0)
        self.assertEqual(len(team.roster), 0)
        
    def test_team_roster_management(self):
        """Test roster management functionality."""
        team = self.create_mock_team()
        player = self.create_mock_player()
        
        # Test adding player
        team.add_player(player, 15.0)
        self.assertEqual(len(team.roster), 1)
        self.assertEqual(team.budget, 185.0)
        self.assertIn(player, team.roster)
        
        # Test removing player
        team.remove_player(player)
        self.assertEqual(len(team.roster), 0)
        self.assertEqual(team.budget, 200.0)
        
    def test_team_needs_calculation(self):
        """Test positional needs calculation."""
        team = self.create_mock_team()
        
        # Initially should need all positions
        needs = team.get_needs()
        self.assertIn('QB', needs)
        self.assertIn('RB', needs)
        self.assertIn('WR', needs)
        
        # Add a QB
        qb = self.create_mock_player(position='QB')
        team.add_player(qb, 20.0)
        
        # Should no longer need QB (as much)
        needs_after_qb = team.get_needs()
        qb_count_before = needs.count('QB')
        qb_count_after = needs_after_qb.count('QB')
        self.assertLessEqual(qb_count_after, qb_count_before)
        
    def test_team_value_calculations(self):
        """Test team value calculations."""
        team = self.create_mock_team()
        
        # Add some players
        players = [
            self.create_mock_player(player_id="p1", projected_points=100.0),
            self.create_mock_player(player_id="p2", projected_points=150.0),
        ]
        
        for i, player in enumerate(players):
            team.add_player(player, 10.0 + i * 5)
            
        # Test total points
        total_points = team.get_projected_points()
        self.assertEqual(total_points, 250.0)
        
        # Test total spent
        total_spent = team.get_total_spent()
        self.assertEqual(total_spent, 25.0)  # 10 + 15
        
    def test_team_strategy_integration(self):
        """Test strategy integration with team."""
        team = self.create_mock_team()
        strategy = self.create_mock_strategy('value')
        
        # Test strategy assignment
        team.set_strategy(strategy)
        self.assertEqual(team.strategy, strategy)
        
        # Test bid calculation through team
        player = self.create_mock_player()
        remaining_players = TestDataGenerator.create_test_players(10)
        
        bid = team.calculate_bid(player, 10.0, remaining_players)
        self.assertGreaterEqual(bid, 0.0)


class TestOwner(BaseTestCase):
    """Test Owner class functionality."""
    
    def test_owner_creation(self):
        """Test basic owner creation."""
        owner = self.create_mock_owner()
        
        self.assertEqual(owner.name, "Test Owner")
        self.assertIsNone(owner.team)
        self.assertEqual(len(owner.preferences['target_players']), 0)
        
    def test_owner_team_assignment(self):
        """Test team assignment to owner."""
        owner = self.create_mock_owner()
        team = self.create_mock_team()
        
        owner.assign_team(team)
        self.assertEqual(owner.team, team)
        
    def test_owner_target_players(self):
        """Test target player management."""
        owner = self.create_mock_owner()
        
        # Add target players
        owner.add_target_player("player_1")
        owner.add_target_player("player_2")
        
        self.assertEqual(len(owner.preferences['target_players']), 2)
        self.assertTrue(owner.is_target_player("player_1"))
        self.assertFalse(owner.is_target_player("player_3"))
        
        # Remove target player
        owner.remove_target_player("player_1")
        self.assertEqual(len(owner.preferences['target_players']), 1)
        self.assertFalse(owner.is_target_player("player_1"))
        
    def test_owner_risk_tolerance(self):
        """Test risk tolerance functionality."""
        owner = self.create_mock_owner()
        
        # Test default risk tolerance
        risk = owner.get_risk_tolerance()
        self.assertBetween(risk, 0.0, 1.0)
        
        # Test setting risk tolerance via preferences
        owner.update_preferences(risk_tolerance=0.8)
        self.assertEqual(owner.get_risk_tolerance(), 0.8)
            
    def test_owner_preferences(self):
        """Test owner preference management."""
        owner = self.create_mock_owner()
        
        # Test updating preferences  
        owner.update_preferences(max_bid_percentage=0.4)
        self.assertEqual(owner.get_max_bid_percentage(), 0.4)
        
        # Test position priorities
        priorities = owner.get_position_priorities()
        self.assertIsInstance(priorities, list)


class TestDraft(BaseTestCase):
    """Test Draft class functionality."""
    
    def test_draft_creation(self):
        """Test basic draft creation."""
        from classes.draft import Draft
        
        draft = Draft(name="Test Draft", budget_per_team=200, roster_size=9)
        
        self.assertEqual(draft.name, "Test Draft")
        self.assertEqual(draft.budget_per_team, 200)
        self.assertEqual(draft.roster_size, 9)
        self.assertEqual(len(draft.teams), 0)
        
    def test_draft_team_management(self):
        """Test adding teams to draft."""
        from classes.draft import Draft
        
        draft = Draft(name="Test Draft", budget_per_team=200, roster_size=9)
        team = self.create_mock_team()

        draft.add_team(team)
        self.assertEqual(len(draft.teams), 1)
        self.assertIn(team, draft.teams)
        
    def test_draft_player_management(self):
        """Test player management in draft."""
        from classes.draft import Draft
        
        draft = Draft(name="Test Draft", budget_per_team=200, roster_size=9)
        players = TestDataGenerator.create_test_players(10)
        
        draft.add_players(players)
        self.assertEqual(len(draft.available_players), 10)
        
        # Test player availability
        self.assertIn(players[0], draft.available_players)
        
        # Test removing/drafting a player
        draft.available_players.remove(players[0])
        self.assertNotIn(players[0], draft.available_players)


class TestAuction(BaseTestCase):
    """Test Auction class functionality."""
    
    def test_auction_creation(self):
        """Test basic auction creation."""
        from classes.auction import Auction
        from classes.draft import Draft
        
        draft = Draft(name="Test Draft", budget_per_team=200, roster_size=9)
        auction = Auction(draft)
        
        self.assertEqual(auction.draft, draft)
        self.assertFalse(auction.is_active)
        
    def test_auction_nomination(self):
        """Test player nomination resolves immediately via sealed bid."""
        from classes.auction import Auction
        from classes.draft import Draft
        from classes.team import Team
        
        draft = Draft(name="Test Draft", budget_per_team=200, roster_size=9)
        players = TestDataGenerator.create_test_players(5)
        draft.add_players(players)
        
        auction = Auction(draft)
        
        # Start the draft first
        team1 = Team("team1", "owner1", "Test Team")
        team2 = Team("team2", "owner2", "Test Team 2")
        draft.add_team(team1)
        draft.add_team(team2)
        draft.start_draft()
        
        # Nomination immediately resolves (sealed bid) — player is drafted
        player = players[0]
        result = auction.nominate_player(player, "owner1")
        
        # nominate_player returns True and the player is no longer available
        self.assertTrue(result)
        self.assertNotIn(player, draft.available_players)


class TestTournament(BaseTestCase):
    """Test Tournament class functionality."""
    
    def test_tournament_creation(self):
        """Test basic tournament creation."""
        from classes.tournament import Tournament
        
        tournament = Tournament(
            name="Test Tournament",
            num_simulations=10,
            budget_per_team=200,
            roster_size=9
        )
        
        self.assertEqual(tournament.name, "Test Tournament")
        self.assertEqual(tournament.num_simulations, 10)
        self.assertEqual(tournament.budget_per_team, 200)
        
    def test_tournament_strategy_management(self):
        """Test strategy configuration in tournament."""
        from classes.tournament import Tournament
        
        tournament = Tournament(
            name="Test Tournament",
            num_simulations=5,
            budget_per_team=200,
            roster_size=9
        )
        
        # Add strategy configuration
        tournament.add_strategy_config(
            strategy_type="value",
            owner_name="Value Owner",
            num_teams=2
        )
        
        self.assertEqual(len(tournament.strategy_configs), 1)
        
    def test_tournament_player_management(self):
        """Test player management in tournament."""
        from classes.tournament import Tournament
        
        tournament = Tournament(
            name="Test Tournament", 
            num_simulations=5,
            budget_per_team=200,
            roster_size=9
        )
        
        players = TestDataGenerator.create_test_players(20)
        tournament.add_players(players)
        
        self.assertEqual(len(tournament.base_players), 20)


class TestTournamentStrategyRegistration(BaseTestCase):
    """Regression tests for #109 — strategy set on team in _run_single_simulation."""

    def test_simulation_teams_have_strategy_set(self):
        """After _run_single_simulation, each team must have a non-None strategy."""
        from classes.tournament import Tournament
        from classes.player import Player

        players = [
            Player(f"p{i}", f"Player {i}", ["RB","WR","QB","TE"][i % 4], "XX",
                   projected_points=float(200 - i), auction_value=float(50 - i))
            for i in range(20)
        ]
        tournament = Tournament(name="Test", num_simulations=1, budget_per_team=200)
        tournament.add_players(players)
        tournament.add_strategy_config("basic", "Bot", num_teams=2)
        draft = tournament._run_single_simulation(0)
        self.assertIsNotNone(draft)
        for team in draft.teams:
            self.assertIsNotNone(
                team.strategy,
                f"team {team.team_id} has no strategy set — #109 regression"
            )


class TestBidRecommendationTeamBudget(BaseTestCase):
    """Regression tests for #125 — Team constructor args misordered in bid_recommendation_service."""

    def test_create_team_from_sleeper_context_uses_correct_budget(self):
        """Team created from Sleeper context must have budget from user_budget, not default 200."""
        from services.bid_recommendation_service import BidRecommendationService
        service = BidRecommendationService.__new__(BidRecommendationService)
        sleeper_context = {"user_budget": 143, "user_roster": []}
        team = service._create_team_from_sleeper_context(sleeper_context, None)
        self.assertEqual(
            team.budget, 143,
            f"Team budget should be 143 (from user_budget) but got {team.budget} — #125 regression"
        )

    def test_create_team_from_sleeper_context_team_name_is_string(self):
        """Team name must be a string, not the integer budget value."""
        from services.bid_recommendation_service import BidRecommendationService
        service = BidRecommendationService.__new__(BidRecommendationService)
        sleeper_context = {"user_budget": 180, "user_roster": []}
        team = service._create_team_from_sleeper_context(sleeper_context, None)
        self.assertIsInstance(
            team.team_name, str,
            f"team_name should be str but got {type(team.team_name)} — #125 regression"
        )


if __name__ == '__main__':
    unittest.main()
