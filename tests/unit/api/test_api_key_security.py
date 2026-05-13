"""P0 security tests for API key validation and /docs gating — issue #355.

Tests (all written before implementation — expected to fail first):
  1. Empty PIGSKIN_API_KEY at startup raises RuntimeError (non-test env)
  2. Unauthenticated GET /health → 200 (public endpoint)
  3. Unauthenticated GET /recommend → 401 (protected endpoint)
  4. PIGSKIN_DOCS_ENABLED unset → GET /docs returns 404
  5. PIGSKIN_DOCS_ENABLED=true → GET /docs returns 200
"""
import pytest
from fastapi.testclient import TestClient

from api.main import create_app


_VALID_KEY = "test-secure-key-xyz987-abcdefghijklm"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(api_key: str = _VALID_KEY, docs_enabled: bool = False) -> TestClient:
    """Create a TestClient with dependency-overridden settings."""
    _app = create_app(
        docs_enabled=docs_enabled,
        api_key=api_key,
    )
    return TestClient(_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Test 1: RuntimeError on empty API key at startup (non-test environment)
# ---------------------------------------------------------------------------

class TestEmptyApiKeyStartupError:
    def test_empty_api_key_raises_runtime_error_outside_testing(self, monkeypatch):
        """create_app() must raise RuntimeError when api_key is empty and
        TESTING env var is not 'true'."""
        monkeypatch.delenv("TESTING", raising=False)
        with pytest.raises(RuntimeError, match="PIGSKIN_API_KEY"):
            create_app(api_key="")

    def test_empty_api_key_allowed_in_test_environment(self, monkeypatch):
        """create_app() must NOT raise when TESTING=true even with empty key."""
        monkeypatch.setenv("TESTING", "true")
        # Should not raise
        app = create_app(api_key="")
        assert app is not None


# ---------------------------------------------------------------------------
# Test 2: /health is always public
# ---------------------------------------------------------------------------

class TestHealthPublic:
    def test_health_no_key_returns_200(self):
        client = _make_client()
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_unauthenticated_no_key_header_returns_200(self):
        """Even with no X-API-Key header, /health must respond 200."""
        client = _make_client()
        resp = client.get("/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Test 3: Protected endpoint /recommend requires auth
# ---------------------------------------------------------------------------

class TestProtectedEndpoint:
    def test_unauthenticated_recommend_returns_401(self):
        client = _make_client()
        resp = client.post("/recommend/bid", json={})
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 for unauthenticated /recommend/bid, got {resp.status_code}"
        )

    def test_authenticated_recommend_does_not_return_401(self):
        client = _make_client()
        resp = client.post("/recommend/bid", json={}, headers={"X-API-Key": _VALID_KEY})
        assert resp.status_code != 401, (
            f"Valid key should not return 401, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Test 4: /docs is gated — disabled by default
# ---------------------------------------------------------------------------

class TestDocsGating:
    def test_docs_not_accessible_when_disabled(self):
        """With docs_enabled=False (default), /docs must return 404."""
        client = _make_client(docs_enabled=False)
        resp = client.get("/docs")
        assert resp.status_code == 404, (
            f"Expected 404 for /docs when disabled, got {resp.status_code}"
        )

    def test_openapi_json_not_accessible_when_disabled(self):
        """With docs_enabled=False, /openapi.json must return 404."""
        client = _make_client(docs_enabled=False)
        resp = client.get("/openapi.json")
        assert resp.status_code == 404, (
            f"Expected 404 for /openapi.json when disabled, got {resp.status_code}"
        )

    def test_redoc_not_accessible_when_disabled(self):
        """With docs_enabled=False, /redoc must return 404."""
        client = _make_client(docs_enabled=False)
        resp = client.get("/redoc")
        assert resp.status_code == 404, (
            f"Expected 404 for /redoc when disabled, got {resp.status_code}"
        )

    # ---------------------------------------------------------------------------
    # Test 5: /docs accessible when PIGSKIN_DOCS_ENABLED=true
    # ---------------------------------------------------------------------------

    def test_docs_accessible_when_enabled(self):
        """With docs_enabled=True, GET /docs must return 200."""
        client = _make_client(docs_enabled=True)
        resp = client.get("/docs")
        assert resp.status_code == 200, (
            f"Expected 200 for /docs when enabled, got {resp.status_code}"
        )

    def test_openapi_json_accessible_when_enabled(self):
        """With docs_enabled=True, GET /openapi.json must return 200."""
        client = _make_client(docs_enabled=True)
        resp = client.get("/openapi.json")
        assert resp.status_code == 200, (
            f"Expected 200 for /openapi.json when enabled, got {resp.status_code}"
        )
