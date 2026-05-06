"""Unit tests for CLI commands — cheatsheet_parser integration."""

from unittest.mock import MagicMock, AsyncMock, patch


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


# ---------------------------------------------------------------------------
# CommandProcessor targeted coverage tests
# ---------------------------------------------------------------------------

class TestCommandProcessorInit:
    """Cover __init__ (lines 20-23)."""

    def test_init_creates_dependencies(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            cp = CommandProcessor()
            assert cp.config_manager is not None
            assert cp.sleeper_api is not None
            assert cp.sleeper_draft_service is not None


class TestGetBidRecommendationDetailed:
    """Cover lines 25-75: get_bid_recommendation_detailed."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_strong_buy_recommendation(self):
        cp = self._make_cp()
        mock_service = MagicMock()
        mock_service.recommend_bid.return_value = {
            'success': True,
            'bid_difference': 15.0,
            'recommended_bid': 20.0,
            'auction_value': 40.0,
            'player_name': 'Josh Allen',
        }
        with patch('services.bid_recommendation_service.BidRecommendationService', return_value=mock_service):
            result = cp.get_bid_recommendation_detailed('Josh Allen', current_bid=5.0)
        assert result['recommendation_level'] == 'STRONG BUY'
        assert result['value_assessment'] == 'EXCELLENT VALUE'

    def test_buy_recommendation(self):
        cp = self._make_cp()
        mock_service = MagicMock()
        mock_service.recommend_bid.return_value = {
            'success': True,
            'bid_difference': 7.0,
            'recommended_bid': 20.0,
            'auction_value': 26.0,  # 26/20 = 1.3 → GOOD VALUE
        }
        with patch('services.bid_recommendation_service.BidRecommendationService', return_value=mock_service):
            result = cp.get_bid_recommendation_detailed('Patrick Mahomes')
        assert result['recommendation_level'] == 'BUY'
        assert result['value_assessment'] == 'GOOD VALUE'

    def test_weak_buy_recommendation(self):
        cp = self._make_cp()
        mock_service = MagicMock()
        mock_service.recommend_bid.return_value = {
            'success': True,
            'bid_difference': 3.0,
            'recommended_bid': 20.0,
            'auction_value': 21.0,  # 21/20 = 1.05 → FAIR VALUE
        }
        with patch('services.bid_recommendation_service.BidRecommendationService', return_value=mock_service):
            result = cp.get_bid_recommendation_detailed('CMC')
        assert result['recommendation_level'] == 'WEAK BUY'
        assert result['value_assessment'] == 'FAIR VALUE'

    def test_pass_overpriced(self):
        cp = self._make_cp()
        mock_service = MagicMock()
        mock_service.recommend_bid.return_value = {
            'success': True,
            'bid_difference': -5.0,
            'recommended_bid': 10.0,
            'auction_value': 8.0,   # 8/10 = 0.8 → OVERPRICED
        }
        with patch('services.bid_recommendation_service.BidRecommendationService', return_value=mock_service):
            result = cp.get_bid_recommendation_detailed('Backup K')
        assert result['recommendation_level'] == 'PASS'
        assert result['value_assessment'] == 'OVERPRICED'

    def test_failure_returns_error(self):
        cp = self._make_cp()
        mock_service = MagicMock()
        mock_service.recommend_bid.return_value = {
            'success': False,
            'error': 'Player not found',
        }
        with patch('services.bid_recommendation_service.BidRecommendationService', return_value=mock_service):
            result = cp.get_bid_recommendation_detailed('Ghost Player')
        assert result['success'] is False
        assert 'error' in result

    def test_uses_config_sleeper_draft_id(self):
        """Cover the branch where sleeper_draft_id comes from config."""
        cp = self._make_cp()
        mock_config = MagicMock()
        mock_config.sleeper_draft_id = 'config-draft-123'
        cp.config_manager.load_config = MagicMock(return_value=mock_config)

        mock_service = MagicMock()
        mock_service.recommend_bid.return_value = {
            'success': True,
            'bid_difference': 5.0,
            'recommended_bid': 20.0,
            'auction_value': 25.0,
        }
        with patch('services.bid_recommendation_service.BidRecommendationService', return_value=mock_service):
            result = cp.get_bid_recommendation_detailed('Josh Allen')
        mock_service.recommend_bid.assert_called_once()

    def test_exception_in_config_load_is_ignored(self):
        """Cover lines 36-37: exception in config load is silently caught."""
        cp = self._make_cp()
        cp.config_manager.load_config.side_effect = Exception("config error")

        mock_service = MagicMock()
        mock_service.recommend_bid.return_value = {
            'success': True,
            'bid_difference': 5.0,
            'recommended_bid': 20.0,
            'auction_value': 25.0,
        }
        with patch('services.bid_recommendation_service.BidRecommendationService', return_value=mock_service):
            result = cp.get_bid_recommendation_detailed('Josh Allen')
        assert result['success'] is True


class TestMapStrategyNameToKey:
    """Cover lines 798-817: _map_strategy_name_to_key."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_known_names_map_correctly(self):
        cp = self._make_cp()
        assert cp._map_strategy_name_to_key('Value-Based') == 'value'
        assert cp._map_strategy_name_to_key('Aggressive') == 'aggressive'
        assert cp._map_strategy_name_to_key('Conservative') == 'conservative'
        assert cp._map_strategy_name_to_key('Balanced') == 'balanced'
        assert cp._map_strategy_name_to_key('Elite Hybrid') == 'elite_hybrid'
        assert cp._map_strategy_name_to_key('Inflation VOR') == 'inflation_vor'

    def test_unknown_name_lowercased(self):
        cp = self._make_cp()
        result = cp._map_strategy_name_to_key('My Custom Strategy')
        assert result == 'my_custom_strategy'


class TestCreateTournamentPools:
    """Cover lines 819-858: _create_tournament_pools."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_few_strategies_creates_one_pool_with_duplicates(self):
        cp = self._make_cp()
        strategies = ['aggressive', 'balanced', 'conservative']
        pools = cp._create_tournament_pools(strategies, teams_per_draft=10)
        assert len(pools) == 1
        assert len(pools[0]) == 10

    def test_many_strategies_creates_multiple_pools(self):
        cp = self._make_cp()
        strategies = [f's{i}' for i in range(20)]
        pools = cp._create_tournament_pools(strategies, teams_per_draft=10)
        assert len(pools) == 2
        for pool in pools:
            assert len(pool) == 10

    def test_strategies_with_remainder(self):
        cp = self._make_cp()
        strategies = [f's{i}' for i in range(13)]
        pools = cp._create_tournament_pools(strategies, teams_per_draft=10)
        # 13 strategies: first pool has 10, remaining 3 go to a second pool
        assert len(pools) >= 1

    def test_exact_match_strategies_and_teams(self):
        cp = self._make_cp()
        strategies = [f's{i}' for i in range(10)]
        pools = cp._create_tournament_pools(strategies, teams_per_draft=10)
        assert len(pools) == 1
        assert len(pools[0]) == 10

    def test_remainder_merged_into_last_pool(self):
        """Cover line 848: remaining strategies fit in last pool."""
        cp = self._make_cp()
        # 12 strategies, teams_per_draft=10: first pool=10, remainder=2
        # len(last_pool=10) + len(remaining=2) = 12 <= 10+2=12 → merge
        strategies = [f's{i}' for i in range(12)]
        pools = cp._create_tournament_pools(strategies, teams_per_draft=10)
        # All 12 fit in 1 expanded pool
        assert len(pools) == 1
        assert len(pools[0]) == 12

    def test_small_strategies_creates_pool_with_duplicates(self):
        """Cover lines 855-856: remaining strategies but pools is empty → create new pool."""
        cp = self._make_cp()
        # 2 strategies with teams_per_draft=10: 2 < 10 so all become remaining
        # This hits the else branch at line 853 (pools is empty)
        strategies = ['balanced', 'aggressive']
        pools = cp._create_tournament_pools(strategies, teams_per_draft=10)
        assert len(pools) == 1
        assert len(pools[0]) == 10  # filled with duplicates


class TestCreateSinglePoolWithDuplicates:
    """Cover lines 860-872: _create_single_pool_with_duplicates."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_fills_to_teams_per_draft(self):
        cp = self._make_cp()
        pool = cp._create_single_pool_with_duplicates(['a', 'b'], 5)
        assert len(pool) == 5
        assert 'a' in pool
        assert 'b' in pool


class TestSleeperWrapperMethods:
    """Cover lines 1646-1697: get_sleeper_draft_status, display_sleeper_draft,
    display_sleeper_league_rosters, list_sleeper_leagues."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_get_sleeper_draft_status_success(self):
        cp = self._make_cp()
        expected = {'success': True, 'draft_id': 'd1'}
        cp.sleeper_draft_service.get_current_draft_status = AsyncMock(return_value=expected)
        with patch('cli.commands.asyncio') as mock_aio:
            mock_aio.run.return_value = expected
            result = cp.get_sleeper_draft_status('testuser')
        assert result == expected

    def test_get_sleeper_draft_status_exception(self):
        cp = self._make_cp()
        with patch('cli.commands.asyncio') as mock_aio:
            mock_aio.run.side_effect = RuntimeError("network error")
            result = cp.get_sleeper_draft_status('testuser')
        assert result['success'] is False
        assert 'error' in result

    def test_display_sleeper_draft_success(self):
        cp = self._make_cp()
        expected = {'success': True, 'draft': {}}
        with patch('cli.commands.asyncio') as mock_aio:
            mock_aio.run.return_value = expected
            result = cp.display_sleeper_draft('draft123')
        assert result == expected

    def test_display_sleeper_draft_exception(self):
        cp = self._make_cp()
        with patch('cli.commands.asyncio') as mock_aio:
            mock_aio.run.side_effect = ValueError("bad id")
            result = cp.display_sleeper_draft('bad')
        assert result['success'] is False

    def test_display_sleeper_league_rosters_success(self):
        cp = self._make_cp()
        expected = {'success': True}
        with patch('cli.commands.asyncio') as mock_aio:
            mock_aio.run.return_value = expected
            result = cp.display_sleeper_league_rosters('league1')
        assert result == expected

    def test_display_sleeper_league_rosters_exception(self):
        cp = self._make_cp()
        with patch('cli.commands.asyncio') as mock_aio:
            mock_aio.run.side_effect = ConnectionError("down")
            result = cp.display_sleeper_league_rosters('league1')
        assert result['success'] is False

    def test_list_sleeper_leagues_success(self):
        cp = self._make_cp()
        expected = {'success': True, 'leagues': []}
        with patch('cli.commands.asyncio') as mock_aio:
            mock_aio.run.return_value = expected
            result = cp.list_sleeper_leagues('username')
        assert result == expected

    def test_list_sleeper_leagues_exception(self):
        cp = self._make_cp()
        with patch('cli.commands.asyncio') as mock_aio:
            mock_aio.run.side_effect = Exception("fail")
            result = cp.list_sleeper_leagues('username')
        assert result['success'] is False


class TestFormatTournamentResultsForDisplay:
    """Cover lines 1698-1762: _format_tournament_results_for_display."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_empty_results(self):
        cp = self._make_cp()
        result = cp._format_tournament_results_for_display([], ['aggressive', 'balanced'])
        assert 'aggressive' in result
        assert 'balanced' in result
        assert result['aggressive']['wins'] == 0

    def test_counts_wins_correctly(self):
        cp = self._make_cp()
        all_results = [
            {
                'draft_data': {
                    'teams': [
                        {'strategy': 'aggressive', 'strategy_display_name': 'Aggressive', 'projected_points': 150, 'total_spent': 180},
                        {'strategy': 'balanced', 'strategy_display_name': 'Balanced', 'projected_points': 130, 'total_spent': 170},
                    ]
                }
            }
        ]
        result = cp._format_tournament_results_for_display(all_results, ['aggressive', 'balanced'])
        assert result['aggressive']['wins'] == 1
        assert result['balanced']['wins'] == 0
        assert result['aggressive']['simulations'] == 1

    def test_calculates_averages(self):
        cp = self._make_cp()
        all_results = [
            {'draft_data': {'teams': [
                {'strategy_display_name': 'Aggressive', 'projected_points': 200, 'total_spent': 180},
            ]}},
            {'draft_data': {'teams': [
                {'strategy_display_name': 'Aggressive', 'projected_points': 100, 'total_spent': 160},
            ]}},
        ]
        result = cp._format_tournament_results_for_display(all_results, ['aggressive'])
        assert result['aggressive']['avg_points'] == 150.0
        assert result['aggressive']['avg_spent'] == 170.0

    def test_skips_results_without_teams(self):
        cp = self._make_cp()
        all_results = [{'draft_data': {}}]  # no 'teams' key
        result = cp._format_tournament_results_for_display(all_results, ['aggressive'])
        assert result['aggressive']['wins'] == 0


class TestRunEnhancedMockDraftErrorPaths:
    """Cover lines 79-163: run_enhanced_mock_draft error paths."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_invalid_single_strategy_returns_error(self):
        cp = self._make_cp()
        result = cp.run_enhanced_mock_draft('not_a_real_strategy_xyz')
        assert result['success'] is False
        assert 'Invalid strategy' in result['error']

    def test_invalid_list_strategy_returns_error(self):
        cp = self._make_cp()
        result = cp.run_enhanced_mock_draft(['not_real_xyz', 'also_fake'])
        assert result['success'] is False
        assert 'Invalid strategies' in result['error']

    def test_exception_in_load_returns_error(self):
        cp = self._make_cp()
        cp.config_manager.load_config.side_effect = RuntimeError("config load fail")
        result = cp.run_enhanced_mock_draft('value')
        assert result['success'] is False
        assert 'Mock draft failed' in result['error']


class TestTestSleeperConnectivity:
    """Cover lines 978-1070: test_sleeper_connectivity."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_all_pass(self):
        cp = self._make_cp()
        mock_players = {
            'abc': {'full_name': 'Josh Allen', 'position': 'QB', 'team': 'BUF'}
        }
        cp.sleeper_api.get_all_players.return_value = mock_players
        result = cp.test_sleeper_connectivity()
        assert result['success'] is True
        assert result['overall_status'] in ('HEALTHY', 'DEGRADED')

    def test_api_returns_empty(self):
        cp = self._make_cp()
        cp.sleeper_api.get_all_players.return_value = {}
        result = cp.test_sleeper_connectivity()
        # Still runs, returns some status
        assert 'success' in result
        assert 'tests' in result

    def test_api_raises_exception(self):
        cp = self._make_cp()
        cp.sleeper_api.get_all_players.side_effect = ConnectionError("down")
        result = cp.test_sleeper_connectivity()
        assert 'success' in result
        # Should have FAIL test entries
        fail_tests = [t for t in result['tests'] if t['status'] == 'FAIL']
        assert len(fail_tests) > 0

    def test_missing_fields_in_player(self):
        cp = self._make_cp()
        # Player missing required fields
        cp.sleeper_api.get_all_players.return_value = {'p1': {'name': 'Joe'}}
        result = cp.test_sleeper_connectivity()
        assert 'tests' in result
        warn_or_fail = [t for t in result['tests'] if t['status'] in ('WARN', 'FAIL')]
        assert len(warn_or_fail) > 0


class TestRunElaborateTournamentMethods:
    """Cover lines 164-186, 598-600: run_elimination_tournament + run_comprehensive_tournament."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_run_comprehensive_tournament_delegates(self):
        cp = self._make_cp()
        cp._run_elimination_rounds = MagicMock(return_value={
            'success': True,
            'tournament_winner': 'aggressive',
            'total_rounds': 2,
        })
        result = cp.run_comprehensive_tournament(num_rounds=1)
        cp._run_elimination_rounds.assert_called_once()
        assert result['success'] is True

    def test_run_elimination_tournament_calls_run_elimination_rounds(self):
        cp = self._make_cp()
        cp._run_elimination_rounds = MagicMock(return_value={
            'success': True,
            'tournament_winner': 'value',
            'total_rounds': 1,
        })
        result = cp.run_elimination_tournament(rounds_per_group=1, teams_per_draft=5)
        cp._run_elimination_rounds.assert_called_once()
        assert result['success'] is True


class TestRunElimRoundsShortCircuit:
    """Cover lines 187-269: _run_elimination_rounds single-strategy short-circuit."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_single_strategy_immediately_returns(self):
        cp = self._make_cp()
        result = cp._run_elimination_rounds(['aggressive'], rounds_per_group=1, teams_per_draft=5, verbose=False)
        # Single strategy — while loop never runs, immediate champion
        assert result['success'] is True
        assert result['tournament_winner'] == 'aggressive'


class TestAnalyzeTournamentPerformance:
    """Cover lines 1557-1611: _analyze_tournament_performance + _generate_strategy_recommendations."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_analyze_empty_rankings(self):
        cp = self._make_cp()
        result = cp._analyze_tournament_performance([])
        assert isinstance(result, dict)

    def test_analyze_with_rankings(self):
        cp = self._make_cp()
        rankings = [
            {'strategy': 'aggressive', 'avg_points': 150.0, 'win_rate': 0.6, 'avg_spent': 200, 'avg_value_efficiency': 1.2, 'efficiency': 0.75, 'wins': 6, 'simulations': 10},
            {'strategy': 'balanced', 'avg_points': 140.0, 'win_rate': 0.4, 'avg_spent': 190, 'avg_value_efficiency': 1.1, 'efficiency': 0.70, 'wins': 4, 'simulations': 10},
        ]
        result = cp._analyze_tournament_performance(rankings)
        assert isinstance(result, dict)

    def test_generate_strategy_recommendations_empty(self):
        cp = self._make_cp()
        result = cp._generate_strategy_recommendations([])
        assert isinstance(result, dict)

    def test_generate_strategy_recommendations_with_data(self):
        cp = self._make_cp()
        rankings = [
            {'strategy': 'aggressive', 'avg_points': 150.0, 'win_rate': 0.6, 'avg_spent': 200, 'avg_value_efficiency': 1.2, 'efficiency': 0.75, 'wins': 6, 'simulations': 10},
            {'strategy': 'balanced', 'avg_points': 140.0, 'win_rate': 0.4, 'avg_spent': 190, 'avg_value_efficiency': 1.0, 'efficiency': 0.70, 'wins': 4, 'simulations': 10},
        ]
        result = cp._generate_strategy_recommendations(rankings)
        assert isinstance(result, dict)


class TestCreateTestDraft:
    """Cover lines 1613-1644: _create_test_draft."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_exception_returns_none(self):
        cp = self._make_cp()
        cp.config_manager.load_config.side_effect = RuntimeError("boom")
        result = cp._create_test_draft(10)
        assert result is None


class TestRunEnhancedMockDraftSuccess:
    """Cover the success path of run_enhanced_mock_draft (lines 101-147)."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_single_strategy_success_path(self):
        """Cover run_enhanced_mock_draft with single valid strategy (lines 101-147)."""
        cp = self._make_cp()

        mock_config = MagicMock()
        mock_config.data_path = "/fake"
        cp.config_manager.load_config.return_value = mock_config

        mock_player = MagicMock()
        mock_player.projected_points = 300.0

        mock_team = MagicMock()
        mock_team.team_name = "Team 1"
        mock_team.strategy.name = "Balanced"
        mock_team.roster = [mock_player]
        mock_team.budget = 100.0

        mock_draft = MagicMock()
        mock_draft.teams = [mock_team]

        mock_simulation = {'completed': True}

        with patch('cli.commands.FantasyProsLoader') as MockLoader:
            MockLoader.return_value.load_all_players.return_value = [mock_player]
            cp._create_mock_draft = MagicMock(return_value=mock_draft)
            cp._run_detailed_simulation = MagicMock(return_value=mock_simulation)

            result = cp.run_enhanced_mock_draft('balanced', 10)

        assert result['success'] is True
        assert 'draft' in result

    def test_list_strategy_success_path(self):
        """Cover run_enhanced_mock_draft with list of valid strategies."""
        cp = self._make_cp()

        mock_config = MagicMock()
        cp.config_manager.load_config.return_value = mock_config

        mock_player = MagicMock()
        mock_player.projected_points = 200.0

        mock_team = MagicMock()
        mock_team.team_name = "Team 1"
        mock_team.strategy.name = "Balanced"
        mock_team.roster = [mock_player]
        mock_team.budget = 150.0

        mock_draft = MagicMock()
        mock_draft.teams = [mock_team]

        with patch('cli.commands.FantasyProsLoader') as MockLoader:
            MockLoader.return_value.load_all_players.return_value = [mock_player]
            cp._create_mock_draft = MagicMock(return_value=mock_draft)
            cp._run_detailed_simulation = MagicMock(return_value={})

            result = cp.run_enhanced_mock_draft(['balanced', 'aggressive'], 10)

        assert result['success'] is True

    def test_winner_determination_path(self):
        """Cover best team winner determination loop (lines 115-133)."""
        cp = self._make_cp()

        mock_config = MagicMock()
        cp.config_manager.load_config.return_value = mock_config

        p1 = MagicMock(); p1.projected_points = 300.0
        p2 = MagicMock(); p2.projected_points = 100.0

        team1 = MagicMock()
        team1.team_name = "Team 1"
        team1.strategy.name = "Balanced"
        team1.roster = [p1]
        team1.budget = 100.0

        team2 = MagicMock()
        team2.team_name = "Team 2"
        team2.strategy.name = "Aggressive"
        team2.roster = [p2]
        team2.budget = 150.0

        mock_draft = MagicMock()
        mock_draft.teams = [team1, team2]

        with patch('cli.commands.FantasyProsLoader') as MockLoader:
            MockLoader.return_value.load_all_players.return_value = [p1]
            cp._create_mock_draft = MagicMock(return_value=mock_draft)
            cp._run_detailed_simulation = MagicMock(return_value={'data': True})

            result = cp.run_enhanced_mock_draft('balanced', 10)

        assert result['success'] is True
        assert result.get('winner_strategy') == 'Balanced'


class TestRunEliminationTournamentFull:
    """Cover _run_elimination_tournament (lines 604-696)."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_two_strategy_single_round(self):
        """Cover _run_elimination_tournament with 2 strategies → 1 round."""
        cp = self._make_cp()

        mock_winner_team = MagicMock()
        mock_winner_team.strategy.name = "balanced"
        mock_winner_team.get_projected_points.return_value = 1200.0
        mock_winner_team.get_total_spent.return_value = 150.0

        mock_pool_result = {
            'success': True,
            'winner': {'strategy': 'balanced', 'points': 1200.0, 'efficiency': 8.0},
            'all_teams': []
        }

        cp._run_elimination_draft = MagicMock(return_value=mock_pool_result)

        result = cp._run_elimination_tournament(['balanced', 'aggressive'], 10)

        assert result['success'] is True
        assert result['champion'] == 'balanced'

    def test_failure_pool_path(self):
        """Cover failed pool result path (lines 644-645)."""
        cp = self._make_cp()

        mock_pool_fail = {'success': False, 'error': 'Draft failed'}
        cp._run_elimination_draft = MagicMock(return_value=mock_pool_fail)

        result = cp._run_elimination_tournament(['balanced', 'aggressive'], 10)

        assert result['success'] is True  # Tournament still succeeds even if pool fails

    def test_many_rounds_triggers_safety(self):
        """Cover lines 668-669 — safety break when round_number > 10."""
        cp = self._make_cp()

        call_num = [0]

        def make_elimination_result(strategies):
            call_num[0] += 1
            return {
                'success': True,
                'winner': {'strategy': strategies[0], 'points': 1200.0, 'efficiency': 8.0},
                'all_teams': []
            }

        cp._run_elimination_draft = MagicMock(side_effect=make_elimination_result)

        # Return 2 pools each round → 2 winners → current_strategies stays 2 → loops > 10
        def fake_pools(strategies, teams_per_draft):
            return [['balanced', 'aggressive'], ['conservative', 'basic']]

        with patch.object(cp, '_create_tournament_pools', side_effect=fake_pools):
            result = cp._run_elimination_tournament(
                ['balanced', 'aggressive', 'conservative', 'basic'], 2
            )

        assert result['success'] is True


class TestRunMockDraftTournamentFull:
    """Cover _run_mock_draft_tournament (lines 700-789)."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_two_strategies(self):
        """Cover _run_mock_draft_tournament with 2 strategies."""
        cp = self._make_cp()

        winner_team = MagicMock()
        winner_team.strategy.name = "Balanced"
        winner_team.get_projected_points.return_value = 1200.0
        winner_team.get_total_spent.return_value = 150.0

        loser_team = MagicMock()
        loser_team.strategy.name = "Aggressive"
        loser_team.get_projected_points.return_value = 900.0
        loser_team.get_total_spent.return_value = 180.0

        mock_draft = MagicMock()
        mock_draft.teams = [winner_team, loser_team]

        cp.run_enhanced_mock_draft = MagicMock(return_value={
            'success': True,
            'draft': mock_draft,
            'winner_strategy': 'Balanced'
        })
        cp._map_strategy_name_to_key = MagicMock(return_value='balanced')

        result = cp._run_mock_draft_tournament(['balanced', 'aggressive'], 10)

        assert result['success'] is True
        assert result['champion'] is not None

    def test_failed_mock_draft(self):
        """Cover failed mock draft path (lines 760-762)."""
        cp = self._make_cp()

        cp.run_enhanced_mock_draft = MagicMock(return_value={
            'success': False,
            'error': 'Load failed'
        })

        result = cp._run_mock_draft_tournament(['balanced', 'aggressive'], 10)

        # Even if all drafts fail, method should complete
        assert result['success'] is True

    def test_empty_teams_in_draft(self):
        """Cover line 756 — mock draft success but draft.teams is empty."""
        cp = self._make_cp()

        mock_draft = MagicMock()
        mock_draft.teams = []  # no teams → sorted list is empty

        cp.run_enhanced_mock_draft = MagicMock(return_value={
            'success': True,
            'draft': mock_draft,
        })

        result = cp._run_mock_draft_tournament(['balanced', 'aggressive'], 2)
        assert result['success'] is True

    def test_many_rounds_triggers_safety(self):
        """Cover line 778 — safety break when round_number > 10."""
        cp = self._make_cp()

        call_num = [0]

        def make_result(strategies, teams_per_draft):
            call_num[0] += 1
            winner = MagicMock()
            winner.strategy.name = strategies[0]
            winner.get_projected_points.return_value = 1200.0
            winner.get_total_spent.return_value = 150.0

            mock_draft = MagicMock()
            mock_draft.teams = [winner]
            return {'success': True, 'draft': mock_draft}

        cp.run_enhanced_mock_draft = MagicMock(side_effect=make_result)
        cp._map_strategy_name_to_key = MagicMock(side_effect=lambda x: x.lower())

        # Return 2 pools each round → 2 winners per round → len(current_strategies) stays 2 → loops > 10 rounds
        def fake_pools(strategies, teams_per_draft):
            return [['balanced', 'aggressive'], ['conservative', 'basic']]

        with patch.object(cp, '_create_tournament_pools', side_effect=fake_pools):
            result = cp._run_mock_draft_tournament(
                ['balanced', 'aggressive', 'conservative', 'basic'], 2
            )

        assert result['success'] is True


class TestRunEliminationDraft:
    """Cover _run_elimination_draft (lines 874-973)."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_no_draft_returns_error(self):
        """Cover _create_test_draft returns None → error (lines 881-884)."""
        cp = self._make_cp()
        cp._create_test_draft = MagicMock(return_value=None)

        result = cp._run_elimination_draft(['balanced', 'aggressive'])

        assert result['success'] is False
        assert 'error' in result

    def test_exception_returns_error(self):
        """Cover exception path (lines 969-972)."""
        cp = self._make_cp()
        cp._create_test_draft = MagicMock(side_effect=RuntimeError("test error"))

        result = cp._run_elimination_draft(['balanced'])

        assert result['success'] is False
        assert 'error' in result


class TestCreateMockDraft:
    """Cover _create_mock_draft (lines 1075-1122)."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_single_strategy_creates_draft(self):
        """Cover single strategy path (lines 1075-1122)."""
        cp = self._make_cp()

        mock_config = MagicMock()
        mock_config.budget_per_team = 200
        mock_config.roster_positions = {'QB': 1, 'RB': 2}
        mock_player = MagicMock()
        mock_player.name = "Test Player"
        mock_player.position = "QB"

        with patch('cli.commands.Draft') as MockDraft, \
             patch('cli.commands.Team') as MockTeam, \
             patch('cli.commands.Owner') as MockOwner, \
             patch('cli.commands.create_strategy') as MockCreate:
            mock_strategy = MagicMock()
            mock_strategy.name = "Balanced"
            MockCreate.return_value = mock_strategy
            MockDraft.return_value = MagicMock()

            result = cp._create_mock_draft(mock_config, [mock_player], 'balanced', 2)

        assert result is not None

    def test_list_strategies_creates_draft(self):
        """Cover list strategies path (lines 1077-1079)."""
        cp = self._make_cp()

        mock_config = MagicMock()
        mock_config.budget_per_team = 200
        mock_config.roster_positions = {'QB': 1, 'RB': 2}
        mock_player = MagicMock()

        with patch('cli.commands.Draft') as MockDraft, \
             patch('cli.commands.Team') as MockTeam, \
             patch('cli.commands.Owner') as MockOwner, \
             patch('cli.commands.create_strategy') as MockCreate:
            mock_strategy = MagicMock()
            mock_strategy.name = "Balanced"
            MockCreate.return_value = mock_strategy

            result = cp._create_mock_draft(mock_config, [mock_player], ['balanced', 'aggressive'], 2)

        assert result is not None


class TestCreateMockDraftExtraCoverage:
    """Cover remaining uncovered paths in _create_mock_draft."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_no_roster_positions_uses_roster_size(self):
        """Cover line 1088: no roster_positions falls back to roster_size."""
        cp = self._make_cp()
        mock_config = MagicMock()
        mock_config.budget_per_team = 200
        mock_config.roster_positions = None  # Force fallback
        mock_config.roster_size = 12
        mock_player = MagicMock()

        with patch('cli.commands.Draft') as MockDraft, \
             patch('cli.commands.Team') as MockTeam, \
             patch('cli.commands.Owner') as MockOwner, \
             patch('cli.commands.create_strategy') as MockCreate:
            mock_strategy = MagicMock()
            mock_strategy.name = "Balanced"
            MockCreate.return_value = mock_strategy
            result = cp._create_mock_draft(mock_config, [mock_player], 'balanced', 2)

        assert result is not None

    def test_gridiron_sage_tournament_mode(self):
        """Cover lines 1105-1108, 1112: gridiron_sage strategy enables tournament mode."""
        cp = self._make_cp()
        mock_config = MagicMock()
        mock_config.budget_per_team = 200
        mock_config.roster_positions = {'QB': 1}
        mock_player = MagicMock()

        mock_strategy = MagicMock()
        mock_strategy.name = "GridironSage"
        mock_strategy.enable_tournament_mode = MagicMock()

        with patch('cli.commands.Draft') as MockDraft, \
             patch('cli.commands.Team') as MockTeam, \
             patch('cli.commands.Owner') as MockOwner, \
             patch('cli.commands.create_strategy') as MockCreate:
            MockCreate.return_value = mock_strategy
            # Pass a non-list string strategy to hit lines 1104-1112
            # Need num_teams > len(active_strategies) = 4 to cycle through
            result = cp._create_mock_draft(mock_config, [mock_player], 'gridiron_sage', 5)

        assert result is not None

    def test_single_element_list_strategy(self):
        """Cover line 1078 — single-element list uses strategies[0].title()."""
        cp = self._make_cp()
        mock_config = MagicMock()
        mock_config.budget_per_team = 200
        mock_config.roster_positions = {'QB': 1}
        mock_player = MagicMock()
        mock_strategy = MagicMock()

        with patch('cli.commands.Draft'), \
             patch('cli.commands.Team'), \
             patch('cli.commands.Owner'), \
             patch('cli.commands.create_strategy', return_value=mock_strategy):
            result = cp._create_mock_draft(mock_config, [mock_player], ['balanced'], 2)

        assert result is not None


class TestRunComprehensiveStatisticalTournament:
    """Cover _run_comprehensive_statistical_tournament (lines 308-586)."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_basic_run(self):
        """Cover statistical tournament with mocked drafts."""
        cp = self._make_cp()

        mock_draft_result = {
            'success': True,
            'team_results': [
                {'strategy': 'balanced', 'total_points': 1200, 'final_budget': 50, 'roster_size': 15},
                {'strategy': 'aggressive', 'total_points': 900, 'final_budget': 10, 'roster_size': 14},
            ],
            'winner_strategy': 'balanced',
            'winner_points': 1200
        }

        cp.run_enhanced_mock_draft = MagicMock(return_value=mock_draft_result)

        result = cp._run_comprehensive_statistical_tournament(
            ['balanced', 'aggressive'], teams_per_draft=2, verbose=False
        )

        assert result['success'] is True

    def test_verbose_mode(self):
        """Cover verbose output path (line 848, 855-856)."""
        cp = self._make_cp()

        mock_draft_result = {
            'success': True,
            'team_results': [
                {'strategy': 'balanced', 'total_points': 1200, 'final_budget': 50, 'roster_size': 15},
            ],
            'winner_strategy': 'balanced',
            'winner_points': 1200
        }

        cp.run_enhanced_mock_draft = MagicMock(return_value=mock_draft_result)

        result = cp._run_comprehensive_statistical_tournament(
            ['balanced', 'aggressive'], teams_per_draft=2, verbose=True
        )

        assert result['success'] is True

    def test_phase2_championship_with_multiple_groups(self):
        """Cover lines 353-586 — Phase 2 championship with 2+ groups."""
        cp = self._make_cp()

        call_count = [0]

        def make_draft_result(group_strategies, *args, **kwargs):
            """Return a draft with teams matching the group's strategies."""
            call_count[0] += 1
            mock_teams = []
            for i, strat_name in enumerate(group_strategies[:2]):
                t = MagicMock()
                t.strategy.name = strat_name
                t.get_starter_projected_points.return_value = 1200.0 - i * 100
                t.get_total_spent.return_value = 150.0
                t.roster = [MagicMock()]
                mock_teams.append(t)
            mock_draft = MagicMock()
            mock_draft.teams = mock_teams
            winner = group_strategies[0] if group_strategies else 'balanced'
            return {
                'success': True,
                'draft': mock_draft,
                'team_results': [
                    {'strategy': s, 'total_points': 1200 - i * 100, 'final_budget': 50, 'roster_size': 5}
                    for i, s in enumerate(group_strategies[:2])
                ],
                'winner_strategy': winner,
                'winner_points': 1200
            }

        cp.run_enhanced_mock_draft = MagicMock(side_effect=make_draft_result)

        # 4 strategies with teams_per_draft=2 → 2 groups → champions from each → Phase 2
        result = cp._run_comprehensive_statistical_tournament(
            ['balanced', 'aggressive', 'conservative', 'basic'],
            teams_per_draft=2, verbose=False
        )
        assert result['success'] is True

    def test_phase2_championship_verbose(self):
        """Cover verbose path of Phase 2 championship (lines 385-386)."""
        cp = self._make_cp()

        def make_draft_result(group_strategies, *args, **kwargs):
            mock_teams = []
            for i, strat_name in enumerate(group_strategies[:2]):
                t = MagicMock()
                t.strategy.name = strat_name
                t.get_starter_projected_points.return_value = 1200.0 - i * 100
                t.get_total_spent.return_value = 150.0
                t.roster = [MagicMock()]
                mock_teams.append(t)
            mock_draft = MagicMock()
            mock_draft.teams = mock_teams
            winner = group_strategies[0] if group_strategies else 'balanced'
            return {
                'success': True,
                'draft': mock_draft,
                'team_results': [
                    {'strategy': s, 'total_points': 1200 - i * 100, 'final_budget': 50, 'roster_size': 5}
                    for i, s in enumerate(group_strategies[:2])
                ],
                'winner_strategy': winner,
                'winner_points': 1200
            }

        cp.run_enhanced_mock_draft = MagicMock(side_effect=make_draft_result)

        result = cp._run_comprehensive_statistical_tournament(
            ['balanced', 'aggressive', 'conservative', 'basic'],
            teams_per_draft=2, verbose=True
        )
        assert result['success'] is True

    def test_failed_draft_result(self):
        """Cover line 404 — failed draft result path."""
        cp = self._make_cp()
        mock_result = {'success': False, 'error': 'Draft failed'}
        cp.run_enhanced_mock_draft = MagicMock(return_value=mock_result)

        result = cp._run_comprehensive_statistical_tournament(
            ['balanced', 'aggressive', 'conservative', 'basic'],
            teams_per_draft=2, verbose=False
        )
        assert result['success'] is True

    def test_phase2_extends_champions_padding(self):
        """Cover line 469 — championship needs padding when champions < teams_per_draft."""
        cp = self._make_cp()

        def make_draft_result(group_strategies, *args, **kwargs):
            mock_teams = []
            for i, strat_name in enumerate(group_strategies[:3]):
                t = MagicMock()
                t.strategy.name = strat_name
                t.get_starter_projected_points.return_value = 1200.0 - i * 100
                t.get_total_spent.return_value = 150.0
                t.roster = [MagicMock()]
                mock_teams.append(t)
            mock_draft = MagicMock()
            mock_draft.teams = mock_teams
            winner = group_strategies[0] if group_strategies else 'balanced'
            return {
                'success': True,
                'draft': mock_draft,
                'team_results': [
                    {'strategy': s, 'total_points': 1200 - i * 100, 'final_budget': 50, 'roster_size': 5}
                    for i, s in enumerate(group_strategies[:3])
                ],
                'winner_strategy': winner,
                'winner_points': 1200
            }

        cp.run_enhanced_mock_draft = MagicMock(side_effect=make_draft_result)

        # 6 strategies with teams_per_draft=3 → 2 groups → 2 champions
        # Phase 2 championship needs teams_per_draft=3 but only 2 champions → extends (line 469)
        result = cp._run_comprehensive_statistical_tournament(
            ['balanced', 'aggressive', 'conservative', 'basic', 'enhanced_vor', 'gridiron_sage'],
            teams_per_draft=3, verbose=False
        )
        assert result['success'] is True

    def test_phase2_no_winner_path(self):
        """Cover lines 544-548 — failed/no-winner paths in Phase 2."""
        cp = self._make_cp()

        phase1_call = [0]

        def make_draft_result(group_strategies, *args, **kwargs):
            phase1_call[0] += 1
            mock_teams = []
            for i, strat_name in enumerate(group_strategies[:2]):
                t = MagicMock()
                t.strategy.name = strat_name
                t.get_starter_projected_points.return_value = 1200.0 - i * 100
                t.get_total_spent.return_value = 150.0
                t.roster = [MagicMock()]
                mock_teams.append(t)
            mock_draft = MagicMock()
            mock_draft.teams = mock_teams
            # Phase 1: success; Phase 2 (calls > 20): fail
            if phase1_call[0] > 20:
                return {'success': False, 'error': 'Phase 2 failed'}
            winner = group_strategies[0] if group_strategies else 'balanced'
            return {
                'success': True,
                'draft': mock_draft,
                'team_results': [
                    {'strategy': s, 'total_points': 1200 - i * 100, 'final_budget': 50, 'roster_size': 5}
                    for i, s in enumerate(group_strategies[:2])
                ],
                'winner_strategy': winner,
                'winner_points': 1200
            }

        cp.run_enhanced_mock_draft = MagicMock(side_effect=make_draft_result)

        result = cp._run_comprehensive_statistical_tournament(
            ['balanced', 'aggressive', 'conservative', 'basic'],
            teams_per_draft=2, verbose=False
        )
        assert result['success'] is True

    def test_phase2_no_winner_no_points(self):
        """Cover line 544 — Phase 2 runs, teams exist but all have 0 points → no winner."""
        cp = self._make_cp()

        phase1_call = [0]

        def make_draft_result(group_strategies, *args, **kwargs):
            phase1_call[0] += 1
            if phase1_call[0] <= 20:
                # Phase 1: valid teams with a winner
                mock_teams = []
                for i, strat_name in enumerate(group_strategies[:2]):
                    t = MagicMock()
                    t.strategy.name = strat_name
                    t.get_starter_projected_points.return_value = 1200.0 - i * 100
                    t.get_total_spent.return_value = 150.0
                    t.roster = [MagicMock()]
                    mock_teams.append(t)
                mock_draft = MagicMock()
                mock_draft.teams = mock_teams
                winner = group_strategies[0]
                return {
                    'success': True, 'draft': mock_draft,
                    'team_results': [{'strategy': s, 'total_points': 1200 - i * 100,
                                      'final_budget': 50, 'roster_size': 5}
                                     for i, s in enumerate(group_strategies[:2])],
                    'winner_strategy': winner, 'winner_points': 1200
                }
            else:
                # Phase 2: teams exist but all 0 points → no winner_strategy
                mock_teams = []
                for strat_name in group_strategies[:2]:
                    t = MagicMock()
                    t.strategy.name = strat_name
                    t.get_starter_projected_points.return_value = 0.0
                    t.get_total_spent.return_value = 150.0
                    t.roster = [MagicMock()]
                    mock_teams.append(t)
                mock_draft = MagicMock()
                mock_draft.teams = mock_teams
                return {'success': True, 'draft': mock_draft, 'team_results': [],
                        'winner_strategy': None, 'winner_points': 0}

        cp.run_enhanced_mock_draft = MagicMock(side_effect=make_draft_result)

        result = cp._run_comprehensive_statistical_tournament(
            ['balanced', 'aggressive', 'conservative', 'basic'],
            teams_per_draft=2, verbose=False
        )
        assert result['success'] is True

    def test_phase1_no_winner_determined(self):
        """Cover line 400 — no winner_strategy when all teams have 0 points."""
        cp = self._make_cp()

        def make_draft_result(group_strategies, *args, **kwargs):
            mock_teams = []
            for i, strat_name in enumerate(group_strategies[:2]):
                t = MagicMock()
                t.strategy.name = strat_name
                t.get_starter_projected_points.return_value = 0.0  # all 0 → winner_strategy stays None
                t.get_total_spent.return_value = 150.0
                t.roster = [MagicMock()]
                mock_teams.append(t)
            mock_draft = MagicMock()
            mock_draft.teams = mock_teams
            return {
                'success': True,
                'draft': mock_draft,
                'team_results': [],
                'winner_strategy': None,  # no winner
                'winner_points': 0
            }

        cp.run_enhanced_mock_draft = MagicMock(side_effect=make_draft_result)

        result = cp._run_comprehensive_statistical_tournament(
            ['balanced', 'aggressive'], teams_per_draft=2, verbose=False
        )
        assert result['success'] is True

    def test_phase2_no_teams_in_draft(self):
        """Cover line 546 — Phase 2 draft has no teams."""
        cp = self._make_cp()

        phase1_call = [0]

        def make_draft_result(group_strategies, *args, **kwargs):
            phase1_call[0] += 1
            if phase1_call[0] <= 20:
                # Phase 1: return valid teams
                mock_teams = []
                for i, strat_name in enumerate(group_strategies[:2]):
                    t = MagicMock()
                    t.strategy.name = strat_name
                    t.get_starter_projected_points.return_value = 1200.0 - i * 100
                    t.get_total_spent.return_value = 150.0
                    t.roster = [MagicMock()]
                    mock_teams.append(t)
                mock_draft = MagicMock()
                mock_draft.teams = mock_teams
                winner = group_strategies[0]
                return {
                    'success': True, 'draft': mock_draft,
                    'team_results': [{'strategy': s, 'total_points': 1200 - i * 100,
                                      'final_budget': 50, 'roster_size': 5}
                                     for i, s in enumerate(group_strategies[:2])],
                    'winner_strategy': winner, 'winner_points': 1200
                }
            else:
                # Phase 2: return draft with no teams (empty teams list)
                mock_draft = MagicMock()
                mock_draft.teams = []
                return {'success': True, 'draft': mock_draft, 'team_results': [],
                        'winner_strategy': None, 'winner_points': 0}

        cp.run_enhanced_mock_draft = MagicMock(side_effect=make_draft_result)

        result = cp._run_comprehensive_statistical_tournament(
            ['balanced', 'aggressive', 'conservative', 'basic'],
            teams_per_draft=2, verbose=False
        )
        assert result['success'] is True


class TestRunEliminationRounds:
    """Cover _run_elimination_rounds (lines 193-263)."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_two_strategies_one_round(self):
        """Cover main while loop and winner selection (lines 193-263)."""
        cp = self._make_cp()

        mock_draft_result = {
            'success': True,
            'winner_strategy': 'balanced',
            'winner_points': 1200.0,
            'team_results': [
                {'strategy': 'balanced', 'total_points': 1200},
                {'strategy': 'aggressive', 'total_points': 900},
            ]
        }

        cp.run_enhanced_mock_draft = MagicMock(return_value=mock_draft_result)

        result = cp._run_elimination_rounds(
            ['balanced', 'aggressive'],
            rounds_per_group=1,
            teams_per_draft=2,
            verbose=False
        )

        assert result['success'] is True
        assert result.get('tournament_winner') == 'balanced'

    def test_verbose_mode(self):
        """Cover verbose output (line 227)."""
        cp = self._make_cp()

        mock_draft_result = {
            'success': True,
            'winner_strategy': 'balanced',
            'winner_points': 1200.0,
            'team_results': [
                {'strategy': 'balanced', 'total_points': 1200},
            ]
        }

        cp.run_enhanced_mock_draft = MagicMock(return_value=mock_draft_result)

        result = cp._run_elimination_rounds(
            ['balanced', 'aggressive'],
            rounds_per_group=1,
            teams_per_draft=2,
            verbose=True
        )

        assert result['success'] is True

    def test_failed_draft_path(self):
        """Cover failed draft → 'Failed: ...' print path (line 244)."""
        cp = self._make_cp()

        cp.run_enhanced_mock_draft = MagicMock(return_value={
            'success': False,
            'error': 'Load failed'
        })

        result = cp._run_elimination_rounds(
            ['balanced', 'aggressive'],
            rounds_per_group=1,
            teams_per_draft=2,
            verbose=False
        )

        assert result['success'] is True


class TestCommandsExtraCoverage:
    """Cover remaining small gaps in commands.py."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_generate_recommendations_high_scoring(self):
        """Cover line 1594: avg_points > 1200."""
        cp = self._make_cp()
        rankings = [
            {'strategy': 'balanced', 'avg_points': 1300.0, 'wins': 5, 'avg_value_efficiency': 1.2, 'std_dev': 50.0},
            {'strategy': 'aggressive', 'avg_points': 1100.0, 'wins': 3, 'avg_value_efficiency': 1.0, 'std_dev': 80.0},
            {'strategy': 'conservative', 'avg_points': 900.0, 'wins': 1, 'avg_value_efficiency': 0.9, 'std_dev': 30.0},
        ]
        result = cp._generate_strategy_recommendations(rankings)
        assert 'High scoring potential' in result['reasoning']

    def test_create_test_draft_success(self):
        """Cover lines 1618-1640: _create_test_draft happy path."""
        cp = self._make_cp()
        mock_config = MagicMock()
        mock_config.data_path = "/fake/path"
        mock_config.budget_per_team = 200
        mock_config.roster_size = 16
        cp.config_manager.load_config.return_value = mock_config

        mock_player = MagicMock()
        mock_loader = MagicMock()
        mock_loader.load_all_players.return_value = [mock_player]

        with patch('cli.commands.FantasyProsLoader', return_value=mock_loader), \
             patch('cli.commands.Draft') as MockDraft, \
             patch('cli.commands.Team') as MockTeam, \
             patch('cli.commands.Owner') as MockOwner:
            MockDraft.return_value = MagicMock()
            result = cp._create_test_draft(2)

        assert result is not None

    def test_create_test_draft_no_players_returns_none(self):
        """Cover line 1622: no players returns None."""
        cp = self._make_cp()
        mock_config = MagicMock()
        mock_config.data_path = "/fake/path"
        cp.config_manager.load_config.return_value = mock_config

        mock_loader = MagicMock()
        mock_loader.load_all_players.return_value = []

        with patch('cli.commands.FantasyProsLoader', return_value=mock_loader):
            result = cp._create_test_draft(2)

        assert result is None


class TestRunDetailedSimulation:
    """Cover _run_detailed_simulation (lines 1126-1555)."""

    def _make_cp(self):
        with patch('cli.commands.ConfigManager'), \
             patch('cli.commands.SleeperAPI'), \
             patch('cli.commands.SleeperDraftService'):
            from cli.commands import CommandProcessor
            return CommandProcessor()

    def test_simulation_completes_with_full_rosters(self):
        """Cover main path: draft.status not 'started' so while loop skipped."""
        cp = self._make_cp()

        mock_config = MagicMock()
        mock_config.roster_positions = {'QB': 1, 'RB': 2}
        cp.config_manager.load_config.return_value = mock_config

        mock_team = MagicMock()
        mock_team.strategy = MagicMock()
        mock_team.strategy.name = 'balanced'
        mock_team.owner_id = 'owner_1'
        mock_team.roster = []
        mock_team.budget = 200.0
        mock_team.get_projected_points.return_value = 500.0
        mock_team.get_starter_projected_points.return_value = 500.0
        mock_team.get_total_spent.return_value = 0.0

        mock_draft = MagicMock()
        # draft.status is 'completed', so while loop won't run
        mock_draft.status = 'completed'
        mock_draft.teams = [mock_team]
        mock_draft.available_players = [MagicMock(), MagicMock()]

        mock_auction = MagicMock()

        with patch('classes.auction.Auction', return_value=mock_auction):
            result = cp._run_detailed_simulation(mock_draft, 'balanced')

        assert 'total_players_drafted' in result
        assert result['primary_strategy'] == 'balanced'

    def test_simulation_all_rosters_complete(self):
        """Cover line 1202-1204: all teams have complete rosters → break."""
        cp = self._make_cp()

        mock_config = MagicMock()
        mock_config.roster_positions = {'QB': 1}  # 1 slot
        cp.config_manager.load_config.return_value = mock_config

        mock_player = MagicMock()
        mock_player.position = 'QB'
        mock_player.name = 'Test Player'
        mock_player.auction_price = 10.0
        mock_player.projected_points = 25.0

        mock_team = MagicMock()
        mock_team.strategy = MagicMock()
        mock_team.strategy.name = 'balanced'
        mock_team.owner_id = 'owner_1'
        mock_team.budget = 200.0
        mock_team.get_projected_points.return_value = 500.0
        mock_team.get_starter_projected_points.return_value = 500.0
        mock_team.get_total_spent.return_value = 0.0
        # Roster already has the 1 slot filled
        mock_team.roster = [mock_player]

        mock_draft = MagicMock()
        mock_draft.status = 'started'
        mock_draft.teams = [mock_team]
        mock_draft.available_players = [MagicMock()]

        mock_auction = MagicMock()

        with patch('classes.auction.Auction', return_value=mock_auction):
            result = cp._run_detailed_simulation(mock_draft, 'balanced')

        assert 'total_players_drafted' in result
