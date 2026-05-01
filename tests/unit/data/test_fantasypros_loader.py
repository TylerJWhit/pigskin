"""Tests for FantasyProsLoader."""
import csv
import io
import os
import pytest
from unittest.mock import patch, MagicMock

from data.fantasypros_loader import FantasyProsLoader, load_fantasypros_players, _parse_csv_file


def _csv_content(rows):
    """Generate CSV string from list of dicts."""
    if not rows:
        return "Player,Team,FPTS\n"
    headers = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _make_csv_file(tmp_path, position, rows):
    path = tmp_path / f"{position}.csv"
    path.write_text(_csv_content(rows))
    return str(tmp_path)


class TestFantasyProsLoaderInit:
    def test_default_data_path(self):
        loader = FantasyProsLoader()
        assert loader.data_path == "data/sheets"

    def test_custom_data_path(self):
        loader = FantasyProsLoader("/custom/path")
        assert loader.data_path == "/custom/path"

    def test_position_files(self):
        loader = FantasyProsLoader()
        assert "QB" in loader.position_files
        assert "RB" in loader.position_files


class TestLoadPositionData:
    def test_unknown_position_raises(self):
        loader = FantasyProsLoader()
        with pytest.raises(ValueError, match="Unknown position"):
            loader.load_position_data("XX")

    def test_file_not_found_raises(self, tmp_path):
        loader = FantasyProsLoader(str(tmp_path))
        with pytest.raises(FileNotFoundError):
            loader.load_position_data("QB")

    def test_load_valid_csv(self, tmp_path):
        rows = [
            {"Player": "Patrick Mahomes", "Team": "KC", "FPTS": "400.5"},
            {"Player": "Josh Allen", "Team": "BUF", "FPTS": "380.2"},
        ]
        data_path = _make_csv_file(tmp_path, "QB", rows)
        loader = FantasyProsLoader(data_path)
        players = loader.load_position_data("QB")
        assert len(players) == 2
        assert players[0].name == "Patrick Mahomes"

    def test_load_csv_skips_empty_player_rows(self, tmp_path):
        rows = [
            {"Player": "Patrick Mahomes", "Team": "KC", "FPTS": "400.5"},
            {"Player": "", "Team": "", "FPTS": ""},  # Empty row
        ]
        data_path = _make_csv_file(tmp_path, "QB", rows)
        loader = FantasyProsLoader(data_path)
        players = loader.load_position_data("QB")
        assert len(players) == 1

    def test_load_csv_error_logs_and_returns_empty(self, tmp_path):
        # Write invalid content to trigger an exception during read
        qb_file = tmp_path / "QB.csv"
        qb_file.write_bytes(b"\xff\xfe invalid utf-8")
        loader = FantasyProsLoader(str(tmp_path))
        # Should catch exception, log it, and return whatever was parsed
        result = loader.load_position_data("QB")
        assert isinstance(result, list)


class TestParsePlayerRow:
    def setup_method(self):
        self.loader = FantasyProsLoader()

    def test_valid_row(self):
        row = {"Player": "Patrick Mahomes", "Team": "KC", "FPTS": "400.5"}
        player = self.loader._parse_player_row(row, "QB")
        assert player is not None
        assert player.name == "Patrick Mahomes"
        assert player.projected_points == 400.5

    def test_empty_player_name_returns_none(self):
        row = {"Player": "", "Team": "KC", "FPTS": "100"}
        result = self.loader._parse_player_row(row, "QB")
        assert result is None

    def test_missing_fpts_defaults_to_zero(self):
        row = {"Player": "Test Player", "Team": "KC", "FPTS": ""}
        player = self.loader._parse_player_row(row, "QB")
        assert player is not None
        assert player.projected_points == 0.0

    def test_fpts_with_comma(self):
        row = {"Player": "Test Player", "Team": "KC", "FPTS": "1,200.5"}
        player = self.loader._parse_player_row(row, "QB")
        assert player.projected_points == 1200.5

    def test_invalid_fpts_skips_player(self):
        row = {"Player": "Test Player", "Team": "KC", "FPTS": "abc_invalid"}
        result = self.loader._parse_player_row(row, "QB")
        assert result is None


class TestLoadAllPlayers:
    def test_load_all_with_min_points_filter(self, tmp_path):
        rows = [
            {"Player": "Top QB", "Team": "KC", "FPTS": "400.0"},
            {"Player": "Backup QB", "Team": "GB", "FPTS": "50.0"},
        ]
        for pos in ["QB", "RB", "WR", "TE", "K", "DST"]:
            (tmp_path / f"{pos}.csv").write_text(_csv_content(rows))
        loader = FantasyProsLoader(str(tmp_path))
        players = loader.load_all_players(min_projected_points=100.0)
        assert all(p.projected_points >= 100.0 for p in players)

    def test_load_all_handles_missing_file(self, tmp_path):
        # Only QB file exists
        rows = [{"Player": "Test QB", "Team": "KC", "FPTS": "300.0"}]
        (tmp_path / "QB.csv").write_text(_csv_content(rows))
        loader = FantasyProsLoader(str(tmp_path))
        # Should not raise even if other files are missing
        players = loader.load_all_players()
        assert isinstance(players, list)


class TestGetPlayerByName:
    def test_found_by_name(self, tmp_path):
        rows = [{"Player": "Patrick Mahomes", "Team": "KC", "FPTS": "400.0"}]
        (tmp_path / "QB.csv").write_text(_csv_content(rows))
        loader = FantasyProsLoader(str(tmp_path))
        player = loader.get_player_by_name("Patrick Mahomes", position="QB")
        assert player is not None
        assert player.name == "Patrick Mahomes"

    def test_not_found_returns_none(self, tmp_path):
        rows = [{"Player": "Patrick Mahomes", "Team": "KC", "FPTS": "400.0"}]
        (tmp_path / "QB.csv").write_text(_csv_content(rows))
        loader = FantasyProsLoader(str(tmp_path))
        result = loader.get_player_by_name("No Such Player", position="QB")
        assert result is None

    def test_search_all_positions(self, tmp_path):
        for pos in ["QB", "RB", "WR", "TE", "K", "DST"]:
            rows = [{"Player": f"{pos} Star", "Team": "KC", "FPTS": "200.0"}]
            (tmp_path / f"{pos}.csv").write_text(_csv_content(rows))
        loader = FantasyProsLoader(str(tmp_path))
        player = loader.get_player_by_name("RB Star")
        assert player is not None
        assert player.name == "RB Star"

    def test_exception_in_load_continues(self, tmp_path):
        # Only QB.csv exists; searching without position should not raise
        rows = [{"Player": "Test QB", "Team": "KC", "FPTS": "300.0"}]
        (tmp_path / "QB.csv").write_text(_csv_content(rows))
        loader = FantasyProsLoader(str(tmp_path))
        result = loader.get_player_by_name("Test QB")  # will fail on RB etc.
        assert result is not None  # Found in QB


class TestCalculateAuctionValues:
    def setup_method(self):
        self.loader = FantasyProsLoader()

    def _make_players(self, positions_pts):
        from classes.player import Player
        players = []
        for i, (pos, pts) in enumerate(positions_pts):
            players.append(Player(
                player_id=f"p{i}",
                name=f"Player{i}",
                position=pos,
                projected_points=pts,
                auction_value=1.0,
                bye_week=5
            ))
        return players

    def test_empty_players_no_op(self):
        self.loader.calculate_auction_values([])  # Should not raise

    def test_assigns_auction_values(self):
        players = self._make_players([("QB", 400.0), ("QB", 200.0)])
        self.loader.calculate_auction_values(players)
        assert players[0].auction_value > players[1].auction_value

    def test_zero_projected_points_skips(self):
        players = self._make_players([("QB", 0.0)])
        self.loader.calculate_auction_values(players)
        # zero total_points causes continue branch
        assert players[0].auction_value >= 1.0

    def test_custom_value_distribution(self):
        players = self._make_players([("QB", 300.0)])
        custom = {"QB": 0.5}
        self.loader.calculate_auction_values(players, value_distribution=custom)
        assert players[0].auction_value > 1.0

    def test_unknown_position_skipped(self):
        players = self._make_players([("QB", 300.0)])
        # Use a value_distribution that doesn't include QB → continue branch
        custom = {"RB": 0.5}
        self.loader.calculate_auction_values(players, value_distribution=custom)
        # QB not in custom distribution → stays at default 1.0
        assert players[0].auction_value == 1.0


class TestGetTopPlayers:
    def test_get_top_players(self, tmp_path):
        rows = [
            {"Player": f"Player{i}", "Team": "KC", "FPTS": str(100 - i * 5)}
            for i in range(10)
        ]
        (tmp_path / "QB.csv").write_text(_csv_content(rows))
        loader = FantasyProsLoader(str(tmp_path))
        top = loader.get_top_players("QB", count=3)
        assert len(top) == 3
        assert top[0].projected_points >= top[1].projected_points


class TestGetDataSummary:
    def test_data_summary(self, tmp_path):
        rows = [{"Player": "Test", "Team": "KC", "FPTS": "100"}]
        for pos in ["QB", "RB", "WR", "TE", "K", "DST"]:
            (tmp_path / f"{pos}.csv").write_text(_csv_content(rows))
        loader = FantasyProsLoader(str(tmp_path))
        summary = loader.get_data_summary()
        assert "QB" in summary
        assert "total" in summary


class TestParseCsvFile:
    def test_parse_csv_file(self):
        content = "Player,Team,FPTS\nPatrick Mahomes,KC,400.0\nJosh Allen,BUF,380.0\n"
        players = _parse_csv_file(content, "QB")
        assert len(players) == 2

    def test_parse_csv_skips_invalid(self):
        content = "Player,Team,FPTS\n,KC,100\nValid Player,KC,100\n"
        players = _parse_csv_file(content, "QB")
        assert len(players) == 1


class TestConvenienceFunction:
    def test_load_fantasypros_players_missing_files(self, tmp_path):
        # No files in tmp_path → all positions fail
        loader_result = load_fantasypros_players(data_path=str(tmp_path))
        assert isinstance(loader_result, list)
