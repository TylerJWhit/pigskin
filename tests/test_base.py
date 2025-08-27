"""Base test utilities and fixtures for auction draft testing."""

import sys
import os
from typing import List, Dict, Any
import unittest
from unittest.mock import Mock, patch

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from classes.player import Player
from classes.team import Team
from classes.owner import Owner
from classes.draft import Draft


class BaseTestCase(unittest.TestCase):
    """Base test case with common utilities."""
    
    def setUp(self):
        """Set up common test fixtures."""
        self.test_config = {
            'budget': 200,
            'roster_positions': {
                'QB': 1,
                'RB': 2,
                'WR': 3,
                'TE': 1,
                'K': 1,
                'DST': 1
            },
            'teams': [
                {
                    'owner_name': 'Test Owner 1',
                    'team_name': 'Test Team 1',
                    'strategy': 'value'
                },
                {
                    'owner_name': 'Test Owner 2', 
                    'team_name': 'Test Team 2',
                    'strategy': 'aggressive'
                }
            ],
            'data_source': 'fantasypros',
            'data_path': 'data/data/sheets',
            'min_projected_points': 5.0
        }
        
    def create_mock_player(
        self,
        player_id: str = "test_player_1",
        name: str = "Test Player",
        position: str = "RB",
        team: str = "TEST",
        projected_points: float = 150.0,
        auction_value: float = 20.0
    ) -> Player:
        """Create a mock player for testing."""
        player = Player(
            player_id=player_id,
            name=name,
            position=position,
            team=team,
            projected_points=projected_points,
            auction_value=auction_value
        )
        return player
        
    def create_mock_team(
        self,
        team_id: str = "test_team_1",
        team_name: str = "Test Team",
        owner_id: str = "test_owner_1",
        budget: float = 200.0
    ) -> Team:
        """Create a mock team for testing."""
        team = Team(
            team_id=team_id,
            team_name=team_name,
            owner_id=owner_id,
            budget=budget
        )
        return team
        
    def create_mock_owner(
        self,
        owner_id: str = "test_owner_1",
        name: str = "Test Owner",
        email: str = "test@example.com",
        is_human: bool = True
    ) -> Owner:
        """Create a mock owner for testing."""
        owner = Owner(
            owner_id=owner_id,
            name=name,
            email=email,
            is_human=is_human
        )
        return owner
    
    def assertBetween(self, value, min_val, max_val, msg=None):
        """Assert that value is between min_val and max_val (inclusive)."""
        if not (min_val <= value <= max_val):
            raise AssertionError(f"{value} is not between {min_val} and {max_val}")
    
    def create_mock_strategy(self, strategy_type: str = 'value'):
        """Create a mock strategy for testing."""
        from strategies import create_strategy
        return create_strategy(strategy_type)
        
    def create_mock_draft(
        self,
        name: str = "Test Draft",
        budget_per_team: float = 200.0,
        roster_size: int = 15
    ) -> Draft:
        """Create a mock draft for testing."""
        draft = Draft(
            name=name,
            budget_per_team=budget_per_team,
            roster_size=roster_size
        )
        return draft
        
    def create_test_player_pool(self, count: int = 50) -> List[Player]:
        """Create a pool of test players."""
        players = []
        positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DST']
        teams = ['NE', 'GB', 'KC', 'BUF', 'TB', 'SF', 'LAR', 'DAL']
        
        for i in range(count):
            position = positions[i % len(positions)]
            team = teams[i % len(teams)]
            
            # Vary the quality of players
            if i < 10:  # Elite players
                projected_points = 250.0 + (i * 10)
                auction_value = 40.0 + (i * 5)
            elif i < 25:  # Good players
                projected_points = 150.0 + (i * 5)
                auction_value = 20.0 + (i * 2)
            else:  # Average/bench players
                projected_points = 80.0 + (i * 2)
                auction_value = 5.0 + i
            
            player = self.create_mock_player(
                player_id=f"test_player_{i}",
                name=f"Test Player {i}",
                position=position,
                team=team,
                projected_points=projected_points,
                auction_value=auction_value
            )
            players.append(player)
            
        return players


class TestDataGenerator:
    """Generate test data for various test scenarios."""
    
    @staticmethod
    def create_test_players(count: int = 50) -> List[Player]:
        """Create a list of test players."""
        players = []
        positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DST']
        teams = ['NE', 'GB', 'KC', 'BUF', 'TB', 'SF', 'LAR', 'DAL']
        
        for i in range(count):
            position = positions[i % len(positions)]
            team = teams[i % len(teams)]
            
            # Vary the quality of players
            if i < 10:  # Elite players
                projected_points = 250.0 + (i * 10)
                auction_value = 40.0 + (i * 5)
            elif i < 25:  # Good players
                projected_points = 150.0 + (i * 5)
                auction_value = 20.0 + (i * 2)
            else:  # Average/bench players
                projected_points = 80.0 + (i * 2)
                auction_value = 5.0 + i
            
            player = Player(
                player_id=f"test_player_{i}",
                name=f"Test Player {i}",
                position=position,
                team=team,
                projected_points=projected_points,
                auction_value=auction_value
            )
            players.append(player)
            
        return players
    
    @staticmethod
    def generate_fantasy_pros_data() -> Dict[str, Any]:
        """Generate mock FantasyPros data."""
        return {
            'players': [
                {
                    'name': 'Josh Allen',
                    'position': 'QB',
                    'team': 'BUF',
                    'projected_points': 350.0,
                    'auction_value': 45.0
                },
                {
                    'name': 'Christian McCaffrey',
                    'position': 'RB', 
                    'team': 'SF',
                    'projected_points': 320.0,
                    'auction_value': 65.0
                },
                {
                    'name': 'Cooper Kupp',
                    'position': 'WR',
                    'team': 'LAR',
                    'projected_points': 300.0,
                    'auction_value': 55.0
                }
            ]
        }
    
    @staticmethod
    def generate_sleeper_data() -> Dict[str, Any]:
        """Generate mock Sleeper API data."""
        return {
            'players': {
                '4046': {
                    'full_name': 'Josh Allen',
                    'position': 'QB',
                    'team': 'BUF',
                    'player_id': '4046',
                    'active': True
                },
                '4035': {
                    'full_name': 'Christian McCaffrey',
                    'position': 'RB',
                    'team': 'SF', 
                    'player_id': '4035',
                    'active': True
                }
            }
        }
    
    @staticmethod
    def generate_auction_state(num_teams: int = 10, round_num: int = 5) -> Dict[str, Any]:
        """Generate mock auction state."""
        teams = []
        for i in range(num_teams):
            teams.append({
                'team_id': f'team_{i}',
                'team_name': f'Team {i}',
                'owner_id': f'owner_{i}',
                'budget': 200.0 - (round_num * 10),  # Simulate budget depletion
                'roster_size': round_num,
                'strategy': 'value'
            })
        
        return {
            'teams': teams,
            'current_round': round_num,
            'players_drafted': round_num * num_teams,
            'players_remaining': 300 - (round_num * num_teams)
        }


def skip_if_no_network(test_func):
    """Decorator to skip tests if no network connection."""
    def wrapper(*args, **kwargs):
        try:
            # Simple network check without external dependencies
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return test_func(*args, **kwargs)
        except OSError:
            raise unittest.SkipTest("No network connection available")
    return wrapper


def skip_if_no_data_files(test_func):
    """Decorator to skip tests if test data files are missing."""
    def wrapper(*args, **kwargs):
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'data')
        if not os.path.exists(data_dir):
            raise unittest.SkipTest("Test data files not available")
        return test_func(*args, **kwargs)
    return wrapper


def run_test_suite():
    """Run the complete test suite."""
    # Discover and run all tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(__file__)
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_test_suite()
    sys.exit(0 if success else 1)
