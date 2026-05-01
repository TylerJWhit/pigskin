"""Unit tests for TournamentService."""

from unittest.mock import MagicMock, patch
import pytest


def _make_service():
    mock_config_manager = MagicMock()
    mock_config = MagicMock()
    mock_config.budget = 200
    mock_config.data_source = 'fantasypros'
    mock_config.data_path = 'data/sheets'
    mock_config.min_projected_points = 0
    mock_config.roster_positions = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DST': 1, 'BN': 5}
    mock_config_manager.load_config.return_value = mock_config
    with patch('services.tournament_service.ConfigManager', return_value=mock_config_manager):
        from services.tournament_service import TournamentService
        svc = TournamentService(config_manager=mock_config_manager)
    return svc, mock_config, mock_config_manager


class TestTournamentServiceInit:
    def test_init_with_config_manager(self):
        svc, _, _ = _make_service()
        assert svc.config_manager is not None
        assert svc.current_tournament is None

    def test_init_without_config_manager(self):
        with patch('services.tournament_service.ConfigManager') as MockCM:
            from services.tournament_service import TournamentService
            svc = TournamentService()
        MockCM.assert_called_once()


class TestRunStrategyTournament:
    def test_invalid_strategy_returns_error(self):
        svc, _, _ = _make_service()
        result = svc.run_strategy_tournament(strategies_to_test=['not_real_xyz'])
        assert result['success'] is False
        assert 'Invalid strategies' in result['error']

    def test_no_players_returns_error(self):
        svc, _, _ = _make_service()
        svc._load_players_for_tournament = MagicMock(return_value=[])
        with patch('services.tournament_service.Tournament'):
            result = svc.run_strategy_tournament(strategies_to_test=['value'])
        assert result['success'] is False
        assert 'player data' in result['error']

    def test_success_path(self):
        svc, mock_config, _ = _make_service()
        mock_tournament = MagicMock()
        mock_tournament.run_tournament.return_value = {
            'completed_simulations': 5,
            'results': {}
        }
        svc._load_players_for_tournament = MagicMock(return_value=[MagicMock()])
        svc._save_tournament_results = MagicMock()
        svc._analyze_tournament_results = MagicMock(return_value={'insights': []})
        with patch('services.tournament_service.Tournament', return_value=mock_tournament):
            result = svc.run_strategy_tournament(strategies_to_test=['value'], num_simulations=2)
        assert result['success'] is True

    def test_success_no_save(self):
        svc, _, _ = _make_service()
        mock_tournament = MagicMock()
        mock_tournament.run_tournament.return_value = {'results': {}}
        svc._load_players_for_tournament = MagicMock(return_value=[MagicMock()])
        svc._analyze_tournament_results = MagicMock(return_value={})
        with patch('services.tournament_service.Tournament', return_value=mock_tournament):
            result = svc.run_strategy_tournament(
                strategies_to_test=['value'], num_simulations=1, save_results=False
            )
        assert result['success'] is True

    def test_uses_all_strategies_when_none(self):
        svc, _, _ = _make_service()
        mock_tournament = MagicMock()
        mock_tournament.run_tournament.return_value = {'results': {}}
        svc._load_players_for_tournament = MagicMock(return_value=[MagicMock()])
        svc._save_tournament_results = MagicMock()
        svc._analyze_tournament_results = MagicMock(return_value={})
        with patch('services.tournament_service.Tournament', return_value=mock_tournament):
            result = svc.run_strategy_tournament(strategies_to_test=None, num_simulations=1)
        assert result['success'] is True

    def test_exception_returns_failure(self):
        svc, _, _ = _make_service()
        svc.config_manager.load_config.side_effect = RuntimeError("crash")
        result = svc.run_strategy_tournament()
        assert result['success'] is False
        assert 'Tournament failed' in result['error']


class TestRunCustomTournament:
    def test_no_players_returns_error(self):
        svc, _, _ = _make_service()
        svc._load_players_for_tournament = MagicMock(return_value=[])
        with patch('services.tournament_service.Tournament'):
            result = svc.run_custom_tournament({'strategies': []})
        assert result['success'] is False

    def test_success_path(self):
        svc, _, _ = _make_service()
        mock_tournament = MagicMock()
        mock_tournament.run_tournament.return_value = {'results': {}}
        svc._load_players_for_tournament = MagicMock(return_value=[MagicMock()])
        svc._save_tournament_results = MagicMock()
        svc._analyze_tournament_results = MagicMock(return_value={})
        config = {
            'name': 'Test',
            'num_simulations': 1,
            'strategies': [{'type': 'value', 'name': 'Value', 'num_teams': 1, 'parameters': {}}],
        }
        with patch('services.tournament_service.Tournament', return_value=mock_tournament):
            result = svc.run_custom_tournament(config)
        assert result['success'] is True

    def test_skips_invalid_strategy_type(self):
        svc, _, _ = _make_service()
        mock_tournament = MagicMock()
        mock_tournament.run_tournament.return_value = {'results': {}}
        svc._load_players_for_tournament = MagicMock(return_value=[MagicMock()])
        svc._save_tournament_results = MagicMock()
        svc._analyze_tournament_results = MagicMock(return_value={})
        config = {
            'strategies': [{'type': 'not_real_xyz', 'name': 'Fake'}],
        }
        with patch('services.tournament_service.Tournament', return_value=mock_tournament):
            result = svc.run_custom_tournament(config)
        # Should succeed but skip the invalid strategy
        assert result['success'] is True
        mock_tournament.add_strategy_config.assert_not_called()

    def test_exception_returns_failure(self):
        svc, _, _ = _make_service()
        svc.config_manager.load_config.side_effect = ValueError("bad config")
        result = svc.run_custom_tournament({})
        assert result['success'] is False


class TestFindOptimalStrategy:
    def test_success_path(self):
        svc, _, _ = _make_service()
        mock_ranking = [('value', {'results': {'win_rate': 0.5, 'avg_points': 150.0}, 'composite_score': 0.8})]
        mock_tournament = MagicMock()
        mock_tournament.get_strategy_rankings.return_value = mock_ranking
        svc.run_custom_tournament = MagicMock(return_value={'success': True, 'results': {}})
        svc.current_tournament = mock_tournament
        result = svc.find_optimal_strategy()
        assert result['success'] is True
        assert result['optimal_strategy'] == 'value'

    def test_no_rankings_returns_failure(self):
        svc, _, _ = _make_service()
        mock_tournament = MagicMock()
        mock_tournament.get_strategy_rankings.return_value = []
        svc.run_custom_tournament = MagicMock(return_value={'success': True, 'results': {}})
        svc.current_tournament = mock_tournament
        result = svc.find_optimal_strategy()
        assert result['success'] is False

    def test_custom_tournament_failure_propagates(self):
        svc, _, _ = _make_service()
        svc.run_custom_tournament = MagicMock(return_value={'success': False, 'error': 'fail'})
        result = svc.find_optimal_strategy()
        assert result['success'] is False

    def test_exception_returns_failure(self):
        svc, _, _ = _make_service()
        svc.run_custom_tournament = MagicMock(side_effect=RuntimeError("boom"))
        result = svc.find_optimal_strategy()
        assert result['success'] is False


class TestGetTournamentProgress:
    def test_no_tournament(self):
        svc, _, _ = _make_service()
        svc.current_tournament = None
        result = svc.get_tournament_progress()
        assert result['active'] is False

    def test_with_tournament(self):
        svc, _, _ = _make_service()
        svc.current_tournament = MagicMock()
        svc.current_tournament.is_running = True
        svc.current_tournament.progress = 50
        svc.current_tournament.num_simulations = 100
        svc.current_tournament.completed_drafts = [1, 2, 3]
        svc.current_tournament.name = 'Test'
        result = svc.get_tournament_progress()
        assert result['active'] is True
        assert result['completed_simulations'] == 3


class TestStopTournament:
    def test_no_tournament(self):
        svc, _, _ = _make_service()
        svc.current_tournament = None
        result = svc.stop_tournament()
        assert result['success'] is False

    def test_stops_running_tournament(self):
        svc, _, _ = _make_service()
        svc.current_tournament = MagicMock()
        svc.current_tournament.completed_drafts = [1, 2]
        result = svc.stop_tournament()
        assert result['success'] is True
        assert svc.current_tournament.is_running is False


class TestLoadPlayersForTournament:
    def test_fantasypros_source(self):
        svc, mock_config, _ = _make_service()
        mock_config.data_source = 'fantasypros'
        mock_players = [MagicMock()]
        with patch('services.tournament_service.load_fantasypros_players', return_value=mock_players):
            result = svc._load_players_for_tournament(mock_config)
        assert result is mock_players

    def test_sleeper_source_returns_empty(self):
        svc, mock_config, _ = _make_service()
        mock_config.data_source = 'sleeper'
        result = svc._load_players_for_tournament(mock_config)
        assert result == []

    def test_unknown_source_returns_empty(self):
        svc, mock_config, _ = _make_service()
        mock_config.data_source = 'unknown'
        result = svc._load_players_for_tournament(mock_config)
        assert result == []

    def test_exception_returns_empty(self):
        svc, mock_config, _ = _make_service()
        mock_config.data_source = 'fantasypros'
        with patch('services.tournament_service.load_fantasypros_players', side_effect=RuntimeError("fail")):
            result = svc._load_players_for_tournament(mock_config)
        assert result == []


class TestGenerateStrategyVariants:
    def test_base_variants_created(self):
        svc, _, _ = _make_service()
        variants = svc._generate_strategy_variants(None, None, None)
        assert len(variants) > 0
        types = [v['type'] for v in variants]
        assert 'value' in types

    def test_risk_tolerance_adds_variants(self):
        svc, _, _ = _make_service()
        variants_no_risk = svc._generate_strategy_variants(None, None, None)
        variants_with_risk = svc._generate_strategy_variants(None, None, 0.5)
        assert len(variants_with_risk) > len(variants_no_risk)

    def test_position_priorities_adds_variant(self):
        svc, _, _ = _make_service()
        variants_no_prio = svc._generate_strategy_variants(None, None, None)
        variants_with_prio = svc._generate_strategy_variants(None, ['RB', 'WR'], None)
        assert len(variants_with_prio) > len(variants_no_prio)


class TestAnalyzeTournamentResults:
    def test_no_tournament_returns_empty(self):
        svc, _, _ = _make_service()
        svc.current_tournament = None
        result = svc._analyze_tournament_results({})
        assert result == {}

    def test_with_rankings(self):
        svc, _, _ = _make_service()
        mock_tournament = MagicMock()
        mock_tournament.get_strategy_rankings.return_value = [
            ('value', {'results': {'win_rate': 0.6, 'avg_points': 150, 'points_std': 30}}),
            ('aggressive', {'results': {'win_rate': 0.4, 'avg_points': 130, 'points_std': 50}}),
        ]
        svc.current_tournament = mock_tournament
        result = svc._analyze_tournament_results({'results': {'value': {'win_rate': 0.6}, 'aggressive': {'win_rate': 0.4}}})
        assert result['best_strategy']['name'] == 'value'
        assert result['worst_strategy']['name'] == 'aggressive'

    def test_empty_rankings(self):
        svc, _, _ = _make_service()
        mock_tournament = MagicMock()
        mock_tournament.get_strategy_rankings.return_value = []
        svc.current_tournament = mock_tournament
        result = svc._analyze_tournament_results({'results': {}})
        assert result['best_strategy'] is None


class TestGenerateInsights:
    def test_generates_win_rate_insight(self):
        svc, _, _ = _make_service()
        rankings = [
            ('value', {'results': {'win_rate': 0.5, 'avg_points': 150}}),
            ('aggressive', {'results': {'win_rate': 0.1, 'avg_points': 100}}),
        ]
        strategy_results = {'value': {'win_rate': 0.5}, 'aggressive': {'win_rate': 0.05}}
        insights = svc._generate_insights(rankings, strategy_results)
        assert len(insights) > 0

    def test_single_ranking_no_diff_insight(self):
        svc, _, _ = _make_service()
        rankings = [('value', {'results': {'win_rate': 0.5, 'avg_points': 150}})]
        insights = svc._generate_insights(rankings, {})
        # len < 2 so no win rate diff insight
        assert isinstance(insights, list)


class TestGenerateStrategyRecommendation:
    def test_consistent_strategy(self):
        svc, _, _ = _make_service()
        data = {'results': {'win_rate': 0.5, 'avg_points': 150, 'points_std': 30}}
        rec = svc._generate_strategy_recommendation('value', data)
        assert 'value' in rec
        assert 'consistency' in rec or 'consistent' in rec

    def test_volatile_strategy(self):
        svc, _, _ = _make_service()
        data = {'results': {'win_rate': 0.5, 'avg_points': 150, 'points_std': 120}}
        rec = svc._generate_strategy_recommendation('aggressive', data)
        assert 'volatile' in rec


class TestSaveTournamentResults:
    def test_saves_json_file(self):
        svc, _, _ = _make_service()
        import json
        results = {'success': True, 'results': {}}
        with patch('builtins.open', create=True) as mock_open, \
             patch('os.makedirs'):
            mock_file = MagicMock()
            mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            svc._save_tournament_results(results)
        mock_open.assert_called_once()

    def test_exception_does_not_raise(self):
        svc, _, _ = _make_service()
        with patch('os.makedirs', side_effect=OSError("no perms")):
            svc._save_tournament_results({})  # should not raise


class TestConvenienceFunctions:
    def test_run_strategy_tournament(self):
        with patch('services.tournament_service.ConfigManager'), \
             patch('services.tournament_service.TournamentService') as MockSvc:
            instance = MockSvc.return_value
            instance.run_strategy_tournament.return_value = {'success': True}
            from services.tournament_service import run_strategy_tournament
            result = run_strategy_tournament(['value'], 10)
        assert result['success'] is True

    def test_find_optimal_strategy(self):
        with patch('services.tournament_service.ConfigManager'), \
             patch('services.tournament_service.TournamentService') as MockSvc:
            instance = MockSvc.return_value
            instance.find_optimal_strategy.return_value = {'success': True}
            from services.tournament_service import find_optimal_strategy
            result = find_optimal_strategy(risk_tolerance=0.5)
        assert result['success'] is True
