"""Dependency injection for FastAPI routes."""
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from config.settings import Settings, get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    api_key: Annotated[str | None, Security(_api_key_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Validate the X-API-Key header against the configured key.

    Raises:
        HTTP 401 — header is missing or empty.
        HTTP 403 — header is present but key is invalid.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    configured_key = settings.api_key
    try:
        keys_match = bool(
            configured_key
            and secrets.compare_digest(
                api_key.encode("utf-8"), configured_key.encode("utf-8")
            )
        )
    except (UnicodeEncodeError, TypeError):
        # Non-encodable or incompatible types — treat as invalid key (403)
        keys_match = False
    if not keys_match:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )


def get_app_settings() -> Settings:
    return get_settings()
