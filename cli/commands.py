"""
Command implementations for the Auction Draft CLI.

This module contains the core command logic separated from the main CLI interface.
"""

from typing import Dict, List, Optional
import asyncio
import time
from classes import Draft, Team, Owner, create_strategy, AVAILABLE_STRATEGIES
from data.fantasypros_loader import FantasyProsLoader
from config.config_manager import ConfigManager
from api.sleeper_api import SleeperAPI
from services.sleeper_draft_service import SleeperDraftService


class CommandProcessor:
    """Processes individual CLI commands with enhanced functionality."""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None, sleeper_api: Optional[SleeperAPI] = None):
        self.config_manager = config_manager if config_manager is not None else ConfigManager()
        self.sleeper_api = sleeper_api if sleeper_api is not None else SleeperAPI()
        self.sleeper_draft_service = SleeperDraftService(sleeper_api=self.sleeper_api)
    
    def get_bid_recommendation_detailed(self, player_name: str, current_bid: float = 1.0, sleeper_draft_id: Optional[str] = None) -> Dict:
        """Get detailed bid recommendation with enhanced display."""
        print(f"Analyzing '{player_name}' for bid recommendation...")
        
        # Try to get sleeper_draft_id from config if not provided
        if not sleeper_draft_id:
            try:
                config = self.config_manager.load_config()
                sleeper_draft_id = getattr(config, 'sleeper_draft_id', None)
                if sleeper_draft_id:
                    print(f"Using Sleeper draft ID from config: {sleeper_draft_id}")
            except Exception:
                pass
        
        # Get the recommendation with optional Sleeper context
        from services.bid_recommendation_service import BidRecommendationService
        service = BidRecommendationService(self.config_manager)
        result = service.recommend_bid(player_name, current_bid, sleeper_draft_id=sleeper_draft_id)
        
        if not result.get('success', False):
            return {
                'success': False,
                'error': result.get('error', 'Failed to get recommendation')
            }
        
        # Enhance with additional context
        enhanced_result = result.copy()
        
        # Add bid strategy context
        bid_diff = result['bid_difference']
        if bid_diff > 10:
            enhanced_result['recommendation_level'] = 'STRONG BUY'
        elif bid_diff > 5:
            enhanced_result['recommendation_level'] = 'BUY'
        elif bid_diff > 0:
            enhanced_result['recommendation_level'] = 'WEAK BUY'
        else:
            enhanced_result['recommendation_level'] = 'PASS'
        
        # Add value assessment
        value_ratio = result['auction_value'] / max(result['recommended_bid'], 1)
        if value_ratio > 1.5:
            enhanced_result['value_assessment'] = 'EXCELLENT VALUE'
        elif value_ratio > 1.2:
            enhanced_result['value_assessment'] = 'GOOD VALUE'
        elif value_ratio > 0.9:
            enhanced_result['value_assessment'] = 'FAIR VALUE'
        else:
            enhanced_result['value_assessment'] = 'OVERPRICED'
            
        return enhanced_result
    
    def run_enhanced_mock_draft(self, strategy, num_teams: int = 10) -> Dict:
        """Run a mock draft with enhanced reporting."""
        print("Initializing mock draft simulation...")
        
        try:
            # Handle both single strategy and multiple strategies
            if isinstance(strategy, str):
                strategies = [strategy]
                if strategy not in AVAILABLE_STRATEGIES:
                    return {
                        'success': False,
                        'error': f"Invalid strategy. Available: {', '.join(AVAILABLE_STRATEGIES)}"
                    }
            else:
                strategies = strategy
                invalid_strategies = [s for s in strategies if s not in AVAILABLE_STRATEGIES]
                if invalid_strategies:
                    return {
                        'success': False,
                        'error': f"Invalid strategies: {', '.join(invalid_strategies)}. Available: {', '.join(AVAILABLE_STRATEGIES)}"
                    }
            
            # Load configuration and data
            config = self.config_manager.load_config()
            loader = FantasyProsLoader(config.data_path)
            players = loader.load_all_players()
            
            print(f"Loaded {len(players)} players from FantasyPros")
            
            # Create draft
            draft = self._create_mock_draft(config, players, strategies, num_teams)
            
            # Run simulation
            # For multiple strategies, use the first one for simulation metadata
            simulation_strategy = strategies[0] if isinstance(strategies, list) else strategies
            simulation_results = self._run_detailed_simulation(draft, simulation_strategy)
            
            # Extract winner and team results for tournament
            winner_strategy = None
            winner_points = 0
            team_results = []
            
            if simulation_results:
                # Find the team with the highest projected points
                best_team = None
                best_points = 0
                
                for team in draft.teams:
                    total_points = 0
                    for player in team.roster:
                        points = getattr(player, 'projected_points', 0)
                        if points > 0:
                            total_points += points
                    
                    team_results.append({
                        'team_name': team.team_name,
                        'strategy': team.strategy.name if team.strategy else 'Unknown',
                        'total_points': total_points,
                        'final_budget': team.budget,
                        'roster_size': len(team.roster)
                    })
                    
                    if total_points > best_points:
                        best_points = total_points
                        best_team = team
                
                if best_team:
                    winner_strategy = best_team.strategy.name if best_team.strategy else 'Unknown'
                    winner_points = best_points
            
            return {
                'success': True,
                'draft': draft,
                'simulation_results': simulation_results,
                'strategy': strategies,
                'num_teams': num_teams,
                'winner_strategy': winner_strategy,
                'winner_points': winner_points,
                'team_results': team_results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Mock draft failed: {str(e)}"
            }
    
    def run_elimination_tournament(self, rounds_per_group: int = 10, teams_per_draft: int = 10, verbose: bool = False) -> Dict:
        """Run a proper elimination tournament.
        
        Args:
            rounds_per_group: Number of drafts to run for each group of strategies
            teams_per_draft: Number of teams per draft (strategies duplicated as needed)
            verbose: Whether to show detailed output
        """
        print("Starting elimination tournament with all available strategies...")
        print(f"Tournament format: {teams_per_draft} teams per draft, {rounds_per_group} rounds per group")
        
        # Use AVAILABLE_STRATEGIES so dynamically-registered strategies are included (#161)
        all_strategies = list(AVAILABLE_STRATEGIES.keys())

        print(f"Available strategies: {', '.join(all_strategies)}")
        
        return self._run_elimination_rounds(all_strategies, rounds_per_group, teams_per_draft, verbose)
    
    def _run_elimination_rounds(self, strategies: List[str], rounds_per_group: int, teams_per_draft: int, verbose: bool) -> Dict:
        """Run elimination rounds until we have a winner."""
        round_number = 1
        current_strategies = strategies.copy()
        
        while len(current_strategies) > 1:
            print(f"\n=== ELIMINATION ROUND {round_number} ===")
            print(f"Competing strategies: {len(current_strategies)}")
            
            # Create groups for this round
            groups = self._create_tournament_pools(current_strategies, teams_per_draft)
            
            print(f"Created {len(groups)} groups of {teams_per_draft} teams each")
            
            # Run rounds for each group
            round_winners = []
            for group_num, group_strategies in enumerate(groups, 1):
                print(f"\nGROUP {group_num}/{len(groups)}: {', '.join(set(group_strategies))}")
                print(f"Running {rounds_per_group} drafts...")
                
                # Track performance across multiple drafts
                group_stats = {}
                for strategy in set(group_strategies):
                    group_stats[strategy] = {
                        'wins': 0,
                        'total_points': 0,
                        'drafts': 0
                    }
                
                # Run multiple drafts for this group
                for draft_num in range(1, rounds_per_group + 1):
                    if verbose:
                        print(f"   Draft {draft_num}/{rounds_per_group}:", end=" ")
                    else:
                        print(f"   Draft {draft_num}/{rounds_per_group}...", end=" ")
                    
                    draft_result = self.run_enhanced_mock_draft(group_strategies, teams_per_draft)
                    
                    if draft_result.get('success', False):
                        winner_strategy = draft_result.get('winner_strategy', 'unknown')
                        winner_points = draft_result.get('winner_points', 0)
                        
                        if verbose:
                            print(f"Winner: {winner_strategy} ({winner_points:.1f} pts)")
                        else:
                            print("✓")
                        
                        # Update stats
                        if winner_strategy in group_stats:
                            group_stats[winner_strategy]['wins'] += 1
                        
                        # Update all participants' points and draft counts
                        for team_result in draft_result.get('team_results', []):
                            strategy_name = team_result.get('strategy', 'unknown')
                            points = team_result.get('total_points', 0)
                            if strategy_name in group_stats:
                                group_stats[strategy_name]['total_points'] += points
                                group_stats[strategy_name]['drafts'] += 1
                    else:
                        print(f"Failed: {draft_result.get('error', 'Unknown error')}")
                
                # Determine group winner (most wins, then highest avg points)
                group_winner = max(group_stats.keys(), 
                                 key=lambda s: (group_stats[s]['wins'], 
                                              group_stats[s]['total_points'] / max(1, group_stats[s]['drafts'])))
                
                round_winners.append(group_winner)
                wins = group_stats[group_winner]['wins']
                avg_points = group_stats[group_winner]['total_points'] / max(1, group_stats[group_winner]['drafts'])
                print(f"   GROUP {group_num} WINNER: {group_winner} ({wins}/{rounds_per_group} wins, {avg_points:.1f} avg pts)")
            
            # Advance winners to next round
            current_strategies = round_winners
            round_number += 1
            
            if len(current_strategies) == 1:
                break
        
        # Tournament complete
        tournament_winner = current_strategies[0] if current_strategies else "No winner"
        print(f"\n🏆 TOURNAMENT CHAMPION: {tournament_winner}")
        
        return {
            'success': True,
            'tournament_winner': tournament_winner,
            'total_rounds': round_number - 1
        }

    def _run_comprehensive_statistical_tournament(self, strategies: List[str], teams_per_draft: int = 10, verbose: bool = False) -> Dict:
        """Run comprehensive tournament with statistical significance (10 runs per group + championship)."""
        print(f"\nStarting comprehensive statistical tournament with {len(strategies)} strategies")
        print(f"Format: {teams_per_draft} teams per draft, 10 runs per group")
        
        all_results = []
        phase_1_results = {}
        
        # PHASE 1: Group all strategies in pools of 10, run each pool 10 times
        print("\n=== PHASE 1: QUALIFYING ROUNDS ===")
        print(f"Testing all {len(strategies)} strategies in groups of {teams_per_draft}")
        
        # Create groups of strategies
        strategy_groups = self._create_tournament_pools(strategies, teams_per_draft)
        
        for group_idx, group_strategies in enumerate(strategy_groups, 1):
            print(f"\nGROUP {group_idx}/{len(strategy_groups)}: {', '.join(group_strategies)}")
            print("   Running 10 drafts for statistical significance...")
            
            group_stats = {}
            for strategy in group_strategies:
                group_stats[strategy] = {
                    'wins': 0,
                    'total_points': 0,
                    'total_spent': 0,
                    'simulations': 0,
                    'points_history': []
                }
            
            # Run 10 drafts for this group
            for run_num in range(1, 11):
                if verbose:
                    print(f"     Draft {run_num}/10:", end=" ")
                else:
                    print(f"     Draft {run_num}/10...", end=" ")
                
                draft_result = self.run_enhanced_mock_draft(group_strategies, len(group_strategies))
                
                if draft_result.get('success', False):
                    # Process teams and update stats - get teams from draft object
                    draft = draft_result.get('draft')
                    teams = []
                    
                    if draft and hasattr(draft, 'teams'):
                        # Convert draft.teams to the expected format
                        for team in draft.teams:
                            team_data = {
                                'strategy': team.strategy.name if team.strategy else 'Unknown',
                                'points': team.get_starter_projected_points(),  # Use starter-only points
                                'spent': team.get_total_spent(),
                                'roster_size': len(team.roster)  # Changed from team.players to team.roster
                            }
                            teams.append(team_data)
                    
                    if teams:
                        # Find winner and update all team stats
                        best_points = 0
                        winner_strategy = None
                        
                        if verbose:
                            print("\n       Team Results:")
                        
                        for team in teams:
                            strategy_name = team.get('strategy', '')
                            strategy_key = self._map_strategy_name_to_key(strategy_name)
                            
                            if strategy_key in group_stats:
                                stats = group_stats[strategy_key]
                                points = team.get('points', 0)  # Changed from projected_points to points
                                spent = team.get('spent', 0)    # Changed from total_spent to spent
                                roster_size = team.get('roster_size', 0)
                                
                                stats['simulations'] += 1
                                stats['total_points'] += points
                                stats['total_spent'] += spent
                                stats['points_history'].append(points)
                                
                                if verbose:
                                    print(f"         {strategy_key}: {points:.1f} pts, ${spent:.0f} spent, {roster_size} players")
                                
                                if points > best_points:
                                    best_points = points
                                    winner_strategy = strategy_key
                        
                        # Award win to best strategy in this draft
                        if winner_strategy and winner_strategy in group_stats:
                            group_stats[winner_strategy]['wins'] += 1
                            if verbose:
                                print(f"       🏆 Winner: {winner_strategy} ({best_points:.1f} pts)")
                            else:
                                print(f"Winner: {winner_strategy} ({best_points:.1f} pts)")
                        else:
                            print("No winner determined")
                    else:
                        print("No team data")
                else:
                    print(f"Failed: {draft_result.get('error', 'Unknown error')}")
                
                all_results.append(draft_result)
            
            # Calculate group statistics and find group winners
            print(f"\n   GROUP {group_idx} RESULTS:")
            group_rankings = []
            for strategy_key, stats in group_stats.items():
                if stats['simulations'] > 0:
                    avg_points = stats['total_points'] / stats['simulations']
                    avg_spent = stats['total_spent'] / stats['simulations']
                    win_rate = stats['wins'] / stats['simulations']
                    efficiency = avg_points / max(avg_spent, 1)
                    
                    # Calculate variance for statistical significance
                    points_variance = 0
                    if len(stats['points_history']) > 1:
                        mean_points = avg_points
                        points_variance = sum((p - mean_points) ** 2 for p in stats['points_history']) / len(stats['points_history'])
                    
                    group_rankings.append({
                        'strategy': strategy_key,
                        'avg_points': avg_points,
                        'win_rate': win_rate,
                        'wins': stats['wins'],
                        'avg_spent': avg_spent,
                        'efficiency': efficiency,
                        'variance': points_variance,
                        'simulations': stats['simulations']
                    })
                    
                    print(f"     {strategy_key}: {win_rate:.1%} wins ({stats['wins']}/10), {avg_points:.1f} avg pts")
            
            # Sort by win rate, then by average points
            group_rankings.sort(key=lambda x: (x['win_rate'], x['avg_points']), reverse=True)
            
            # Take top performer from each group for championship
            if group_rankings:
                group_winner = group_rankings[0]
                phase_1_results[f"group_{group_idx}_winner"] = group_winner
                print(f"   GROUP {group_idx} CHAMPION: {group_winner['strategy'].upper()}")
        
        # PHASE 2: Championship round with group winners
        champions = [result['strategy'] for result in phase_1_results.values()]
        
        # Skip championship if only one group (no meaningful competition)
        if len(champions) < 2:
            print("\n=== TOURNAMENT COMPLETE ===")
            print(f"Only one group competed, champion is: {champions[0] if champions else 'No winner'}")
            
            return {
                'success': True,
                'tournament_winner': champions[0] if champions else None,
                'phase_1_results': phase_1_results,
                'championship_results': None,
                'message': 'Single group tournament - no championship round needed'
            }
        
        print("\n=== PHASE 2: CHAMPIONSHIP ROUND ===")
        print(f"Champions from each group: {', '.join(champions)}")
        print("Running 10 championship drafts...")
        
        # Pad to 10 teams if needed
        championship_strategies = champions.copy()
        while len(championship_strategies) < teams_per_draft:
            championship_strategies.extend(champions)
        championship_strategies = championship_strategies[:teams_per_draft]
        
        # Initialize championship stats
        championship_stats = {}
        for strategy in set(championship_strategies):
            championship_stats[strategy] = {
                'wins': 0,
                'total_points': 0,
                'total_spent': 0,
                'simulations': 0,
                'points_history': []
            }
        
        # Run 10 championship drafts
        for run_num in range(1, 11):
            if verbose:
                print(f"   Championship Draft {run_num}/10:", end=" ")
            else:
                print(f"   Championship Draft {run_num}/10...", end=" ")
            
            draft_result = self.run_enhanced_mock_draft(championship_strategies, len(championship_strategies))
            
            if draft_result.get('success', False):
                # Process teams and update stats - get teams from draft object
                draft = draft_result.get('draft')
                teams = []
                
                if draft and hasattr(draft, 'teams'):
                    # Convert draft.teams to the expected format
                    for team in draft.teams:
                        team_data = {
                            'strategy': team.strategy.name if team.strategy else 'Unknown',
                            'points': team.get_starter_projected_points(),  # Use starter-only points
                            'spent': team.get_total_spent(),
                            'roster_size': len(team.roster)  # Changed from team.players to team.roster
                        }
                        teams.append(team_data)
                
                if teams:
                    best_points = 0
                    winner_strategy = None
                    
                    if verbose:
                        print("\n     Championship Team Results:")
                    
                    for team in teams:
                        strategy_name = team.get('strategy', '')
                        strategy_key = self._map_strategy_name_to_key(strategy_name)
                        
                        if strategy_key in championship_stats:
                            stats = championship_stats[strategy_key]
                            points = team.get('points', 0)     # Changed from projected_points to points
                            spent = team.get('spent', 0)      # Changed from total_spent to spent
                            roster_size = team.get('roster_size', 0)
                            
                            stats['simulations'] += 1
                            stats['total_points'] += points
                            stats['total_spent'] += spent
                            stats['points_history'].append(points)
                            
                            if verbose:
                                print(f"       {strategy_key}: {points:.1f} pts, ${spent:.0f} spent, {roster_size} players")
                            
                            if points > best_points:
                                best_points = points
                                winner_strategy = strategy_key
                    
                    if winner_strategy:
                        championship_stats[winner_strategy]['wins'] += 1
                        if verbose:
                            print(f"     🏆 Championship Winner: {winner_strategy} ({best_points:.1f} pts)")
                        else:
                            print(f"Winner: {winner_strategy} ({best_points:.1f} pts)")
                    else:
                        print("No winner")
                else:
                    print("No teams")
            else:
                print(f"Failed: {draft_result.get('error', 'Unknown')}")
            
            all_results.append(draft_result)
        
        # Determine overall tournament champion
        championship_rankings = []
        for strategy_key, stats in championship_stats.items():
            if stats['simulations'] > 0:
                avg_points = stats['total_points'] / stats['simulations']
                avg_spent = stats['total_spent'] / stats['simulations']
                win_rate = stats['wins'] / stats['simulations']
                efficiency = avg_points / max(avg_spent, 1)
                
                championship_rankings.append({
                    'strategy': strategy_key,
                    'avg_points': avg_points,
                    'win_rate': win_rate,
                    'wins': stats['wins'],
                    'avg_spent': avg_spent,
                    'efficiency': efficiency,
                    'simulations': stats['simulations']
                })
        
        championship_rankings.sort(key=lambda x: (x['win_rate'], x['avg_points']), reverse=True)
        
        # Display championship results
        print("\n=== CHAMPIONSHIP RESULTS ===")
        for i, result in enumerate(championship_rankings, 1):
            print(f"   {i}. {result['strategy']}: {result['win_rate']:.1%} wins ({result['wins']}/10), {result['avg_points']:.1f} avg pts")
        
        tournament_champion = championship_rankings[0]['strategy'] if championship_rankings else None
        
        if tournament_champion:
            print(f"\n🏆 TOURNAMENT CHAMPION: {tournament_champion.upper()} 🏆")
            print(f"   Championship win rate: {championship_rankings[0]['win_rate']:.1%}")
            print(f"   Average points: {championship_rankings[0]['avg_points']:.1f}")
            print(f"   Total drafts: {len(all_results)}")
        
        return {
            'success': True,
            'tournament_type': 'comprehensive_statistical',
            'champion': tournament_champion,
            'phase_1_results': phase_1_results,
            'championship_results': championship_rankings,
            'total_drafts': len(all_results),
            'all_draft_results': all_results,
            'group_count': len(strategy_groups),
            'strategies_tested': len(strategies)
        }

    def run_comprehensive_tournament(self, num_rounds: int = 3, teams_per_draft: int = 10, verbose: bool = False) -> Dict:
        """Run comprehensive tournament with statistical testing (legacy method)."""
        return self.run_elimination_tournament(num_rounds, teams_per_draft, verbose)

    def _run_elimination_tournament(self, strategies: List[str], teams_per_draft: int) -> Dict:
        """Run elimination-style tournament with advancing winners."""
        print(f"\nStarting elimination tournament with {len(strategies)} strategies")
        
        all_results = []
        round_number = 1
        current_strategies = strategies.copy()
        
        # Track tournament bracket
        tournament_bracket = {
            'rounds': [],
            'champion': None,
            'total_participants': len(strategies)
        }
        
        while len(current_strategies) > 1:
            print(f"\nROUND {round_number}: {len(current_strategies)} strategies competing")
            
            # Create pools of exactly teams_per_draft strategies
            pools = self._create_tournament_pools(current_strategies, teams_per_draft)
            
            print(f"   Created {len(pools)} draft pools of {teams_per_draft} teams each")
            
            round_winners = []
            round_results = []
            
            # Run each pool
            for pool_idx, pool_strategies in enumerate(pools, 1):
                print(f"   Running Draft Pool {pool_idx}/{len(pools)}: {', '.join(pool_strategies)}")
                
                # Run mock draft with these strategies
                pool_result = self._run_elimination_draft(pool_strategies)
                
                if pool_result.get('success', False):
                    # Get the winning strategy from this pool
                    winner = pool_result['winner']
                    round_winners.append(winner)
                    round_results.append(pool_result)
                    
                    print(f"      Pool {pool_idx} Winner: {winner['strategy']}")
                    print(f"      Score: {winner['points']:.1f} pts, Efficiency: {winner['efficiency']:.2f}")
                else:
                    print(f"      Pool {pool_idx} failed: {pool_result.get('error', 'Unknown error')}")
            
            # Store round results
            tournament_bracket['rounds'].append({
                'round_number': round_number,
                'participants': current_strategies.copy(),
                'pools': pools,
                'winners': [w['strategy'] for w in round_winners],
                'detailed_results': round_results
            })
            
            all_results.extend(round_results)
            
            # Advance winners to next round
            current_strategies = [winner['strategy'] for winner in round_winners]
            
            print(f"   Round {round_number} complete! {len(current_strategies)} strategies advance")
            if current_strategies:
                print(f"   Advancing: {', '.join(current_strategies)}")
            
            round_number += 1
            
            # Safety check to prevent infinite loops
            if round_number > 10:
                print("   Maximum rounds reached, ending tournament")
                break
        
        # Determine champion
        champion = current_strategies[0] if current_strategies else None
        tournament_bracket['champion'] = champion
        
        if champion:
            print(f"\nTOURNAMENT CHAMPION: {champion.upper()}")
            print(f"Total rounds: {round_number - 1}")
            print(f"Total drafts conducted: {len(all_results)}")
        
        # Format results for consistent display
        tournament_results = {
            'success': True,
            'tournament_type': 'elimination',
            'tournament_name': 'Mock Draft Elimination Tournament',
            'champion': champion,
            'tournament_bracket': tournament_bracket,
            'rounds_completed': round_number - 1,
            'total_drafts': len(all_results),
            'all_draft_results': all_results,
            'completed_simulations': len(all_results),
            'num_simulations': len(all_results),
            'strategies_tested': len(strategies),
            'results': self._format_tournament_results_for_display(all_results, strategies)
        }
        
        return tournament_results
    
    def _run_mock_draft_tournament(self, strategies: List[str], teams_per_draft: int) -> Dict:
        """Run tournament using mock drafts in a loop."""
        print(f"\nStarting mock draft tournament with {len(strategies)} strategies")
        
        all_results = []
        round_number = 1
        current_strategies = strategies.copy()
        
        # Track tournament bracket
        tournament_bracket = {
            'rounds': [],
            'champion': None,
            'total_participants': len(strategies)
        }
        
        while len(current_strategies) > 1:
            print(f"\nROUND {round_number}: {len(current_strategies)} strategies competing")
            
            # Create pools for this round
            pools = self._create_tournament_pools(current_strategies, teams_per_draft)
            print(f"   Created {len(pools)} mock draft pools of {teams_per_draft} teams each")
            
            round_winners = []
            round_results = []
            
            # Run mock draft for each pool
            for pool_idx, pool_strategies in enumerate(pools, 1):
                print(f"   Running Mock Draft {pool_idx}/{len(pools)}: {', '.join(pool_strategies)}")
                
                # Run enhanced mock draft with these strategies
                mock_result = self.run_enhanced_mock_draft(pool_strategies, teams_per_draft)
                
                if mock_result.get('success', False):
                    # Determine winner from mock draft results
                    draft = mock_result['draft']
                    teams_sorted = sorted(draft.teams, key=lambda t: t.get_projected_points(), reverse=True)
                    
                    if teams_sorted:
                        winning_team = teams_sorted[0]
                        winner_strategy = winning_team.strategy.name if winning_team.strategy else 'Unknown'
                        
                        # Map strategy display name back to key
                        winner_key = self._map_strategy_name_to_key(winner_strategy)
                        round_winners.append(winner_key)
                        
                        pool_result = {
                            'pool_id': pool_idx,
                            'strategies': pool_strategies,
                            'winner': winner_key,
                            'winner_points': winning_team.get_projected_points(),
                            'winner_efficiency': winning_team.get_projected_points() / max(1, winning_team.get_total_spent()),
                            'teams_results': [(team.strategy.name, team.get_projected_points(), team.get_total_spent()) 
                                            for team in teams_sorted]
                        }
                        round_results.append(pool_result)
                        
                        print(f"     Winner: {winner_strategy} ({winning_team.get_projected_points():.1f} points)")
                    else:
                        print("     ERROR: No teams in mock draft result")
                else:
                    print(f"     ERROR: Mock draft failed - {mock_result.get('error', 'Unknown error')}")
            
            # Record round results
            round_info = {
                'round_number': round_number,
                'participants': current_strategies.copy(),
                'winners': round_winners.copy(),
                'pools': round_results
            }
            tournament_bracket['rounds'].append(round_info)
            all_results.extend(round_results)
            
            print(f"   Round {round_number} winners: {', '.join(round_winners)}")
            
            # Advance to next round
            current_strategies = round_winners
            round_number += 1
            
            # Safety check
            if round_number > 10:  # Prevent infinite loops
                break
        
        # Determine champion
        champion = current_strategies[0] if current_strategies else None
        tournament_bracket['champion'] = champion
        tournament_bracket['rounds_completed'] = round_number - 1
        
        print("\nTOURNAMENT COMPLETE!")
        print(f"CHAMPION: {champion}")
        print(f"Rounds completed: {round_number - 1}")
        
        return {
            'success': True,
            'champion': champion,
            'tournament_bracket': tournament_bracket,
            'all_results': all_results,
            'rounds_completed': round_number - 1,
            'total_participants': len(strategies)
        }
    
    def _map_strategy_name_to_key(self, strategy_name: str) -> str:
        """Map strategy display name back to key."""
        name_to_key = {
            'Value-Based': 'value',
            'Aggressive': 'aggressive', 
            'Conservative': 'conservative',
            'Balanced': 'balanced',
            'Sigmoid': 'sigmoid',
            'VOR': 'vor',
            'Basic': 'basic',
            'Adaptive': 'adaptive',
            'Improved Value': 'improved_value',
            'Elite Hybrid': 'elite_hybrid',
            'Value Random': 'value_random',
            'Value Smart': 'value_smart',
            'Inflation VOR': 'inflation_vor',
            'League': 'league',
            'Refined Value Random': 'refined_value_random'
        }
        return name_to_key.get(strategy_name, strategy_name.lower().replace(' ', '_'))
    
    def _create_tournament_pools(self, strategies: List[str], teams_per_draft: int) -> List[List[str]]:
        """Create pools for elimination tournament, ensuring competitive rounds."""
        pools = []
        
        # For elimination tournament, we want to respect the teams_per_draft parameter
        # When user specifies 10 teams, they want 10 teams per draft
        
        if len(strategies) <= teams_per_draft:
            # If we have fewer strategies than requested teams, create one pool with duplicates
            pool = self._create_single_pool_with_duplicates(strategies, teams_per_draft)
            pools.append(pool)
        else:
            # Split into multiple pools of exactly teams_per_draft size
            remaining_strategies = strategies.copy()
            
            while len(remaining_strategies) >= teams_per_draft:
                # Take exactly teams_per_draft strategies for this pool
                pool = remaining_strategies[:teams_per_draft]
                remaining_strategies = remaining_strategies[teams_per_draft:]
                pools.append(pool)
            
            # Handle remaining strategies (fewer than teams_per_draft)
            if remaining_strategies:
                # Add remaining strategies to the last pool or create a new one
                if pools:
                    # Merge with last pool if it won't exceed reasonable size
                    last_pool = pools[-1]
                    if len(last_pool) + len(remaining_strategies) <= teams_per_draft + 2:
                        # Extend last pool with remaining strategies
                        last_pool.extend(remaining_strategies)
                    else:
                        # Create new pool with duplicates to fill teams_per_draft
                        new_pool = self._create_single_pool_with_duplicates(remaining_strategies, teams_per_draft)
                        pools.append(new_pool)
        
        return pools
    
    def _create_single_pool_with_duplicates(self, strategies: List[str], teams_per_draft: int) -> List[str]:
        """Create a single pool with strategy duplicates to fill teams_per_draft."""
        pool = []
        
        # Add all unique strategies first
        pool.extend(strategies)
        
        # Fill remaining slots with duplicates (round-robin)
        while len(pool) < teams_per_draft:
            duplicate_strategy = strategies[len(pool) % len(strategies)]
            pool.append(duplicate_strategy)
        
        return pool
    
    def _run_elimination_draft(self, strategies: List[str], verbose: bool = False) -> Dict:
        """Run a single elimination draft with given strategies."""
        try:
            # Create draft
            draft = self._create_test_draft(len(strategies))
            
            if not draft:
                return {
                    'success': False,
                    'error': 'Failed to create draft'
                }
            
            # Import auction classes
            from classes.auction import Auction
            from classes import create_strategy
            
            # Start the draft
            draft.start_draft()
            
            # Create auction with fast timers
            auction = Auction(draft)
            
            # Assign strategies to teams and enable auto-bidding
            team_strategies = {}
            for i, team in enumerate(draft.teams):
                strategy_name = strategies[i % len(strategies)]
                strategy = create_strategy(strategy_name)
                if hasattr(strategy, 'enable_tournament_mode') and 'gridiron_sage' in strategy_name.lower():
                    strategy.enable_tournament_mode(True)
                team.set_strategy(strategy)
                auction.enable_auto_bid(team.owner_id, strategy)
                team_strategies[team.team_name] = strategy_name
            
            # Start auction
            auction.start_auction()
            
            # Run the auction simulation
            max_iterations = len(draft.available_players) * 2
            iterations = 0
            
            while (draft.status == "started" and iterations < max_iterations):
                # Force nomination if no current player
                if not draft.current_player:
                    auction._auto_nominate_player()
                
                # Let auto-bids process
                if draft.current_player:
                    for _ in range(3):  # Multiple bid rounds
                        auction._process_auto_bids()
                    auction.force_complete_auction()
                
                iterations += 1
                
                # Check if enough players drafted (teams might not complete full rosters)
                if len(draft.drafted_players) >= len(draft.teams) * 12:  # At least 12 players per team
                    break
            
            # Stop auction
            auction.stop_auction()
            
            if draft.status == "started":
                draft._complete_draft()
            
            # Determine winner (team with highest projected points)
            if not draft.teams:
                return {
                    'success': False,
                    'error': 'No teams in draft'
                }
            
            # Compile results
            team_results = []
            for team in draft.teams:
                strategy_name = team_strategies.get(team.team_name, 'unknown')
                points = team.get_projected_points()
                spent = team.get_total_spent()
                efficiency = points / spent if spent > 0 else 0
                
                team_results.append({
                    'team_name': team.team_name,
                    'strategy': strategy_name,
                    'points': points,
                    'spent': spent,
                    'efficiency': efficiency,
                    'roster_size': len(team.roster)
                })
            
            # Sort by points
            team_results.sort(key=lambda x: x['points'], reverse=True)
            
            return {
                'success': True,
                'winner': team_results[0],
                'all_teams': team_results,
                'total_players_drafted': len(draft.drafted_players),
                'iterations': iterations
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Draft simulation failed: {str(e)}"
            }
    
    def test_sleeper_connectivity(self) -> Dict:
        """Test Sleeper API with comprehensive connectivity check."""
        print("Running comprehensive Sleeper API connectivity test...")
        
        tests = []
        
        # Test 1: Basic connectivity
        print("Testing basic API connectivity...")
        try:
            players = self.sleeper_api.get_all_players()
            if players:
                tests.append({
                    'test': 'Basic Connectivity',
                    'status': 'PASS',
                    'details': f'Retrieved {len(players)} NFL players'
                })
            else:
                tests.append({
                    'test': 'Basic Connectivity',
                    'status': 'FAIL',
                    'details': 'No data returned'
                })
        except Exception as e:
            tests.append({
                'test': 'Basic Connectivity',
                'status': 'FAIL',
                'details': str(e)
            })
        
        # Test 2: Rate limiting
        print("Testing rate limiting...")
        try:
            start_time = time.time()
            for _ in range(3):
                self.sleeper_api.get_all_players()
            elapsed = time.time() - start_time
            
            tests.append({
                'test': 'Rate Limiting',
                'status': 'PASS',
                'details': f'3 requests in {elapsed:.2f}s'
            })
        except Exception as e:
            tests.append({
                'test': 'Rate Limiting',
                'status': 'FAIL',
                'details': str(e)
            })
        
        # Test 3: Data quality
        print("Testing data quality...")
        try:
            players = self.sleeper_api.get_all_players()
            if players:
                sample_player = next(iter(players.values()))
                required_fields = ['full_name', 'position', 'team']
                missing_fields = [field for field in required_fields if field not in sample_player]
                
                if not missing_fields:
                    tests.append({
                        'test': 'Data Quality',
                        'status': 'PASS',
                        'details': 'All required fields present'
                    })
                else:
                    tests.append({
                        'test': 'Data Quality',
                        'status': 'WARN',
                        'details': f'Missing fields: {missing_fields}'
                    })
            else:
                tests.append({
                    'test': 'Data Quality',
                    'status': 'FAIL',
                    'details': 'No player data available'
                })
        except Exception as e:
            tests.append({
                'test': 'Data Quality',
                'status': 'FAIL',
                'details': str(e)
            })
        
        # Overall status
        passed_tests = sum(1 for test in tests if test['status'] == 'PASS')
        total_tests = len(tests)
        
        return {
            'success': passed_tests > 0,
            'tests': tests,
            'summary': f'{passed_tests}/{total_tests} tests passed',
            'overall_status': 'HEALTHY' if passed_tests == total_tests else 'DEGRADED' if passed_tests > 0 else 'FAILED'
        }
    
    def _create_mock_draft(self, config, players: List, strategies, num_teams: int) -> Draft:
        """Create a mock draft with teams and strategy assignment."""
        # Handle strategy name for draft title
        if isinstance(strategies, list) and len(strategies) > 1:
            strategy_name = f"Mixed ({len(strategies)} strategies)"
        elif isinstance(strategies, list):
            strategy_name = strategies[0].title()
        else:
            strategy_name = strategies.title()
            strategies = [strategies]
        
        # Calculate roster size from config positions
        roster_positions = getattr(config, 'roster_positions', None)
        if roster_positions:
            roster_size = sum(roster_positions.values())
        else:
            roster_size = getattr(config, 'roster_size', 16)
        
        draft = Draft(
            name=f"Mock Draft - {strategy_name} Strategy",
            budget_per_team=getattr(config, 'budget_per_team', getattr(config, 'budget', 200)),
            roster_size=roster_size
        )
        
        draft.add_players(players)
        
        # Create teams cycling through provided strategies
        for i in range(num_teams):
            # Use provided strategies in rotation (even if just one strategy repeated)
            team_strategy = strategies[i % len(strategies)]
                
            strategy_obj = create_strategy(team_strategy)
            if hasattr(strategy_obj, 'enable_tournament_mode') and 'gridiron_sage' in team_strategy.lower():
                strategy_obj.enable_tournament_mode(True)
            owner = Owner(f"owner_{i+1}", f"Owner {i+1}", is_human=(i == 0))
            roster_config = getattr(config, 'roster_positions', None)
            team = Team(f"team_{i+1}", f"owner_{i+1}", f"Team {i+1}", 
                       budget=getattr(config, 'budget_per_team', getattr(config, 'budget', 200)),
                       roster_config=roster_config)
            team.set_strategy(strategy_obj)
            owner.assign_team(team)
            draft.add_team(team)
        
        return draft
    
    def _run_detailed_simulation(self, draft: Draft, primary_strategy: str) -> Dict:
        """Run a detailed draft simulation with proper auction mechanics."""
        print("Starting detailed auction simulation...")
        
        # Get roster size from config
        config = self.config_manager.load_config()
        total_roster_slots = sum(config.roster_positions.values())
        
        print(f"Target roster size: {total_roster_slots} players per team")
        print("Running competitive auction with strategy-based bidding...")
        
        # Import auction classes
        from classes.auction import Auction
        from classes import create_strategy
        
        # Start the draft
        draft.start_draft()
        
        # Create auction with reasonable timers for simulation
        auction = Auction(draft)
        
        # Configure strategies for each team and enable auto-bidding
        for team in draft.teams:
            # Use the strategy already assigned to the team
            if team.strategy:
                strategy = team.strategy
            else:
                # Fallback to primary strategy if no strategy assigned
                strategy = create_strategy(primary_strategy)
                team.set_strategy(strategy)
            
            # Enable auto-bidding with the team's strategy
            auction.enable_auto_bid(team.owner_id, strategy)
        
        print("Teams and strategies:")
        for team in draft.teams:
            strategy_name = team.strategy.name if team.strategy else 'None'
            print(f"  {team.team_name}: {strategy_name}")
        print()
        
        # Start auction
        auction.start_auction()
        
        # Create debug log file
        import os
        from datetime import datetime
        debug_log_dir = "/home/tezell/Documents/code/pigskin/logs"
        os.makedirs(debug_log_dir, exist_ok=True)
        debug_log_file = os.path.join(debug_log_dir, f"auction_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        def log_debug(message):
            with open(debug_log_file, 'a') as f:
                f.write(f"{message}\n")
        
        log_debug("=== AUCTION DEBUG LOG ===")
        log_debug(f"Teams: {len(draft.teams)}")
        log_debug(f"Available players: {len(draft.available_players)}")
        log_debug(f"Target roster size: {total_roster_slots}")
        
        # Log initial player pool by position
        position_counts = {}
        for player in draft.available_players:
            pos = getattr(player, 'position', 'UNKNOWN')
            position_counts[pos] = position_counts.get(pos, 0) + 1
        log_debug(f"Available players by position: {dict(position_counts)}")
        
        # Track simulation progress
        drafted_players = []
        max_iterations = len(draft.available_players) * 2  # Safety limit
        iterations = 0
        iterations_without_progress = 0
        last_total_roster_size = 0
        
        # Run the auction simulation
        while draft.status == "started" and iterations < max_iterations:
            
            # Check if all teams have complete rosters at start of each iteration
            incomplete_teams = [team for team in draft.teams if len(team.roster) < total_roster_slots]
            if not incomplete_teams:
                print("All teams have complete rosters, ending auction...")
                break  # All teams have complete rosters
                
            # Emergency termination: if auction has run too long, force completion
            if iterations > 300:  # Reduced from 500 for faster completion
                print(f"Auction reached iteration limit ({iterations}), forcing completion...")
                # Fill remaining slots with minimum bids for any team that needs players
                for team in incomplete_teams:
                    while len(team.roster) < total_roster_slots and team.budget >= 1:
                        # Find cheapest available player
                        available_players = [p for p in draft.available_players if not p.is_drafted]
                        if available_players:
                            cheapest_player = min(available_players, key=lambda p: getattr(p, 'auction_value', 1.0))
                            cheapest_player.mark_as_drafted(1.0, team.owner_id)
                            team.roster.append(cheapest_player)
                            team.budget -= 1.0
                            if cheapest_player in draft.available_players:
                                draft.available_players.remove(cheapest_player)
                        else:
                            break
                break
            
            # Check if all teams have complete rosters at start of each iteration
            incomplete_teams = [team for team in draft.teams if len(team.roster) < total_roster_slots]
            if not incomplete_teams:
                print("All teams have complete rosters, ending auction...")
                break  # All teams have complete rosters
            
            # Check if teams can still afford to nominate players to complete rosters
            # Use $1 per slot since minimum bid is $1
            teams_that_can_continue = []
            for team in incomplete_teams:
                remaining_slots = total_roster_slots - len(team.roster)
                
                # Budget logic: need $1 per remaining slot since minimum bid is $1
                min_budget_needed = remaining_slots * 1.0
                
                if team.budget >= min_budget_needed:
                    teams_that_can_continue.append(team)
            
            if not teams_that_can_continue:
                print("\n=== DEBUGGING: Teams cannot afford to complete rosters ===")
                for team in incomplete_teams:
                    remaining_slots = total_roster_slots - len(team.roster)
                    
                    # Calculate budget needed - $1 per slot since minimum bid is $1
                    min_budget_needed = remaining_slots * 1.0
                    budget_type = "minimum bid rate ($1.00/slot)"
                    
                    print(f"\nTeam {team.team_name} (Strategy: {getattr(team, 'strategy', 'Unknown')}):")
                    print(f"  Current roster size: {len(team.roster)}/{total_roster_slots}")
                    print(f"  Remaining slots needed: {remaining_slots}")
                    print(f"  Current budget: ${team.budget:.2f}")
                    print(f"  Budget needed to complete: ${min_budget_needed:.2f} ({budget_type})")
                    print(f"  Can afford completion: {team.budget >= min_budget_needed}")
                    
                    # Show current roster composition
                    position_counts = {}
                    for player in team.roster:
                        pos = getattr(player, 'position', 'UNKNOWN')
                        position_counts[pos] = position_counts.get(pos, 0) + 1
                    print(f"  Current roster: {dict(position_counts)}")
                    
                    # Show what actual player positions are still needed (exclude FLEX/BN)
                    if hasattr(team, 'roster_config') and team.roster_config:
                        needed_positions = {}
                        for pos, required in team.roster_config.items():
                            # Skip non-player positions
                            if pos in ['FLEX', 'BN', 'BENCH']:
                                continue
                            current_count = position_counts.get(pos, 0)
                            if current_count < required:
                                needed_positions[pos] = required - current_count
                        
                        # Calculate remaining flex/bench slots
                        total_position_slots = sum(team.roster_config.get(pos, 0) for pos in ['QB', 'RB', 'WR', 'TE', 'K', 'DST'])
                        flex_bench_slots = total_roster_slots - total_position_slots
                        filled_flex_bench = len(team.roster) - sum(position_counts.get(pos, 0) for pos in ['QB', 'RB', 'WR', 'TE', 'K', 'DST'])
                        remaining_flex_bench = max(0, flex_bench_slots - filled_flex_bench)
                        
                        if needed_positions:
                            print(f"  Missing required positions: {needed_positions}")
                        if remaining_flex_bench > 0:
                            print(f"  Remaining flex/bench slots: {remaining_flex_bench}")
                        if not needed_positions and remaining_flex_bench == 0:
                            print("  All requirements met, but total slots calculation seems off")
                    
                print("=== END DEBUGGING ===\n")
                print("No teams can afford to complete their rosters, ending auction...")
                break
            
            # Force nomination if no current player
            if not draft.current_player:
                log_debug(f"\nIteration {iterations}: No current player, forcing nomination...")
                auction._auto_nominate_player()
                
                if draft.current_player:
                    player = draft.current_player
                    log_debug(f"NOMINATED: {player.name} ({getattr(player, 'position', 'UNKNOWN')}) - Value: ${getattr(player, 'auction_value', 'N/A')}")
                else:
                    log_debug("NOMINATION FAILED: No player nominated")
                
                # If still no current player, we might be out of players to nominate
                if not draft.current_player:
                    log_debug("No more players available for nomination, ending auction...")
                    print("No more players available for nomination, ending auction...")
                    break
            
            # Let auto-bids process with competitive bidding
            if draft.current_player:
                player = draft.current_player
                initial_bid = getattr(player, 'current_bid', 1.0)
                log_debug(f"AUCTION START: {player.name} - Initial bid: ${initial_bid}")
                
                # Process competitive bidding efficiently for simulation
                for bid_round in range(2):  # Reduced to 2 rounds for speed
                    log_debug(f"  BID ROUND {bid_round + 1}: Processing auto-bids for {player.name}")
                    auction._process_auto_bids()
                    log_debug(f"    After bidding: high_bidder={draft.current_high_bidder}, current_bid=${draft.current_bid}")
                    # No delay needed - let bidding happen instantly
                
                # Capture auction state BEFORE completing
                pre_completion_high_bidder = draft.current_high_bidder
                pre_completion_bid = draft.current_bid
                
                # Complete the auction after bidding rounds
                auction.force_complete_auction()
                
                # Log the result using PRE-completion state
                if pre_completion_high_bidder:
                    winning_team = next((team for team in draft.teams if team.owner_id == pre_completion_high_bidder), None)
                    winning_strategy = winning_team.strategy.name if winning_team and winning_team.strategy else 'Unknown'
                    log_debug(f"AUCTION WON: {player.name} ({getattr(player, 'position', 'UNKNOWN')}) -> {winning_strategy} for ${pre_completion_bid}")
                else:
                    log_debug(f"AUCTION FAILED: {player.name} - No winning team (high_bidder: {pre_completion_high_bidder}, current_bid: ${pre_completion_bid})")
                    # Check if any teams can bid
                    eligible_teams = [team for team in draft.teams if team.can_bid(player, 1.0)]
                    log_debug(f"  Eligible teams for bidding: {len(eligible_teams)}")
                    for i, team in enumerate(eligible_teams[:3]):  # Log first 3 eligible teams
                        strategy_name = team.strategy.name if team.strategy else 'No Strategy'
                        log_debug(f"    Team {team.team_name} ({strategy_name}): Budget ${team.budget:.2f}, Roster {len(team.roster)}/{total_roster_slots}")
                    if not eligible_teams:
                        log_debug("  No teams eligible to bid!")
                
                # Update progress
                current_drafted = len(draft.drafted_players)
                if current_drafted > len(drafted_players):
                    drafted_players = draft.drafted_players.copy()
                    if len(drafted_players) % 25 == 0:
                        print(f"   Auctioned {len(drafted_players)} players...")
                        log_debug(f"PROGRESS: {len(drafted_players)} players drafted")
                
                # Check again after each player auction to stop immediately when rosters are full
                incomplete_teams_after = [team for team in draft.teams if len(team.roster) < total_roster_slots]
                if not incomplete_teams_after:
                    print("All teams now have complete rosters, ending auction...")
                    break
                    
                # Also check if we've drafted enough players for reasonable rosters
                min_reasonable_roster = 12  # Teams should have at least 12 players
                teams_with_reasonable_rosters = [
                    team for team in draft.teams 
                    if len(team.roster) >= min_reasonable_roster
                ]
                if len(teams_with_reasonable_rosters) == len(draft.teams):
                    remaining_budget_total = sum(team.budget for team in draft.teams)
                    if remaining_budget_total < len(draft.teams) * 5:  # Less than $5 per team left
                        print("All teams have reasonable rosters and little budget left, ending auction...")
                        break
                
                # Track progress to detect stalled auctions
                current_total_roster_size = sum(len(team.roster) for team in draft.teams)
                if current_total_roster_size == last_total_roster_size:
                    iterations_without_progress += 1
                    # Be more aggressive about terminating for mock drafts
                    teams_with_budget = [team for team in draft.teams if team.budget >= 1.0]
                    teams_needing_players = [team for team in draft.teams if len(team.roster) < total_roster_slots]
                    
                    # Reduced patience for mock draft simulations
                    max_stall_iterations = 20  # Reduced from 50
                    if teams_with_budget and teams_needing_players:
                        # Check if teams needing players also have budget
                        teams_needing_and_with_budget = [
                            team for team in teams_needing_players 
                            if team.budget >= (total_roster_slots - len(team.roster))  # Can afford remaining slots
                        ]
                        if teams_needing_and_with_budget:
                            max_stall_iterations = 60  # Give more time if teams can afford to complete
                        else:
                            max_stall_iterations = 40  # Less time if teams can't afford completion
                    
                    if iterations_without_progress > max_stall_iterations:
                        log_debug(f"\nAUCTION STALLED: {max_stall_iterations} iterations without progress")
                        log_debug(f"Teams with budget >= $1: {len(teams_with_budget)}")
                        log_debug(f"Teams needing players: {len(teams_needing_players)}")
                        
                        print(f"Auction stalled - no progress for {max_stall_iterations} iterations, ending...")
                        print(f"DEBUG: Teams with budget >= $1: {len(teams_with_budget)}")
                        print(f"DEBUG: Teams needing players: {len(teams_needing_players)}")
                        
                        # Force completion for teams that can afford it
                        for team in teams_needing_players:
                            if team.budget >= (total_roster_slots - len(team.roster)):
                                strategy_name = team.strategy.name if team.strategy else 'No Strategy'
                                slots_needed = total_roster_slots - len(team.roster)
                                log_debug(f"FORCE COMPLETE: {team.team_name} ({strategy_name}): ${team.budget:.2f}, needs {slots_needed} players")
                                print(f"  FORCE COMPLETE: {team.team_name} ({strategy_name}): ${team.budget:.2f}, needs {slots_needed} players")
                                
                                # Force team to fill remaining slots with cheapest available players
                                for slot_num in range(slots_needed):
                                    if team.budget >= 1.0:
                                        available_players = [p for p in draft.available_players if not p.is_drafted]
                                        if available_players:
                                            # Pick cheapest player or random if no pricing
                                            cheapest_player = min(available_players, 
                                                                key=lambda p: getattr(p, 'auction_value', 1.0))
                                            log_debug(f"  FORCE DRAFT: {cheapest_player.name} ({getattr(cheapest_player, 'position', 'UNKNOWN')}) -> {team.team_name} for $1.00")
                                            cheapest_player.mark_as_drafted(1.0, team.owner_id)
                                            team.roster.append(cheapest_player)
                                            team.budget -= 1.0
                                            if cheapest_player in draft.available_players:
                                                draft.available_players.remove(cheapest_player)
                                            draft.drafted_players.append(cheapest_player)
                                        else:
                                            log_debug(f"  FORCE DRAFT FAILED: No available players for {team.team_name}")
                                            break
                                    else:
                                        log_debug(f"  FORCE DRAFT STOPPED: {team.team_name} out of budget")
                                        break
                        break
                else:
                    iterations_without_progress = 0
                    last_total_roster_size = current_total_roster_size
                    
                # Emergency check: if we've been iterating too long without roster completion
                if iterations > 200 and iterations % 50 == 0:
                    print(f"Long auction detected (iteration {iterations}), checking for termination...")
                    # Force complete teams with reasonable rosters if they're stuck
                    stuck_teams = [team for team in draft.teams 
                                 if len(team.roster) >= 12 and team.budget < 5]
                    if len(stuck_teams) >= len(draft.teams) * 0.8:  # 80% of teams are stuck
                        print("Most teams have reasonable rosters but little budget, forcing completion...")
                        break
            
            iterations += 1
        
        # Stop auction
        auction.stop_auction()
        
        # Mark as completed if not already
        if draft.status == "started":
            draft._complete_draft()
        
        completed_rosters = len([team for team in draft.teams if len(team.roster) == total_roster_slots])
        print(f"Auction simulation complete! Drafted {len(drafted_players)} players")
        print(f"Teams with complete rosters: {completed_rosters}/{len(draft.teams)}")
        print(f"Auction iterations: {iterations}")
        
        # Final debug logging
        log_debug("\n=== AUCTION COMPLETE ===")
        log_debug(f"Total iterations: {iterations}")
        log_debug(f"Players drafted: {len(drafted_players)}")
        log_debug(f"Teams with complete rosters: {completed_rosters}/{len(draft.teams)}")
        
        # Log remaining players by position
        remaining_players = [p for p in draft.available_players if not p.is_drafted]
        remaining_by_position = {}
        for player in remaining_players:
            pos = getattr(player, 'position', 'UNKNOWN')
            remaining_by_position[pos] = remaining_by_position.get(pos, 0) + 1
        log_debug(f"Remaining players by position: {dict(remaining_by_position)}")
        
        # Log some specific remaining players for each position
        for pos in remaining_by_position.keys():
            players_in_pos = [p for p in remaining_players if getattr(p, 'position', 'UNKNOWN') == pos][:5]  # First 5
            log_debug(f"Sample remaining {pos} players: {[p.name for p in players_in_pos]}")
        
        # Log final team rosters
        log_debug("\n=== FINAL TEAM ROSTERS ===")
        for team in draft.teams:
            strategy_name = team.strategy.name if team.strategy else 'No Strategy'
            log_debug(f"{team.team_name} ({strategy_name}): {len(team.roster)}/{total_roster_slots} players, ${team.budget:.2f} remaining")
            
            # Position breakdown
            team_positions = {}
            for player in team.roster:
                pos = getattr(player, 'position', 'UNKNOWN')
                team_positions[pos] = team_positions.get(pos, 0) + 1
            log_debug(f"  Positions: {dict(team_positions)}")
        
        log_debug(f"\nDebug log saved to: {debug_log_file}")
        print(f"Debug log saved to: {debug_log_file}")
        
        # Debug: Show final rosters for all teams
        print("\n=== FINAL TOURNAMENT ROSTERS ===")
        for i, team in enumerate(draft.teams, 1):
            strategy_name = team.strategy.name if team.strategy else 'No Strategy'
            roster_status = "COMPLETE" if len(team.roster) == total_roster_slots else "INCOMPLETE"
            print(f"\n{i}. {team.team_name} ({strategy_name}) - {roster_status}")
            print(f"   Roster: {len(team.roster)}/{total_roster_slots} players")
            print(f"   Budget: ${team.budget:.2f} remaining (spent: ${200 - team.budget:.2f})")
            print(f"   Projected Points: {team.get_projected_points():.1f}")
            
            # Show position breakdown
            position_counts = {}
            total_spent_by_position = {}
            for player in team.roster:
                pos = getattr(player, 'position', 'UNKNOWN')
                position_counts[pos] = position_counts.get(pos, 0) + 1
                spent = getattr(player, 'auction_price', 1.0)
                total_spent_by_position[pos] = total_spent_by_position.get(pos, 0) + spent
            
            print(f"   Position breakdown: {dict(position_counts)}")
            
            # Show top 5 most expensive players
            if team.roster:
                sorted_roster = sorted(team.roster, 
                                     key=lambda p: getattr(p, 'auction_price', 1.0), 
                                     reverse=True)
                print("   Top players:")
                for j, player in enumerate(sorted_roster[:5], 1):
                    pos = getattr(player, 'position', 'UNKNOWN')
                    price = getattr(player, 'auction_price', 1.0)
                    points = getattr(player, 'projected_points', 0)
                    print(f"     {j}. {player.name} ({pos}) - ${price:.0f}, {points:.1f} pts")
            
            if len(team.roster) < total_roster_slots:
                missing = total_roster_slots - len(team.roster)
                print(f"   ❌ Missing {missing} players")
                
                # Show why team couldn't complete roster
                if team.budget < missing:
                    print(f"   ❌ Insufficient budget: ${team.budget:.2f} < ${missing:.2f} needed")
                else:
                    available_count = len([p for p in draft.available_players if not p.is_drafted])
                    print(f"   ❓ Had budget but didn't complete (available players: {available_count})")
        
        print("\n=== TOURNAMENT SUMMARY ===")
        print(f"Complete rosters: {completed_rosters}/{len(draft.teams)}")
        total_spent = sum(200 - team.budget for team in draft.teams)
        avg_spent = total_spent / len(draft.teams) if draft.teams else 0
        print(f"Average spent per team: ${avg_spent:.2f}")
        print(f"Total auction iterations: {iterations}")
        print("=== END TOURNAMENT DEBUG ===\n")
        
        return {
            'total_players_drafted': len(drafted_players),
            'total_roster_slots': total_roster_slots,
            'completed_rosters': completed_rosters,
            'rounds_completed': len(drafted_players) // len(draft.teams) if draft.teams else 0,
            'round_results': [],
            'primary_strategy': primary_strategy
        }
    
    def _analyze_tournament_performance(self, rankings: List[Dict]) -> Dict:
        """Analyze tournament performance patterns."""
        if not rankings:
            return {}
        
        # Calculate performance metrics
        avg_points = sum(r['avg_points'] for r in rankings) / len(rankings)
        avg_efficiency = sum(r['avg_value_efficiency'] for r in rankings) / len(rankings)
        
        # Find best performers
        best_points = max(rankings, key=lambda r: r['avg_points'])
        best_efficiency = max(rankings, key=lambda r: r['avg_value_efficiency'])
        most_consistent = min(rankings, key=lambda r: r.get('std_dev', float('inf')))
        
        return {
            'avg_points_across_strategies': avg_points,
            'avg_efficiency_across_strategies': avg_efficiency,
            'best_points_strategy': best_points['strategy'],
            'best_efficiency_strategy': best_efficiency['strategy'],
            'most_consistent_strategy': most_consistent['strategy'],
            'performance_spread': max(r['avg_points'] for r in rankings) - min(r['avg_points'] for r in rankings)
        }
    
    def _generate_strategy_recommendations(self, rankings: List[Dict]) -> Dict:
        """Generate strategy recommendations based on tournament results."""
        if not rankings:
            return {}
        
        top_strategy = rankings[0]
        
        recommendations = {
            'primary_recommendation': top_strategy['strategy'],
            'reasoning': []
        }
        
        # Add reasoning based on performance
        if top_strategy['avg_points'] > 1200:
            recommendations['reasoning'].append("High scoring potential")
        
        if top_strategy['avg_value_efficiency'] > 1.1:
            recommendations['reasoning'].append("Excellent value efficiency")
        
        if top_strategy['wins'] > len(rankings) * 0.3:
            recommendations['reasoning'].append("High win rate")
        
        # Alternative recommendations
        recommendations['alternatives'] = [
            {
                'strategy': r['strategy'],
                'reason': 'Balanced performance' if r['avg_value_efficiency'] > 1.0 else 'High upside potential'
            }
            for r in rankings[1:3]
        ]
        
        return recommendations
    
    def _create_test_draft(self, num_teams: int) -> Optional[Draft]:
        """Create a test draft for tournament elimination rounds."""
        try:
            # Load configuration and data
            config = self.config_manager.load_config()
            loader = FantasyProsLoader(config.data_path)
            players = loader.load_all_players()
            
            if not players:
                return None
            
            # Create draft
            draft = Draft(
                name=f"Tournament Draft - {num_teams} Teams",
                budget_per_team=getattr(config, 'budget_per_team', getattr(config, 'budget', 200)),
                roster_size=getattr(config, 'roster_size', 16)
            )
            
            draft.add_players(players)
            
            # Create teams (strategies will be assigned by caller)
            for i in range(num_teams):
                owner = Owner(f"owner_{i+1}", f"Owner {i+1}", is_human=False)
                team = Team(f"team_{i+1}", f"owner_{i+1}", f"Team {i+1}")
                owner.assign_team(team)
                draft.add_team(team)
            
            return draft
            
        except Exception as e:
            print(f"Error creating test draft: {e}")
            return None
    
    def get_sleeper_draft_status(self, username: str, season: str = "2024") -> Dict:
        """Get current draft status for a Sleeper user."""
        print(f"Fetching draft status for '{username}' in {season}...")
        
        try:
            result = asyncio.run(self.sleeper_draft_service.get_current_draft_status(username, season))
            return result
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to get draft status: {e}"
            }
    
    def display_sleeper_draft(self, draft_id: str) -> Dict:
        """Display detailed Sleeper draft information."""
        print(f"Fetching draft information for ID: {draft_id}...")
        
        try:
            result = asyncio.run(self.sleeper_draft_service.display_draft_info(draft_id))
            return result
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to display draft: {e}"
            }
    
    def display_sleeper_league_rosters(self, league_id: str) -> Dict:
        """Display Sleeper league rosters."""
        print(f"Fetching league rosters for ID: {league_id}...")
        
        try:
            result = asyncio.run(self.sleeper_draft_service.display_league_rosters(league_id))
            return result
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to display league rosters: {e}"
            }
    
    def list_sleeper_leagues(self, username: str, season: str = "2024") -> Dict:
        """List all leagues for a Sleeper user."""
        print(f"Fetching leagues for '{username}' in {season}...")
        
        try:
            result = asyncio.run(self.sleeper_draft_service.list_user_leagues(username, season))
            return result
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to list leagues: {e}"
            }
    
    def _format_tournament_results_for_display(self, all_results: List[Dict], strategies: List[str]) -> Dict:
        """Format tournament results for consistent display."""
        results = {}
        
        # Initialize strategy stats
        for strategy in strategies:
            results[strategy] = {
                'wins': 0,
                'simulations': 0,
                'total_points': 0,
                'total_spent': 0,
                'avg_points': 0,
                'avg_spent': 0,
                'win_rate': 0,
                'efficiency': 0
            }
        
        # Process all draft results
        for draft_result in all_results:
            # Extract team data from draft result
            teams = draft_result.get('draft_data', {}).get('teams', [])
            if not teams:
                continue
                
            # Find winner and update stats
            best_points = 0
            winner_strategy = None
            
            for team in teams:
                strategy_name = team.get('strategy_display_name', team.get('strategy', ''))
                # Map display name back to key
                strategy_key = self._map_strategy_name_to_key(strategy_name)
                
                if strategy_key in results:
                    # Update simulation count
                    results[strategy_key]['simulations'] += 1
                    
                    # Update points and spending
                    points = team.get('projected_points', 0)
                    spent = team.get('total_spent', 0)
                    
                    results[strategy_key]['total_points'] += points
                    results[strategy_key]['total_spent'] += spent
                    
                    # Track winner
                    if points > best_points:
                        best_points = points
                        winner_strategy = strategy_key
            
            # Award win to best strategy
            if winner_strategy:
                results[winner_strategy]['wins'] += 1
        
        # Calculate averages and rates
        for strategy_key in results:
            stats = results[strategy_key]
            sims = max(stats['simulations'], 1)  # Avoid division by zero
            
            stats['avg_points'] = stats['total_points'] / sims
            stats['avg_spent'] = stats['total_spent'] / sims
            stats['win_rate'] = stats['wins'] / sims if sims > 0 else 0
            stats['efficiency'] = stats['avg_points'] / max(stats['avg_spent'], 1)
        
        return results
