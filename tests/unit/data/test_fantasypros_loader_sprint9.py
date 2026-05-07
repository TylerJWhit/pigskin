"""Sprint 9 QA tests — Issue #167: calculate_auction_values hardcodes total_budget=2400.0.

Expected outcome:
  - FAILS before fix  (FantasyProsLoader has no budget param; load_all_players always uses 2400.0)
  - PASSES after fix  (loader accepts/stores total_budget; load_all_players uses it)
"""

import csv
import io
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
