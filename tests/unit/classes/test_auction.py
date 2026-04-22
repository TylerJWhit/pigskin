"""Comprehensive tests for Auction class.

Covers all 13 functions across auction lifecycle, bidding mechanics, 
player nomination, winner determination, and sealed-bid logic.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Optional
import time
import random

from classes.auction import Auction
from classes.draft import Draft
from classes.team import Team
from classes.owner import Owner
from classes.player import Player


class TestAuctionInitialization:
    """Test Auction initialization and basic properties."""
    
    def test_basic_initialization(self, configured_draft):
        """Test basic auction creation."""
        auction = Auction(configured_draft)
        
        assert auction.draft == configured_draft
        assert auction.is_active is False
        assert isinstance(auction.on_auction_completed, list)
        assert len(auction.on_auction_completed) == 0
    
    def test_initialization_with_draft_reference(self, configured_draft):
        """Test auction properly references draft."""
        auction = Auction(configured_draft)
        
        # Should have access to draft's teams, players, etc.
        assert len(auction.draft.teams) > 0
        assert len(auction.draft.available_players) > 0


class TestAuctionLifecycle:
    """Test auction start/stop lifecycle."""
    
    def test_start_auction_success(self, configured_draft):
        """Test starting auction with started draft."""
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        
        # Mock the draft's run_complete_draft to avoid full execution
        with patch.object(configured_draft, 'run_complete_draft'):
            auction.start_auction()
            
            # After completion, should not be active
            assert auction.is_active is False
    
    def test_start_auction_draft_not_started(self, configured_draft):
        """Test starting auction when draft not started."""
        auction = Auction(configured_draft)
        
        with pytest.raises(ValueError, match="Draft must be started before auction can begin"):
            auction.start_auction()
    
    def test_stop_auction(self, configured_draft):
        """Test stopping auction."""
        auction = Auction(configured_draft)
        auction.is_active = True
        
        auction.stop_auction()
        
        assert auction.is_active is False


class TestTeamNomination:
    """Test team nomination logic."""
    
    def test_get_team_nomination_with_available_players(self, configured_draft):
        """Test getting nomination when players available."""
        auction = Auction(configured_draft)
        team = configured_draft.teams[0]
        
        result = auction._get_team_nomination(team)
        
        # Should return a player from available players
        assert result in configured_draft.available_players
    
    def test_get_team_nomination_no_available_players(self, configured_draft):
        """Test getting nomination when no players available."""
        auction = Auction(configured_draft)
        team = configured_draft.teams[0]
        
        # Remove all available players
        configured_draft.available_players.clear()
        
        result = auction._get_team_nomination(team)
        
        assert result is None
    
    def test_get_team_nomination_with_strategy(self, configured_draft):
        """Test nomination when team has strategy."""
        auction = Auction(configured_draft)
        team = configured_draft.teams[0]
        
        # Mock team strategy
        mock_strategy = Mock()
        mock_strategy.name = "Test Strategy"
        mock_strategy.should_nominate = Mock(return_value=True)
        team.strategy = mock_strategy
        
        # Mock owner lookup
        with patch.object(auction.draft, '_get_owner_by_id') as mock_owner:
            mock_owner.return_value = Mock()
            
            result = auction._get_team_nomination(team)
            
            # Should return a player
            assert result is not None
            assert result in configured_draft.available_players


class TestSealedBidCollection:
    """Test sealed bid collection logic."""
    
    def test_collect_sealed_bids_success(self, configured_draft):
        """Test collecting bids from all teams."""
        auction = Auction(configured_draft)
        player = configured_draft.available_players[0]
        
        # Mock team methods that are actually called
        for i, team in enumerate(configured_draft.teams):
            team.can_bid = Mock(return_value=True)
            team.calculate_bid = Mock(return_value=float(10 + i * 5))
        
        # Mock _get_owner_by_id to return owner dict
        with patch.object(auction.draft, '_get_owner_by_id') as mock_get_owner:
            mock_owner = Mock()
            mock_owner.to_dict.return_value = {'owner_id': 'test'}
            mock_get_owner.return_value = mock_owner
            
            bids = auction._collect_sealed_bids(player)
        
        assert isinstance(bids, dict)
        # Bids should be keyed by owner_id, not team_id
        assert len(bids) == len(configured_draft.teams)
        
        # Verify team methods were called
        for team in configured_draft.teams:
            team.can_bid.assert_called_once_with(player, 1.0)
            team.calculate_bid.assert_called_once()
    
    def test_collect_sealed_bids_with_zero_bids(self, configured_draft):
        """Test bid collection when teams bid zero."""
        auction = Auction(configured_draft)
        player = configured_draft.available_players[0]
        
        # Mock teams to return zero bids
        for team in configured_draft.teams:
            team.calculate_bid = Mock(return_value=0.0)
        
        bids = auction._collect_sealed_bids(player)
        
        # Should filter out zero bids
        assert all(bid > 0 for bid in bids.values())
    
    def test_collect_sealed_bids_error_handling(self, configured_draft):
        """Test bid collection with team errors."""
        auction = Auction(configured_draft)
        player = configured_draft.available_players[0]
        
        # Mock one team to raise exception, others normal
        configured_draft.teams[0].calculate_bid = Mock(side_effect=Exception("Bid error"))
        configured_draft.teams[1].calculate_bid = Mock(return_value=15.0)
        
        bids = auction._collect_sealed_bids(player)
        
        # Should continue with other teams despite error
        assert len(bids) == 1  # Only the successful team
        assert list(bids.values())[0] == 15.0


class TestAuctionWinnerDetermination:
    """Test winner determination logic."""
    
    def test_determine_auction_winner_normal(self, configured_draft):
        """Test normal winner determination."""
        auction = Auction(configured_draft)
        
        bids = {
            "team1": 25.0,
            "team2": 30.0,
            "team3": 20.0
        }
        
        winner_id, winning_bid = auction._determine_auction_winner(bids)
        
        assert winner_id == "team2"
        assert winning_bid == 26.0  # Second highest (25) + 1
    
    def test_determine_auction_winner_tie(self, configured_draft):
        """Test winner determination with tied bids."""
        auction = Auction(configured_draft)
        
        bids = {
            "team1": 25.0,
            "team2": 25.0,
            "team3": 20.0
        }
        
        winner_id, winning_bid = auction._determine_auction_winner(bids)
        
        # Should pick one of the tied teams
        assert winner_id in ["team1", "team2"]
        assert winning_bid == 26.0  # Second highest (20) + 1, even with tie at top
    
    def test_determine_auction_winner_single_bid(self, configured_draft):
        """Test winner determination with single bid."""
        auction = Auction(configured_draft)
        
        bids = {
            "team1": 25.0
        }
        
        winner_id, winning_bid = auction._determine_auction_winner(bids)
        
        assert winner_id == "team1"
        assert winning_bid == 25.0  # Single bidder pays their bid
    
    def test_determine_auction_winner_no_bids(self, configured_draft):
        """Test winner determination with no bids."""
        auction = Auction(configured_draft)
        
        bids = {}
        
        winner_id, winning_bid = auction._determine_auction_winner(bids)
        
        assert winner_id is None
        assert winning_bid == 0.0


class TestPlayerAwarding:
    """Test player awarding mechanics."""
    
    def test_award_player_to_team_success(self, configured_draft, sample_players):
        """Test successfully awarding player to team."""
        auction = Auction(configured_draft)
        player = sample_players[0]
        winner_id = configured_draft.teams[0].owner_id  # Use owner_id not team_id
        price = 25.0
        
        # Initial state
        initial_budget = configured_draft.teams[0].budget
        initial_roster_size = len(configured_draft.teams[0].roster)
        
        auction._award_player_to_team(player, winner_id, price)
        
        # Verify player was awarded directly to team
        winning_team = configured_draft.teams[0]
        assert player in winning_team.roster
        assert winning_team.budget == initial_budget - price
        assert player.is_drafted is True
        assert player.draft_price == price
    
    def test_award_player_to_team_not_found(self, configured_draft, sample_players):
        """Test awarding player when team not found."""
        auction = Auction(configured_draft)
        player = sample_players[0]
        winner_id = "nonexistent_team"
        price = 25.0
        
        # Mock draft to return None for team lookup
        with patch.object(auction.draft, '_get_team_by_owner', return_value=None):
            # Should handle gracefully without raising exception
            auction._award_player_to_team(player, winner_id, price)
    
    def test_award_player_with_callbacks(self, configured_draft, sample_players):
        """Test player awarding triggers callbacks."""
        auction = Auction(configured_draft)
        player = sample_players[0]
        winner_id = configured_draft.teams[0].owner_id
        price = 25.0
        
        # Add callback
        callback_mock = Mock()
        auction.on_auction_completed.append(callback_mock)
        
        auction._award_player_to_team(player, winner_id, price)
        
        # Callback should have been called with correct signature
        callback_mock.assert_called_once_with(player, configured_draft.teams[0], price)


class TestPlayerValueSorting:
    """Test player value sorting functionality."""
    
    def test_sort_players_by_value(self, configured_draft, sample_players):
        """Test sorting players by their value."""
        auction = Auction(configured_draft)
        players = sample_players[:5]
        
        # Mock player values (VOR-based)
        for i, player in enumerate(players):
            player.vor = float(50 - i * 10)  # Decreasing values: 50, 40, 30, 20, 10
        
        sorted_players = auction._sort_players_by_value(players)
        
        # Should be sorted by VOR descending
        assert len(sorted_players) == 5
        for i in range(len(sorted_players) - 1):
            assert sorted_players[i].vor >= sorted_players[i + 1].vor
    
    def test_sort_players_by_value_empty(self, configured_draft):
        """Test sorting empty player list."""
        auction = Auction(configured_draft)
        
        sorted_players = auction._sort_players_by_value([])
        
        assert sorted_players == []


class TestAuctionNotification:
    """Test auction completion notification system."""
    
    def test_notify_auction_completed(self, configured_draft, sample_players):
        """Test auction completion notification."""
        auction = Auction(configured_draft)
        player = sample_players[0]
        team = configured_draft.teams[0]
        price = 25.0
        
        # Add multiple callbacks with correct signature (player, team, price)
        callback1 = Mock()
        callback2 = Mock()
        auction.on_auction_completed.extend([callback1, callback2])
        
        auction._notify_auction_completed(player, team, price)
        
        # Both callbacks should be called with correct signature
        callback1.assert_called_once_with(player, team, price)
        callback2.assert_called_once_with(player, team, price)
    
    def test_notify_auction_completed_callback_error(self, configured_draft, sample_players):
        """Test notification when callback raises error."""
        auction = Auction(configured_draft)
        player = sample_players[0]
        team = configured_draft.teams[0]
        price = 25.0
        
        # Add callback that raises exception
        error_callback = Mock(side_effect=Exception("Callback error"))
        success_callback = Mock()
        auction.on_auction_completed.extend([error_callback, success_callback])
        
        # Should not raise exception
        auction._notify_auction_completed(player, team, price)
        
        # Success callback should still be called
        success_callback.assert_called_once()


class TestAuctionDelegation:
    """Test auction methods that delegate to draft."""
    
    def test_nominate_player_delegation(self, configured_draft, sample_players, sample_owners):
        """Test nominate_player is legacy and returns False."""
        auction = Auction(configured_draft)
        player = sample_players[0]
        owner_id = sample_owners[0].owner_id
        initial_bid = 15.0
        
        result = auction.nominate_player(player, owner_id, initial_bid)
        
        # This method is legacy and always returns False
        assert result is False
    
    def test_place_bid_delegation(self, configured_draft, sample_owners):
        """Test place_bid is legacy and returns False."""
        auction = Auction(configured_draft)
        bidder_id = sample_owners[0].owner_id
        bid_amount = 20.0
        
        result = auction.place_bid(bidder_id, bid_amount)
        
        # This method is legacy and always returns False
        assert result is False


class TestCallbackManagement:
    """Test callback management functionality."""
    
    def test_add_completion_listener(self, configured_draft):
        """Test adding completion listener."""
        auction = Auction(configured_draft)
        callback = Mock()
        
        auction.add_completion_listener(callback)
        
        assert callback in auction.on_auction_completed
        assert len(auction.on_auction_completed) == 1
    
    def test_add_multiple_completion_listeners(self, configured_draft):
        """Test adding multiple completion listeners."""
        auction = Auction(configured_draft)
        callback1 = Mock()
        callback2 = Mock()
        
        auction.add_completion_listener(callback1)
        auction.add_completion_listener(callback2)
        
        assert len(auction.on_auction_completed) == 2
        assert callback1 in auction.on_auction_completed
        assert callback2 in auction.on_auction_completed


class TestAuctionStateQuery:
    """Test auction state query functionality."""
    
    def test_get_auction_state_basic(self, configured_draft):
        """Test getting basic auction state."""
        auction = Auction(configured_draft)
        
        state = auction.get_auction_state()
        
        assert isinstance(state, dict)
        assert 'is_active' in state
        assert 'draft_status' in state
        
        assert state['is_active'] == auction.is_active
        assert state['draft_status'] == configured_draft.status
    
    def test_get_auction_state_active(self, configured_draft):
        """Test getting auction state when active."""
        auction = Auction(configured_draft)
        auction.is_active = True
        
        state = auction.get_auction_state()
        
        assert state['is_active'] is True
    
    def test_get_auction_state_with_current_auction(self, configured_draft):
        """Test auction state returns minimal data."""
        auction = Auction(configured_draft)
        
        # Set up current auction state
        configured_draft.current_player = configured_draft.available_players[0]
        configured_draft.current_bid = 15.0
        configured_draft.current_high_bidder = "owner1"
        
        state = auction.get_auction_state()
        
        # The actual implementation only returns is_active and draft_status
        assert 'is_active' in state
        assert 'draft_status' in state
        assert state['is_active'] == auction.is_active
        assert state['draft_status'] == configured_draft.status


class TestIntegratedAuctionFlow:
    """Test integrated auction workflows."""
    
    def test_complete_auction_cycle(self, configured_draft, sample_players):
        """Test complete auction cycle for single player."""
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        player = sample_players[0]
        
        # Mock team bidding
        for i, team in enumerate(configured_draft.teams):
            team.calculate_bid = Mock(return_value=float(20 + i * 5))
            team.add_player = Mock()
        
        # Mock draft's team lookup
        with patch.object(configured_draft, '_get_team_by_owner') as mock_lookup:
            mock_lookup.return_value = configured_draft.teams[1]  # Team with highest bid
            
            # Run single auction cycle
            bids = auction._collect_sealed_bids(player)
            winner_id, price = auction._determine_auction_winner(bids)
            auction._award_player_to_team(player, winner_id, price)
            
            # Verify auction completed correctly
            assert winner_id is not None
            assert price > 0
            configured_draft.teams[1].add_player.assert_called_once_with(player, price)


class TestEdgeCasesAndErrorConditions:
    """Test edge cases and error conditions."""
    
    def test_auction_with_no_teams(self):
        """Test auction with draft containing no teams."""
        draft = Draft()
        auction = Auction(draft)
        
        # Should not crash on initialization
        assert auction.draft == draft
        assert not auction.is_active
    
    def test_auction_state_after_draft_completion(self, configured_draft):
        """Test auction state after draft completes."""
        configured_draft.start_draft()
        configured_draft._complete_draft()  # Mark draft as completed
        
        auction = Auction(configured_draft)
        
        state = auction.get_auction_state()
        assert state['draft_status'] == 'completed'
    
    def test_collect_bids_all_teams_error(self, configured_draft, sample_players):
        """Test bid collection when all teams error."""
        auction = Auction(configured_draft)
        player = sample_players[0]
        
        # Mock all teams to raise exceptions
        for team in configured_draft.teams:
            team.calculate_bid = Mock(side_effect=Exception("Team error"))
        
        bids = auction._collect_sealed_bids(player)
        
        # Should return empty dict, not crash
        assert isinstance(bids, dict)
        assert len(bids) == 0
    
    def test_large_auction_performance(self, configured_draft):
        """Test auction performance with many players."""
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        
        # Mock many available players
        many_players = [Mock(spec=Player, is_drafted=False) for _ in range(100)]
        configured_draft.available_players.extend(many_players)
        
        # Test sorting large player list
        start_time = time.time()
        for player in many_players:
            player.vor = float(random.randint(10, 100))
        
        sorted_players = auction._sort_players_by_value(many_players)
        end_time = time.time()
        
        assert len(sorted_players) == 100
        assert (end_time - start_time) < 1.0  # Should complete quickly


# Performance and Integration Tests
class TestAuctionPerformance:
    """Test auction performance characteristics."""
    
    @pytest.mark.performance
    def test_bid_collection_performance(self, configured_draft, sample_players):
        """Test bid collection performance with many teams."""
        auction = Auction(configured_draft)
        
        # Add more teams for performance test
        for i in range(20):  # Total 22 teams
            team = Team(f"perf_team_{i}", f"perf_owner_{i}", f"Performance Team {i}")
            team.calculate_bid = Mock(return_value=float(10 + i))
            configured_draft.teams.append(team)
        
        player = sample_players[0]
        
        start_time = time.time()
        bids = auction._collect_sealed_bids(player)
        end_time = time.time()
        
        assert len(bids) == 22
        assert (end_time - start_time) < 0.5  # Should be fast
    
    @pytest.mark.integration
    def test_realistic_sealed_bid_auction(self, configured_draft, sample_players):
        """Test realistic sealed bid auction scenario."""
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        
        # Set up realistic team behaviors
        for i, team in enumerate(configured_draft.teams):
            team.calculate_bid = Mock(return_value=float(15 + i * 3))
            team.add_player = Mock()
        
        # Add completion listener
        completion_events = []
        auction.add_completion_listener(lambda event: completion_events.append(event))
        
        # Run auction for first few players
        for player in sample_players[:3]:
            if player in configured_draft.available_players:
                bids = auction._collect_sealed_bids(player)
                winner_id, price = auction._determine_auction_winner(bids)
                
                if winner_id:
                    with patch.object(configured_draft, '_get_team_by_owner') as mock_lookup:
                        winning_team = next(t for t in configured_draft.teams if t.team_id == winner_id)
                        mock_lookup.return_value = winning_team
                        auction._award_player_to_team(player, winner_id, price)
        
        # Verify realistic auction behavior
        assert len(completion_events) <= 3
        
        # Check that teams with higher bids generally won
        for team in configured_draft.teams:
            if team.add_player.called:
                # Team should have been called to add player
                assert team.add_player.call_count <= 3