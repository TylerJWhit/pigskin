"""lab/data/sleeper_auction_scraper.py — transforms Sleeper API picks to corpus rows.

Issue #234: SleeperAuctionScraper.scrape_league(league_id, season) writes to
real_auction_picks and related tables via SQLAlchemy async session.

Field mapping:
  Sleeper pick → RealAuctionPick:
    player_id     → sleeper_player_id
    position      → position
    nfl_team      → nfl_team
    auction_price → winner_bid
    draft_id      → via RealAuctionDraft FK
    budget_pct    = winner_bid / league_budget  (stored in AuctionCorpus)

Deduplication: (draft_id, player_id) unique constraint prevents duplicate rows.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from lab.data.sleeper_client import AuctionPick, SleeperLabClient
from lab.results_db.models import (
    AuctionCorpus,
    Base,
    RealAuctionDraft,
    RealAuctionPick,
)

logger = logging.getLogger(__name__)


def _make_session_factory(db_url: str):
    engine = create_async_engine(db_url, echo=False)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


class SleeperAuctionScraper:
    """Scrapes real auction draft data from Sleeper and persists to the lab DB."""

    def __init__(
        self,
        db_url: str = "sqlite+aiosqlite:///./lab/results_db/pigskin_lab.db",
        client: Optional[SleeperLabClient] = None,
    ) -> None:
        self._db_url = db_url
        self._client = client or SleeperLabClient()
        self._session_factory, self._engine = _make_session_factory(db_url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape_league(self, league_id: str, season: str) -> dict:
        """Scrape all drafts for a league-season and persist to the corpus DB.

        Args:
            league_id: Sleeper league ID.
            season: NFL season year string, e.g. "2024".

        Returns:
            Summary dict: {'drafts_processed': int, 'picks_inserted': int, 'picks_skipped': int}
        """
        return asyncio.run(self._scrape_league_async(league_id, season))

    # ------------------------------------------------------------------
    # Async internals
    # ------------------------------------------------------------------

    async def _scrape_league_async(self, league_id: str, season: str) -> dict:
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
    ) -> tuple[int, int]:
        """Persist one draft and its picks. Returns (inserted, skipped)."""
        async with self._session_factory() as session:
            # Upsert draft row
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

            # Upsert corpus entry with quality score (budget_pct sum check)
            await self._upsert_corpus(session, db_draft, league_budget, picks)
            await session.commit()
            logger.info(
                "Draft %s: %d inserted, %d skipped", draft_id, inserted, skipped
            )
            return inserted, skipped

    async def _get_or_create_draft(
        self,
        session: AsyncSession,
        sleeper_draft_id: str,
        league_id: str,
        season: str,
        meta: dict,
    ) -> Optional[RealAuctionDraft]:
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
        session: AsyncSession,
        db_draft: RealAuctionDraft,
        pick: AuctionPick,
    ) -> bool:
        """Insert one pick; return True if inserted, False if duplicate/skipped."""
        # Deduplication: check existing (draft_id, sleeper_player_id)
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
        session: AsyncSession,
        db_draft: RealAuctionDraft,
        league_budget: int,
        picks: list[AuctionPick],
    ) -> None:
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
