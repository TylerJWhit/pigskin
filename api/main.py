"""FastAPI application factory for Pigskin Draft Assistant."""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends

from api.deps import require_api_key
from api.routers import auction, draft, players, recommend, strategies


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler — startup and shutdown."""
    # Future: initialise DB connection pool, load player cache, etc.
    yield
    # Future: clean up resources


def create_app(
    *,
    api_key: str | None = None,
    docs_enabled: bool | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Parameters
    ----------
    api_key:
        Override the API key (used in tests).  When *None* the value is read
        from ``settings.api_key`` / ``PIGSKIN_API_KEY`` env var.
    docs_enabled:
        Override whether /docs is exposed (used in tests).  When *None* the
        value is read from ``settings.docs_enabled`` / ``PIGSKIN_DOCS_ENABLED``.
    """
    from config.settings import get_settings

    settings = get_settings()

    resolved_api_key = api_key if api_key is not None else settings.api_key
    resolved_docs_enabled = docs_enabled if docs_enabled is not None else settings.docs_enabled

    # Security guard: refuse to start with an empty API key outside of tests.
    if not resolved_api_key and os.getenv("TESTING") != "true":
        raise RuntimeError(
            "PIGSKIN_API_KEY must be set. "
            "An empty API key is not allowed in non-test environments."
        )

    # Gate /docs, /openapi.json and /redoc behind PIGSKIN_DOCS_ENABLED.
    _docs_url = "/docs" if resolved_docs_enabled else None
    _openapi_url = "/openapi.json" if resolved_docs_enabled else None
    _redoc_url = "/redoc" if resolved_docs_enabled else None

    app = FastAPI(
        title="Pigskin Draft Assistant",
        description="Fantasy football auction draft assistant API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=_docs_url,
        openapi_url=_openapi_url,
        redoc_url=_redoc_url,
    )

    # Health check (no auth required)
    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    # Mount routers — all require a valid API key
    _auth = [Depends(require_api_key)]
    app.include_router(strategies.router, dependencies=_auth)
    app.include_router(players.router, dependencies=_auth)
    app.include_router(draft.router, dependencies=_auth)
    app.include_router(auction.router, dependencies=_auth)
    app.include_router(recommend.router, dependencies=_auth)

    return app


app = create_app()
