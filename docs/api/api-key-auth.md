# API Key Authentication — Design Note

**Issue:** [#210](https://github.com/TylerJWhit/pigskin/issues/210)  
**Date:** 2026-05-01  
**Author:** Security Agent (Sprint 7, Track E)  
**Status:** Accepted  
**Parent:** ADR-002 (API Design), #98 (No authentication on any endpoint)  
**Unblocks:** #211 (auth middleware), #212 (auth tests)

---

## Problem

All `/api/v1/` endpoints in `api/routers/` (draft, auction, players, strategies) are currently unauthenticated. Any caller on the network can invoke any endpoint. This is tracked as #98.

---

## Decision

Use a **static API key** stored as an environment variable, passed in a custom HTTP header. This is the simplest secure scheme for a single-user, locally-hosted application with no multi-tenant requirements.

---

## Auth Scheme

### Header

```
X-API-Key: <key>
```

- Header name: `X-API-Key` (standard convention; see RFC 8725 §3.1 for prior art)
- Header value: an opaque random string, minimum 32 bytes of entropy (256 bits)
- Clients that omit the header receive `401 Unauthorized`
- Clients that send an invalid key receive `403 Forbidden`

### Key Generation

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Key Storage

| Mechanism | Decision |
|-----------|----------|
| **Environment variable `PIGSKIN_API_KEY`** | ✅ **Chosen** |
| `config.json` | ❌ Rejected — config.json may be committed to version control |
| Database table | ❌ Rejected — overkill for single-user v1; requires DB dependency in auth path |
| `.env` file | ✅ Acceptable as local-dev convenience only; must be in `.gitignore` |

**`PIGSKIN_API_KEY` is loaded via `pydantic-settings`** (already in requirements for `config/settings.py`). The settings model gains one field:

```python
# config/settings.py
class Settings(BaseSettings):
    ...
    api_key: str = ""   # empty string = auth disabled (local dev only)
```

If `api_key` is empty, the auth dependency is a **no-op** — all requests pass. This preserves local dev workflow without requiring a key. In production or CI, `PIGSKIN_API_KEY` must be set.

### Key Rotation

Version 1 rotation is **manual**:
1. Generate a new key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Update `PIGSKIN_API_KEY` in the deployment environment
3. Restart the server

A rotation admin endpoint is deferred to v2 (requires a session/token store for revocation).

---

## Protected vs. Public Routes

| Route | Method | Auth Required | Reason |
|-------|--------|--------------|--------|
| `GET /health` | GET | ❌ Public | Liveness probe; must be callable without credentials |
| `GET /docs` | GET | ❌ Public | OpenAPI UI; acceptable to expose schema |
| `GET /openapi.json` | GET | ❌ Public | Consumed by `/docs` |
| `GET /api/v1/players` | GET | ✅ Required | Returns player data |
| `POST /api/v1/players/search` | POST | ✅ Required | |
| `GET /api/v1/draft` | GET | ✅ Required | Returns draft state |
| `POST /api/v1/draft/start` | POST | ✅ Required | Mutates draft |
| `POST /api/v1/auction/nominate` | POST | ✅ Required | Mutates auction state |
| `GET /api/v1/strategies` | GET | ✅ Required | Returns strategy list |
| All other `/api/v1/...` | Any | ✅ Required | Default: protect all |

**Rule:** Any route registered under the `/api/v1/` prefix requires auth. Routes at the root (`/health`, `/docs`, `/openapi.json`) are public.

---

## Implementation Sketch

```python
# api/deps.py
from fastapi import Depends, Header, HTTPException
from config.settings import get_settings

async def require_api_key(
    x_api_key: str = Header(default=""),
) -> None:
    settings = get_settings()
    if not settings.api_key:
        return  # auth disabled (local dev mode)
    if x_api_key != settings.api_key:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="Missing X-API-Key header")
        raise HTTPException(status_code=403, detail="Invalid API key")
```

Apply as a router-level dependency in each router:

```python
# api/routers/draft.py
from fastapi import APIRouter, Depends
from api.deps import require_api_key

router = APIRouter(prefix="/api/v1/draft", dependencies=[Depends(require_api_key)])
```

Or as an application-level middleware that exempts `/health`, `/docs`, and `/openapi.json`.

---

## Security Properties

| Property | Satisfied? |
|----------|-----------|
| No key in version control | ✅ Env var only |
| Minimum entropy (128 bits) | ✅ `secrets.token_urlsafe(32)` = 256 bits |
| Constant-time comparison | ✅ Use `secrets.compare_digest(provided, expected)` in `require_api_key` |
| No key in logs | ✅ FastAPI access log does not log header values by default |
| HTTPS enforcement | ⚠️ Out of scope for v1 (no TLS termination); document as deployment requirement |
| Rate limiting | ⚠️ Out of scope for v1; deferred to Nginx/proxy layer |

> **Constant-time comparison is mandatory.** Using `x_api_key != settings.api_key` is acceptable for early draft but must be replaced with `secrets.compare_digest` before any non-localhost deployment.

---

## Files Changed

- `docs/api/api-key-auth.md` — this document  
- `config/settings.py` — add `api_key: str = ""` field  
- `api/deps.py` — add `require_api_key` dependency  
- `api/routers/*.py` — apply dependency (tracked by #211)  
- `tests/test_api_auth.py` — 401/403/200 tests (tracked by #212)

---

## References

- [FastAPI Security — API Keys](https://fastapi.tiangolo.com/tutorial/security/)
- [OWASP A07:2021 — Identification and Authentication Failures](https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/)
- `secrets.compare_digest` — Python stdlib constant-time comparison
