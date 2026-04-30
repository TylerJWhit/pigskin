"""Tournament class for auction draft tool."""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import copy
import statistics
import threading
import concurrent.futures
from .draft import Draft
from .auction import Auction
from .player import Player
from .team import Team
from .owner import Owner
from .strategy import create_strategy

logger = logging.getLogger(__name__)


class Tournament:
    """Runs multiple drafts to test and optimize strategies."""
    
    def __init__(
        self,
        name: str = "Strategy Tournament",
        num_simulations: int = 100,
        budget_per_team: float = 200.0,
        roster_size: int = 16
    ):
        self.name = name
        self.num_simulations = num_simulations
        self.budget_per_team = budget_per_team
        self.roster_size = roster_size
        self.created_at = datetime.now()
        
        # Tournament configuration
        self.base_players: List[Player] = []
        self.base_owners: List[Owner] = []
        self.strategy_configs: List[Dict] = []
        
        # Results
        self.completed_drafts: List[Draft] = []
        self.results: Dict[str, Dict] = {}
        self.is_running = False
        self.progress = 0
        self._lock = threading.Lock()  # Protect shared state across parallel threads
        
    def add_players(self, players: List[Player]) -> None:
        """Add base player pool for simulations."""
        self.base_players = copy.deepcopy(players)
        
    def add_strategy_config(
        self,
        strategy_type: str,
        owner_name: str,
        num_teams: int = 1,
        **strategy_params
    ) -> None:
        """Add a strategy configuration to test."""
        config = {
            'strategy_type': strategy_type,
            'owner_name': owner_name,
            'num_teams': num_teams,
            'strategy_params': strategy_params
        }
        self.strategy_configs.append(config)
        
    def run_tournament(self, parallel: bool = True) -> Dict:
        """Run the tournament simulations."""
        if not self.base_players:
            raise ValueError("No players added to tournament")
            
        if not self.strategy_configs:
            raise ValueError("No strategy configurations added")
            
        self.is_running = True
        self.progress = 0
        self.completed_drafts = []
        self.results = {}
        
        try:
            if parallel:
                self._run_parallel_simulations()
            else:
                self._run_sequential_simulations()
                
            self._analyze_results()
            return self.get_tournament_summary()
            
        finally:
            self.is_running = False
            
    def _run_parallel_simulations(self) -> None:
        """Run simulations in parallel."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            for i in range(self.num_simulations):
                future = executor.submit(self._run_single_simulation, i)
                futures.append(future)
                
            # Wait for all simulations to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    draft = future.result()
                    if draft:
                        with self._lock:
                            self.completed_drafts.append(draft)
                    with self._lock:
                        self.progress += 1
                except Exception as e:
                    logger.error("Simulation failed: %s", e)
                    with self._lock:
                        self.progress += 1
                    
    def _run_sequential_simulations(self) -> None:
        """Run simulations sequentially."""
        for i in range(self.num_simulations):
            try:
                draft = self._run_single_simulation(i)
                if draft:
                    self.completed_drafts.append(draft)
            except Exception as e:
                logger.error("Simulation %d failed: %s", i, e)
            finally:
                self.progress += 1
                
    def _run_single_simulation(self, simulation_id: int) -> Optional[Draft]:
        """Run a single draft simulation."""
        # Create draft
        draft = Draft(
            name=f"{self.name} - Simulation {simulation_id}",
            budget_per_team=self.budget_per_team,
            roster_size=self.roster_size
        )
        
        # Add players (deep copy to avoid state sharing)
        players = copy.deepcopy(self.base_players)
        draft.add_players(players)
        
        # Create teams and owners based on strategy configs
        team_counter = 0
        for config in self.strategy_configs:
            for i in range(config['num_teams']):
                owner_id = f"{config['owner_name']}_{simulation_id}_{i}"
                team_id = f"team_{team_counter}"
                
                # Create owner
                owner = Owner(
                    owner_id=owner_id,
                    name=f"{config['owner_name']} {i+1}",
                    is_human=False
                )
                draft.add_owner(owner)
                
                # Create team
                team = Team(
                    team_id=team_id,
                    owner_id=owner_id,
                    team_name=f"Team {team_counter + 1}",
                    budget=self.budget_per_team
                )
                draft.add_team(team)
                
                team_counter += 1
                
        # Start draft
        draft.start_draft()
        
        # Create auction with strategies
        auction = Auction(draft, bid_timer=1, nomination_timer=1)  # Fast timers for simulation
        
        # Configure strategies for each owner
        for config in self.strategy_configs:
            strategy = create_strategy(config['strategy_type'])
            
            # Apply custom parameters
            for param, value in config['strategy_params'].items():
                strategy.set_parameter(param, value)
                
            # Enable auto-bid for all teams of this strategy type
            for i in range(config['num_teams']):
                owner_id = f"{config['owner_name']}_{simulation_id}_{i}"
                auction.enable_auto_bid(owner_id, strategy)
                
        # Run the simulation
        auction.start_auction()
        
        # Simulate the draft by forcing nominations and completions
        max_iterations = len(players) * 2  # Safety limit
        iterations = 0
        
        while draft.status == "started" and iterations < max_iterations:
            if not draft.current_player:
                # Force nomination
                auction._auto_nominate_player()
                
            if draft.current_player:
                # Let auto-bids process for a moment
                auction._process_auto_bids()
                # Force completion after brief bidding
                auction.force_complete_auction()
                
            iterations += 1
            
        auction.stop_auction()
        
        # Mark as completed if not already
        if draft.status == "started":
            draft._complete_draft()
            
        return draft
        
    def _analyze_results(self) -> None:
        """Analyze tournament results."""
        strategy_stats = {}
        
        for draft in self.completed_drafts:
            leaderboard = draft.get_leaderboard()
            
            for rank, team_data in enumerate(leaderboard):
                team = team_data['team']
                owner_id = team.owner_id
                
                # Extract strategy type from owner name
                strategy_type = owner_id.split('_')[0]
                
                if strategy_type not in strategy_stats:
                    strategy_stats[strategy_type] = {
                        'total_points': [],
                        'total_spent': [],
                        'remaining_budget': [],
                        'roster_sizes': [],
                        'rankings': [],
                        'wins': 0,
                        'simulations': 0
                    }
                    
                stats = strategy_stats[strategy_type]
                stats['total_points'].append(team_data['projected_points'])
                stats['total_spent'].append(team_data['total_spent'])
                stats['remaining_budget'].append(team_data['remaining_budget'])
                stats['roster_sizes'].append(team_data['roster_size'])
                stats['rankings'].append(rank + 1)  # 1-based ranking
                stats['simulations'] += 1
                
                if rank == 0:  # First place
                    stats['wins'] += 1
                    
        # Calculate summary statistics
        for strategy_type, stats in strategy_stats.items():
            if stats['simulations'] > 0:
                self.results[strategy_type] = {
                    'simulations': stats['simulations'],
                    'wins': stats['wins'],
                    'win_rate': stats['wins'] / stats['simulations'],
                    'avg_points': statistics.mean(stats['total_points']),
                    'avg_spent': statistics.mean(stats['total_spent']),
                    'avg_remaining': statistics.mean(stats['remaining_budget']),
                    'avg_ranking': statistics.mean(stats['rankings']),
                    'points_std': statistics.stdev(stats['total_points']) if len(stats['total_points']) > 1 else 0,
                    'best_points': max(stats['total_points']),
                    'worst_points': min(stats['total_points']),
                    'median_ranking': statistics.median(stats['rankings'])
                }
                
    def get_tournament_summary(self) -> Dict:
        """Get tournament summary and results."""
        return {
            'tournament_name': self.name,
            'num_simulations': self.num_simulations,
            'completed_simulations': len(self.completed_drafts),
            'strategies_tested': len(self.strategy_configs),
            'results': self.results,
            'created_at': self.created_at,
            'is_running': self.is_running,
            'progress': self.progress
        }
        
    def get_strategy_rankings(self) -> List[Tuple[str, Dict]]:
        """Get strategies ranked by performance."""
        strategy_scores = []
        
        for strategy_type, results in self.results.items():
            # Calculate composite score (higher is better)
            # Weight: 40% win rate, 30% avg points, 20% avg ranking (inverted), 10% consistency
            win_rate_score = results['win_rate'] * 40
            
            # Normalize points (assume max reasonable is 1500)
            points_score = min(results['avg_points'] / 1500, 1.0) * 30
            
            # Ranking score (lower ranking is better, so invert)
            ranking_score = (1 - (results['avg_ranking'] - 1) / (len(self.strategy_configs) - 1)) * 20
            
            # Consistency score (lower std deviation is better)
            consistency_score = max(0, 1 - results['points_std'] / 100) * 10
            
            composite_score = win_rate_score + points_score + ranking_score + consistency_score
            
            strategy_scores.append((strategy_type, {
                'composite_score': composite_score,
                'results': results
            }))
            
        # Sort by composite score (descending)
        strategy_scores.sort(key=lambda x: x[1]['composite_score'], reverse=True)
        return strategy_scores
        
    def export_results(self, filepath: str) -> None:
        """Export tournament results to file."""
        import json
        
        export_data = {
            'summary': self.get_tournament_summary(),
            'rankings': [(strategy, data['results']) for strategy, data in self.get_strategy_rankings()],
            'detailed_drafts': [draft.to_dict() for draft in self.completed_drafts[:5]]  # First 5 for space
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
            
    def __str__(self) -> str:
        return f"{self.name} ({len(self.completed_drafts)}/{self.num_simulations} completed)"
        
    def __repr__(self) -> str:
        return f"Tournament(name='{self.name}', simulations={self.num_simulations})"


def run_strategy_comparison(
    players: List[Player],
    strategies_to_test: List[str],
    num_simulations: int = 50
) -> Dict:
    """Convenience function to compare different strategies."""
    tournament = Tournament(
        name="Strategy Comparison",
        num_simulations=num_simulations
    )
    
    tournament.add_players(players)
    
    for strategy_type in strategies_to_test:
        tournament.add_strategy_config(
            strategy_type=strategy_type,
            owner_name=strategy_type.title(),
            num_teams=2  # 2 teams per strategy for better statistics
        )
        
    return tournament.run_tournament()
