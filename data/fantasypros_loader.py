"""FantasyPros data loader for auction draft tool."""

import csv
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import ValidationError

from classes.player import Player

logger = logging.getLogger(__name__)


class FantasyProsLoader:
    """Loads player data from FantasyPros CSV files."""
    
    def __init__(self, data_path: str = "data/sheets", total_budget: float = 2400.0):
        """
        Initialize the FantasyPros loader.
        
        Args:
            data_path: Path to the directory containing CSV files
        """
        _resolved = Path(data_path).resolve()
        _project_root = Path(__file__).resolve().parents[1]
        _raw = Path(data_path)
        # Block traversal via '..' components that escape the project root
        if '..' in _raw.parts and not _resolved.is_relative_to(_project_root):
            raise ValueError("Invalid data path: access outside allowed directory")
        # Block exact sensitive system directories (not their subdirectories, to allow test tmp dirs)
        _sensitive_exact = [Path('/etc'), Path('/proc'), Path('/sys'), Path('/root'),
                            Path('/boot'), Path('/dev'), Path('/tmp')]  # nosec B108
        if _resolved in _sensitive_exact:
            raise ValueError("Invalid data path: access outside allowed directory")
        # Block paths under sensitive directories (except /tmp which is used in tests)
        for s in [Path('/etc'), Path('/proc'), Path('/sys'), Path('/root'), Path('/boot'), Path('/dev')]:
            if _resolved.is_relative_to(s):
                raise ValueError("Invalid data path: access outside allowed directory")
        self.data_path = str(_resolved)
        self.total_budget = total_budget
        self.position_files = {
            'QB': 'QB.csv',
            'RB': 'RB.csv', 
            'WR': 'WR.csv',
            'TE': 'TE.csv',
            'K': 'K.csv',
            'DST': 'DST.csv'
        }
        
    def load_position_data(self, position: str) -> List[Player]:
        """
        Load data for a specific position.
        
        Args:
            position: Position to load (QB, RB, WR, TE, K, DST)
            
        Returns:
            List of validated Player objects
        """
        if position not in self.position_files:
            raise ValueError(f"Unknown position: {position}")
            
        file_path = os.path.join(self.data_path, self.position_files[position])
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Data file not found: {file_path}")
            
        players = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    # Skip empty rows or header-like rows
                    player_name = row.get('Player', '').strip()
                    if not player_name or player_name == ' ' or not player_name:
                        continue
                        
                    # Extract player data
                    player_data = self._parse_player_row(row, position)
                    if player_data:
                        players.append(player_data)
                        
        except Exception as e:
            logger.error("Error loading %s data: %s", position, e)
            
        return players
        
    def _parse_player_row(self, row: Dict[str, str], position: str) -> Optional[Player]:
        """
        Parse a single player row from CSV.
        
        Args:
            row: CSV row as dictionary
            position: Player position
            
        Returns:
            Validated Player object or None if invalid
        """
        try:
            player_name = row.get('Player', '').strip()
            team = row.get('Team', '').strip()
            
            if not player_name or player_name == ' ':
                return None
                
            # Get fantasy points (FPTS column)
            fpts_str = row.get('FPTS', '0').strip()
            if not fpts_str or fpts_str == '':
                projected_points = 0.0
            else:
                # Remove commas and convert to float
                projected_points = float(fpts_str.replace(',', ''))
                
            # Generate a unique player ID
            player_id = self._generate_player_id(player_name, team, position)

            return Player(
                player_id=player_id,
                name=player_name,
                position=position,
                team=team,
                projected_points=projected_points,
                auction_value=0.0,
                bye_week=None,
            )
            
        except (ValueError, TypeError, ValidationError) as e:
            logger.warning("Skipping invalid player row: %s", e)
            return None
            
    def _generate_player_id(self, name: str, team: str, position: str) -> str:
        """Generate a unique player ID."""
        # Clean name for ID generation
        clean_name = name.replace(' ', '_').replace("'", "").replace(".", "").lower()
        return f"{position.lower()}_{team.lower()}_{clean_name}"
        
    def load_all_players(self, min_projected_points: float = 0.0) -> List[Player]:
        """
        Load all players from all position files.
        
        Args:
            min_projected_points: Minimum projected points to include player
            
        Returns:
            List of Player objects
        """
        all_players = []
        
        for position in self.position_files.keys():
            try:
                position_data = self.load_position_data(position)
                
                for player in position_data:
                    if player.projected_points >= min_projected_points:
                        all_players.append(player)
                        
            except Exception as e:
                logger.error("Error loading %s players: %s", position, e)
                continue
        
        # Calculate auction values for all players
        self.calculate_auction_values(all_players, total_budget=self.total_budget)
                
        return all_players
        
    def get_top_players(self, position: str, count: int = 50) -> List[Player]:
        """
        Get top players for a position by projected points.
        
        Args:
            position: Position to get players for
            count: Number of top players to return
            
        Returns:
            List of top Player objects
        """
        players = self.load_position_data(position)
        # Sort by projected points (descending)
        players.sort(key=lambda p: p.projected_points, reverse=True)
        return players[:count]
        
    def get_player_by_name(self, name: str, position: Optional[str] = None) -> Optional[Player]:
        """
        Find a player by name, optionally filtered by position.
        
        Args:
            name: Player name to search for
            position: Optional position filter
            
        Returns:
            Player object or None if not found
        """
        positions_to_search = [position] if position else list(self.position_files.keys())
        
        for pos in positions_to_search:
            try:
                players = self.load_position_data(pos)
                for player in players:
                    if player.name.lower() == name.lower():
                        return player
            except Exception:
                continue
                
        return None
        
    def calculate_auction_values(
        self,
        players: List[Player],
        total_budget: float = 2400.0,
        value_distribution: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Calculate auction values for players based on projected points.
        Modifies players in-place.
        
        Args:
            players: List of Player objects
            total_budget: Total budget across all teams (12 teams * $200 = $2400)
            value_distribution: Custom position value weights
        """
        if not players:
            return
            
        # Default position weights for value distribution
        if value_distribution is None:
            value_distribution = {
                'QB': 0.15,  # 15% of budget for QBs
                'RB': 0.35,  # 35% of budget for RBs  
                'WR': 0.35,  # 35% of budget for WRs
                'TE': 0.10,  # 10% of budget for TEs
                'K': 0.025,  # 2.5% of budget for Kickers
                'DST': 0.025 # 2.5% of budget for Defenses
            }
            
        # Group players by position
        players_by_position = {}
        for player in players:
            if player.position not in players_by_position:
                players_by_position[player.position] = []
            players_by_position[player.position].append(player)
            
        # Calculate auction values for each position
        for position, position_players in players_by_position.items():
            if position not in value_distribution:
                continue
                
            # Calculate total points for this position
            total_points = sum(p.projected_points for p in position_players)
            if total_points == 0:
                continue
                
            # Budget allocated to this position
            position_budget = total_budget * value_distribution[position]
            
            # Reserve some budget for minimum bids ($1 per player)
            reserve_budget = len(position_players) * 1.0
            usable_budget = max(0, position_budget - reserve_budget)
            
            # Calculate value per point for this position
            if total_points > 0:
                value_per_point = usable_budget / total_points
            else:
                value_per_point = 0
                
            # Assign auction values
            for player in position_players:
                base_value = player.projected_points * value_per_point + 1.0  # +$1 minimum
                
                # Apply position-specific adjustments
                position_multipliers = {
                    'QB': 1.0,
                    'RB': 1.1,   # Slight premium for RB scarcity
                    'WR': 1.05,  # Small premium for WR
                    'TE': 1.0,
                    'K': 0.8,    # Discount for kickers
                    'DST': 0.8   # Discount for defenses
                }
                
                multiplier = position_multipliers.get(position, 1.0)
                player.auction_value = max(1.0, base_value * multiplier)
                
    def export_player_summary(self, output_file: str = "player_summary.csv") -> None:
        """Export a summary of all players to CSV."""
        players = self.load_all_players()
        
        # Calculate auction values
        self.calculate_auction_values(players)
        
        with open(output_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            
            # Write header
            writer.writerow([
                'Player', 'Position', 'Team', 'Projected Points', 
                'Auction Value', 'Value Per Point'
            ])
            
            # Sort by auction value (descending)
            players.sort(key=lambda p: p.auction_value, reverse=True)
            
            # Write player data
            for player in players:
                value_per_point = (player.auction_value / player.projected_points 
                                 if player.projected_points > 0 else 0)
                
                writer.writerow([
                    player.name,
                    player.position,
                    player.team,
                    round(player.projected_points, 1),
                    round(player.auction_value, 2),
                    round(value_per_point, 3)
                ])
                
        logger.info("Player summary exported to %s", output_file)
        
    def get_data_summary(self) -> Dict[str, int]:
        """Get summary statistics about the loaded data."""
        summary = {}
        
        for position in self.position_files.keys():
            try:
                players = self.load_position_data(position)
                summary[position] = len(players)
            except Exception:
                summary[position] = 0
                
        summary['total'] = sum(summary.values())
        return summary


# Convenience functions for easy importing
def _parse_csv_file(csv_content: str, position: str) -> List[Player]:
    """Parse a CSV string for a given position and return a list of Player objects.

    Rows with non-numeric projected_points or auction_value are silently skipped.
    """
    import io
    loader = FantasyProsLoader()
    players = []
    reader = csv.DictReader(io.StringIO(csv_content))
    for row in reader:
        player = loader._parse_player_row(row, position)
        if player:
            players.append(player)
    return players


def load_fantasypros_players(
    data_path: str = "data/sheets",
    min_projected_points: float = 0.0
) -> List[Player]:
    """
    Convenience function to load all FantasyPros players.
    
    Args:
        data_path: Path to CSV files directory
        min_projected_points: Minimum projected points threshold
        
    Returns:
        List of Player objects with auction values calculated
    """
    try:
        loader = FantasyProsLoader(data_path)
    except ValueError:
        logger.warning("load_fantasypros_players: invalid data path rejected")
        return []
    players = loader.load_all_players(min_projected_points)
    loader.calculate_auction_values(players)
    return players


def get_position_rankings(
    position: str,
    data_path: str = "data/sheets",
    top_n: int = 50
) -> List[Dict]:
    """
    Get top players for a specific position.
    
    Args:
        position: Position to get rankings for
        data_path: Path to CSV files directory
        top_n: Number of top players to return
        
    Returns:
        List of player dictionaries sorted by projected points
    """
    try:
        loader = FantasyProsLoader(data_path)
    except ValueError:
        logger.warning("get_position_rankings: invalid data path rejected")
        return []
    return loader.get_top_players(position, top_n)
