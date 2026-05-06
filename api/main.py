"""FastAPI application factory for Pigskin Draft Assistant."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends

from api.deps import require_api_key
from api.routers import auction, draft, players, strategies


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler — startup and shutdown."""
    # Future: initialise DB connection pool, load player cache, etc.
    yield
    # Future: clean up resources


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Pigskin Draft Assistant",
        description="Fantasy football auction draft assistant API",
        version="0.1.0",
        lifespan=lifespan,
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

    return app


app = create_app()
