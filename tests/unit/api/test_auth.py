"""Auth dependency tests for FastAPI routes — issue #212.

Scenarios:
  1. No API key header → HTTP 401
  2. Wrong API key → HTTP 403
  3. Valid API key → HTTP 200
  4. Public /health route accessible without key
  5. API key is never echoed in response body
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import create_app
from config.settings import Settings

_VALID_KEY = "test-secret-key-abc123"

# Protected endpoints to test auth against
_PROTECTED_ROUTES = [
    "/strategies/",
    "/players/",
    "/draft/",
    "/auction/",
]


@pytest.fixture
def app():
    """Create a fresh app with a known API key injected via dependency override."""
    _app = create_app()

    def _mock_settings() -> Settings:
        return Settings(api_key=_VALID_KEY)

    from api.deps import get_app_settings
    from config.settings import get_settings
    _app.dependency_overrides[get_settings] = _mock_settings
    return _app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Scenario 4: /health is always public
# ---------------------------------------------------------------------------

class TestPublicHealth:
    def test_health_no_key(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_health_key_not_required(self, client):
        """Key can be sent but is not validated for /health."""
        resp = client.get("/health", headers={"X-API-Key": "anything"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Scenario 1: Missing key → 401
# ---------------------------------------------------------------------------

class TestMissingKey:
    @pytest.mark.parametrize("route", _PROTECTED_ROUTES)
    def test_no_key_returns_401(self, client, route):
        resp = client.get(route)
        assert resp.status_code == 401, f"Expected 401 for {route}, got {resp.status_code}"

    @pytest.mark.parametrize("route", _PROTECTED_ROUTES)
    def test_empty_key_returns_401(self, client, route):
        """An empty X-API-Key header is treated the same as absent."""
        resp = client.get(route, headers={"X-API-Key": ""})
        assert resp.status_code == 401, f"Expected 401 for {route}, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Scenario 2: Wrong key → 403
# ---------------------------------------------------------------------------

class TestInvalidKey:
    @pytest.mark.parametrize("route", _PROTECTED_ROUTES)
    def test_wrong_key_returns_403(self, client, route):
        resp = client.get(route, headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 403, f"Expected 403 for {route}, got {resp.status_code}"

    @pytest.mark.parametrize("route", _PROTECTED_ROUTES)
    def test_partial_key_returns_403(self, client, route):
        resp = client.get(route, headers={"X-API-Key": _VALID_KEY[:-1]})
        assert resp.status_code == 403, f"Expected 403 for {route}, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Scenario 3: Valid key → 200
# ---------------------------------------------------------------------------

class TestValidKey:
    @pytest.mark.parametrize("route", _PROTECTED_ROUTES)
    def test_valid_key_returns_200(self, client, route):
        resp = client.get(route, headers={"X-API-Key": _VALID_KEY})
        assert resp.status_code == 200, f"Expected 200 for {route}, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Scenario 5: Key never echoed in error response body
# ---------------------------------------------------------------------------

class TestKeyNotLeaked:
    def test_401_body_does_not_echo_key(self, client):
        resp = client.get("/strategies/")
        body = resp.text
        assert _VALID_KEY not in body

    def test_403_body_does_not_echo_key(self, client):
        resp = client.get("/strategies/", headers={"X-API-Key": "bad-key"})
        body = resp.text
        assert "bad-key" not in body
        assert _VALID_KEY not in body
