"""FastAPI application factory for Pigskin Draft Assistant."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

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

    # Mount routers
    app.include_router(strategies.router)
    app.include_router(players.router)
    app.include_router(draft.router)
    app.include_router(auction.router)

    return app


app = create_app()
