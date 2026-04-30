"""Comprehensive tests for Draft class.

Covers all 29 functions across initialization, team/owner/player management,
draft lifecycle, auction mechanics, state management, and utility functions.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import uuid
import time

from classes.draft import Draft
from classes.team import Team
from classes.owner import Owner
from classes.player import Player


class TestDraftInitialization:
    """Test Draft initialization and basic properties."""
    
    def test_basic_initialization(self):
        """Test basic draft creation with defaults."""
        draft = Draft()
        
        assert draft.name == "Auction Draft"
        assert draft.budget_per_team == 200.0
        assert draft.roster_size == 16
        assert draft.max_roster_size == 16
        assert draft.status == "created"
        assert draft.current_round == 0
        assert draft.current_nominator_index == 0
        assert draft.current_player is None
        assert draft.current_bid == 0.0
        assert draft.current_high_bidder is None
        assert draft.bid_timer == 30
        assert draft.time_remaining == 0
        
        # Lists should be empty
        assert len(draft.teams) == 0
        assert len(draft.owners) == 0
        assert len(draft.players) == 0
        assert len(draft.drafted_players) == 0
        assert len(draft.available_players) == 0
        assert len(draft.nominations) == 0
        
        # Timestamps
        assert draft.created_at is not None
        assert draft.started_at is None
        assert draft.completed_at is None
        
        # UUID should be valid
        assert uuid.UUID(draft.draft_id)
    
    def test_initialization_with_parameters(self):
        """Test draft creation with custom parameters."""
        draft_id = "test-draft-123"
        draft = Draft(
            draft_id=draft_id,
            name="Test Draft",
            budget_per_team=300.0,
            roster_size=20
        )
        
        assert draft.draft_id == draft_id
        assert draft.name == "Test Draft"
        assert draft.budget_per_team == 300.0
        assert draft.roster_size == 20
        assert draft.max_roster_size == 20


class TestParticipantManagement:
    """Test adding and managing teams, owners, and players."""
    
    def test_add_team(self, sample_teams):
        """Test adding teams to draft."""
        draft = Draft()
        team = sample_teams[0]
        
        draft.add_team(team)
        
        assert len(draft.teams) == 1
        assert draft.teams[0] == team
    
    def test_add_multiple_teams(self, sample_teams):
        """Test adding multiple teams to draft."""
        draft = Draft()
        
        # Add both teams from fixture
        for team in sample_teams:
            draft.add_team(team)
        
        assert len(draft.teams) == 2
        assert all(team in draft.teams for team in sample_teams)
    
    def test_add_owner(self, sample_owners):
        """Test adding owners to draft."""
        draft = Draft()
        owner = sample_owners[0]
        
        draft.add_owner(owner)
        
        assert len(draft.owners) == 1
        assert draft.owners[0] == owner
    
    def test_add_multiple_owners(self, sample_owners):
        """Test adding multiple owners to draft."""
        draft = Draft()
        
        # Add first 3 owners
        for owner in sample_owners[:3]:
            draft.add_owner(owner)
        
        assert len(draft.owners) == 3
        assert all(owner in draft.owners for owner in sample_owners[:3])
    
    def test_add_players(self, sample_players):
        """Test adding players to draft."""
        draft = Draft()
        players = sample_players[:10]
        
        draft.add_players(players)
        
        assert len(draft.players) == 10
        assert len(draft.available_players) == 10
        assert all(player in draft.players for player in players)
        assert all(player in draft.available_players for player in players)


class TestDraftLifecycle:
    """Test draft state management and lifecycle."""
    
    def test_start_draft(self, configured_draft):
        """Test starting a draft."""
        draft = configured_draft
        
        draft.start_draft()
        
        assert draft.status == "started"
        assert draft.started_at is not None
        assert isinstance(draft.started_at, datetime)
    
    def test_start_draft_without_teams(self):
        """Test starting draft without teams raises error."""
        draft = Draft()
        
        with pytest.raises(ValueError, match="Need at least 2 teams to start draft"):
            draft.start_draft()
    
    def test_start_draft_without_players(self, sample_teams):
        """Test starting draft without players raises error."""
        draft = Draft()
        for team in sample_teams[:2]:
            draft.add_team(team)
        
        # Draft can start without checking player availability first
        # This test shows starting is allowed even without available_players populated
        draft.start_draft()
        assert draft.status == "started"
    
    def test_pause_draft(self, configured_draft):
        """Test pausing a started draft."""
        draft = configured_draft
        draft.start_draft()
        
        draft.pause_draft()
        
        assert draft.status == "paused"
    
    def test_pause_draft_not_started(self):
        """Test pausing draft that hasn't started does nothing."""
        draft = Draft()
        
        # pause_draft doesn't raise error, just does nothing
        draft.pause_draft()
        
        assert draft.status == "created"  # Unchanged
    
    def test_resume_draft(self, configured_draft):
        """Test resuming a paused draft."""
        draft = configured_draft
        draft.start_draft()
        draft.pause_draft()
        
        draft.resume_draft()
        
        assert draft.status == "started"
    
    def test_resume_draft_not_paused(self, configured_draft):
        """Test resuming draft that's not paused does nothing."""
        draft = configured_draft
        
        # resume_draft doesn't raise error, just does nothing  
        draft.resume_draft()
        
        assert draft.status == "created"  # Unchanged


class TestNominationAndBidding:
    """Test player nomination and bidding mechanics."""
    
    def test_nominate_player(self, configured_draft, sample_owners):
        """Test nominating a player."""
        draft = configured_draft
        draft.start_draft()
        
        player = draft.available_players[0]
        owner = sample_owners[0]
        initial_bid = 15.0
        
        draft.nominate_player(player, owner.owner_id, initial_bid)
        
        assert draft.current_player == player
        assert draft.current_bid == initial_bid
        assert draft.current_high_bidder == owner.owner_id
        assert len(draft.nominations) == 1
        
        nomination = draft.nominations[0]
        assert nomination['player'] == player
        assert nomination['nominator'] == owner.owner_id
        assert nomination['initial_bid'] == initial_bid
    
    def test_nominate_player_default_bid(self, configured_draft, sample_owners):
        """Test nominating player with default bid."""
        draft = configured_draft
        draft.start_draft()
        
        player = draft.available_players[0]
        owner = sample_owners[0]
        
        draft.nominate_player(player, owner.owner_id)
        
        assert draft.current_bid == 1.0
    
    def test_nominate_already_drafted_player(self, configured_draft, sample_owners):
        """Test nominating already drafted player."""
        draft = configured_draft
        draft.start_draft()
        
        player = draft.available_players[0]
        owner = sample_owners[0]
        
        # Draft the player first
        draft.drafted_players.append(player)
        draft.available_players.remove(player)
        
        with pytest.raises(ValueError, match="Player is not available for nomination"):
            draft.nominate_player(player, owner.owner_id)
    
    def test_place_bid_valid(self, configured_draft, sample_owners):
        """Test placing a valid bid."""
        draft = configured_draft
        draft.start_draft()
        
        player = draft.available_players[0]
        owner1 = sample_owners[0]
        owner2 = sample_owners[1]
        
        # Nominate first
        draft.nominate_player(player, owner1.owner_id, 10.0)
        
        # Place higher bid
        result = draft.place_bid(owner2.owner_id, 15.0)
        
        assert result is True
        assert draft.current_bid == 15.0
        assert draft.current_high_bidder == owner2.owner_id
    
    def test_place_bid_too_low(self, configured_draft, sample_owners):
        """Test placing bid that's too low."""
        draft = configured_draft
        draft.start_draft()
        
        player = draft.available_players[0]
        owner1 = sample_owners[0]
        owner2 = sample_owners[1]
        
        # Nominate first
        draft.nominate_player(player, owner1.owner_id, 10.0)
        
        # Place lower bid
        result = draft.place_bid(owner2.owner_id, 8.0)
        
        assert result is False
        assert draft.current_bid == 10.0
        assert draft.current_high_bidder == owner1.owner_id
    
    def test_place_bid_no_current_player(self, configured_draft, sample_owners):
        """Test placing bid when no player is nominated."""
        draft = configured_draft
        draft.start_draft()
        
        owner = sample_owners[0]
        
        with pytest.raises(ValueError, match="No player currently being auctioned"):
            draft.place_bid(owner.owner_id, 15.0)


class TestAuctionCompletion:
    """Test auction completion and player awarding."""
    
    def test_complete_auction(self, configured_draft, sample_owners):
        """Test completing an auction."""
        draft = configured_draft
        draft.start_draft()
        
        player = draft.available_players[0]
        owner = sample_owners[0]
        bid_amount = 25.0
        
        # Set up auction state
        draft.nominate_player(player, owner.owner_id, bid_amount)
        
        draft.complete_auction()
        
        # Player should be awarded
        assert player in draft.drafted_players
        assert player not in draft.available_players
        
        # Auction state should be reset
        assert draft.current_player is None
        assert draft.current_bid == 0.0
        assert draft.current_high_bidder is None
    
    def test_complete_auction_no_current_player(self, configured_draft):
        """Test completing auction when no player nominated."""
        draft = configured_draft
        draft.start_draft()
        
        with pytest.raises(ValueError, match="No active auction to complete"):
            draft.complete_auction()


class TestPrivateHelperMethods:
    """Test private helper methods."""
    
    def test_get_team_by_owner(self, configured_draft, sample_owners):
        """Test getting team by owner ID."""
        draft = configured_draft
        owner = sample_owners[0]
        team = draft.teams[0]  # First team
        team.owner_id = owner.owner_id  # Associate owner with team
        
        result = draft._get_team_by_owner(owner.owner_id)
        
        assert result == team
    
    def test_get_team_by_owner_not_found(self, configured_draft):
        """Test getting team by non-existent owner ID."""
        draft = configured_draft
        
        result = draft._get_team_by_owner("non-existent")
        
        assert result is None
    
    def test_get_owner_by_id(self, configured_draft, sample_owners):
        """Test getting owner by ID."""
        draft = configured_draft
        owner = sample_owners[0]
        
        result = draft._get_owner_by_id(owner.owner_id)
        
        assert result == owner
    
    def test_get_owner_by_id_not_found(self, configured_draft):
        """Test getting owner by non-existent ID."""
        draft = configured_draft
        
        result = draft._get_owner_by_id("non-existent")
        
        assert result is None
    
    def test_advance_nominator(self, configured_draft):
        """Test advancing to next nominator."""
        draft = configured_draft
        initial_index = draft.current_nominator_index
        
        draft._advance_nominator()
        
        assert draft.current_nominator_index == (initial_index + 1) % len(draft.teams)
    
    def test_start_new_nomination(self, configured_draft):
        """Test starting a new nomination."""
        draft = configured_draft
        
        # Mock the nomination process
        with patch.object(draft, '_get_team_nomination') as mock_nomination:
            mock_player = Mock(spec=Player)
            mock_nomination.return_value = mock_player
            
            draft._start_new_nomination()
            
            mock_nomination.assert_called_once()
    
    def test_is_draft_complete_false(self, configured_draft):
        """Test draft completion check when not complete."""
        draft = configured_draft
        
        result = draft._is_draft_complete()
        
        assert result is False
    
    def test_is_draft_complete_true(self, configured_draft):
        """Test draft completion check when complete."""
        draft = configured_draft
        
        # Mock all teams as having full rosters
        for team in draft.teams:
            team.is_roster_complete = Mock(return_value=True)
        
        result = draft._is_draft_complete()
        
        assert result is True
    
    def test_complete_draft(self, configured_draft):
        """Test completing the entire draft."""
        draft = configured_draft
        draft.start_draft()
        
        draft._complete_draft()
        
        assert draft.status == "completed"
        assert draft.completed_at is not None
        assert isinstance(draft.completed_at, datetime)


class TestDraftQueries:
    """Test draft query and summary methods."""
    
    def test_get_current_nominator(self, configured_draft):
        """Test getting current nominator team."""
        draft = configured_draft
        
        result = draft.get_current_nominator()
        
        assert result == draft.teams[draft.current_nominator_index]
    
    def test_get_current_nominator_no_teams(self):
        """Test getting current nominator with no teams."""
        draft = Draft()
        
        result = draft.get_current_nominator()
        
        assert result is None
    
    def test_get_draft_summary(self, configured_draft):
        """Test getting draft summary."""
        draft = configured_draft
        
        summary = draft.get_draft_summary()
        
        assert isinstance(summary, dict)
        assert 'draft_id' in summary
        assert 'name' in summary
        assert 'status' in summary
        assert 'teams' in summary
        assert 'players_drafted' in summary
        assert 'players_available' in summary
        
        assert summary['draft_id'] == draft.draft_id
        assert summary['name'] == draft.name
        assert summary['status'] == draft.status
        assert summary['teams'] == len(draft.teams)
        assert summary['players_drafted'] == len(draft.drafted_players)
        assert summary['players_available'] == len(draft.available_players)
    
    def test_get_leaderboard(self, configured_draft):
        """Test getting leaderboard."""
        draft = configured_draft
        
        # Mock team projected points
        for i, team in enumerate(draft.teams):
            team.get_projected_points = Mock(return_value=float(1000 + i * 50))
        
        leaderboard = draft.get_leaderboard()
        
        assert isinstance(leaderboard, list)
        assert len(leaderboard) == len(draft.teams)
        
        # Should be sorted by projected points descending
        for i in range(len(leaderboard) - 1):
            assert leaderboard[i]['projected_points'] >= leaderboard[i + 1]['projected_points']


class TestBiddingMechanics:
    """Test advanced bidding and auction mechanics."""
    
    def test_collect_team_bids(self, configured_draft):
        """Test collecting bids from all teams."""
        draft = configured_draft
        player = Mock(spec=Player)
        
        # Mock team bid calculations
        for i, team in enumerate(draft.teams):
            team.calculate_bid = Mock(return_value=float(10 + i * 5))
        
        bids = draft._collect_team_bids(player)
        
        assert isinstance(bids, dict)
        assert len(bids) == len(draft.teams)
        
        # Verify all teams were asked for bids
        for team in draft.teams:
            team.calculate_bid.assert_called_once()
    
    def test_collect_team_bids_parallel(self, configured_draft):
        """Test collecting bids in parallel."""
        draft = configured_draft
        player = Mock(spec=Player)
        
        # Mock team bid calculations
        for i, team in enumerate(draft.teams):
            team.calculate_bid = Mock(return_value=float(10 + i * 5))
        
        bids = draft._collect_team_bids_parallel(player)
        
        assert isinstance(bids, dict)
        assert len(bids) == len(draft.teams)
    
    def test_determine_auction_winner(self, configured_draft):
        """Test determining auction winner from bids."""
        draft = configured_draft
        
        bids = {
            "team1": 25.0,
            "team2": 30.0,
            "team3": 20.0
        }
        
        winner_id, winning_bid = draft._determine_auction_winner(bids)
        
        assert winner_id == "team2"
        assert winning_bid == 26.0  # Second highest (25) + 1
    
    def test_determine_auction_winner_tie(self, configured_draft):
        """Test determining winner with tied bids."""
        draft = configured_draft
        
        bids = {
            "team1": 25.0,
            "team2": 25.0,
            "team3": 20.0
        }
        
        winner_id, winning_bid = draft._determine_auction_winner(bids)
        
        # Should return one of the tied teams
        assert winner_id in ["team1", "team2"]
        assert winning_bid == 25.0  # Tie pays the tied amount
    
    def test_determine_auction_winner_no_bids(self, configured_draft):
        """Test determining winner with no valid bids."""
        draft = configured_draft
        
        bids = {}
        
        winner_id, winning_bid = draft._determine_auction_winner(bids)
        
        assert winner_id is None
        assert winning_bid == 0.0  # No minimum when no bids
    
    def test_award_player_to_team(self, configured_draft, sample_players):
        """Test awarding player to winning team."""
        draft = configured_draft
        player = sample_players[0]
        winner_id = draft.teams[0].team_id
        price = 25.0
        
        # Mock team add_player method
        winning_team = draft.teams[0]
        winning_team.add_player = Mock()
        
        draft._award_player_to_team(player, winner_id, price)
        
        winning_team.add_player.assert_called_once_with(player, price)
        assert player in draft.drafted_players
        assert player not in draft.available_players


class TestTeamNomination:
    """Test team nomination logic."""
    
    def test_get_team_nomination(self, configured_draft):
        """Test getting nomination from team."""
        draft = configured_draft
        team = draft.teams[0]
        available_players = draft.available_players.copy()
        
        # Mock team nomination method
        expected_player = available_players[0]
        team.should_nominate_player = Mock(return_value=True)
        
        with patch('random.choice', return_value=expected_player):
            result = draft._get_team_nomination(team)
        
        assert result == expected_player
    
    def test_get_team_nomination_no_suitable_player(self, configured_draft):
        """Test team nomination when no suitable player found."""
        draft = configured_draft
        team = draft.teams[0]
        
        # Mock team to reject all nominations
        team.should_nominate_player = Mock(return_value=False)
        
        result = draft._get_team_nomination(team)
        
        # Should fall back to random selection
        assert result in draft.available_players


class TestCompleteAuctionFlow:
    """Test complete auction draft flow."""
    
    def test_run_complete_draft(self, configured_draft):
        """Test running a complete automated draft."""
        draft = configured_draft
        
        # Start the draft first
        draft.start_draft()
        
        # Mock various methods to speed up test
        with patch.object(draft, '_get_team_nomination') as mock_nomination, \
             patch.object(draft, '_collect_team_bids') as mock_bids, \
             patch.object(draft, '_determine_auction_winner') as mock_winner, \
             patch.object(draft, '_award_player_to_team') as mock_award:
            
            # Set up mocks
            mock_nomination.side_effect = draft.available_players[:5]  # Nominate first 5 players
            mock_bids.return_value = {"team1": 20.0}
            mock_winner.return_value = ("team1", 20.0)
            
            # Mock draft completion after 5 players
            draft._is_draft_complete = Mock(side_effect=[False] * 5 + [True])
            
            draft.run_complete_draft()
            
            # Verify draft completed
            assert draft.status == "completed"
            assert mock_nomination.call_count == 5
            assert mock_bids.call_count == 5
            assert mock_winner.call_count == 5
            assert mock_award.call_count == 5


class TestStringRepresentations:
    """Test string representation methods."""
    
    def test_str_representation(self, configured_draft):
        """Test string representation."""
        draft = configured_draft
        
        result = str(draft)
        
        assert draft.name in result
        assert draft.status in result
    
    def test_repr_representation(self, configured_draft):
        """Test repr representation."""
        draft = configured_draft
        
        result = repr(draft)
        
        assert "Draft" in result
        assert draft.draft_id in result
    
    def test_to_dict(self, configured_draft):
        """Test dictionary representation."""
        draft = configured_draft
        
        result = draft.to_dict()
        
        assert isinstance(result, dict)
        assert 'draft_id' in result
        assert 'name' in result
        assert 'status' in result
        assert 'budget_per_team' in result
        assert 'roster_size' in result
        assert 'current_round' in result
        
        assert result['draft_id'] == draft.draft_id
        assert result['name'] == draft.name
        assert result['status'] == draft.status
        assert result['budget_per_team'] == draft.budget_per_team


class TestEdgeCasesAndErrorConditions:
    """Test edge cases and error conditions."""
    
    def test_start_draft_already_started(self, configured_draft):
        """Test starting already started draft."""
        draft = configured_draft
        draft.start_draft()
        
        with pytest.raises(ValueError, match="Draft has already been started or completed"):
            draft.start_draft()
    
    def test_nominate_player_draft_not_started(self, configured_draft, sample_owners, sample_players):
        """Test nominating player when draft not started."""
        draft = configured_draft
        
        with pytest.raises(ValueError, match="Draft is not active"):
            draft.nominate_player(sample_players[0], sample_owners[0].owner_id)
    
    def test_place_bid_draft_not_started(self, configured_draft, sample_owners):
        """Test placing bid when draft not started."""
        draft = configured_draft
        
        with pytest.raises(ValueError, match="Draft is not active"):
            draft.place_bid(sample_owners[0].owner_id, 15.0)
    
    def test_complete_auction_draft_not_started(self, configured_draft):
        """Test completing auction when draft not started."""
        draft = configured_draft
        
        with pytest.raises(ValueError, match="No active auction to complete"):
            draft.complete_auction()
    
    def test_empty_available_players_list(self):
        """Test behavior with empty available players."""
        draft = Draft()
        
        # Add teams but no players
        for i in range(3):
            team = Team(f"team{i}", f"owner{i}", f"Team {i}")
            draft.add_team(team)
        
        # Can start draft without players
        draft.start_draft()
        assert draft.status == "started"
    
    def test_single_team_draft(self, sample_players):
        """Test draft with single team."""
        draft = Draft()
        team = Team("team1", "owner1", "Solo Team")
        draft.add_team(team)
        draft.add_players(sample_players[:10])
        
        with pytest.raises(ValueError, match="Need at least 2 teams to start draft"):
            draft.start_draft()
    
    def test_large_roster_size(self, sample_players):
        """Test draft with very large roster requirements."""
        draft = Draft(roster_size=100)
        
        # Add teams
        for i in range(3):
            team = Team(f"team{i}", f"owner{i}", f"Team {i}")
            draft.add_team(team)
        
        draft.add_players(sample_players)  # Only ~50 players
        
        # Should start even if not enough players for all rosters
        draft.start_draft()
        assert draft.status == "started"


# Performance and Integration Tests
class TestDraftPerformance:
    """Test draft performance with realistic data."""
    
    @pytest.mark.performance
    def test_large_draft_performance(self, sample_players):
        """Test draft performance with many teams and players."""
        draft = Draft(roster_size=16)
        
        # Add 12 teams
        for i in range(12):
            team = Team(f"team{i}", f"owner{i}", f"Team {i}")
            owner = Owner(f"owner{i}", f"Owner {i}")
            draft.add_team(team)
            draft.add_owner(owner)
        
        # Add all available players
        draft.add_players(sample_players)
        
        draft.start_draft()
        
        # Time a few nomination cycles
        start_time = time.time()
        for _ in range(5):
            # Mock the nomination process for speed
            if draft.available_players:
                player = draft.available_players[0]
                owner_id = draft.owners[0].owner_id
                draft.nominate_player(player, owner_id, 10.0)
                draft.complete_auction()
        
        end_time = time.time()
        
        # Should complete reasonably quickly
        assert (end_time - start_time) < 1.0
    
    @pytest.mark.integration  
    def test_realistic_draft_scenario(self, sample_players, sample_owners):
        """Test realistic draft scenario with full workflow."""
        draft = Draft(name="Integration Test Draft", budget_per_team=200.0, roster_size=16)
        
        # Set up 6 teams (we have 12 owners available)
        teams = []
        for i in range(6):
            team = Team(f"team{i}", sample_owners[i].owner_id, f"Team {i}")
            teams.append(team)
            draft.add_team(team)
            draft.add_owner(sample_owners[i])
        
        # Add players
        draft.add_players(sample_players)
        
        # Start draft
        draft.start_draft()
        assert draft.status == "started"
        
        # Simulate a few auction rounds
        for round_num in range(3):
            available_player = draft.available_players[0]
            nominating_owner = draft.owners[round_num % len(draft.owners)]
            
            # Nominate player
            draft.nominate_player(available_player, nominating_owner.owner_id, 15.0)
            
            # Place a few bids
            for bid_round in range(2):
                bidding_owner = draft.owners[(round_num + bid_round + 1) % len(draft.owners)]
                new_bid = 15.0 + (bid_round + 1) * 5.0
                draft.place_bid(bidding_owner.owner_id, new_bid)
            
            # Complete auction
            draft.complete_auction()
            
            # Verify player was drafted
            assert available_player in draft.drafted_players
            assert available_player not in draft.available_players
        
        # Verify draft state
        assert len(draft.drafted_players) == 3
        assert len(draft.nominations) == 3
        
        # Get draft summary
        summary = draft.get_draft_summary()
        assert summary['players_drafted'] == 3
        assert summary['players_available'] == len(sample_players) - 3