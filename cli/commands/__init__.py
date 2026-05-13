"""Command processor package — composed from focused submodules.

This package replaces the former monolithic cli/commands.py.
All public symbols remain the same; external code can continue to use::

    from cli.commands import CommandProcessor
"""

from __future__ import annotations

from typing import Optional

from config.config_manager import ConfigManager
from api.sleeper_api import SleeperAPI
from services.sleeper_draft_service import SleeperDraftService

from ._bid import BidMixin
from ._mock import MockDraftMixin
from ._tournament import TournamentMixin
from ._tournament_stats import TournamentStatsMixin
from ._tournament_helpers import TournamentHelpersMixin
from ._simulation import SimulationMixin
from ._simulation_display import SimulationDisplayMixin
from ._sleeper import SleeperMixin


class CommandProcessor(
    BidMixin,
    MockDraftMixin,
    TournamentMixin,
    TournamentStatsMixin,
    TournamentHelpersMixin,
    SimulationMixin,
    SimulationDisplayMixin,
    SleeperMixin,
):
    """Processes individual CLI commands with enhanced functionality."""

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        sleeper_api: Optional[SleeperAPI] = None,
    ) -> None:
        self.config_manager = (
            config_manager if config_manager is not None else ConfigManager()
        )
        self.sleeper_api = sleeper_api if sleeper_api is not None else SleeperAPI()
        self.sleeper_draft_service = SleeperDraftService(sleeper_api=self.sleeper_api)


__all__ = ["CommandProcessor"]
