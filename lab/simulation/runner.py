"""Simulation runner for multi-strategy benchmarking.

Runs N auction draft simulations per strategy and persists results to the
lab SQLite database (BenchmarkRun + StrategyResult rows per ADR-004).

Usage (CLI):
    python -m lab.simulation.runner --strategies all --runs 100 --budget 200

Usage (API):
    from lab.simulation.runner import SimulationRunner
    runner = SimulationRunner(strategies=["balanced", "inflation_vor"], runs=100)
    runner.run()
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import subprocess
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from classes.tournament import Tournament  # type: ignore

logger = logging.getLogger(__name__)


def _git_sha() -> str:
    """Return the current HEAD git SHA, or 'unknown' if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _load_players():
    """Load players from the default FantasyPros data source."""
    from data.fantasypros_loader import FantasyProsLoader  # type: ignore

    loader = FantasyProsLoader()
    return loader.load_all_players()


def _run_tournament_for_strategy(
    strategy_key: str,
    players,
    budget: float,
    roster_size: int,
    num_opponents: int,
    runs: int,
) -> Dict:
    """Run a Tournament with *strategy_key* vs. *num_opponents* balanced opponents.

    Returns the raw tournament results dict for *strategy_key*.
    """

    tournament = Tournament(
        name=f"bench_{strategy_key}",
        num_simulations=runs,
        budget_per_team=budget,
        roster_size=roster_size,
    )
    tournament.add_players(players)

    # Focal strategy: owner_name used as prefix in _analyze_results
    tournament.add_strategy_config(
        strategy_type=strategy_key,
        owner_name=strategy_key,
        num_teams=1,
    )
    # Balanced opponents fill the rest of the league
    for i in range(num_opponents):
        tournament.add_strategy_config(
            strategy_type="balanced",
            owner_name=f"opp{i}",
            num_teams=1,
        )

    summary = tournament.run_tournament(parallel=True)
    return summary.get("results", {})


async def _persist_results(
    experiment_id: str,
    strategy_summaries: Dict[str, Dict],
    total_runs: int,
    opponent_set: List[str],
    db_url: str,
) -> None:
    """Write BenchmarkRun + StrategyResult rows to the lab DB."""
    from lab.results_db.models import (  # type: ignore
        Base,
        BenchmarkRun,
        StrategyResult,
        make_engine,
        make_session_factory,
    )

    engine = make_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = make_session_factory(engine)
    async with session_factory() as session:
        run = BenchmarkRun(
            experiment_id=experiment_id,
            run_at=datetime.utcnow(),
            lab_git_sha=_git_sha(),
            core_version="sprint7",
            simulation_count=total_runs,
            opponent_set=json.dumps(opponent_set),
        )
        session.add(run)
        await session.flush()  # populate run.id

        for strategy_name, summary in strategy_summaries.items():
            raw = summary.get("raw_results", [])
            result = StrategyResult(
                run_id=run.id,
                strategy_name=strategy_name,
                win_rate=summary["win_rate"],
                win_rate_stddev=summary.get("win_rate_stddev"),
                avg_rank=summary.get("avg_rank"),
                avg_budget_efficiency=summary.get("avg_budget_efficiency"),
                gate_result=summary.get("gate_result", "NOT_EVALUATED"),
                raw_results=json.dumps(raw),
            )
            session.add(result)

        await session.commit()

    await engine.dispose()
    logger.info("Results persisted as BenchmarkRun id=%s", run.id)


class SimulationRunner:
    """Multi-strategy auction draft benchmark runner.

    Args:
        strategies:    List of strategy keys to benchmark, or ["all"] for every
                       registered strategy.
        runs:          Number of simulations per strategy (default 100).
        budget:        Auction budget per team (default 200).
        roster_size:   Roster slots per team (default 16).
        num_opponents: Number of "balanced" opponent teams (default 11).
        db_url:        SQLAlchemy URL for result storage.
        experiment_id: Unique label for this benchmark batch; auto-generated
                       (UUID4 short) if not provided.
    """

    def __init__(
        self,
        strategies: Optional[List[str]] = None,
        runs: int = 100,
        budget: float = 200.0,
        roster_size: int = 16,
        num_opponents: int = 11,
        db_url: str = "sqlite+aiosqlite:///lab/results_db/pigskin_lab.db",
        experiment_id: Optional[str] = None,
    ) -> None:
        self.strategies = strategies or ["all"]
        self.runs = runs
        self.budget = budget
        self.roster_size = roster_size
        self.num_opponents = num_opponents
        self.db_url = db_url
        self.experiment_id = experiment_id or str(uuid.uuid4())[:8]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> Dict[str, Dict]:
        """Execute the benchmark synchronously. Returns per-strategy summaries."""
        return asyncio.run(self._run_async())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _run_async(self) -> Dict[str, Dict]:
        from strategies import AVAILABLE_STRATEGIES  # type: ignore

        target_keys: List[str]
        if self.strategies == ["all"] or self.strategies is None:
            target_keys = list(AVAILABLE_STRATEGIES.keys())
        else:
            target_keys = self.strategies

        # Validate keys early.
        unknown = [k for k in target_keys if k not in AVAILABLE_STRATEGIES]
        if unknown:
            raise ValueError(f"Unknown strategy key(s): {unknown!r}")

        players = _load_players()
        logger.info(
            "Benchmark %s: %d strategies × %d runs each, %d players loaded",
            self.experiment_id,
            len(target_keys),
            self.runs,
            len(players),
        )

        summaries: Dict[str, Dict] = {}
        for key in target_keys:
            summary = self._benchmark_strategy(key, players)
            summaries[key] = summary
            logger.info(
                "  %-30s  win_rate=%.1f%%  avg_rank=%.2f  budget_eff=%.3f",
                key,
                summary["win_rate"] * 100,
                summary["avg_rank"],
                summary["avg_budget_efficiency"],
            )

        await _persist_results(
            experiment_id=self.experiment_id,
            strategy_summaries=summaries,
            total_runs=self.runs,
            opponent_set=["balanced"] * self.num_opponents,
            db_url=self.db_url,
        )

        return summaries

    def _benchmark_strategy(self, key: str, players) -> Dict:
        try:
            all_results = _run_tournament_for_strategy(
                strategy_key=key,
                players=players,
                budget=self.budget,
                roster_size=self.roster_size,
                num_opponents=self.num_opponents,
                runs=self.runs,
            )
        except Exception as exc:
            logger.error("Tournament for %s failed: %s", key, exc)
            return {
                "win_rate": 0.0,
                "win_rate_stddev": None,
                "avg_rank": float(self.num_opponents + 1),
                "avg_budget_efficiency": 0.0,
                "gate_result": "NOT_EVALUATED",
                "raw_results": [],
            }

        # Tournament._analyze_results buckets by strategy_type prefix.
        # The focal key should be present directly.
        focal = all_results.get(key)
        if focal is None:
            logger.warning("No results found for strategy %r in tournament output", key)
            return {
                "win_rate": 0.0,
                "win_rate_stddev": None,
                "avg_rank": float(self.num_opponents + 1),
                "avg_budget_efficiency": 0.0,
                "gate_result": "NOT_EVALUATED",
                "raw_results": [],
            }

        win_rate = focal.get("win_rate", 0.0)
        avg_rank = focal.get("avg_ranking", float(self.num_opponents + 1))
        avg_spent = focal.get("avg_spent", self.budget)
        avg_points = focal.get("avg_points", 0.0)
        avg_budget_efficiency = avg_points / avg_spent if avg_spent > 0 else 0.0

        num_teams = self.num_opponents + 1
        expected_win_rate = 1.0 / num_teams
        gate_result = "PASS" if win_rate >= expected_win_rate else "FAIL"

        return {
            "win_rate": win_rate,
            "win_rate_stddev": None,
            "avg_rank": avg_rank,
            "avg_budget_efficiency": avg_budget_efficiency,
            "gate_result": gate_result,
            "raw_results": [],
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run multi-strategy auction draft benchmarks and store results."
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=["all"],
        metavar="KEY",
        help="Strategy keys to benchmark (default: all). Use 'all' to run every registered strategy.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=100,
        metavar="N",
        help="Number of simulations per strategy (default: 100).",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=200.0,
        help="Auction budget per team (default: 200).",
    )
    parser.add_argument(
        "--roster-size",
        type=int,
        default=16,
        dest="roster_size",
        help="Roster slots per team (default: 16).",
    )
    parser.add_argument(
        "--opponents",
        type=int,
        default=11,
        dest="num_opponents",
        help="Number of balanced opponent teams (default: 11).",
    )
    parser.add_argument(
        "--db-url",
        default="sqlite+aiosqlite:///lab/results_db/pigskin_lab.db",
        dest="db_url",
        help="SQLAlchemy database URL (default: lab SQLite).",
    )
    parser.add_argument(
        "--experiment-id",
        default=None,
        dest="experiment_id",
        help="Human-readable label for this benchmark batch.",
    )
    parser.add_argument(
        "--list-strategies",
        action="store_true",
        dest="list_strategies",
        help="Print all available strategy keys and exit.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.list_strategies:
        from strategies import AVAILABLE_STRATEGIES  # type: ignore

        print("Available strategies:")
        for key in sorted(AVAILABLE_STRATEGIES):
            print(f"  {key}")
        return

    runner = SimulationRunner(
        strategies=args.strategies,
        runs=args.runs,
        budget=args.budget,
        roster_size=args.roster_size,
        num_opponents=args.num_opponents,
        db_url=args.db_url,
        experiment_id=args.experiment_id,
    )

    summaries = runner.run()

    # Print results table.
    print(f"\nBenchmark: {runner.experiment_id}  ({args.runs} runs × {len(summaries)} strategies)\n")
    header = f"{'Strategy':<32}  {'Win%':>6}  {'AvgRank':>7}  {'BudEff':>7}  {'Gate':>10}"
    print(header)
    print("-" * len(header))
    for key, s in sorted(summaries.items(), key=lambda t: -t[1]["win_rate"]):
        print(
            f"{key:<32}  {s['win_rate']*100:>5.1f}%  {s['avg_rank']:>7.2f}  "
            f"{s['avg_budget_efficiency']:>7.3f}  {s.get('gate_result',''):>10}"
        )


if __name__ == "__main__":
    main()
