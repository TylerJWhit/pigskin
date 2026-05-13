"""lab/data/sleeper_auction_scraper.py — fetches historical auction data from Sleeper API.

Dual-mode implementation:
  - New API (issue #195): SleeperAuctionScraper(league_id, season) + fetch()
  - Legacy API (issue #234): SleeperAuctionScraper(db_url, client) + scrape_league()
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _make_session_factory(db_url: str):
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_async_engine(db_url, echo=False)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


class SleeperAuctionScraper:
    """Fetches historical auction draft data for a Sleeper league/season.

    Supports two constructor signatures:
      - SleeperAuctionScraper(league_id, season)  →  use fetch() [issue #195]
      - SleeperAuctionScraper(db_url, client)     →  use scrape_league() [issue #234]
    """

    def __init__(
        self,
        league_id: Optional[str] = None,
        season: Optional[str] = None,
        *,
        db_url: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> None:
        # New API: (league_id, season)
        self.league_id = league_id
        self.season = season
        self._cache: Optional[List[Dict]] = None

        # Legacy DB-backed API: (db_url, client)
        if db_url is not None or client is not None:
            _db_url = db_url or "sqlite+aiosqlite:///./lab/results_db/pigskin_lab.db"
            from lab.data.sleeper_client import SleeperLabClient
            self._client = client or SleeperLabClient()
            self._session_factory, self._engine = _make_session_factory(_db_url)
        else:
            self._client = None
            self._session_factory = None
            self._engine = None

    # ------------------------------------------------------------------
    # New public API (issue #195)
    # ------------------------------------------------------------------

    def fetch(self) -> List[Dict]:
        """Return auction data as a list of dicts with required keys.

        Returns cached results on subsequent calls.
        Each dict has: player_name, position, auction_value, actual_price.
        """
        if self._cache is not None:
            return self._cache
        raw = self._fetch_from_api()
        self._cache = self._normalize(raw)
        return self._cache

    def _fetch_from_api(self) -> list:
        """Fetch raw pick data from the Sleeper API.

        Returns an empty list on any error (network, auth, missing data).
        Override or patch this method in tests to inject fixture data.
        """
        try:
            from lab.data.sleeper_client import SleeperLabClient
            client = SleeperLabClient()
            drafts = client.get_league_drafts(self.league_id) or []
            picks: list = []
            for draft in drafts:
                draft_id = str(draft.get("draft_id", ""))
                if draft_id:
                    raw_picks = client.get_draft_picks(draft_id) or []
                    picks.extend(raw_picks)
            return picks
        except Exception:
            logger.debug(
                "SleeperAuctionScraper._fetch_from_api failed for league=%s",
                self.league_id,
            )
            return []

    def _normalize(self, raw: list) -> List[Dict]:
        """Normalize raw pick data to the required schema."""
        result = []
        for item in raw:
            if not isinstance(item, dict):
                try:
                    result.append({
                        "player_name": str(getattr(item, "player_name", "Unknown")),
                        "position": str(getattr(item, "position", "")),
                        "auction_value": float(getattr(item, "auction_value", 0) or 0),
                        "actual_price": float(getattr(item, "winner_bid", 0) or 0),
                    })
                except Exception:
                    continue
            else:
                result.append({
                    "player_name": item.get("player_name") or item.get("name", "Unknown"),
                    "position": item.get("position", ""),
                    "auction_value": float(item.get("auction_value") or item.get("value") or 0),
                    "actual_price": float(item.get("actual_price") or item.get("winner_bid") or item.get("amount") or 0),
                })
        return result

    # ------------------------------------------------------------------
    # Legacy DB-backed API (issue #234)
    # ------------------------------------------------------------------

    def scrape_league(self, league_id: str, season: str) -> dict:
        """Scrape all drafts for a league-season and persist to the corpus DB.

        Returns:
            Summary dict: {'drafts_processed': int, 'picks_inserted': int, 'picks_skipped': int}
        """
        return asyncio.run(self._scrape_league_async(league_id, season))

    async def _scrape_league_async(self, league_id: str, season: str) -> dict:
        from lab.results_db.models import Base

        drafts_meta = self._client.get_league_drafts(league_id)
        if not drafts_meta:
            logger.info("No drafts found for league %s / %s", league_id, season)
            return {"drafts_processed": 0, "picks_inserted": 0, "picks_skipped": 0}

        total_inserted = 0
        total_skipped = 0
        drafts_processed = 0

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        for draft_meta in drafts_meta:
            draft_id_str = str(draft_meta.get("draft_id", ""))
            if not draft_id_str:
                continue

            inserted, skipped = await self._scrape_draft(
                draft_id_str, league_id, season, draft_meta
            )
            total_inserted += inserted
            total_skipped += skipped
            drafts_processed += 1

        return {
            "drafts_processed": drafts_processed,
            "picks_inserted": total_inserted,
            "picks_skipped": total_skipped,
        }

    async def _scrape_draft(
        self,
        draft_id: str,
        league_id: str,
        season: str,
        draft_meta: dict,
    ) -> tuple:
        """Persist one draft and its picks. Returns (inserted, skipped)."""
        async with self._session_factory() as session:
            db_draft = await self._get_or_create_draft(
                session, draft_id, league_id, season, draft_meta
            )
            if db_draft is None:
                return 0, 0

            detail = self._client.get_draft_detail(draft_id)
            picks = self._client.get_draft_picks(draft_id)

            league_budget: int = (
                detail.get("settings", {}).get("budget") or 200
            )

            inserted = 0
            skipped = 0

            for pick in picks:
                ok = await self._insert_pick(session, db_draft, pick)
                if ok:
                    inserted += 1
                else:
                    skipped += 1

            await self._upsert_corpus(session, db_draft, league_budget, picks)
            await session.commit()
            logger.info(
                "Draft %s: %d inserted, %d skipped", draft_id, inserted, skipped
            )
            return inserted, skipped

    async def _get_or_create_draft(
        self,
        session: Any,
        sleeper_draft_id: str,
        league_id: str,
        season: str,
        meta: dict,
    ) -> Optional[Any]:
        from sqlalchemy import select
        from lab.results_db.models import RealAuctionDraft

        result = await session.execute(
            select(RealAuctionDraft).where(
                RealAuctionDraft.sleeper_draft_id == sleeper_draft_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        settings = meta.get("settings") or {}
        draft_date_raw = meta.get("start_time")
        draft_date: Optional[datetime] = None
        if draft_date_raw:
            try:
                draft_date = datetime.utcfromtimestamp(int(draft_date_raw) / 1000)
            except (TypeError, ValueError):
                pass

        db_draft = RealAuctionDraft(
            sleeper_draft_id=sleeper_draft_id,
            sleeper_league_id=str(league_id),
            season=str(season),
            team_count=settings.get("teams") or 12,
            scoring_format=settings.get("scoring_format"),
            auction_budget=settings.get("budget"),
            draft_date=draft_date,
            fetched_at=datetime.utcnow(),
            raw_metadata=json.dumps(meta),
        )
        session.add(db_draft)
        await session.flush()
        return db_draft

    async def _insert_pick(
        self,
        session: Any,
        db_draft: Any,
        pick: Any,
    ) -> bool:
        from sqlalchemy import select
        from lab.results_db.models import RealAuctionPick

        result = await session.execute(
            select(RealAuctionPick).where(
                RealAuctionPick.draft_id == db_draft.id,
                RealAuctionPick.sleeper_player_id == pick.sleeper_player_id,
            )
        )
        if result.scalar_one_or_none():
            logger.debug(
                "Duplicate pick draft=%s player=%s; skipping",
                pick.draft_id,
                pick.sleeper_player_id,
            )
            return False

        db_pick = RealAuctionPick(
            draft_id=db_draft.id,
            sleeper_player_id=pick.sleeper_player_id,
            player_name=pick.player_name.strip(),
            position=pick.position,
            nfl_team=pick.nfl_team,
            winner_bid=pick.winner_bid,
            picked_by_slot=pick.picked_by_slot,
            pick_order=pick.pick_order,
            raw_pick=json.dumps(pick.raw),
        )
        session.add(db_pick)
        return True

    async def _upsert_corpus(
        self,
        session: Any,
        db_draft: Any,
        league_budget: int,
        picks: list,
    ) -> None:
        from sqlalchemy import select
        from lab.results_db.models import AuctionCorpus

        result = await session.execute(
            select(AuctionCorpus).where(AuctionCorpus.draft_id == db_draft.id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return

        total_spent = sum(p.winner_bid for p in picks)
        quality_score = (
            round(total_spent / (league_budget * len(picks)), 4)
            if picks and league_budget
            else None
        )

        corpus = AuctionCorpus(
            draft_id=db_draft.id,
            quality_score=quality_score,
            used_in_backtest=False,
            included_at=datetime.utcnow(),
        )
        session.add(corpus)
