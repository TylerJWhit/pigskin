"""QA Phase 1 regression tests for issue #179.

POST /api/v1/recommend/bid endpoint (ADR-002)

These tests define the contract for the endpoint. They are written BEFORE
implementation so they fail until the feature is complete (QA-First lifecycle).

Scenarios:
  1. Valid request → 200 with BidRecommendationResponse fields
  2. Missing required fields → 422 Unprocessable Entity
  3. Service unavailable (no draft context) → 503
  4. Auth required — missing key → 401
  5. Response model enforced — no domain objects leak
  6. Route is registered at /recommend/bid
  7. request/response schema round-trips (field names, types)
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from api.main import create_app
from config.settings import Settings

_VALID_KEY = "test-secret-key-abc123"

_VALID_REQUEST = {
    "player_id": "1234",
    "player_name": "Patrick Mahomes",
    "current_bid": 10.0,
    "team_budget": 200.0,
    "roster_spots_remaining": 8,
}

_MOCK_RECOMMENDATION = {
    "recommended_bid": 42.0,
    "confidence": 0.85,
    "rationale": "High VOR player with low scarcity risk.",
}


@pytest.fixture
def app():
    """Fresh app with test API key and mocked bid recommendation service."""
    _app = create_app()

    def _mock_settings() -> Settings:
        return Settings(api_key=_VALID_KEY)

    from config.settings import get_settings
    _app.dependency_overrides[get_settings] = _mock_settings
    return _app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers():
    return {"X-API-Key": _VALID_KEY}


# ---------------------------------------------------------------------------
# Scenario 4: Auth required
# ---------------------------------------------------------------------------

class TestBidRecommendationAuth:
    def test_missing_key_returns_401(self, client):
        resp = client.post("/recommend/bid", json=_VALID_REQUEST)
        assert resp.status_code == 401, f"Expected 401 without key, got {resp.status_code}"

    def test_wrong_key_returns_403(self, client):
        resp = client.post("/recommend/bid", json=_VALID_REQUEST,
                           headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 403, f"Expected 403 with wrong key, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Scenario 6: Route is registered
# ---------------------------------------------------------------------------

class TestRouteRegistration:
    def test_route_exists(self, client, auth_headers):
        """Route must be registered — a 404 means the router is not wired up."""
        with patch(
            "services.bid_recommendation_service.BidRecommendationService.recommend_bid",
            return_value=_MOCK_RECOMMENDATION,
        ):
            resp = client.post("/recommend/bid", json=_VALID_REQUEST,
                               headers=auth_headers)
        assert resp.status_code != 404, "/recommend/bid is not registered"

    def test_route_accessible_with_prefix(self, client, auth_headers):
        """Endpoint must be reachable at /recommend/bid (not /api/v1/... prefix in test)."""
        with patch(
            "services.bid_recommendation_service.BidRecommendationService.recommend_bid",
            return_value=_MOCK_RECOMMENDATION,
        ):
            resp = client.post("/recommend/bid", json=_VALID_REQUEST,
                               headers=auth_headers)
        assert resp.status_code in (200, 503), (
            f"Expected 200 or 503 but got {resp.status_code} — route likely missing"
        )


# ---------------------------------------------------------------------------
# Scenario 1: Valid request → 200
# ---------------------------------------------------------------------------

class TestBidRecommendationSuccess:
    def test_returns_200_with_valid_request(self, client, auth_headers):
        with patch(
            "services.bid_recommendation_service.BidRecommendationService.recommend_bid",
            return_value=_MOCK_RECOMMENDATION,
        ):
            resp = client.post("/recommend/bid", json=_VALID_REQUEST,
                               headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_response_contains_recommended_bid(self, client, auth_headers):
        with patch(
            "services.bid_recommendation_service.BidRecommendationService.recommend_bid",
            return_value=_MOCK_RECOMMENDATION,
        ):
            resp = client.post("/recommend/bid", json=_VALID_REQUEST,
                               headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "recommended_bid" in body, f"'recommended_bid' missing from response: {body}"

    def test_response_contains_confidence(self, client, auth_headers):
        with patch(
            "services.bid_recommendation_service.BidRecommendationService.recommend_bid",
            return_value=_MOCK_RECOMMENDATION,
        ):
            resp = client.post("/recommend/bid", json=_VALID_REQUEST,
                               headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "confidence" in body, f"'confidence' missing from response: {body}"

    def test_response_contains_rationale(self, client, auth_headers):
        with patch(
            "services.bid_recommendation_service.BidRecommendationService.recommend_bid",
            return_value=_MOCK_RECOMMENDATION,
        ):
            resp = client.post("/recommend/bid", json=_VALID_REQUEST,
                               headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "rationale" in body, f"'rationale' missing from response: {body}"

    def test_recommended_bid_is_numeric(self, client, auth_headers):
        with patch(
            "services.bid_recommendation_service.BidRecommendationService.recommend_bid",
            return_value=_MOCK_RECOMMENDATION,
        ):
            resp = client.post("/recommend/bid", json=_VALID_REQUEST,
                               headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["recommended_bid"], (int, float)), (
            f"recommended_bid must be numeric, got {type(body['recommended_bid'])}"
        )

    def test_confidence_is_float_between_0_and_1(self, client, auth_headers):
        with patch(
            "services.bid_recommendation_service.BidRecommendationService.recommend_bid",
            return_value=_MOCK_RECOMMENDATION,
        ):
            resp = client.post("/recommend/bid", json=_VALID_REQUEST,
                               headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        confidence = body["confidence"]
        assert isinstance(confidence, float), f"confidence must be float, got {type(confidence)}"
        assert 0.0 <= confidence <= 1.0, f"confidence must be in [0, 1], got {confidence}"

    def test_no_domain_objects_in_response(self, client, auth_headers):
        """Response must be JSON-serializable plain data, not domain objects."""
        with patch(
            "services.bid_recommendation_service.BidRecommendationService.recommend_bid",
            return_value=_MOCK_RECOMMENDATION,
        ):
            resp = client.post("/recommend/bid", json=_VALID_REQUEST,
                               headers=auth_headers)
        assert resp.status_code == 200
        # If domain objects leaked, serialization would fail → non-200 or error body
        body = resp.json()
        assert isinstance(body, dict), "Response must be a plain JSON object"

    def test_optional_sleeper_draft_id(self, client, auth_headers):
        """sleeper_draft_id is optional — endpoint must accept request without it."""
        payload = {k: v for k, v in _VALID_REQUEST.items()}
        payload["sleeper_draft_id"] = "draft_abc123"
        with patch(
            "services.bid_recommendation_service.BidRecommendationService.recommend_bid",
            return_value=_MOCK_RECOMMENDATION,
        ):
            resp = client.post("/recommend/bid", json=payload,
                               headers=auth_headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Scenario 2: Missing required fields → 422
# ---------------------------------------------------------------------------

class TestBidRecommendationValidation:
    def test_missing_player_name_returns_422(self, client, auth_headers):
        payload = {k: v for k, v in _VALID_REQUEST.items() if k != "player_name"}
        resp = client.post("/recommend/bid", json=payload, headers=auth_headers)
        assert resp.status_code == 422, f"Expected 422 for missing player_name, got {resp.status_code}"

    def test_missing_current_bid_returns_422(self, client, auth_headers):
        payload = {k: v for k, v in _VALID_REQUEST.items() if k != "current_bid"}
        resp = client.post("/recommend/bid", json=payload, headers=auth_headers)
        assert resp.status_code == 422, f"Expected 422 for missing current_bid, got {resp.status_code}"

    def test_negative_budget_returns_422(self, client, auth_headers):
        payload = {**_VALID_REQUEST, "team_budget": -50.0}
        resp = client.post("/recommend/bid", json=payload, headers=auth_headers)
        assert resp.status_code == 422, f"Expected 422 for negative budget, got {resp.status_code}"

    def test_negative_current_bid_returns_422(self, client, auth_headers):
        payload = {**_VALID_REQUEST, "current_bid": -1.0}
        resp = client.post("/recommend/bid", json=payload, headers=auth_headers)
        assert resp.status_code == 422, f"Expected 422 for negative current_bid, got {resp.status_code}"

    def test_empty_player_name_returns_422(self, client, auth_headers):
        payload = {**_VALID_REQUEST, "player_name": ""}
        resp = client.post("/recommend/bid", json=payload, headers=auth_headers)
        assert resp.status_code == 422, f"Expected 422 for empty player_name, got {resp.status_code}"

    def test_empty_body_returns_422(self, client, auth_headers):
        resp = client.post("/recommend/bid", json={}, headers=auth_headers)
        assert resp.status_code == 422, f"Expected 422 for empty body, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Scenario 3: No draft context → 503
# ---------------------------------------------------------------------------

class TestBidRecommendationServiceUnavailable:
    def test_service_unavailable_returns_503(self, client, auth_headers):
        """When BidRecommendationService returns no usable context, respond 503."""
        with patch(
            "services.bid_recommendation_service.BidRecommendationService.recommend_bid",
            return_value={"success": False, "error": "No draft context available"},
        ):
            resp = client.post("/recommend/bid", json=_VALID_REQUEST,
                               headers=auth_headers)
        assert resp.status_code == 503, (
            f"Expected 503 when service has no context, got {resp.status_code}"
        )

    def test_503_has_detail_message(self, client, auth_headers):
        with patch(
            "services.bid_recommendation_service.BidRecommendationService.recommend_bid",
            return_value={"success": False, "error": "No draft context available"},
        ):
            resp = client.post("/recommend/bid", json=_VALID_REQUEST,
                               headers=auth_headers)
        assert resp.status_code == 503
        body = resp.json()
        assert "detail" in body, f"503 response must include 'detail', got: {body}"
