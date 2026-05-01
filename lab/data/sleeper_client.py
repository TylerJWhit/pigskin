"""lab/data/sleeper_client.py — rate-limited Sleeper API client for auction data.

Issue #233: thin wrapper over Sleeper's REST API with:
  - Token bucket rate limiter: max 1000 req/day
  - File-based cache (lab/data/cache/) with TTL=7 days
  - Typed AuctionPick dataclass return from get_draft_picks()

Sleeper API base: https://api.sleeper.app/v1
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.sleeper.app/v1"
_CACHE_DIR = Path(__file__).resolve().parent / "cache"
_CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days

# ---------------------------------------------------------------------------
# Typed result
# ---------------------------------------------------------------------------


@dataclass
class AuctionPick:
    """A single auction pick extracted from a Sleeper draft."""

    draft_id: str
    sleeper_player_id: str
    player_name: str
    position: str
    nfl_team: Optional[str]
    winner_bid: int  # winning auction price in dollars
    picked_by_slot: Optional[int]
    pick_order: Optional[int]
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


# ---------------------------------------------------------------------------
# Token-bucket rate limiter (1000 req / day)
# ---------------------------------------------------------------------------


class _DailyBucket:
    """Simple in-process token bucket — 1 000 requests per 24-hour window."""

    LIMIT = 1_000
    WINDOW = 86_400  # seconds

    def __init__(self) -> None:
        self._calls: List[float] = []

    def acquire(self) -> None:
        """Block until a request slot is available, then consume it."""
        now = time.monotonic()
        cutoff = now - self.WINDOW
        self._calls = [t for t in self._calls if t > cutoff]
        if len(self._calls) >= self.LIMIT:
            sleep_for = self._calls[0] - cutoff
            logger.warning("Rate limit reached; sleeping %.1fs", sleep_for)
            time.sleep(sleep_for)
        self._calls.append(time.monotonic())

    @property
    def remaining(self) -> int:
        now = time.monotonic()
        cutoff = now - self.WINDOW
        active = [t for t in self._calls if t > cutoff]
        return max(0, self.LIMIT - len(active))


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class SleeperLabClient:
    """Thin Sleeper REST wrapper for auction data, with rate limiting and cache."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        cache_ttl: int = _CACHE_TTL_SECONDS,
        rate_limiter: Optional[_DailyBucket] = None,
    ) -> None:
        self._cache_dir = Path(cache_dir) if cache_dir else _CACHE_DIR
        self._cache_ttl = cache_ttl
        self._rate_limiter = rate_limiter or _DailyBucket()
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_league_drafts(self, league_id: str) -> List[Dict[str, Any]]:
        """Return list of draft objects for the given league.

        Args:
            league_id: Sleeper league ID string.

        Returns:
            List of raw draft dicts from Sleeper API.
        """
        return self._get(f"league/{league_id}/drafts")

    def get_draft_picks(self, draft_id: str) -> List[AuctionPick]:
        """Return typed AuctionPick list for the given draft.

        Args:
            draft_id: Sleeper draft ID string.

        Returns:
            List of AuctionPick dataclasses.
        """
        raw_picks: List[Dict[str, Any]] = self._get(f"draft/{draft_id}/picks")
        results = []
        for raw in raw_picks:
            pick = self._parse_pick(draft_id, raw)
            if pick is not None:
                results.append(pick)
        return results

    def get_draft_detail(self, draft_id: str) -> Dict[str, Any]:
        """Return full draft metadata (settings, budget, teams, etc.).

        Args:
            draft_id: Sleeper draft ID string.

        Returns:
            Raw draft detail dict from Sleeper API.
        """
        return self._get(f"draft/{draft_id}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str) -> Any:
        """Fetch a Sleeper API endpoint, using cache when possible."""
        cache_key = hashlib.sha256(path.encode()).hexdigest()
        cache_file = self._cache_dir / f"{cache_key}.json"

        # Cache hit?
        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < self._cache_ttl:
                logger.debug("Cache hit: %s", path)
                return json.loads(cache_file.read_text(encoding="utf-8"))
            logger.debug("Cache stale: %s", path)

        # Network request
        self._rate_limiter.acquire()
        url = f"{_BASE_URL}/{path}"
        logger.debug("Fetching %s", url)
        try:
            response = httpx.get(url, timeout=30)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Sleeper API error {exc.response.status_code} for {url}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Network error fetching {url}: {exc}") from exc

        data = response.json()
        cache_file.write_text(json.dumps(data), encoding="utf-8")
        return data

    @staticmethod
    def _parse_pick(draft_id: str, raw: Dict[str, Any]) -> Optional[AuctionPick]:
        """Convert a raw Sleeper pick dict to an AuctionPick, or None if invalid."""
        metadata = raw.get("metadata") or {}
        player_id = raw.get("player_id")
        if not player_id:
            logger.warning("Pick missing player_id; skipping")
            return None

        # Auction price stored as string in metadata.amount
        raw_amount = metadata.get("amount")
        try:
            winner_bid = int(raw_amount)
        except (TypeError, ValueError):
            logger.warning(
                "Pick %s has no valid auction_price (%r); skipping", player_id, raw_amount
            )
            return None

        return AuctionPick(
            draft_id=str(draft_id),
            sleeper_player_id=str(player_id),
            player_name=metadata.get("first_name", "") + " " + metadata.get("last_name", ""),
            position=metadata.get("position") or raw.get("position") or "UNK",
            nfl_team=metadata.get("team") or raw.get("team"),
            winner_bid=winner_bid,
            picked_by_slot=raw.get("draft_slot"),
            pick_order=raw.get("pick_no"),
            raw=raw,
        )
