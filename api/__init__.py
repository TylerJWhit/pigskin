"""
API module for external fantasy football data sources.

This module provides wrappers for various fantasy football APIs:
- Sleeper API: For player data, league information, and draft data
"""

from .sleeper_api import SleeperAPI, SleeperAPIError

__all__ = [
    'SleeperAPI',
    'SleeperAPIError'
]
