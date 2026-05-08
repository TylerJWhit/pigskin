"""Sprint 9 QA tests — Issue #167 and #166.

Issue #167: calculate_auction_values hardcodes total_budget=2400.0.
Issue #166: CSV files re-read from disk on every load_position_data call — no caching.

Expected outcome:
  - FAILS before fix  (FantasyProsLoader has no budget param; no cache; no clear_cache)
  - PASSES after fix  (loader accepts/stores total_budget; caches per-position; clear_cache works)
"""

import csv
import io
import os
from unittest.mock import patch
from data.fantasypros_loader import FantasyProsLoader
from classes.player import Player


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_player(position: str, projected_points: float) -> Player:
    return Player(
        player_id=f"{position.lower()}_test",
        name="Test Player",
        position=position,
        team="TST",
        projected_points=projected_points,
        auction_value=0.0,
        bye_week=None,
    )


def _make_csv(rows: list[dict]) -> str:
    if not rows:
        return "Player,Team,FPTS\n"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _write_position_csv(tmp_path, position: str, rows: list[dict]) -> None:
    (tmp_path / f"{position}.csv").write_text(_make_csv(rows))


# ── Issue #167 tests ──────────────────────────────────────────────────────────


class TestCalculateAuctionValuesHardcodedBudget:
    """Issue #167: FantasyProsLoader must respect a configurable total budget."""

    def test_loader_constructor_accepts_total_budget_param(self):
        """FantasyProsLoader.__init__ must accept a total_budget keyword argument.

        Currently FAILS with TypeError (no such parameter exists).
        After fix the constructor stores the value as self.total_budget.
        """
        loader = FantasyProsLoader(data_path="data/sheets", total_budget=1000.0)
        assert loader.total_budget == 1000.0, (
            "FantasyProsLoader must expose total_budget attribute (Issue #167)"
        )

    def test_calculate_auction_values_with_small_budget_produces_lower_values(self):
        """Auction values must scale proportionally with total_budget.

        Passing total_budget=1000.0 must yield values noticeably lower than
        the hardcoded default of 2400.0.  This already works at the method
        API level and serves as a regression guard once the callers are fixed.
        """
        loader = FantasyProsLoader()
        players_1000 = [_make_player("QB", 300.0)]
        players_2400 = [_make_player("QB", 300.0)]

        loader.calculate_auction_values(players_1000, total_budget=1000.0)
        loader.calculate_auction_values(players_2400, total_budget=2400.0)

        assert players_1000[0].auction_value < players_2400[0].auction_value, (
            "Auction values must reflect total_budget; 1000.0 budget must produce "
            "lower values than 2400.0 budget (Issue #167)"
        )

    def test_load_all_players_uses_configured_budget_not_hardcoded_2400(self, tmp_path):
        """load_all_players() must use the loader's configured budget, not 2400.0.

        Currently FAILS because:
          1. FantasyProsLoader has no total_budget parameter.
          2. load_all_players() calls self.calculate_auction_values(players) with
             no budget argument, so the default 2400.0 is always used.

        After fix: loader.total_budget is passed through to the calculation.
        """
        # Write a minimal QB CSV so load_all_players() can run
        _write_position_csv(
            tmp_path,
            "QB",
            [{"Player": "Test QB", "Team": "TST", "FPTS": "300.0"}],
        )
        for pos in ("RB", "WR", "TE", "K", "DST"):
            (tmp_path / f"{pos}.csv").write_text("Player,Team,FPTS\n")

        # Load at default 2400.0 budget
        loader_default = FantasyProsLoader(data_path=str(tmp_path))
        players_default = loader_default.load_all_players()

        qb_default = next(
            (p for p in players_default if p.position == "QB"), None
        )
        assert qb_default is not None, "Expected at least one QB loaded"

        # Load at custom 1000.0 budget — requires the fix
        loader_custom = FantasyProsLoader(
            data_path=str(tmp_path), total_budget=1000.0
        )  # FAILS here until constructor is fixed
        players_custom = loader_custom.load_all_players()

        qb_custom = next(
            (p for p in players_custom if p.position == "QB"), None
        )
        assert qb_custom is not None

        assert qb_custom.auction_value < qb_default.auction_value, (
            "load_all_players() with total_budget=1000.0 must produce lower auction "
            "values than the default 2400.0 (Issue #167)"
        )


# ---------------------------------------------------------------------------
# Issue #166 — per-position in-memory cache
# ---------------------------------------------------------------------------

class TestLoadPositionDataCaching:
    """Acceptance criteria for #166: each position CSV read at most once per instance."""

    _CSV_CONTENT = (
        "Player,Team,Bye,Projected,Auction Value\n"
        "Patrick Mahomes,KC,6,380,52\n"
        "Josh Allen,BUF,12,370,50\n"
    )

    def _make_loader(self, tmp_path):
        return FantasyProsLoader(data_path=str(tmp_path))

    def _write_csv(self, tmp_path, filename="QB.csv", content=None):
        path = tmp_path / filename
        path.write_text(content or self._CSV_CONTENT)

    def test_load_position_data_reads_file_only_once(self, tmp_path):
        """Three consecutive calls for the same position open the file exactly once."""
        self._write_csv(tmp_path)
        loader = self._make_loader(tmp_path)

        with patch("builtins.open", wraps=open) as mock_file:
            loader.load_position_data("QB")
            loader.load_position_data("QB")
            loader.load_position_data("QB")

        qb_path = os.path.join(str(tmp_path.resolve()), "QB.csv")
        open_calls = [str(c.args[0]) for c in mock_file.call_args_list]
        assert open_calls.count(qb_path) == 1, (
            f"QB.csv opened {open_calls.count(qb_path)} times; expected 1 (Issue #166)"
        )

    def test_load_position_data_returns_same_object_on_cache_hit(self, tmp_path):
        """The cached call must return the identical list (not a new copy)."""
        self._write_csv(tmp_path)
        loader = self._make_loader(tmp_path)

        first = loader.load_position_data("QB")
        second = loader.load_position_data("QB")
        assert first is second, "Cached result must be the same list object (Issue #166)"

    def test_clear_cache_method_exists(self, tmp_path):
        """FantasyProsLoader must expose a clear_cache() method."""
        loader = self._make_loader(tmp_path)
        assert hasattr(loader, "clear_cache") and callable(loader.clear_cache), (
            "FantasyProsLoader.clear_cache() must exist (Issue #166)"
        )

    def test_clear_cache_forces_re_read(self, tmp_path):
        """After clear_cache(), the next call must re-read from disk."""
        self._write_csv(tmp_path)
        loader = self._make_loader(tmp_path)

        first = loader.load_position_data("QB")
        loader.clear_cache()

        with patch("builtins.open", wraps=open) as mock_file:
            second = loader.load_position_data("QB")

        qb_path = os.path.join(str(tmp_path.resolve()), "QB.csv")
        open_calls = [str(c.args[0]) for c in mock_file.call_args_list]
        assert open_calls.count(qb_path) == 1, (
            "clear_cache() must cause the next call to re-read the file (Issue #166)"
        )
        assert first is not second, (
            "clear_cache() must return a fresh list on the next call (Issue #166)"
        )

    def test_different_positions_cached_independently(self, tmp_path):
        """Each position CSV is read at most once independently."""
        self._write_csv(tmp_path, "QB.csv")
        self._write_csv(tmp_path, "RB.csv",
                        "Player,Team,Bye,Projected,Auction Value\nC. McCaffrey,SF,9,320,48\n")
        loader = self._make_loader(tmp_path)

        with patch("builtins.open", wraps=open) as mock_file:
            loader.load_position_data("QB")
            loader.load_position_data("RB")
            loader.load_position_data("QB")   # cache hit
            loader.load_position_data("RB")   # cache hit

        qb_path = os.path.join(str(tmp_path.resolve()), "QB.csv")
        rb_path = os.path.join(str(tmp_path.resolve()), "RB.csv")
        open_calls = [str(c.args[0]) for c in mock_file.call_args_list]
        assert open_calls.count(qb_path) == 1
        assert open_calls.count(rb_path) == 1

    def test_load_all_players_warms_cache(self, tmp_path):
        """After load_all_players(), load_position_data hits the cache."""
        for pos, fname in [("QB", "QB.csv"), ("RB", "RB.csv"), ("WR", "WR.csv"),
                           ("TE", "TE.csv"), ("K", "K.csv"), ("DST", "DST.csv")]:
            (tmp_path / fname).write_text(
                f"Player,Team,Bye,Projected,Auction Value\nPlayer {pos},NYG,6,100,10\n"
            )
        loader = self._make_loader(tmp_path)
        loader.load_all_players()

        with patch("builtins.open", wraps=open) as mock_file:
            loader.load_position_data("QB")
            loader.load_position_data("RB")

        assert len(mock_file.call_args_list) == 0, (
            "load_position_data must hit the cache populated by load_all_players (Issue #166)"
        )

