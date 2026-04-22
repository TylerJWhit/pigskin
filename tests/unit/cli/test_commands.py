"""Unit tests for CLI commands — cheatsheet_parser integration."""

from unittest.mock import MagicMock, patch


class TestAnalyzeUndervaluedPlayersCommands:
    """Tests for analyze_undervalued_players commands that use utils.cheatsheet_parser."""

    def test_get_cheatsheet_parser_importable(self):
        """utils.cheatsheet_parser.get_cheatsheet_parser is importable."""
        from utils.cheatsheet_parser import get_cheatsheet_parser
        parser = get_cheatsheet_parser()
        assert parser is not None

    def test_cheatsheet_parser_find_undervalued_simple(self):
        """CheatsheetParser.find_undervalued_players_simple returns a list."""
        from utils.cheatsheet_parser import get_cheatsheet_parser
        parser = get_cheatsheet_parser()
        result = parser.find_undervalued_players_simple(threshold=10.0)
        assert isinstance(result, list)

    def test_cheatsheet_parser_find_undervalued_detailed(self):
        """CheatsheetParser.find_undervalued_players returns a list."""
        from utils.cheatsheet_parser import get_cheatsheet_parser
        parser = get_cheatsheet_parser()
        result = parser.find_undervalued_players(threshold=10.0)
        assert isinstance(result, list)

    def test_get_cheatsheet_parser_mock(self):
        """utils.cheatsheet_parser.get_cheatsheet_parser can be mocked."""
        mock_parser = MagicMock()
        mock_parser.find_undervalued_players_simple.return_value = [
            {"name": "Josh Allen", "position": "QB", "value": 50, "projected": 40}
        ]
        with patch("utils.cheatsheet_parser.get_cheatsheet_parser", return_value=mock_parser):
            from utils.cheatsheet_parser import get_cheatsheet_parser
            parser = get_cheatsheet_parser()
            results = parser.find_undervalued_players_simple(threshold=10.0)
            assert len(results) == 1
            assert results[0]["name"] == "Josh Allen"

    def test_cheatsheet_parser_default_threshold(self):
        """CheatsheetParser methods work with default threshold."""
        from utils.cheatsheet_parser import CheatsheetParser
        parser = CheatsheetParser()
        assert parser.find_undervalued_players_simple() == []
        assert parser.find_undervalued_players() == []
        assert parser.get_all_players() == {}
