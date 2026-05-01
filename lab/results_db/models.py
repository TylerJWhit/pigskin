"""SQLAlchemy ORM models for the Pigskin Lab results database.

Schema defined by ADR-004. Three tables:
  - benchmark_runs    : one row per full simulation batch
  - strategy_results  : per-strategy results within a run
  - promotions        : strategy promotion history with single-current trigger

Database: SQLite with WAL mode, accessed via SQLAlchemy async (aiosqlite).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    ForeignKey,
    Index,
    event,
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


class Base(DeclarativeBase):
    pass


class BenchmarkRun(Base):
    """One row per full simulation batch (one call to the benchmark runner)."""

    __tablename__ = "benchmark_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(String, nullable=False)
    run_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    lab_git_sha = Column(String, nullable=False)
    core_version = Column(String, nullable=False)
    simulation_count = Column(Integer, nullable=False)
    seed_list = Column(Text, nullable=True)          # JSON array of seeds used
    opponent_set = Column(Text, nullable=False)      # JSON array of strategy names
    config_snapshot = Column(Text, nullable=True)    # JSON snapshot of DraftConfig

    strategy_results = relationship(
        "StrategyResult", back_populates="run", cascade="all, delete-orphan"
    )


class StrategyResult(Base):
    """Per-strategy results within a single benchmark run."""

    __tablename__ = "strategy_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("benchmark_runs.id"), nullable=False)
    strategy_name = Column(String, nullable=False)
    win_rate = Column(Float, nullable=False)
    win_rate_stddev = Column(Float, nullable=True)
    avg_rank = Column(Float, nullable=True)
    avg_budget_efficiency = Column(Float, nullable=True)
    p_value_vs_current = Column(Float, nullable=True)
    gate_result = Column(String, nullable=True)    # 'PASS', 'FAIL', 'NOT_EVALUATED'
    raw_results = Column(Text, nullable=True)      # JSON array of per-simulation outcomes

    run = relationship("BenchmarkRun", back_populates="strategy_results")


class Promotion(Base):
    """Strategy promotion history.

    The is_current invariant — at most one row has is_current=1 at any
    time — is enforced by SQLite triggers in the Alembic baseline migration.
    """

    __tablename__ = "promotions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    promoted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    strategy_name = Column(String, nullable=False)
    benchmark_run_id = Column(Integer, ForeignKey("benchmark_runs.id"), nullable=False)
    win_rate_at_promotion = Column(Float, nullable=False)
    improvement_pp = Column(Float, nullable=False)   # percentage-point improvement
    p_value = Column(Float, nullable=False)
    app_git_sha = Column(String, nullable=True)
    promoted_by = Column(String, nullable=True)      # GitHub username or 'auto'
    is_current = Column(Integer, nullable=False, default=1)
    rolled_back_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Index declarations (mirrors ADR-004)
# ---------------------------------------------------------------------------

Index("idx_benchmark_runs_experiment", BenchmarkRun.experiment_id)
Index("idx_strategy_results_run", StrategyResult.run_id)
Index("idx_strategy_results_name", StrategyResult.strategy_name)
Index("idx_promotions_current", Promotion.is_current)


# ---------------------------------------------------------------------------
# Async engine factory
# ---------------------------------------------------------------------------

def make_engine(db_url: str = "sqlite+aiosqlite:///lab/results_db/pigskin_lab.db"):
    """Return an async SQLAlchemy engine with SQLite WAL mode enabled."""
    engine = create_async_engine(db_url, echo=False)

    # Enable WAL mode on every new connection for concurrent read safety.
    @event.listens_for(engine.sync_engine, "connect")
    def _set_wal_mode(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def make_session_factory(engine):
    """Return an async session factory bound to the given engine."""
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
