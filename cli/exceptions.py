"""CLI exception hierarchy with exit_code attributes."""
from __future__ import annotations


class PigskinCLIError(Exception):
    """Base exception for all Pigskin CLI errors."""

    exit_code: int = 1

    def __init__(self, message: str = "", exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class NetworkError(PigskinCLIError):
    """Raised when a network request fails."""

    exit_code: int = 3


class AuthError(PigskinCLIError):
    """Raised when authentication fails."""

    exit_code: int = 4


class LabNotInstalledError(PigskinCLIError):
    """Raised when the optional lab package is not installed."""

    exit_code: int = 126
