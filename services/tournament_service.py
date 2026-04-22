"""Tournament service for testing auction draft strategies."""

import os
from typing import Optional, Dict, Any, List, Tuple
import json
from datetime import datetime

from classes import Tournament, DraftSetup, create_strategy, AVAILABLE_STRATEGIES
from config.config_manager import ConfigManager
from data.fantasypros_loader import load_fantasypros_players
from utils.print_module import print_tournament


class TournamentService:
    """Service for running tournament simulations to test strategies."""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the tournament service.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or ConfigManager()
        self.current_tournament: Optional[Tournament] = None
        
    def run_strategy_tournament(
        self,
        strategies_to_test: Optional[List[str]] = None,
        num_simulations: int = 50,
        teams_per_strategy: int = 2,
        save_results: bool = True
    ) -> Dict[str, Any]:
        """
        Run a tournament to test different strategies.
        
        Args:
            strategies_to_test: List of strategies to test (default: all available)
            num_simulations: Number of simulations to run
            teams_per_strategy: Number of teams per strategy type
            save_results: Whether to save results to file
            
        Returns:
            Tournament results dictionary
        """
        try:
            config = self.config_manager.load_config()
            
            # Default to all available strategies
            if strategies_to_test is None:
                strategies_to_test = list(AVAILABLE_STRATEGIES.keys())
            
            # Validate strategies
            invalid_strategies = [s for s in strategies_to_test if s not in AVAILABLE_STRATEGIES]
            if invalid_strategies:
                return {
                    'success': False,
                    'error': f"Invalid strategies: {invalid_strategies}",
                    'available_strategies': list(AVAILABLE_STRATEGIES.keys())
                }
            
            # Create tournament
            self.current_tournament = Tournament(
                name=f"Strategy Comparison {datetime.now().strftime('%Y%m%d_%H%M%S')}",
                num_simulations=num_simulations,
                budget_per_team=config.budget,
                roster_size=sum(config.roster_positions.values())
            )
            
            # Load players
            players = self._load_players_for_tournament(config)
            if not players:
                return {
                    'success': False,
                    'error': "Could not load player data for tournament"
                }
            
            self.current_tournament.add_players(players)
            
            # Add strategy configurations
            for strategy_type in strategies_to_test:
                self.current_tournament.add_strategy_config(
                    strategy_type=strategy_type,
                    owner_name=strategy_type.title(),
                    num_teams=teams_per_strategy
                )
            
            # Run tournament
            print(f"Running tournament with {num_simulations} simulations...")
            print(f"Testing strategies: {', '.join(strategies_to_test)}")
            print(f"Teams per strategy: {teams_per_strategy}")
            
            results = self.current_tournament.run_tournament(parallel=True)
            
            # Save results if requested
            if save_results:
                self._save_tournament_results(results)
            
            # Add analysis
            results['analysis'] = self._analyze_tournament_results(results)
            results['success'] = True
            
            return results
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Tournament failed: {e}"
            }
    
    def run_custom_tournament(
        self,
        tournament_config: Dict[str, Any],
        save_results: bool = True
    ) -> Dict[str, Any]:
        """
        Run a custom tournament with specific configuration.
        
        Args:
            tournament_config: Custom tournament configuration
            save_results: Whether to save results
            
        Returns:
            Tournament results dictionary
        """
        try:
            config = self.config_manager.load_config()
            
            # Extract tournament parameters
            name = tournament_config.get('name', 'Custom Tournament')
            num_simulations = tournament_config.get('num_simulations', 50)
            strategies = tournament_config.get('strategies', [])
            
            # Create tournament
            self.current_tournament = Tournament(
                name=name,
                num_simulations=num_simulations,
                budget_per_team=config.budget,
                roster_size=sum(config.roster_positions.values())
            )
            
            # Load players
            players = self._load_players_for_tournament(config)
            if not players:
                return {
                    'success': False,
                    'error': "Could not load player data"
                }
            
            self.current_tournament.add_players(players)
            
            # Add custom strategy configurations
            for strategy_config in strategies:
                strategy_type = strategy_config.get('type')
                if strategy_type not in AVAILABLE_STRATEGIES:
                    continue
                
                self.current_tournament.add_strategy_config(
                    strategy_type=strategy_type,
                    owner_name=strategy_config.get('name', strategy_type.title()),
                    num_teams=strategy_config.get('num_teams', 1),
                    **strategy_config.get('parameters', {})
                )
            
            # Run tournament
            results = self.current_tournament.run_tournament(parallel=True)
            
            # Save results if requested
            if save_results:
                self._save_tournament_results(results)
            
            # Add analysis
            results['analysis'] = self._analyze_tournament_results(results)
            results['success'] = True
            
            return results
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Custom tournament failed: {e}"
            }
    
    def find_optimal_strategy(
        self,
        budget_constraints: Optional[Dict[str, float]] = None,
        position_priorities: Optional[List[str]] = None,
        risk_tolerance: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Find the optimal strategy for given constraints.
        
        Args:
            budget_constraints: Budget allocation constraints
            position_priorities: Position drafting priorities
            risk_tolerance: Risk tolerance level (0.0-1.0)
            
        Returns:
            Optimal strategy recommendation
        """
        try:
            # Test all strategies with different parameter sets
            strategy_variants = self._generate_strategy_variants(
                budget_constraints, position_priorities, risk_tolerance
            )
            
            # Run tournament with variants
            tournament_config = {
                'name': 'Optimal Strategy Search',
                'num_simulations': 30,  # Fewer sims for speed
                'strategies': strategy_variants
            }
            
            results = self.run_custom_tournament(tournament_config, save_results=False)
            
            if not results.get('success'):
                return results
            
            # Find best performing strategy
            rankings = self.current_tournament.get_strategy_rankings()
            if rankings:
                best_strategy, best_data = rankings[0]
                return {
                    'success': True,
                    'optimal_strategy': best_strategy,
                    'performance_metrics': best_data['results'],
                    'confidence_score': best_data['composite_score'],
                    'recommendation': self._generate_strategy_recommendation(best_strategy, best_data),
                    'all_rankings': rankings[:5]  # Top 5
                }
            else:
                return {
                    'success': False,
                    'error': "No strategy rankings available"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Strategy optimization failed: {e}"
            }
    
    def get_tournament_progress(self) -> Dict[str, Any]:
        """
        Get progress of current tournament.
        
        Returns:
            Progress information dictionary
        """
        if not self.current_tournament:
            return {
                'active': False,
                'message': "No tournament currently running"
            }
        
        return {
            'active': self.current_tournament.is_running,
            'progress': self.current_tournament.progress,
            'total_simulations': self.current_tournament.num_simulations,
            'completed_simulations': len(self.current_tournament.completed_drafts),
            'tournament_name': self.current_tournament.name
        }
    
    def stop_tournament(self) -> Dict[str, Any]:
        """
        Stop the current tournament.
        
        Returns:
            Status dictionary
        """
        if not self.current_tournament:
            return {
                'success': False,
                'message': "No tournament currently running"
            }
        
        # Tournament doesn't have a built-in stop method, so we just mark it
        self.current_tournament.is_running = False
        
        return {
            'success': True,
            'message': "Tournament stopped",
            'completed_simulations': len(self.current_tournament.completed_drafts)
        }
    
    def _load_players_for_tournament(self, config) -> List:
        """Load players for tournament based on config."""
        try:
            if config.data_source == "fantasypros":
                players = load_fantasypros_players(
                    data_path=config.data_path,
                    min_projected_points=config.min_projected_points
                )
                return players
            elif config.data_source == "sleeper":
                # Could implement Sleeper loading here
                print("Sleeper data source not yet implemented for tournaments")
                return []
            else:
                print(f"Unknown data source: {config.data_source}")
                return []
        except Exception as e:
            print(f"Error loading players: {e}")
            return []
    
    def _generate_strategy_variants(
        self,
        budget_constraints: Optional[Dict[str, float]],
        position_priorities: Optional[List[str]],
        risk_tolerance: Optional[float]
    ) -> List[Dict[str, Any]]:
        """Generate strategy variants for testing."""
        variants = []
        
        # Base strategies
        for strategy_type in AVAILABLE_STRATEGIES.keys():
            base_variant = {
                'type': strategy_type,
                'name': f"{strategy_type.title()}_Base",
                'num_teams': 2,
                'parameters': {}
            }
            variants.append(base_variant)
        
        # Add parameter variations if constraints provided
        if risk_tolerance is not None:
            for strategy_type in ['aggressive', 'conservative']:
                variant = {
                    'type': strategy_type,
                    'name': f"{strategy_type.title()}_Risk_{risk_tolerance:.1f}",
                    'num_teams': 1,
                    'parameters': {
                        'risk_tolerance': risk_tolerance
                    }
                }
                variants.append(variant)
        
        # Position priority variations
        if position_priorities:
            variant = {
                'type': 'value',
                'name': f"Value_Priority_{'_'.join(position_priorities[:2])}",
                'num_teams': 1,
                'parameters': {
                    'position_priorities': position_priorities
                }
            }
            variants.append(variant)
        
        return variants
    
    def _analyze_tournament_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze tournament results and provide insights."""
        if not self.current_tournament:
            return {}
        
        rankings = self.current_tournament.get_strategy_rankings()
        strategy_results = results.get('results', {})
        
        analysis = {
            'total_strategies_tested': len(strategy_results),
            'total_simulations': results.get('completed_simulations', 0),
            'best_strategy': None,
            'worst_strategy': None,
            'most_consistent': None,
            'insights': []
        }
        
        if rankings:
            # Best and worst strategies
            analysis['best_strategy'] = {
                'name': rankings[0][0],
                'win_rate': rankings[0][1]['results']['win_rate'],
                'avg_points': rankings[0][1]['results']['avg_points']
            }
            
            analysis['worst_strategy'] = {
                'name': rankings[-1][0],
                'win_rate': rankings[-1][1]['results']['win_rate'],
                'avg_points': rankings[-1][1]['results']['avg_points']
            }
            
            # Most consistent (lowest std deviation)
            most_consistent = min(rankings, key=lambda x: x[1]['results']['points_std'])
            analysis['most_consistent'] = {
                'name': most_consistent[0],
                'std_dev': most_consistent[1]['results']['points_std'],
                'avg_points': most_consistent[1]['results']['avg_points']
            }
            
            # Generate insights
            analysis['insights'] = self._generate_insights(rankings, strategy_results)
        
        return analysis
    
    def _generate_insights(self, rankings: List[Tuple[str, Dict]], strategy_results: Dict) -> List[str]:
        """Generate insights from tournament results."""
        insights = []
        
        if len(rankings) >= 2:
            best = rankings[0]
            worst = rankings[-1]
            
            win_rate_diff = best[1]['results']['win_rate'] - worst[1]['results']['win_rate']
            insights.append(f"Win rate difference between best and worst: {win_rate_diff:.1%}")
            
            points_diff = best[1]['results']['avg_points'] - worst[1]['results']['avg_points']
            insights.append(f"Average points difference: {points_diff:.1f}")
        
        # Strategy-specific insights
        for strategy_name, data in strategy_results.items():
            if data['win_rate'] > 0.4:
                insights.append(f"{strategy_name} showed strong performance with {data['win_rate']:.1%} win rate")
            elif data['win_rate'] < 0.1:
                insights.append(f"{strategy_name} struggled with only {data['win_rate']:.1%} win rate")
        
        return insights
    
    def _generate_strategy_recommendation(self, strategy_name: str, strategy_data: Dict) -> str:
        """Generate recommendation text for optimal strategy."""
        results = strategy_data['results']
        
        recommendation = f"The {strategy_name} strategy performed best with a {results['win_rate']:.1%} win rate "
        recommendation += f"and {results['avg_points']:.1f} average points. "
        
        if results['points_std'] < 50:
            recommendation += "This strategy showed good consistency. "
        elif results['points_std'] > 100:
            recommendation += "This strategy was volatile but had high upside. "
        
        recommendation += f"Consider using this strategy for similar league conditions."
        
        return recommendation
    
    def _save_tournament_results(self, results: Dict[str, Any]) -> None:
        """Save tournament results to file."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"tournament_results_{timestamp}.json"
            filepath = os.path.join("results", filename)
            
            # Ensure results directory exists
            os.makedirs("results", exist_ok=True)
            
            # Save results
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=str)
            
            print(f"Tournament results saved to {filepath}")
            
        except Exception as e:
            print(f"Error saving tournament results: {e}")


# Convenience functions
def run_strategy_tournament(
    strategies_to_test: Optional[List[str]] = None,
    num_simulations: int = 50,
    config_dir: str = "config"
) -> Dict[str, Any]:
    """
    Convenience function to run a strategy tournament.
    
    Args:
        strategies_to_test: List of strategies to test
        num_simulations: Number of simulations
        config_dir: Configuration directory
        
    Returns:
        Tournament results
    """
    config_manager = ConfigManager(config_dir)
    service = TournamentService(config_manager)
    return service.run_strategy_tournament(strategies_to_test, num_simulations)


def find_optimal_strategy(
    config_dir: str = "config",
    risk_tolerance: Optional[float] = None
) -> Dict[str, Any]:
    """
    Convenience function to find optimal strategy.
    
    Args:
        config_dir: Configuration directory
        risk_tolerance: Risk tolerance level
        
    Returns:
        Optimal strategy recommendation
    """
    config_manager = ConfigManager(config_dir)
    service = TournamentService(config_manager)
    return service.find_optimal_strategy(risk_tolerance=risk_tolerance)
