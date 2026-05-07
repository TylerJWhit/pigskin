"""Sprint 9 QA tests — Issue #115: Auction winner charged top_bid+1 on tie.

These tests FAIL before the fix and PASS after.
"""

from unittest.mock import Mock

from classes.auction import Auction
from classes.draft import Draft


def _make_auction() -> Auction:
    """Return a minimal Auction backed by a mock Draft."""
    mock_draft = Mock(spec=Draft)
    mock_draft.status = "started"
    mock_draft.teams = []
    mock_draft.available_players = []
    mock_draft.current_player = None
    mock_draft.current_bid = 0.0
    mock_draft.current_high_bidder = None
    return Auction(mock_draft)


class TestIssue115AuctionTieCharging:
    """Issue #115 — winner pays top_bid + 1 on a tie instead of top_bid."""

    def test_tie_winner_pays_top_bid_not_top_bid_plus_one(self):
        """On a two-way tie, winner should pay top_bid (50), not top_bid+1 (51)."""
        auction = _make_auction()
        bids = {"team_a": 50.0, "team_b": 50.0}
        winner_id, price = auction._determine_auction_winner(bids)
        assert winner_id in ("team_a", "team_b"), "Winner must be one of the tied bidders"
        # BUG: current code returns top_bid + 1.0 = 51.0 for ties
        assert price == 50.0, (
            f"Expected winner to pay top_bid=50.0 on tie, but paid {price}. "
            "Issue #115: _determine_auction_winner charges top_bid+1 instead of top_bid on tie."
        )

    def test_three_way_tie_winner_pays_top_bid(self):
        """On a three-way tie, winner should pay top_bid, not top_bid+1."""
        auction = _make_auction()
        bids = {"team_x": 100.0, "team_y": 100.0, "team_z": 100.0}
        winner_id, price = auction._determine_auction_winner(bids)
        assert winner_id in ("team_x", "team_y", "team_z")
        assert price == 100.0, (
            f"Expected 100.0 on three-way tie, got {price}. "
            "Issue #115 still present."
        )

    def test_tie_winner_is_one_of_the_tied_bidders(self):
        """Sanity: winner must always come from the tied set."""
        auction = _make_auction()
        bids = {"alpha": 75.0, "beta": 75.0}
        winner_id, _ = auction._determine_auction_winner(bids)
        assert winner_id in ("alpha", "beta")

    def test_no_tie_uses_second_price_plus_one(self):
        """No tie: Vickrey second-price+1 logic should still work (baseline)."""
        auction = _make_auction()
        bids = {"team_a": 80.0, "team_b": 50.0}
        winner_id, price = auction._determine_auction_winner(bids)
        assert winner_id == "team_a"
        assert price == 51.0, f"Expected second_bid+1=51.0, got {price}"

    def test_single_bidder_pays_own_bid(self):
        """Only one bidder: pays their own bid (no second price)."""
        auction = _make_auction()
        bids = {"solo": 60.0}
        winner_id, price = auction._determine_auction_winner(bids)
        assert winner_id == "solo"
        assert price == 60.0
