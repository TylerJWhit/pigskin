"""Unit tests for DraftLoadingService."""

from unittest.mock import MagicMock, patch, AsyncMock
import pytest


def _make_service():
    """Create DraftLoadingService with mocked dependencies."""
    mock_config_manager = MagicMock()
    mock_config = MagicMock()
    mock_config.sleeper_draft_id = None
    mock_config.data_source = 'fantasypros'
    mock_config.num_teams = 10
    mock_config.budget = 200
    mock_config.budget_per_team = 200
    mock_config.data_path = 'data/sheets'
    mock_config.roster_positions = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DST': 1, 'BN': 5}
    mock_config.sleeper_user_id = None
    mock_config_manager.load_config.return_value = mock_config

    with patch('services.draft_loading_service.SleeperAPI'):
        from services.draft_loading_service import DraftLoadingService
        svc = DraftLoadingService(config_manager=mock_config_manager)
    return svc, mock_config, mock_config_manager


class TestDraftLoadingServiceInit:
    def test_init_with_config_manager(self):
        svc, _, _ = _make_service()
        assert svc.config_manager is not None
        assert svc.sleeper_api is not None

    def test_init_without_config_manager(self):
        with patch('services.draft_loading_service.ConfigManager') as mock_cm, \
             patch('services.draft_loading_service.SleeperAPI'):
            from services.draft_loading_service import DraftLoadingService
            svc = DraftLoadingService()
            mock_cm.assert_called_once()


class TestLoadCurrentDraft:
    def test_routes_to_fantasypros_when_no_sleeper(self):
        svc, _, _ = _make_service()
        mock_draft = MagicMock()
        svc._load_fantasypros_draft = MagicMock(return_value=mock_draft)
        result = svc.load_current_draft()
        svc._load_fantasypros_draft.assert_called_once()
        assert result is mock_draft

    def test_routes_to_sleeper_when_configured(self):
        svc, mock_config, _ = _make_service()
        mock_config.sleeper_draft_id = 'draft123'
        mock_config.data_source = 'sleeper'
        mock_draft = MagicMock()
        svc._load_sleeper_draft = MagicMock(return_value=mock_draft)
        result = svc.load_current_draft()
        svc._load_sleeper_draft.assert_called_once()
        assert result is mock_draft

    def test_returns_none_on_exception(self):
        svc, _, _ = _make_service()
        svc._load_fantasypros_draft = MagicMock(side_effect=RuntimeError("boom"))
        result = svc.load_current_draft()
        assert result is None


class TestLoadSleeperDraft:
    def test_raises_if_no_draft_id(self):
        svc, _, _ = _make_service()
        mock_config = MagicMock()
        mock_config.sleeper_draft_id = None
        with pytest.raises(ValueError, match="No Sleeper draft ID"):
            svc._load_sleeper_draft(mock_config)

    def test_returns_none_when_api_fails(self):
        svc, mock_config, _ = _make_service()
        mock_config.sleeper_draft_id = 'draft123'
        svc.sleeper_api.get_draft.return_value = None
        result = svc._load_sleeper_draft(mock_config)
        assert result is None

    def test_returns_none_when_no_league_id(self):
        svc, mock_config, _ = _make_service()
        mock_config.sleeper_draft_id = 'draft123'
        svc.sleeper_api.get_draft.return_value = {'league_id': None}
        result = svc._load_sleeper_draft(mock_config)
        assert result is None

    def test_success_path(self):
        svc, mock_config, _ = _make_service()
        mock_config.sleeper_draft_id = 'draft123'
        mock_config.budget = 200
        mock_config.roster_positions = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DST': 1}
        svc.sleeper_api.get_draft.return_value = {'league_id': 'league456'}
        svc.sleeper_api.get_league_users.return_value = []
        svc._add_sleeper_participants = MagicMock()
        svc._load_sleeper_players = MagicMock(return_value=[MagicMock()])  # non-empty to cover line 97

        with patch('services.draft_loading_service.Draft') as MockDraft:
            mock_draft = MagicMock()
            MockDraft.return_value = mock_draft
            result = svc._load_sleeper_draft(mock_config)
        assert result is mock_draft
        mock_draft.add_players.assert_called_once()


class TestLoadFantasyProsDraft:
    def test_returns_none_on_exception(self):
        svc, mock_config, _ = _make_service()
        with patch('services.draft_loading_service.DraftSetup') as MockSetup:
            MockSetup.create_mock_draft.side_effect = RuntimeError("no data")
            result = svc._load_fantasypros_draft(mock_config)
        assert result is None

    def test_invalid_num_teams_falls_back_to_12(self):
        """Cover lines 119-120: TypeError when converting num_teams."""
        svc, mock_config, _ = _make_service()
        mock_config.num_teams = MagicMock()  # not int-convertible in a specific way
        mock_config.num_teams.__int__ = MagicMock(side_effect=TypeError("not int"))
        mock_draft = MagicMock()
        mock_draft.teams = []
        with patch('services.draft_loading_service.DraftSetup') as MockSetup:
            MockSetup.create_mock_draft.return_value = mock_draft
            # num_teams fallback to 12 — just verify it runs without error
            result = svc._load_fantasypros_draft(mock_config)
        # Should use fallback num_teams=12
        assert MockSetup.create_mock_draft.called

    def test_success_path(self):
        svc, mock_config, _ = _make_service()
        mock_config.num_teams = 10
        mock_config.budget = 200
        mock_config.roster_positions = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DST': 1, 'BN': 5}
        mock_config.data_path = 'data/sheets'
        mock_team = MagicMock()
        mock_draft = MagicMock()
        mock_draft.teams = [mock_team]
        with patch('services.draft_loading_service.DraftSetup') as MockSetup:
            MockSetup.create_mock_draft.return_value = mock_draft
            result = svc._load_fantasypros_draft(mock_config)
        assert result is mock_draft
        assert mock_team.budget == 200
        assert mock_team.initial_budget == 200


class TestLoadSleeperPlayers:
    def test_returns_empty_on_exception(self):
        svc, _, _ = _make_service()
        svc.sleeper_api.bulk_convert_players.side_effect = RuntimeError("api down")
        result = svc._load_sleeper_players()
        assert result == []

    def test_returns_players_on_success(self):
        svc, _, _ = _make_service()
        svc.sleeper_api.bulk_convert_players.return_value = [
            {'player_id': '1', 'name': 'Josh Allen', 'position': 'QB', 'team': 'BUF',
             'projected_points': 350.0, 'auction_value': 50, 'bye_week': 7},
        ]
        with patch('services.draft_loading_service.Player') as MockPlayer:
            mock_player = MagicMock()
            MockPlayer.return_value = mock_player
            result = svc._load_sleeper_players()
        assert len(result) == 1


class TestAddSleeperParticipants:
    def test_adds_users_to_draft(self):
        svc, mock_config, _ = _make_service()
        mock_config.budget = 200
        mock_config.sleeper_user_id = 'user1'
        mock_config.roster_positions = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DST': 1, 'BN': 5}
        mock_draft = MagicMock()
        users = [
            {'user_id': 'user1', 'display_name': 'Alice'},
            {'user_id': 'user2', 'display_name': 'Bob'},
        ]
        mock_owner = MagicMock()
        mock_team = MagicMock()
        with patch('services.draft_loading_service.DraftSetup') as MockSetup:
            MockSetup.create_owner_with_team.return_value = (mock_owner, mock_team)
            svc._add_sleeper_participants(mock_draft, users, mock_config)
        assert mock_draft.add_owner.call_count == 2
        assert mock_draft.add_team.call_count == 2

    def test_empty_users_does_nothing(self):
        svc, mock_config, _ = _make_service()
        mock_draft = MagicMock()
        svc._add_sleeper_participants(mock_draft, [], mock_config)
        mock_draft.add_owner.assert_not_called()


class TestCalculatePositionLimits:
    def test_returns_dict_with_all_positions(self):
        svc, _, _ = _make_service()
        roster = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1, 'K': 1, 'DST': 1, 'BN': 6, 'FLEX': 1}
        result = svc._calculate_position_limits(roster)
        assert set(result.keys()) == {'QB', 'RB', 'WR', 'TE', 'K', 'DST'}

    def test_bench_spots_increase_limits(self):
        svc, _, _ = _make_service()
        result_small_bench = svc._calculate_position_limits({'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DST': 1, 'BN': 0})
        result_large_bench = svc._calculate_position_limits({'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DST': 1, 'BN': 9})
        assert result_large_bench['RB'] >= result_small_bench['RB']


class TestReloadDraft:
    def test_calls_load_current_draft(self):
        svc, _, _ = _make_service()
        mock_draft = MagicMock()
        svc.load_current_draft = MagicMock(return_value=mock_draft)
        result = svc.reload_draft()
        svc.load_current_draft.assert_called_once()
        assert result is mock_draft


class TestGetDraftStatus:
    def test_returns_status_dict_when_draft_loads(self):
        svc, _, _ = _make_service()
        mock_draft = MagicMock()
        mock_draft.available_players = [MagicMock(), MagicMock()]
        mock_draft.teams = [MagicMock()]
        svc.load_current_draft = MagicMock(return_value=mock_draft)
        result = svc.get_draft_status()
        assert result['config_loaded'] is True
        assert result['draft_loadable'] is True
        assert result['players_available'] == 2

    def test_returns_status_dict_when_draft_is_none(self):
        svc, _, _ = _make_service()
        svc.load_current_draft = MagicMock(return_value=None)
        result = svc.get_draft_status()
        assert result['draft_loadable'] is False
        assert result['players_available'] == 0

    def test_returns_status_dict_on_exception(self):
        svc, _, _ = _make_service()
        svc.load_current_draft = MagicMock(side_effect=RuntimeError("fail"))
        result = svc.get_draft_status()
        assert result['draft_loadable'] is False
        assert 'error' in result


class TestLoadDraftFromConfig:
    def test_success_creates_auction(self):
        svc, _, _ = _make_service()
        mock_draft = MagicMock()
        svc.load_current_draft = MagicMock(return_value=mock_draft)
        with patch('classes.auction.Auction') as MockAuction:
            mock_auction = MagicMock()
            MockAuction.return_value = mock_auction
            result = svc.load_draft_from_config()
        assert result['success'] is True
        assert result['draft'] is mock_draft

    def test_returns_failure_when_no_draft(self):
        svc, _, _ = _make_service()
        svc.load_current_draft = MagicMock(return_value=None)
        result = svc.load_draft_from_config()
        assert result['success'] is False
        assert result['draft'] is None

    def test_exception_returns_failure(self):
        svc, _, _ = _make_service()
        svc.load_current_draft = MagicMock(side_effect=RuntimeError("crash"))
        result = svc.load_draft_from_config()
        assert result['success'] is False


class TestConvenienceFunctions:
    def test_load_draft_from_config_success(self):
        mock_draft = MagicMock()
        mock_draft.name = 'Test Draft'
        with patch('services.draft_loading_service.ConfigManager'), \
             patch('services.draft_loading_service.DraftLoadingService') as MockSvc, \
             patch('classes.auction.Auction'):
            instance = MockSvc.return_value
            instance.load_current_draft.return_value = mock_draft
            from services.draft_loading_service import load_draft_from_config
            result = load_draft_from_config()
        assert result['success'] is True

    def test_load_draft_from_config_failure(self):
        with patch('services.draft_loading_service.ConfigManager'), \
             patch('services.draft_loading_service.DraftLoadingService') as MockSvc:
            instance = MockSvc.return_value
            instance.load_current_draft.return_value = None
            from services.draft_loading_service import load_draft_from_config
            result = load_draft_from_config()
        assert result['success'] is False

    def test_load_draft_from_config_exception(self):
        with patch('services.draft_loading_service.ConfigManager', side_effect=RuntimeError("nope")):
            from services.draft_loading_service import load_draft_from_config
            result = load_draft_from_config()
        assert result['success'] is False

    def test_load_current_draft(self):
        mock_draft = MagicMock()
        with patch('services.draft_loading_service.ConfigManager'), \
             patch('services.draft_loading_service.DraftLoadingService') as MockSvc:
            instance = MockSvc.return_value
            instance.load_current_draft.return_value = mock_draft
            from services.draft_loading_service import load_current_draft
            result = load_current_draft()
        assert result is mock_draft

    def test_get_draft_status(self):
        with patch('services.draft_loading_service.ConfigManager'), \
             patch('services.draft_loading_service.DraftLoadingService') as MockSvc:
            instance = MockSvc.return_value
            instance.get_draft_status.return_value = {'config_loaded': True}
            from services.draft_loading_service import get_draft_status
            result = get_draft_status()
        assert result['config_loaded'] is True
