"""Tests for API schema models — covers all 0% schema modules."""
import pytest
from pydantic import ValidationError

from api.schemas.auction import BidRequest, BidResponse
from api.schemas.common import HealthResponse, ErrorDetail
from api.schemas.draft import DraftCreateRequest, DraftStatusResponse
from api.schemas.players import PlayerResponse, PlayerListResponse
from api.schemas.strategies import StrategyListResponse


class TestAuctionSchemas:
    def test_bid_request_valid(self):
        req = BidRequest(player_id="qb1", bid_amount=25, team_name="Team A")
        assert req.player_id == "qb1"
        assert req.bid_amount == 25

    def test_bid_request_min_bid_enforced(self):
        with pytest.raises(ValidationError):
            BidRequest(player_id="qb1", bid_amount=0, team_name="Team A")

    def test_bid_response_valid(self):
        resp = BidResponse(
            player_id="qb1",
            winning_bid=30,
            winning_team="Team A",
            success=True,
            message="Won"
        )
        assert resp.success is True
        assert resp.message == "Won"

    def test_bid_response_default_message(self):
        resp = BidResponse(player_id="qb1", winning_bid=1, winning_team="T", success=False)
        assert resp.message == ""


class TestCommonSchemas:
    def test_health_response(self):
        r = HealthResponse(status="ok")
        assert r.status == "ok"

    def test_error_detail_defaults(self):
        e = ErrorDetail(title="Not Found", status=404)
        assert e.type == "about:blank"
        assert e.detail is None
        assert e.instance is None

    def test_error_detail_full(self):
        e = ErrorDetail(
            type="urn:pigskin:error",
            title="Bad Request",
            status=400,
            detail="Invalid player ID",
            instance="/drafts/123"
        )
        assert e.detail == "Invalid player ID"


class TestDraftSchemas:
    def test_draft_create_request_defaults(self):
        r = DraftCreateRequest()
        assert r.budget == 200
        assert r.num_teams == 10
        assert r.strategy_type == "value"
        assert r.sleeper_draft_id is None

    def test_draft_create_request_custom(self):
        r = DraftCreateRequest(budget=150, num_teams=8, strategy_type="aggressive", sleeper_draft_id="abc123")
        assert r.budget == 150
        assert r.sleeper_draft_id == "abc123"

    def test_draft_create_request_budget_ge_1(self):
        with pytest.raises(ValidationError):
            DraftCreateRequest(budget=0)

    def test_draft_create_request_num_teams_bounds(self):
        with pytest.raises(ValidationError):
            DraftCreateRequest(num_teams=1)
        with pytest.raises(ValidationError):
            DraftCreateRequest(num_teams=33)

    def test_draft_status_response(self):
        r = DraftStatusResponse(
            draft_id="d1", status="started", budget=200,
            num_teams=10, players_drafted=5
        )
        assert r.draft_id == "d1"
        assert r.players_drafted == 5


class TestPlayerSchemas:
    def test_player_response_defaults(self):
        p = PlayerResponse(player_id="rb1", name="CMC", position="RB", nfl_team="SF")
        assert p.projected_points == 0.0
        assert p.auction_value == 0.0
        assert p.vor == 0.0
        assert p.bye_week is None
        assert p.is_drafted is False

    def test_player_response_full(self):
        p = PlayerResponse(
            player_id="rb1", name="CMC", position="RB", nfl_team="SF",
            projected_points=320.0, auction_value=65.0, vor=180.0,
            bye_week=9, is_drafted=True
        )
        assert p.bye_week == 9
        assert p.is_drafted is True

    def test_player_response_projected_points_ge_0(self):
        with pytest.raises(ValidationError):
            PlayerResponse(player_id="x", name="X", position="QB", nfl_team="Y", projected_points=-1.0)

    def test_player_list_response(self):
        players = [
            PlayerResponse(player_id="rb1", name="CMC", position="RB", nfl_team="SF"),
        ]
        resp = PlayerListResponse(players=players, count=1, total=50)
        assert resp.count == 1
        assert len(resp.players) == 1


class TestStrategySchemas:
    def test_strategy_list_response(self):
        r = StrategyListResponse(strategies=["aggressive", "balanced"], count=2)
        assert r.count == 2
        assert "aggressive" in r.strategies
