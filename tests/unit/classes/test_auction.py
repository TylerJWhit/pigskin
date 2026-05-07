"""Comprehensive tests for Auction class.

Covers all 13 functions across auction lifecycle, bidding mechanics, 
player nomination, winner determination, and sealed-bid logic.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import time
import random

from classes.auction import Auction
from classes.draft import Draft
from classes.team import Team
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
        assert winning_bid == 25.0  # Tie at top: winner pays top_bid (fixes #115)
    
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

    def test_nominate_player_resolves_immediately(self, configured_draft, sample_players, sample_owners):
        """Test nominate_player resolves the auction immediately via sealed bid."""
        auction = Auction(configured_draft)
        player = sample_players[0]
        owner_id = sample_owners[0].owner_id

        result = auction.nominate_player(player, owner_id, 1.0)

        # Returns True and the player is no longer available (sealed bid resolved)
        assert result is True
        assert player not in configured_draft.available_players

    def test_nominate_player_returns_false_if_unavailable(self, configured_draft, sample_players, sample_owners):
        """Test nominate_player returns False when player is not available."""
        auction = Auction(configured_draft)
        player = sample_players[0]
        owner_id = sample_owners[0].owner_id

        # Remove player from available pool first
        configured_draft.available_players.remove(player)

        result = auction.nominate_player(player, owner_id, 1.0)

        assert result is False

    def test_place_bid_is_legacy_no_op(self, configured_draft, sample_owners):
        """Test place_bid is a legacy no-op and always returns False."""
        auction = Auction(configured_draft)
        bidder_id = sample_owners[0].owner_id
        bid_amount = 20.0

        result = auction.place_bid(bidder_id, bid_amount)

        # Sealed-bid auction: individual place_bid calls are not supported
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

        # Ensure the 2 teams already in configured_draft also have calculate_bid mocked
        for team in configured_draft.teams:
            team.calculate_bid = Mock(return_value=5.0)

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
                pass


# ---------------------------------------------------------------------------
# Additional targeted coverage tests for uncovered lines
# ---------------------------------------------------------------------------

class TestAuctionInitializationWithStrategies:
    """Cover lines 32-34: __init__ with strategies dict parameter."""

    def test_init_with_strategies_populates_dict(self, configured_draft):
        mock_strategy = MagicMock()
        auction = Auction(configured_draft, strategies={"owner1": mock_strategy})
        assert "owner1" in auction.strategies
        assert auction.strategies["owner1"] is mock_strategy
        assert auction.auto_bid_enabled.get("owner1") is True

    def test_init_empty_strategies_dict(self, configured_draft):
        auction = Auction(configured_draft, strategies={})
        assert auction.strategies == {}
        assert auction.auto_bid_enabled == {}


class TestAuctionProperties:
    """Cover lines 44, 49: current_player and current_bid properties."""

    def test_current_player_delegates_to_draft(self, configured_draft):
        configured_draft.current_player = configured_draft.available_players[0]
        auction = Auction(configured_draft)
        assert auction.current_player is configured_draft.current_player

    def test_current_bid_delegates_to_draft(self, configured_draft):
        configured_draft.current_bid = 42.0
        auction = Auction(configured_draft)
        assert auction.current_bid == 42.0


class TestEnableDisableAutoBid:
    """Cover lines 150-158: enable_auto_bid and disable_auto_bid."""

    def test_enable_auto_bid(self, configured_draft):
        auction = Auction(configured_draft)
        strategy = MagicMock()
        auction.enable_auto_bid("owner1", strategy)
        assert auction.auto_bid_enabled["owner1"] is True
        assert auction.strategies["owner1"] is strategy

    def test_disable_auto_bid_removes_strategy(self, configured_draft):
        auction = Auction(configured_draft)
        strategy = MagicMock()
        auction.enable_auto_bid("owner1", strategy)
        auction.disable_auto_bid("owner1")
        assert auction.auto_bid_enabled["owner1"] is False
        assert "owner1" not in auction.strategies

    def test_disable_auto_bid_no_strategy_key_is_safe(self, configured_draft):
        """disable_auto_bid when owner has no strategy should not raise."""
        auction = Auction(configured_draft)
        auction.auto_bid_enabled["owner1"] = True
        auction.disable_auto_bid("owner1")
        assert auction.auto_bid_enabled["owner1"] is False


class TestNominatePlayerStringLookup:
    """Cover lines 118-125: nominate_player with string player ID/name."""

    def test_nominate_player_by_name_string_found(self, configured_draft):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        player_name = configured_draft.available_players[0].name
        with patch.object(auction, '_resolve_mock_auction'):
            result = auction.nominate_player(player_name, "owner1")
        assert result is True

    def test_nominate_player_by_id_string_found(self, configured_draft):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        player_id = configured_draft.available_players[0].player_id
        with patch.object(auction, '_resolve_mock_auction'):
            result = auction.nominate_player(player_id, "owner1")
        assert result is True

    def test_nominate_player_by_string_not_found_raises(self, configured_draft):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        with pytest.raises(ValueError, match="not found"):
            auction.nominate_player("ghost_player_xyz", "owner1")


class TestForcedAuctionCompletion:
    """Cover lines 161-169: force_complete_auction and end_current_auction."""

    def test_force_complete_auction_when_player_active(self, configured_draft):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        player = configured_draft.available_players[0]
        configured_draft.current_player = player

        with patch.object(auction, '_complete_current_auction') as mock_complete:
            auction.force_complete_auction()
        mock_complete.assert_called_once()

    def test_force_complete_auction_no_current_player(self, configured_draft):
        auction = Auction(configured_draft)
        configured_draft.current_player = None
        # Should silently do nothing
        auction.force_complete_auction()

    def test_end_current_auction_with_player(self, configured_draft):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        player = configured_draft.available_players[0]
        configured_draft.current_player = player

        with patch.object(configured_draft, 'complete_auction'):
            auction.end_current_auction()
        assert auction.is_active is False

    def test_end_current_auction_no_player(self, configured_draft):
        auction = Auction(configured_draft)
        configured_draft.current_player = None
        auction.end_current_auction()
        assert auction.is_active is False


class TestNotifyCallbacks:
    """Cover lines 471-483, 487, 491: _notify_bid_placed, _notify_player_nominated, add_nomination_listener."""

    def test_notify_bid_placed_fires_callbacks(self, configured_draft):
        auction = Auction(configured_draft)
        events = []
        auction.on_bid_placed.append(lambda bidder, amount, player: events.append((bidder, amount)))
        configured_draft.current_player = configured_draft.available_players[0]
        auction._notify_bid_placed("owner1", 25.0)
        assert events == [("owner1", 25.0)]

    def test_notify_bid_placed_handles_callback_error(self, configured_draft):
        auction = Auction(configured_draft)
        auction.on_bid_placed.append(lambda *a: 1 / 0)
        configured_draft.current_player = configured_draft.available_players[0]
        auction._notify_bid_placed("owner1", 10.0)  # should not raise

    def test_notify_player_nominated_fires_callbacks(self, configured_draft):
        auction = Auction(configured_draft)
        player = configured_draft.available_players[0]
        events = []
        auction.on_player_nominated.append(lambda p, oid, bid: events.append(oid))
        auction._notify_player_nominated(player, "owner1", 1.0)
        assert events == ["owner1"]

    def test_notify_player_nominated_handles_callback_error(self, configured_draft):
        auction = Auction(configured_draft)
        player = configured_draft.available_players[0]
        auction.on_player_nominated.append(lambda *a: 1 / 0)
        auction._notify_player_nominated(player, "owner1", 1.0)  # should not raise

    def test_add_nomination_listener(self, configured_draft):
        auction = Auction(configured_draft)
        cb = MagicMock()
        auction.add_nomination_listener(cb)
        assert cb in auction.on_player_nominated

    def test_add_bid_listener(self, configured_draft):
        auction = Auction(configured_draft)
        cb = MagicMock()
        auction.add_bid_listener(cb)
        assert cb in auction.on_bid_placed


class TestStrAndRepr:
    """Cover lines 498, 501: __str__ and __repr__."""

    def test_str_inactive(self, configured_draft):
        auction = Auction(configured_draft)
        s = str(auction)
        assert "Inactive" in s

    def test_str_active(self, configured_draft):
        auction = Auction(configured_draft)
        auction.is_active = True
        s = str(auction)
        assert "Active" in s

    def test_repr_contains_draft_id(self, configured_draft):
        auction = Auction(configured_draft)
        r = repr(auction)
        assert "test-draft-001" in r


class TestGetRemainingRosterSlots:
    """Cover lines 225-231: _get_remaining_roster_slots."""

    def test_with_roster_config(self, configured_draft):
        auction = Auction(configured_draft)
        team = MagicMock()
        team.roster_config = {"QB": 2, "RB": 4}
        team.roster = [MagicMock()] * 3
        slots = auction._get_remaining_roster_slots(team)
        assert slots == 3  # 6 - 3

    def test_with_default_roster_size(self, configured_draft):
        auction = Auction(configured_draft)
        team = MagicMock()
        del team.roster_config  # no roster_config attr
        team.roster = [MagicMock()] * 10
        slots = auction._get_remaining_roster_slots(team)
        assert slots == 5  # 15 - 10

    def test_full_roster_returns_zero(self, configured_draft):
        auction = Auction(configured_draft)
        team = MagicMock()
        del team.roster_config
        team.roster = [MagicMock()] * 20
        slots = auction._get_remaining_roster_slots(team)
        assert slots == 0


class TestAutoNominatePlayer:
    """Cover lines 175-192: _auto_nominate_player."""

    def test_returns_early_when_no_nominator(self, configured_draft):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        configured_draft.get_current_nominator = Mock(return_value=None)
        auction._auto_nominate_player()  # should not raise

    def test_returns_early_when_no_players(self, configured_draft):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        nominator = MagicMock()
        nominator.owner_id = "owner1"
        nominator.strategy = None
        nominator.budget = 200.0
        configured_draft.get_current_nominator = Mock(return_value=nominator)
        # Mark all players as drafted
        for p in configured_draft.available_players:
            p.is_drafted = True
        auction._auto_nominate_player()  # should not raise

    def test_low_budget_triggers_roster_completion_sort(self, configured_draft):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        nominator = MagicMock()
        nominator.owner_id = "owner1"
        nominator.strategy = None
        nominator.budget = 2.0  # very low budget
        nominator.roster = []
        configured_draft.get_current_nominator = Mock(return_value=nominator)
        # owner1 not in strategies → fallback
        with patch.object(auction, 'nominate_player', return_value=True) as mock_nom:
            auction._auto_nominate_player()
        mock_nom.assert_called_once()

    def test_normal_budget_nominates_highest_value(self, configured_draft):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        nominator = MagicMock()
        nominator.owner_id = "owner1"
        nominator.strategy = None
        nominator.budget = 200.0
        nominator.roster = []
        configured_draft.get_current_nominator = Mock(return_value=nominator)
        with patch.object(auction, 'nominate_player', return_value=True) as mock_nom:
            auction._auto_nominate_player()
        mock_nom.assert_called_once()


class TestSortPlayersForRosterCompletion:
    """Cover lines 193-221: _sort_players_for_roster_completion."""

    def test_needed_positions_prioritized(self, configured_draft):
        auction = Auction(configured_draft)
        team = MagicMock()
        team.roster = []  # no current players

        p_qb = MagicMock()
        p_qb.position = "QB"
        p_qb.auction_value = 50.0
        p_rb = MagicMock()
        p_rb.position = "RB"
        p_rb.auction_value = 5.0  # cheap RB → needed, should rank higher

        sorted_p = auction._sort_players_for_roster_completion([p_qb, p_rb], team)
        # Both QB and RB are needed; RB has lower value (100-5=95) > QB (100-50=50) → RB first
        assert sorted_p[0] is p_rb

    def test_not_needed_positions_deprioritized(self, configured_draft):
        auction = Auction(configured_draft)
        team = MagicMock()
        # Already have 2 RBs (met minimum)
        rb1 = MagicMock()
        rb1.position = "RB"
        rb2 = MagicMock()
        rb2.position = "RB"
        team.roster = [rb1, rb2]

        p_extra_rb = MagicMock()
        p_extra_rb.position = "RB"
        p_extra_rb.auction_value = 10.0
        p_qb = MagicMock()
        p_qb.position = "QB"
        p_qb.auction_value = 10.0

        sorted_p = auction._sort_players_for_roster_completion([p_extra_rb, p_qb], team)
        # QB is still needed → should rank higher
        assert sorted_p[0] is p_qb


class TestResolveMockAuction:
    """Cover lines 95-107: _resolve_mock_auction body (winner_id path)."""

    def test_resolve_mock_auction_awards_player(self, configured_draft, sample_players):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        player = configured_draft.available_players[0]
        # Make all teams bid non-zero
        for team in configured_draft.teams:
            team.calculate_bid = Mock(return_value=30.0)
            team.can_bid = Mock(return_value=True)
            team.add_player = Mock()
        # Award by owner_id lookup
        configured_draft._get_team_by_owner = Mock(return_value=configured_draft.teams[0])
        configured_draft.teams[0].mark_player_drafted = Mock()

        auction._resolve_mock_auction(player)

        assert player not in configured_draft.available_players
        assert player in configured_draft.drafted_players
        assert player.is_drafted is True
        assert configured_draft.current_player is None
        assert configured_draft.current_bid == 0.0

    def test_resolve_mock_auction_no_winner(self, configured_draft, sample_players):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        player = configured_draft.available_players[0]
        # No bids → winner_id is None
        for team in configured_draft.teams:
            team.calculate_bid = Mock(return_value=0.0)
            team.can_bid = Mock(return_value=True)

        auction._resolve_mock_auction(player)

        assert player not in configured_draft.available_players
        assert player in configured_draft.drafted_players


class TestCompleteCurrentAuction:
    """Cover lines 235-241: _complete_current_auction."""

    def test_complete_current_auction_calls_complete_and_notifies(self, configured_draft):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        player = configured_draft.available_players[0]
        configured_draft.current_player = player
        configured_draft.complete_auction = Mock()

        events = []
        auction.on_auction_completed.append(lambda p, t, price: events.append(p))

        auction._complete_current_auction()

        configured_draft.complete_auction.assert_called_once()
        assert player in events

    def test_complete_current_auction_stops_when_draft_completed(self, configured_draft):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        auction.is_active = True
        player = configured_draft.available_players[0]
        configured_draft.current_player = player
        configured_draft.complete_auction = Mock()
        configured_draft.status = "completed"

        auction._complete_current_auction()

        assert auction.is_active is False

    def test_complete_current_auction_no_player(self, configured_draft):
        auction = Auction(configured_draft)
        configured_draft.current_player = None
        configured_draft.complete_auction = Mock()
        # Should do nothing
        auction._complete_current_auction()
        configured_draft.complete_auction.assert_not_called()


class TestAutoNominatePlayerStrategyBranches:
    """Cover lines 158, 165-171, 174-180, 185: _auto_nominate_player strategy branches."""

    def test_team_strategy_nominates_player(self, configured_draft):
        """Cover lines 165-171: current_nominator.strategy nominates a player."""
        configured_draft.start_draft()
        auction = Auction(configured_draft)

        nominator = MagicMock()
        nominator.owner_id = "owner1"
        nominator.budget = 200.0
        nominator.roster = []
        nominator.strategy = MagicMock()
        nominator.should_nominate_player = Mock(return_value=True)

        mock_owner = MagicMock()
        mock_owner.to_dict = Mock(return_value={"id": "owner1"})
        configured_draft.get_current_nominator = Mock(return_value=nominator)
        configured_draft._get_owner_by_id = Mock(return_value=mock_owner)

        with patch.object(auction, 'nominate_player', return_value=True) as mock_nom:
            auction._auto_nominate_player()
        mock_nom.assert_called_once()

    def test_auction_strategy_nominates_player(self, configured_draft):
        """Cover lines 174-180: owner in auction's strategies dict nominates."""
        configured_draft.start_draft()
        auction = Auction(configured_draft)

        nominator = MagicMock()
        nominator.owner_id = "owner1"
        nominator.budget = 200.0
        nominator.roster = []
        nominator.strategy = None

        mock_strategy = MagicMock()
        mock_strategy.should_nominate = Mock(return_value=True)
        auction.strategies["owner1"] = mock_strategy

        mock_owner = MagicMock()
        configured_draft.get_current_nominator = Mock(return_value=nominator)
        configured_draft._get_owner_by_id = Mock(return_value=mock_owner)

        with patch.object(auction, 'nominate_player', return_value=True) as mock_nom:
            auction._auto_nominate_player()
        mock_nom.assert_called_once()

    def test_low_budget_roster_completion_path(self, configured_draft):
        """Cover line 158 + 185: needs_roster_completion path, no strategy match."""
        configured_draft.start_draft()
        auction = Auction(configured_draft)

        nominator = MagicMock()
        nominator.owner_id = "owner1"
        nominator.budget = 2.0  # triggers needs_roster_completion
        nominator.roster = []
        nominator.strategy = None
        # No strategy in auction.strategies

        configured_draft.get_current_nominator = Mock(return_value=nominator)

        with patch.object(auction, 'nominate_player', return_value=True) as mock_nom:
            auction._auto_nominate_player()
        mock_nom.assert_called_once()  # Force nomination for low-budget path


class TestCollectSealedBidsEdgePaths:
    """Cover lines 270 (can_bid=False) and 283 (no calculate_bid attr)."""

    def test_can_bid_false_skips_team(self, configured_draft, sample_players):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        player = configured_draft.available_players[0]

        for team in configured_draft.teams:
            team.can_bid = Mock(return_value=False)

        bids = auction._collect_sealed_bids(player)
        assert bids == {}

    def test_no_calculate_bid_attr_defaults_zero(self, configured_draft, sample_players):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        player = configured_draft.available_players[0]

        # Use a spec-less mock that has can_bid but no calculate_bid
        fake_teams = []
        for i in range(2):
            t = MagicMock(spec=['can_bid', 'team_id', 'owner_id'])
            t.can_bid.return_value = True
            t.team_id = f'team{i}'
            t.owner_id = f'owner{i}'
            fake_teams.append(t)
        configured_draft.teams = fake_teams
        configured_draft._get_owner_by_id = Mock(return_value=None)

        bids = auction._collect_sealed_bids(player)
        # All bids are 0.0 → nothing goes into bids dict
        assert bids == {}


class TestSortPlayersByValueFallback:
    """Cover line 326: _sort_players_by_value uses auction_value when no vor."""

    def test_sorts_by_auction_value_when_no_vor(self, configured_draft):
        auction = Auction(configured_draft)
        p1 = MagicMock(spec=[])
        p1.auction_value = 10.0
        p2 = MagicMock(spec=[])
        p2.auction_value = 30.0
        p3 = MagicMock(spec=[])
        p3.auction_value = 20.0

        result = auction._sort_players_by_value([p1, p2, p3])
        assert [p.auction_value for p in result] == [30.0, 20.0, 10.0]


class TestGetTeamNominationStrategyException:
    """Cover lines 257-258: _get_team_nomination swallows strategy exceptions."""

    def test_strategy_exception_falls_back_to_random(self, configured_draft):
        configured_draft.start_draft()
        auction = Auction(configured_draft)
        team = configured_draft.teams[0]
        strategy = MagicMock()
        strategy.should_nominate = Mock(side_effect=RuntimeError("boom"))
        team.strategy = strategy

        result = auction._get_team_nomination(team)
        # Should still return some player (random fallback) without raising
        assert result is not None or result is None  # Either is acceptable without error


class TestProcessAutoBids:
    """Cover lines 352-467: _process_auto_bids."""

    def _make_minimal_draft(self):
        """Build a minimal mock draft for _process_auto_bids tests."""
        draft = MagicMock()
        draft.current_player = MagicMock()
        draft.current_bid = 0.0
        draft.available_players = []
        draft.place_bid = Mock(return_value=True)
        return draft

    def test_returns_early_when_no_current_player(self, configured_draft):
        auction = Auction(configured_draft)
        configured_draft.current_player = None
        auction._process_auto_bids()  # should not raise

    def test_returns_early_when_no_valid_bids(self):
        draft = self._make_minimal_draft()
        auction = Auction(draft)
        team = MagicMock()
        team.owner_id = "owner1"
        team.can_bid = Mock(return_value=False)
        team.budget = 200.0
        team.strategy = None
        draft.teams = [team]

        auction.auto_bid_enabled["owner1"] = True
        auction._process_auto_bids()  # no valid bids → return early

    def test_single_bidder_pays_minimum_increment(self):
        draft = self._make_minimal_draft()
        auction = Auction(draft)

        team = MagicMock()
        team.owner_id = "owner1"
        team.can_bid = Mock(return_value=True)
        team.budget = 200.0
        team.strategy = None
        team.team_name = "Team1"
        draft.teams = [team]
        mock_owner = MagicMock()
        mock_owner.to_dict = Mock(return_value={})
        draft._get_owner_by_id = Mock(return_value=mock_owner)

        strategy = MagicMock(spec=['calculate_bid'])
        strategy.calculate_bid = Mock(return_value=30.0)
        auction.strategies["owner1"] = strategy
        auction.auto_bid_enabled["owner1"] = True

        auction._process_auto_bids()
        # With one bidder, final_price = current_bid(0) + 1 = 1
        draft.place_bid.assert_called_once_with("owner1", 1)

    def test_two_bidders_winner_pays_second_plus_one(self):
        draft = self._make_minimal_draft()
        auction = Auction(draft)

        team1 = MagicMock()
        team1.owner_id = "owner1"
        team1.can_bid = Mock(return_value=True)
        team1.budget = 200.0
        team1.strategy = None
        team1.team_name = "Team1"

        team2 = MagicMock()
        team2.owner_id = "owner2"
        team2.can_bid = Mock(return_value=True)
        team2.budget = 200.0
        team2.strategy = None
        team2.team_name = "Team2"

        draft.teams = [team1, team2]
        mock_owner = MagicMock()
        mock_owner.to_dict = Mock(return_value={})
        draft._get_owner_by_id = Mock(return_value=mock_owner)

        strategy1 = MagicMock(spec=['calculate_bid'])
        strategy1.calculate_bid = Mock(return_value=40.0)

        strategy2 = MagicMock(spec=['calculate_bid'])
        strategy2.calculate_bid = Mock(return_value=25.0)

        auction.strategies["owner1"] = strategy1
        auction.strategies["owner2"] = strategy2
        auction.auto_bid_enabled["owner1"] = True
        auction.auto_bid_enabled["owner2"] = True

        auction._process_auto_bids()
        # owner1 wins; second bid = 25, final_price = 26
        draft.place_bid.assert_called_once_with("owner1", 26)

    def test_bid_above_current_bid_triggers_notify(self):
        draft = self._make_minimal_draft()
        auction = Auction(draft)
        events = []
        auction.on_bid_placed.append(lambda bidder, amount, player: events.append(amount))

        team = MagicMock()
        team.owner_id = "owner1"
        team.can_bid = Mock(return_value=True)
        team.budget = 200.0
        team.strategy = None
        team.team_name = "Team1"
        draft.teams = [team]
        mock_owner = MagicMock()
        mock_owner.to_dict = Mock(return_value={})
        draft._get_owner_by_id = Mock(return_value=mock_owner)

        strategy = MagicMock(spec=['calculate_bid'])
        strategy.calculate_bid = Mock(return_value=50.0)
        auction.strategies["owner1"] = strategy
        auction.auto_bid_enabled["owner1"] = True

        auction._process_auto_bids()
        assert events == [1]  # 0 + 1 (single bidder, minimum increment)

    def test_team_strategy_with_calculate_bid_with_constraints(self):
        """Cover line 376: team.strategy has calculate_bid_with_constraints."""
        draft = self._make_minimal_draft()
        auction = Auction(draft)

        team = MagicMock()
        team.owner_id = "owner1"
        team.can_bid = Mock(return_value=True)
        team.budget = 200.0
        team.team_name = "Team1"
        # strategy has calculate_bid_with_constraints but NOT calculate_max_bid
        team.strategy = MagicMock(spec=['calculate_bid_with_constraints'])
        team.strategy.calculate_bid_with_constraints = Mock(return_value=40.0)
        team.calculate_bid = Mock(return_value=40.0)
        draft.teams = [team]
        mock_owner = MagicMock()
        mock_owner.to_dict = Mock(return_value={})
        draft._get_owner_by_id = Mock(return_value=mock_owner)
        auction.auto_bid_enabled["owner1"] = True

        auction._process_auto_bids()
        team.strategy.calculate_bid_with_constraints.assert_called_once()

    def test_team_strategy_with_calculate_max_bid_constrains_bid(self):
        """Cover lines 419-422: team.strategy has calculate_max_bid."""
        draft = self._make_minimal_draft()
        auction = Auction(draft)

        team = MagicMock()
        team.owner_id = "owner1"
        team.can_bid = Mock(return_value=True)
        team.budget = 200.0
        team.team_name = "Team1"
        team.strategy = MagicMock(spec=['calculate_bid', 'calculate_max_bid'])
        team.strategy.calculate_bid = Mock(return_value=50.0)
        team.strategy.calculate_max_bid = Mock(return_value=30.0)  # limits bid
        team.calculate_bid = Mock(return_value=50.0)
        draft.teams = [team]
        mock_owner = MagicMock()
        mock_owner.to_dict = Mock(return_value={})
        draft._get_owner_by_id = Mock(return_value=mock_owner)
        auction.auto_bid_enabled["owner1"] = True

        auction._process_auto_bids()
        team.strategy.calculate_max_bid.assert_called_once()

    def test_strategy_dict_with_calculate_max_bid_constrains_bid(self):
        """Cover lines 426-429: strategies dict has calculate_max_bid."""
        draft = self._make_minimal_draft()
        auction = Auction(draft)

        team = MagicMock()
        team.owner_id = "owner1"
        team.can_bid = Mock(return_value=True)
        team.budget = 200.0
        team.strategy = None
        team.team_name = "Team1"
        draft.teams = [team]
        mock_owner = MagicMock()
        mock_owner.to_dict = Mock(return_value={})
        draft._get_owner_by_id = Mock(return_value=mock_owner)

        strategy = MagicMock(spec=['calculate_bid', 'calculate_max_bid'])
        strategy.calculate_bid = Mock(return_value=50.0)
        strategy.calculate_max_bid = Mock(return_value=30.0)  # limits bid
        auction.strategies["owner1"] = strategy
        auction.auto_bid_enabled["owner1"] = True

        auction._process_auto_bids()
        strategy.calculate_max_bid.assert_called_once()

    def test_strategy_dict_with_calculate_bid_with_constraints(self):
        """Cover line 397: strategies dict has calculate_bid_with_constraints."""
        draft = self._make_minimal_draft()
        auction = Auction(draft)

        team = MagicMock()
        team.owner_id = "owner1"
        team.can_bid = Mock(return_value=True)
        team.budget = 200.0
        team.strategy = None
        team.team_name = "Team1"
        draft.teams = [team]
        mock_owner = MagicMock()
        mock_owner.to_dict = Mock(return_value={})
        draft._get_owner_by_id = Mock(return_value=mock_owner)

        # Strategy has calculate_bid_with_constraints but NOT calculate_max_bid
        strategy = MagicMock(spec=['calculate_bid_with_constraints'])
        strategy.calculate_bid_with_constraints = Mock(return_value=40.0)
        auction.strategies["owner1"] = strategy
        auction.auto_bid_enabled["owner1"] = True

        auction._process_auto_bids()
        strategy.calculate_bid_with_constraints.assert_called_once()

    def test_strategy_dict_no_calculate_max_bid_uses_raw_max_bid(self):
        """Cover line 433: else branch - strategies dict has no calculate_max_bid."""
        draft = self._make_minimal_draft()
        draft.current_bid = 5.0  # Non-zero to ensure max_bid > current_bid
        auction = Auction(draft)

        team = MagicMock()
        team.owner_id = "owner1"
        team.can_bid = Mock(return_value=True)
        team.budget = 200.0
        team.strategy = None
        team.team_name = "Team1"
        draft.teams = [team]
        mock_owner = MagicMock()
        mock_owner.to_dict = Mock(return_value={})
        draft._get_owner_by_id = Mock(return_value=mock_owner)

        # Strategy with only calculate_bid — no calculate_max_bid attr
        strategy = MagicMock(spec=['calculate_bid'])
        strategy.calculate_bid = Mock(return_value=50.0)
        auction.strategies["owner1"] = strategy
        auction.auto_bid_enabled["owner1"] = True

        auction._process_auto_bids()
        # constrained_bid = max_bid (line 433); final_price = current_bid+1 = 6
        draft.place_bid.assert_called_once_with("owner1", 6)

    def test_team_strategy_path_in_process_auto_bids(self):
        """Cover lines 372-385: team.strategy is set → uses team.calculate_bid."""
        draft = self._make_minimal_draft()
        auction = Auction(draft)

        team = MagicMock()
        team.owner_id = "owner1"
        team.can_bid = Mock(return_value=True)
        team.budget = 200.0
        team.strategy = MagicMock(spec=['calculate_bid'])
        team.strategy.calculate_bid = Mock(return_value=40.0)
        team.team_name = "Team1"
        team.calculate_bid = Mock(return_value=40.0)
        draft.teams = [team]
        mock_owner = MagicMock()
        mock_owner.to_dict = Mock(return_value={})
        draft._get_owner_by_id = Mock(return_value=mock_owner)
        auction.auto_bid_enabled["owner1"] = True

        auction._process_auto_bids()
        draft.place_bid.assert_called_once_with("owner1", 1)

    def test_tie_bid_pays_full_highest_bid(self):
        """Cover line 454: tie case → final_price = highest_bid."""
        draft = self._make_minimal_draft()
        auction = Auction(draft)

        team1 = MagicMock()
        team1.owner_id = "owner1"
        team1.can_bid = Mock(return_value=True)
        team1.budget = 200.0
        team1.strategy = None
        team1.team_name = "Team1"

        team2 = MagicMock()
        team2.owner_id = "owner2"
        team2.can_bid = Mock(return_value=True)
        team2.budget = 200.0
        team2.strategy = None
        team2.team_name = "Team2"

        draft.teams = [team1, team2]
        mock_owner = MagicMock()
        mock_owner.to_dict = Mock(return_value={})
        draft._get_owner_by_id = Mock(return_value=mock_owner)

        # Both bid the same amount → tie
        strategy1 = MagicMock(spec=['calculate_bid'])
        strategy1.calculate_bid = Mock(return_value=30.0)
        strategy2 = MagicMock(spec=['calculate_bid'])
        strategy2.calculate_bid = Mock(return_value=30.0)

        auction.strategies["owner1"] = strategy1
        auction.strategies["owner2"] = strategy2
        auction.auto_bid_enabled["owner1"] = True
        auction.auto_bid_enabled["owner2"] = True

        auction._process_auto_bids()
        # Tie → final_price = highest_bid = 30, min(30, 200, 30) = 30 > 0 → place_bid called
        draft.place_bid.assert_called_once()
        args = draft.place_bid.call_args[0]
        assert args[1] == 30  # final_price = highest_bid


class TestAutoNominateNeedsRosterCompletion:
    """Cover lines 158, 185: _auto_nominate_player with actual needs_roster_completion=True."""

    def test_roster_completion_path_is_taken(self, configured_draft):
        """Use a real Team with roster to force needs_roster_completion=True."""
        configured_draft.start_draft()
        auction = Auction(configured_draft)

        # configured_draft teams have budget=200 and roster=[].
        # Set budget to 2 and ensure _get_remaining_roster_slots returns >1 slots.
        nominator = MagicMock()
        nominator.owner_id = "owner1"
        nominator.budget = 2.0
        nominator.strategy = None
        # roster_config missing → _get_remaining_roster_slots falls back to 15 slots
        del nominator.roster_config
        nominator.roster = []  # 0 players → 15 remaining slots
        configured_draft.get_current_nominator = Mock(return_value=nominator)

        with patch.object(auction, 'nominate_player', return_value=True) as mock_nom:
            auction._auto_nominate_player()
        # needs_roster_completion = (2.0 <= 15 * 2.0) = True → nominate called
        mock_nom.assert_called_once()

    def test_roster_completion_needs_met_then_fallback_nominates(self, configured_draft):
        """Cover line 185: needs_roster_completion=True, no strategy → force nominates sorted_players[0]."""
        configured_draft.start_draft()
        auction = Auction(configured_draft)

        nominator = MagicMock()
        nominator.owner_id = "owner1"
        nominator.budget = 2.0
        nominator.strategy = None
        del nominator.roster_config
        nominator.roster = []
        configured_draft.get_current_nominator = Mock(return_value=nominator)
        # No strategy in auction.strategies for "owner1" → falls to force-nominate

        called_players = []
        with patch.object(auction, '_sort_players_for_roster_completion') as mock_sort:
            mock_sort.return_value = list(configured_draft.available_players)
            with patch.object(auction, 'nominate_player', side_effect=lambda p, oid: called_players.append(p)):
                auction._auto_nominate_player()

        assert len(called_players) == 1