"""Regression tests for sealed-bid auction behavior."""

from classes.auction import Auction
from classes.draft import Draft
from classes.owner import Owner
from classes.player import Player
from classes.team import Team


class FixedBidStrategy:
    def __init__(self, bid):
        self.bid = bid

    def calculate_bid(self, *_args, **_kwargs):
        return self.bid


def _draft_with_player():
    draft = Draft(name="sealed bid test", budget_per_team=200, roster_size=1)
    for idx in range(1, 4):
        owner = Owner(f"owner{idx}", f"Owner {idx}")
        team = Team(f"team{idx}", f"owner{idx}", f"Team {idx}", 200)
        draft.add_owner(owner)
        draft.add_team(team)
    player = Player("p1", "Player One", "RB", "TST", 100)
    draft.add_players([player])
    draft.start_draft()
    return draft, player


def test_nomination_resolves_immediately_as_vickrey_second_price():
    draft, player = _draft_with_player()
    auction = Auction(draft)
    auction.start_auction()
    auction.enable_auto_bid("owner2", FixedBidStrategy(40))
    auction.enable_auto_bid("owner3", FixedBidStrategy(25))

    assert auction.nominate_player(player, "owner1", initial_bid=1)

    assert draft.current_player is None
    assert player in draft.drafted_players
    winner = next(team for team in draft.teams if team.owner_id == "owner2")
    assert player in winner.roster
    assert draft.transactions[-1]["winning_bidder"] == "owner2"
    assert draft.transactions[-1]["final_price"] == 26


def test_auction_state_has_no_timer_field():
    draft, _player = _draft_with_player()
    state = Auction(draft).get_auction_state()
    assert "time_remaining" not in state
