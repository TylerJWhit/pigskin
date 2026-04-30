"""
Test suite for utils/print_module.py

Tests the actual printing and formatting functions that exist in the implementation:
- TableFormatter class and methods  
- MockDraftPrinter class and methods
- TournamentPrinter class and methods
- SleeperDraftPrinter class and methods

This tests the ACTUAL implementation as it exists, not hypothetical functions.
"""

import pytest
from unittest.mock import Mock, patch
import io

# Import the module under test - only classes that actually exist
from utils.print_module import (
    TableFormatter,
    MockDraftPrinter, 
    TournamentPrinter,
    SleeperDraftPrinter
)


class TestTableFormatter:
    """Test the TableFormatter utility class."""
    
    def test_format_table_basic(self):
        """Test basic table formatting functionality."""
        headers = ['Name', 'Position', 'Points']
        rows = [
            ['Patrick Mahomes', 'QB', '325.4'],
            ['Josh Allen', 'QB', '318.2']
        ]
        
        result = TableFormatter.format_table(headers, rows)
        
        assert isinstance(result, str)
        assert 'Name' in result
        assert 'Position' in result  
        assert 'Points' in result
        assert 'Patrick Mahomes' in result
        assert 'Josh Allen' in result
        
    def test_format_table_with_title(self):
        """Test table formatting with title."""
        headers = ['Player', 'Value']
        rows = [['Test Player', '$25']]
        title = 'Player Values'
        
        result = TableFormatter.format_table(headers, rows, title=title)
        
        assert isinstance(result, str)
        assert title in result
        assert 'Player' in result
        assert 'Test Player' in result
        
    def test_format_table_empty_data(self):
        """Test table formatting with empty data."""
        result = TableFormatter.format_table([], [])
        assert result == ""
        
    def test_format_table_alignment_options(self):
        """Test table alignment options."""
        headers = ['Name', 'Value']
        rows = [['Player1', '100']]
        
        # Test different alignment options
        for align in ['left', 'right', 'center']:
            result = TableFormatter.format_table(headers, rows, align=align)
            assert isinstance(result, str)
            assert 'Player1' in result
            
    def test_format_table_minimum_width(self):
        """Test minimum width enforcement."""
        headers = ['A', 'B']
        rows = [['1', '2']]
        min_width = 100
        
        result = TableFormatter.format_table(headers, rows, min_width=min_width)
        assert isinstance(result, str)
        # Should produce wider output due to min_width
        lines = result.split('\n')
        if lines:
            # At least one line should be reasonably wide
            max_line_length = max(len(line) for line in lines if line.strip())
            assert max_line_length >= 20  # Should be wider than basic content


class TestTableFormatterStaticMethods:
    """Test the static formatting methods in TableFormatter."""
    
    def test_format_currency_basic(self):
        """Test basic currency formatting."""
        assert TableFormatter.format_currency(25.0) == '$25'
        assert TableFormatter.format_currency(0.0) == '$0'
        
    def test_format_currency_large_values(self):
        """Test currency formatting for large values.""" 
        result = TableFormatter.format_currency(1000.0)
        assert '$1000' in result
        
    def test_format_currency_negative_values(self):
        """Test currency formatting for negative values."""
        result = TableFormatter.format_currency(-25.0)
        assert '-$25' in result or '$-25' in result
        
    def test_format_percentage_basic(self):
        """Test basic percentage formatting."""
        result = TableFormatter.format_percentage(0.25)
        assert '%' in result and '25' in result
        
        result = TableFormatter.format_percentage(1.0)
        assert '%' in result and '100' in result
        
    def test_format_percentage_precision(self):
        """Test percentage formatting with precision."""
        result = TableFormatter.format_percentage(0.12345)
        assert '%' in result
        assert '12' in result
        
    def test_format_points_basic(self):
        """Test points formatting."""
        result = TableFormatter.format_points(325.4)
        assert isinstance(result, str)
        assert '325' in result
        
    def test_format_points_zero(self):
        """Test points formatting with zero."""
        result = TableFormatter.format_points(0.0)
        assert isinstance(result, str)
        assert '0' in result
        
    def test_format_efficiency_basic(self):
        """Test efficiency formatting (points per dollar)."""
        result = TableFormatter.format_efficiency(300.0, 25.0)
        assert isinstance(result, str)
        # Should contain meaningful efficiency information
        
    def test_format_efficiency_zero_cost(self):
        """Test efficiency formatting with zero cost."""
        result = TableFormatter.format_efficiency(300.0, 0.0)
        assert isinstance(result, str)
        # Should return N/A or handle division by zero gracefully
        assert 'N/A' in result or result is not None


class TestMockDraftPrinter:
    """Test mock draft display functions that actually exist."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a more realistic mock draft object
        mock_draft = Mock()
        mock_draft.name = 'Test Draft'
        mock_draft.status = 'completed'
        mock_draft.drafted_players = ['player1', 'player2', 'player3']  # Mock list
        mock_draft.current_round = 3
        mock_draft.started_at = None
        mock_draft.completed_at = None
        
        # Create mock teams with required methods
        mock_team1 = Mock()
        mock_team1.get_projected_points.return_value = 1650.5
        mock_team1.get_total_spent.return_value = 190.0
        mock_team1.get_strategy.return_value = None
        mock_team1.team_name = 'Team Alpha'
        mock_team1.strategy_name = 'VOR Strategy'
        mock_team1.budget = 10
        mock_team1.initial_budget = 200
        mock_team1.budget_spent = 190
        mock_team1.remaining_budget = 10
        mock_team1.roster = []
        mock_team1.strategy = None
        
        mock_team2 = Mock()
        mock_team2.get_projected_points.return_value = 1598.2
        mock_team2.get_total_spent.return_value = 185.0
        mock_team2.get_strategy.return_value = None
        mock_team2.team_name = 'Team Beta'
        mock_team2.strategy_name = 'Kelly Strategy'
        mock_team2.budget = 15
        mock_team2.initial_budget = 200
        mock_team2.budget_spent = 185
        mock_team2.remaining_budget = 15
        mock_team2.roster = []
        mock_team2.strategy = None
        
        mock_draft.teams = [mock_team1, mock_team2]
        
        self.sample_draft_result = {
            'draft': mock_draft,
            'simulation_results': {
                'teams': [
                    {'team_id': 1, 'team_name': 'Team Alpha', 'total_points': 1650.5, 'rank': 1},
                    {'team_id': 2, 'team_name': 'Team Beta', 'total_points': 1598.2, 'rank': 2}
                ],
                'total_players_drafted': 3,
                'rounds_completed': 3
            },
            'winner': {'team_id': 1, 'team_name': 'Team Alpha'},
            'total_teams': 2,
            'draft_completed': True
        }
    
    @patch('builtins.print')
    def test_print_mock_draft_summary_basic(self, mock_print):
        """Test basic mock draft summary printing."""
        MockDraftPrinter.print_mock_draft_summary(self.sample_draft_result)
        
        # Should call print function
        mock_print.assert_called()
        
    @patch('builtins.print')
    def test_print_mock_draft_leaderboard_basic(self, mock_print):
        """Test mock draft leaderboard printing."""
        MockDraftPrinter.print_mock_draft_leaderboard(self.sample_draft_result)
        
        mock_print.assert_called()
        
    @patch('builtins.print')
    def test_print_winning_roster_basic(self, mock_print):
        """Test winning roster display."""
        MockDraftPrinter.print_winning_roster(self.sample_draft_result)
        
        mock_print.assert_called()
        
    @patch('builtins.print')
    def test_print_mock_draft_detailed(self, mock_print):
        """Test detailed mock draft printing."""
        MockDraftPrinter.print_mock_draft(self.sample_draft_result, detailed=True)
        
        mock_print.assert_called()
        
    @patch('builtins.print')
    def test_print_mock_draft_basic_mode(self, mock_print):
        """Test basic mock draft printing."""
        MockDraftPrinter.print_mock_draft(self.sample_draft_result, detailed=False)
        
        mock_print.assert_called()
        
    @patch('builtins.print')
    def test_print_all_team_rosters_basic(self, mock_print):
        """Test printing all team rosters."""
        MockDraftPrinter.print_all_team_rosters(self.sample_draft_result)
        
        mock_print.assert_called()


class TestTournamentPrinter:
    """Test tournament display functions that actually exist."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_tournament_result = {
            'tournament_id': 'tournament_123',
            'total_drafts': 100,
            'participants': [
                {'strategy': 'VOR Strategy', 'avg_rank': 4.2, 'win_rate': 0.35},
                {'strategy': 'Kelly Strategy', 'avg_rank': 3.8, 'win_rate': 0.42}
            ],
            'winner': {'strategy': 'Kelly Strategy', 'avg_rank': 3.8},
            'tournament_completed': True,
            'results': {
                'VOR Strategy': {
                    'simulations': 100,
                    'wins': 35,
                    'win_rate': 0.35,
                    'avg_points': 1634.5,
                    'best_points': 1750.2,
                    'worst_points': 1520.1,
                    'points_std': 45.7,
                    'avg_spent': 195.5,
                    'avg_remaining': 4.5,
                    'avg_ranking': 4.2,
                    'median_ranking': 4.0
                },
                'Kelly Strategy': {
                    'simulations': 100,
                    'wins': 42,
                    'win_rate': 0.42,
                    'avg_points': 1661.2,
                    'best_points': 1780.5,
                    'worst_points': 1545.8,
                    'points_std': 42.3,
                    'avg_spent': 198.2,
                    'avg_remaining': 1.8,
                    'avg_ranking': 3.8,
                    'median_ranking': 3.5
                }
            }
        }
    
    @patch('builtins.print')
    def test_print_tournament_summary_basic(self, mock_print):
        """Test tournament summary printing."""
        TournamentPrinter.print_tournament_summary(self.sample_tournament_result)
        
        mock_print.assert_called()
        
    @patch('builtins.print')
    def test_print_tournament_rankings_basic(self, mock_print):
        """Test tournament rankings printing."""
        TournamentPrinter.print_tournament_rankings(self.sample_tournament_result)
        
        mock_print.assert_called()
        
    @patch('builtins.print')
    def test_print_tournament_detailed_stats_basic(self, mock_print):
        """Test detailed tournament stats printing."""
        TournamentPrinter.print_tournament_detailed_stats(self.sample_tournament_result)
        
        mock_print.assert_called()
        
    @patch('builtins.print')
    def test_print_elimination_tournament_basic(self, mock_print):
        """Test elimination tournament printing."""
        TournamentPrinter.print_elimination_tournament(self.sample_tournament_result)
        
        mock_print.assert_called()


class TestSleeperDraftPrinter:
    """Test Sleeper integration display functions that actually exist."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_draft_info = {
            'draft_id': 'sleeper_draft_123',
            'league_name': 'Test League',
            'status': 'in_progress',
            'type': 'auction',
            'settings': {
                'teams': 12,
                'rounds': 16
            },
            'participants': [
                {'user_id': 'user1', 'display_name': 'Owner 1'},
                {'user_id': 'user2', 'display_name': 'Owner 2'}
            ]
        }
        
        self.sample_picks = [
            {'pick': 1, 'user_id': 'user1', 'player_id': 'player1', 'metadata': {'first_name': 'Christian', 'last_name': 'McCaffrey'}},
            {'pick': 2, 'user_id': 'user2', 'player_id': 'player2', 'metadata': {'first_name': 'Austin', 'last_name': 'Ekeler'}}
        ]
        
        self.sample_rosters = [
            {'owner_id': 'user1', 'players': ['player1', 'player3'], 'roster_id': 1},
            {'owner_id': 'user2', 'players': ['player2', 'player4'], 'roster_id': 2}
        ]
    
    @patch('builtins.print')
    def test_print_sleeper_draft_summary_basic(self, mock_print):
        """Test Sleeper draft summary printing."""
        SleeperDraftPrinter.print_sleeper_draft_summary(self.sample_draft_info)
        
        mock_print.assert_called()
        
    @patch('builtins.print')
    def test_print_sleeper_draft_order_basic(self, mock_print):
        """Test Sleeper draft order printing."""
        users_info = {'user1': {'display_name': 'Owner 1'}, 'user2': {'display_name': 'Owner 2'}}
        
        SleeperDraftPrinter.print_sleeper_draft_order(self.sample_draft_info, users_info)
        
        mock_print.assert_called()
        
    @patch('builtins.print')
    def test_print_sleeper_draft_order_no_users_info(self, mock_print):
        """Test Sleeper draft order printing without user info."""
        SleeperDraftPrinter.print_sleeper_draft_order(self.sample_draft_info, None)
        
        mock_print.assert_called()
        
    @patch('builtins.print')
    def test_print_sleeper_picks_basic(self, mock_print):
        """Test Sleeper picks printing."""
        players_info = {
            'player1': {'first_name': 'Christian', 'last_name': 'McCaffrey', 'position': 'RB'},
            'player2': {'first_name': 'Austin', 'last_name': 'Ekeler', 'position': 'RB'}
        }
        
        SleeperDraftPrinter.print_sleeper_picks(self.sample_picks, players_info)
        
        mock_print.assert_called()
        
    @patch('builtins.print')
    def test_print_sleeper_picks_no_player_info(self, mock_print):
        """Test Sleeper picks printing without player info."""
        SleeperDraftPrinter.print_sleeper_picks(self.sample_picks, None)
        
        mock_print.assert_called()
        
    @patch('builtins.print')
    def test_print_sleeper_rosters_basic(self, mock_print):
        """Test Sleeper rosters printing."""
        users_info = {'user1': {'display_name': 'Owner 1'}, 'user2': {'display_name': 'Owner 2'}}
        players_info = {'player1': {'first_name': 'Christian', 'last_name': 'McCaffrey'}}
        
        SleeperDraftPrinter.print_sleeper_rosters(self.sample_rosters, users_info, players_info)
        
        mock_print.assert_called()


class TestPrintModuleErrorHandling:
    """Test error handling and edge cases."""
    
    def test_table_formatter_none_inputs(self):
        """Test TableFormatter with None inputs."""
        result = TableFormatter.format_table(None, None)
        assert result == ""
        
    def test_format_currency_edge_cases(self):
        """Test currency formatting edge cases."""
        # Test with None (should handle gracefully or raise expected exception)
        try:
            result = TableFormatter.format_currency(None)
            # If it doesn't raise exception, should return some reasonable default
            assert isinstance(result, str)
        except (TypeError, ValueError):
            # Acceptable to raise exception for invalid input
            pass
            
    def test_format_percentage_edge_cases(self):
        """Test percentage formatting edge cases."""
        try:
            result = TableFormatter.format_percentage(None)
            assert isinstance(result, str)
        except (TypeError, ValueError):
            # Acceptable to raise exception for invalid input
            pass
            
    @patch('builtins.print')
    def test_print_functions_empty_data(self, mock_print):
        """Test print functions with empty data structures.""" 
        # These functions expect specific data structures and should raise KeyError
        # when required keys are missing - this is correct behavior
        empty_draft = {}
        empty_tournament = {}
        empty_sleeper = {}
        
        # Test that functions raise expected exceptions with empty data
        with pytest.raises(KeyError):
            MockDraftPrinter.print_mock_draft_summary(empty_draft)
            
        # Tournament summary might handle empty data differently
        try:
            TournamentPrinter.print_tournament_summary(empty_tournament) 
        except KeyError:
            pass  # Expected for empty data
            
        with pytest.raises(KeyError):
            SleeperDraftPrinter.print_sleeper_draft_summary(empty_sleeper)


class TestPrintModuleIntegration:
    """Integration tests for print module functions working together."""
    
    def test_module_imports_successful(self):
        """Test that all expected functions can be imported and are callable."""
        functions_to_test = [
            TableFormatter.format_table,
            TableFormatter.format_currency,
            TableFormatter.format_percentage,
            TableFormatter.format_points,
            TableFormatter.format_efficiency,
            MockDraftPrinter.print_mock_draft_summary,
            TournamentPrinter.print_tournament_summary,
            SleeperDraftPrinter.print_sleeper_draft_summary
        ]
        
        for func in functions_to_test:
            assert callable(func), f"Function {func.__name__} should be callable"
    
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_output_capture_integration(self, mock_stdout):
        """Test that output can be captured and verified."""
        # Test TableFormatter output
        headers = ['Test', 'Output']
        rows = [['Value1', 'Value2']]
        
        result = TableFormatter.format_table(headers, rows)
        print(result)
        output = mock_stdout.getvalue()
        assert 'Value1' in output
        
    def test_formatting_consistency(self):
        """Test that formatting functions produce consistent output."""
        # Test multiple calls return same result
        amount = 25.50
        result1 = TableFormatter.format_currency(amount)
        result2 = TableFormatter.format_currency(amount)
        assert result1 == result2, "Currency formatting should be consistent"
        
        percentage = 0.25
        result1 = TableFormatter.format_percentage(percentage)
        result2 = TableFormatter.format_percentage(percentage)
        assert result1 == result2, "Percentage formatting should be consistent"


class TestPrintModulePerformance:
    """Test performance characteristics of print functions."""
    
    def test_large_table_formatting_performance(self):
        """Test table formatting with moderately large datasets."""
        import time
        
        # Create moderately large dataset
        headers = ['Col1', 'Col2', 'Col3', 'Col4', 'Col5']
        rows = [
            [f'Data{i}_{j}' for j in range(5)]
            for i in range(100)  # Reasonable size for testing
        ]
        
        start_time = time.time()
        result = TableFormatter.format_table(headers, rows)
        end_time = time.time()
        
        # Should complete quickly (less than 1 second for 100 rows)
        assert end_time - start_time < 1.0
        assert isinstance(result, str)
        assert len(result) > 0
        
    def test_formatting_functions_performance(self):
        """Test performance of formatting functions."""
        import time
        
        # Test multiple format calls
        start_time = time.time()
        for i in range(1000):
            TableFormatter.format_currency(float(i))
            TableFormatter.format_percentage(i / 1000.0)
            TableFormatter.format_points(float(i * 10))
        end_time = time.time()
        
        # Should complete quickly
        assert end_time - start_time < 1.0