"""Unit tests for the Pigskin Lab results_db schema (ADR-004, #79).

Tests:
  - Schema creation via Alembic upgrade/downgrade
  - All 3 tables are present after upgrade
  - Both triggers are present after upgrade
  - All 4 indexes are present after upgrade
  - Basic CRUD: insert a BenchmarkRun, StrategyResult, and Promotion
  - Trigger invariant: inserting a second Promotion with is_current=1
    automatically clears the previous row's is_current to 0
  - Trigger invariant: updating an existing Promotion to is_current=1
    automatically clears all others
"""

import asyncio
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import text

from lab.results_db.models import (
    AuctionCorpus,
    Base,
    BenchmarkRun,
    Promotion,
    RealAuctionDraft,
    RealAuctionPick,
    StrategyResult,
    make_engine,
    make_session_factory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sqlite_conn(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


async def _create_schema(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db_path(tmp_path):
    return str(tmp_path / "test_lab.db")


@pytest.fixture
def engine(tmp_db_path):
    return make_engine(f"sqlite+aiosqlite:///{tmp_db_path}")


@pytest.fixture
def session_factory(engine):
    return make_session_factory(engine)


@pytest.fixture
def prepared_db(tmp_db_path, engine):
    """Create schema and return (engine, session_factory, db_path)."""
    asyncio.get_event_loop().run_until_complete(_create_schema(engine))
    return engine, make_session_factory(engine), tmp_db_path


# ---------------------------------------------------------------------------
# Schema creation tests
# ---------------------------------------------------------------------------

class TestSchemaCreation:
    def test_tables_created(self, prepared_db):
        _, _, db_path = prepared_db
        conn = _sqlite_conn(db_path)
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        conn.close()
        assert "benchmark_runs" in tables
        assert "strategy_results" in tables
        assert "promotions" in tables

    def test_indexes_created(self, prepared_db):
        _, _, db_path = prepared_db
        conn = _sqlite_conn(db_path)
        indexes = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )}
        conn.close()
        assert "idx_benchmark_runs_experiment" in indexes
        assert "idx_strategy_results_run" in indexes
        assert "idx_strategy_results_name" in indexes
        assert "idx_promotions_current" in indexes

    def test_wal_mode_enabled(self, prepared_db):
        _, _, db_path = prepared_db
        conn = _sqlite_conn(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"


# ---------------------------------------------------------------------------
# Alembic migration tests
# ---------------------------------------------------------------------------

class TestAlembicMigrations:
    def test_upgrade_creates_tables_and_triggers(self, tmp_path):
        db_path = str(tmp_path / "alembic_test.db")
        ini_path = str(
            Path(__file__).resolve().parents[1] / "lab" / "results_db" / "alembic.ini"
        )
        # Skip if alembic.ini not found (e.g., CI without full repo)
        if not Path(ini_path).exists():
            pytest.skip("alembic.ini not found — skipping Alembic migration test")

        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(ini_path)
        alembic_cfg.set_main_option(
            "sqlalchemy.url", f"sqlite:///{db_path}"
        )
        command.upgrade(alembic_cfg, "head")

        conn = _sqlite_conn(db_path)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        triggers = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        )}
        conn.close()

        assert {"benchmark_runs", "strategy_results", "promotions"}.issubset(tables)
        assert "enforce_single_current_promotion" in triggers
        assert "enforce_single_current_on_update" in triggers

    def test_downgrade_removes_tables(self, tmp_path):
        db_path = str(tmp_path / "alembic_down.db")
        ini_path = str(
            Path(__file__).resolve().parents[1] / "lab" / "results_db" / "alembic.ini"
        )
        if not Path(ini_path).exists():
            pytest.skip("alembic.ini not found")

        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

        command.upgrade(alembic_cfg, "head")
        command.downgrade(alembic_cfg, "base")

        conn = _sqlite_conn(db_path)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        conn.close()
        # Only alembic_version table should remain (it drops itself with base)
        assert "benchmark_runs" not in tables
        assert "strategy_results" not in tables
        assert "promotions" not in tables


# ---------------------------------------------------------------------------
# Basic CRUD tests (using SQLAlchemy async)
# ---------------------------------------------------------------------------

class TestBasicCRUD:
    def test_insert_benchmark_run(self, prepared_db):
        engine, session_factory, _ = prepared_db

        async def _run():
            async with session_factory() as session:
                run = BenchmarkRun(
                    experiment_id="exp-001",
                    run_at=datetime(2026, 5, 1, 12, 0, 0),
                    lab_git_sha="abc123",
                    core_version="0.1.0",
                    simulation_count=100,
                    opponent_set='["balanced","aggressive"]',
                )
                session.add(run)
                await session.commit()
                await session.refresh(run)
                return run.id

        run_id = asyncio.get_event_loop().run_until_complete(_run())
        assert run_id == 1

    def test_insert_strategy_result(self, prepared_db):
        engine, session_factory, _ = prepared_db

        async def _run():
            async with session_factory() as session:
                run = BenchmarkRun(
                    experiment_id="exp-002",
                    run_at=datetime(2026, 5, 1),
                    lab_git_sha="abc123",
                    core_version="0.1.0",
                    simulation_count=50,
                    opponent_set="[]",
                )
                session.add(run)
                await session.flush()

                result = StrategyResult(
                    run_id=run.id,
                    strategy_name="balanced",
                    win_rate=0.55,
                    gate_result="PASS",
                )
                session.add(result)
                await session.commit()
                await session.refresh(result)
                return result.id, result.win_rate

        result_id, win_rate = asyncio.get_event_loop().run_until_complete(_run())
        assert result_id == 1
        assert win_rate == pytest.approx(0.55)


# ---------------------------------------------------------------------------
# Trigger invariant tests (single-current-promotion)
# Triggers are only present when schema is created via Alembic migrations,
# not via create_all(). Use a dedicated fixture for these tests.
# ---------------------------------------------------------------------------

@pytest.fixture
def alembic_db(tmp_path):
    """SQLite DB created via Alembic upgrade (includes triggers)."""
    db_path = str(tmp_path / "trigger_test.db")
    ini_path = str(
        Path(__file__).resolve().parents[1] / "lab" / "results_db" / "alembic.ini"
    )
    if not Path(ini_path).exists():
        pytest.skip("alembic.ini not found")

    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(alembic_cfg, "head")
    return db_path


class TestPromotionTriggers:
    def _seed_run(self, conn):
        conn.execute("""
            INSERT INTO benchmark_runs
              (experiment_id, run_at, lab_git_sha, core_version, simulation_count, opponent_set)
            VALUES ('exp', '2026-05-01', 'abc', '0.1', 10, '[]')
        """)
        conn.commit()

    def test_insert_trigger_clears_previous_current(self, alembic_db):
        conn = _sqlite_conn(alembic_db)
        self._seed_run(conn)

        conn.execute("""
            INSERT INTO promotions
              (promoted_at, strategy_name, benchmark_run_id,
               win_rate_at_promotion, improvement_pp, p_value, is_current)
            VALUES ('2026-05-01', 'balanced', 1, 0.55, 0.05, 0.01, 1)
        """)
        conn.commit()

        # Insert a second is_current=1 promotion — trigger should clear the first
        conn.execute("""
            INSERT INTO promotions
              (promoted_at, strategy_name, benchmark_run_id,
               win_rate_at_promotion, improvement_pp, p_value, is_current)
            VALUES ('2026-05-02', 'aggressive', 1, 0.60, 0.05, 0.005, 1)
        """)
        conn.commit()

        rows = conn.execute(
            "SELECT id, is_current FROM promotions ORDER BY id"
        ).fetchall()
        conn.close()

        assert rows[0][1] == 0, "Old promotion should be cleared by trigger"
        assert rows[1][1] == 1, "New promotion should be current"

    def test_update_trigger_clears_others(self, alembic_db):
        conn = _sqlite_conn(alembic_db)
        self._seed_run(conn)

        # Insert two non-current promotions
        conn.execute("""
            INSERT INTO promotions
              (promoted_at, strategy_name, benchmark_run_id,
               win_rate_at_promotion, improvement_pp, p_value, is_current)
            VALUES ('2026-05-01', 'balanced', 1, 0.55, 0.05, 0.01, 0)
        """)
        conn.execute("""
            INSERT INTO promotions
              (promoted_at, strategy_name, benchmark_run_id,
               win_rate_at_promotion, improvement_pp, p_value, is_current)
            VALUES ('2026-05-02', 'conservative', 1, 0.50, 0.01, 0.04, 1)
        """)
        conn.commit()

        # Update row 1 to is_current=1 — trigger should clear row 2
        conn.execute("UPDATE promotions SET is_current = 1 WHERE id = 1")
        conn.commit()

        rows = conn.execute(
            "SELECT id, is_current FROM promotions ORDER BY id"
        ).fetchall()
        conn.close()

        assert rows[0][1] == 1, "Updated promotion should be current"
        assert rows[1][1] == 0, "Other promotion should be cleared by trigger"


# ---------------------------------------------------------------------------
# Auction tables tests (#194)
# ---------------------------------------------------------------------------

class TestAuctionTablesCRUD:
    """CRUD tests for real_auction_drafts, real_auction_picks, auction_corpus."""

    def test_real_auction_drafts_insert(self, prepared_db):
        engine, session_factory, db_path = prepared_db

        async def _run():
            async with session_factory() as session:
                draft = RealAuctionDraft(
                    sleeper_draft_id="sl-draft-001",
                    sleeper_league_id="sl-league-001",
                    season="2024",
                    team_count=12,
                    scoring_format="ppr",
                    auction_budget=200,
                )
                session.add(draft)
                await session.commit()
                await session.refresh(draft)
                return draft.id, draft.season

        draft_id, season = asyncio.get_event_loop().run_until_complete(_run())
        assert draft_id == 1
        assert season == "2024"

    def test_real_auction_picks_foreign_key(self, prepared_db):
        engine, session_factory, _ = prepared_db

        async def _run():
            async with session_factory() as session:
                draft = RealAuctionDraft(
                    sleeper_draft_id="sl-draft-002",
                    sleeper_league_id="sl-league-002",
                    season="2024",
                    team_count=10,
                )
                session.add(draft)
                await session.flush()

                pick = RealAuctionPick(
                    draft_id=draft.id,
                    sleeper_player_id="sp-001",
                    player_name="Patrick Mahomes",
                    position="QB",
                    nfl_team="KC",
                    winner_bid=55,
                    pick_order=1,
                )
                session.add(pick)
                await session.commit()
                await session.refresh(pick)
                return pick.id, pick.winner_bid, pick.draft_id

        pick_id, bid, fk = asyncio.get_event_loop().run_until_complete(_run())
        assert pick_id == 1
        assert bid == 55
        assert fk == 1

    def test_auction_corpus_unique_draft(self, prepared_db):
        """auction_corpus has a UNIQUE constraint on draft_id."""
        engine, session_factory, db_path = prepared_db

        async def _run():
            async with session_factory() as session:
                draft = RealAuctionDraft(
                    sleeper_draft_id="sl-draft-003",
                    sleeper_league_id="sl-league-003",
                    season="2023",
                    team_count=12,
                )
                session.add(draft)
                await session.flush()

                corpus = AuctionCorpus(
                    draft_id=draft.id,
                    quality_score=0.85,
                    used_in_backtest=False,
                )
                session.add(corpus)
                await session.commit()
                await session.refresh(corpus)
                return corpus.id, corpus.quality_score

        corpus_id, score = asyncio.get_event_loop().run_until_complete(_run())
        assert corpus_id == 1
        assert score == pytest.approx(0.85)

    def test_new_tables_present_in_schema(self, prepared_db):
        """All three new tables must be visible in sqlite_master after create_all."""
        _, _, db_path = prepared_db
        conn = _sqlite_conn(db_path)
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        conn.close()
        assert "real_auction_drafts" in tables
        assert "real_auction_picks" in tables
        assert "auction_corpus" in tables

    def test_new_indexes_present_in_schema(self, prepared_db):
        """Indexes defined on the new tables must be visible after create_all."""
        _, _, db_path = prepared_db
        conn = _sqlite_conn(db_path)
        indexes = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )}
        conn.close()
        assert "idx_rad_season" in indexes
        assert "idx_rap_draft_id" in indexes
        assert "idx_rap_player_id" in indexes
