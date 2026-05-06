"""Shared response wrappers following RFC 7807 error format."""
from typing import Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ErrorDetail(BaseModel):
    """RFC 7807 Problem Details."""
    type: str = "about:blank"
    title: str
    status: int
    detail: Optional[str] = None
    instance: Optional[str] = None
