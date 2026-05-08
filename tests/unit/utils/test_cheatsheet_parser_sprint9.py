"""Sprint 9 QA tests — Issue #168: CheatsheetParser stub must raise NotImplementedError.

Expected outcome:
  - FAILS before fix  (stub methods silently return empty results)
  - PASSES after fix  (each stub method raises NotImplementedError)
"""

import pytest

from utils.cheatsheet_parser import CheatsheetParser, get_cheatsheet_parser


class TestCheatsheetParserStubRaisesNotImplemented:
    """Issue #168: All stub methods on CheatsheetParser must raise NotImplementedError."""

    def test_get_all_players_raises_not_implemented(self):
        """CheatsheetParser.get_all_players() must raise NotImplementedError.

        Currently FAILS: returns {} silently (invisible failure when stub is used accidentally).
        After fix: raises NotImplementedError with a descriptive message.
        """
        parser = CheatsheetParser()
        with pytest.raises(NotImplementedError):
            parser.get_all_players()

    def test_find_undervalued_players_simple_raises_not_implemented(self):
        """CheatsheetParser.find_undervalued_players_simple() must raise NotImplementedError.

        Currently FAILS: returns [] silently.
        After fix: raises NotImplementedError.
        """
        parser = CheatsheetParser()
        with pytest.raises(NotImplementedError):
            parser.find_undervalued_players_simple()

    def test_find_undervalued_players_raises_not_implemented(self):
        """CheatsheetParser.find_undervalued_players() must raise NotImplementedError.

        Currently FAILS: returns [] silently.
        After fix: raises NotImplementedError.
        """
        parser = CheatsheetParser()
        with pytest.raises(NotImplementedError):
            parser.find_undervalued_players()

    def test_factory_returns_parser_that_raises_on_get_all_players(self):
        """get_cheatsheet_parser() factory must also return a stub that raises.

        Currently FAILS: the returned instance silently returns {}.
        After fix: raises NotImplementedError.
        """
        parser = get_cheatsheet_parser()
        with pytest.raises(NotImplementedError):
            parser.get_all_players()

    def test_stub_does_not_return_empty_dict_for_get_all_players(self):
        """Returning {} is the silent-failure bug; the stub must never silently return it.

        Currently FAILS because the return value IS {}.
        After fix: NotImplementedError is raised so this assertion is moot
        (but included as an explicit guard against the empty-return regression).
        """
        parser = CheatsheetParser()
        try:
            result = parser.get_all_players()
            # If we reach here, no exception was raised — that is the bug.
            assert result != {}, (
                "CheatsheetParser.get_all_players() returned {} without raising "
                "NotImplementedError. Stub methods must raise to prevent silent misuse "
                "(Issue #168)."
            )
        except NotImplementedError:
            pass  # Correct post-fix behaviour

    def test_stub_does_not_return_empty_list_for_find_undervalued(self):
        """Returning [] is the silent-failure bug for find_undervalued_players().

        Currently FAILS because the return value IS [].
        After fix: NotImplementedError is raised.
        """
        parser = CheatsheetParser()
        try:
            result = parser.find_undervalued_players()
            assert result != [], (
                "CheatsheetParser.find_undervalued_players() returned [] without raising "
                "NotImplementedError. Stub methods must raise (Issue #168)."
            )
        except NotImplementedError:
            pass  # Correct post-fix behaviour
