"""
Print module for displaying fantasy football draft information in table format.

This module provides consistent table formatting for mock drafts, tournaments,
and Sleeper draft information.
"""

from typing import Dict, Optional, Any, Tuple, List
from datetime import datetime
import math


class TableFormatter:
    """Utility class for formatting data in tables."""
    
    @staticmethod
    def format_table(
        headers: List[str],
        rows: List[List[str]],
        title: Optional[str] = None,
        min_width: int = 80,
        align: str = 'left'
    ) -> str:
        """
        Format data as a table.
        
        Args:
            headers: Column headers
            rows: Data rows
            title: Optional table title
            min_width: Minimum table width
            align: Text alignment ('left', 'right', 'center')
            
        Returns:
            Formatted table string
        """
        if not rows or not headers:
            return ""
            
        # Calculate column widths
        col_widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Ensure minimum width
        total_width = sum(col_widths) + len(headers) * 3 + 1
        if total_width < min_width:
            extra_width = min_width - total_width
            col_widths[-1] += extra_width
            
        # Build table
        result = []
        
        # Title
        if title:
            total_table_width = sum(col_widths) + len(headers) * 3 + 1
            result.append("=" * total_table_width)
            result.append(f"{title:^{total_table_width}}")
            result.append("=" * total_table_width)
        
        # Header
        header_line = "|"
        for i, header in enumerate(headers):
            header_line += f" {header:<{col_widths[i]}} |"
        result.append(header_line)
        
        # Header separator
        sep_line = "|"
        for width in col_widths:
            sep_line += "-" * (width + 2) + "|"
        result.append(sep_line)
        
        # Data rows
        for row in rows:
            row_line = "|"
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    if align == 'right':
                        row_line += f" {str(cell):>{col_widths[i]}} |"
                    elif align == 'center':
                        row_line += f" {str(cell):^{col_widths[i]}} |"
                    else:  # left
                        row_line += f" {str(cell):<{col_widths[i]}} |"
            result.append(row_line)
        
        # Bottom border
        result.append(sep_line)
        
        return "\n".join(result)
    
    @staticmethod
    def format_currency(amount: float) -> str:
        """Format currency amount."""
        return f"${amount:.0f}"
    
    @staticmethod
    def format_percentage(value: float) -> str:
        """Format percentage value."""
        return f"{value:.1%}"
    
    @staticmethod
    def format_points(points: float) -> str:
        """Format fantasy points."""
        return f"{points:.1f}"
    
    @staticmethod
    def format_efficiency(points: float, cost: float) -> str:
        """Format points per dollar efficiency."""
        if cost <= 0:
            return "N/A"
        return f"{points/cost:.2f}"


class MockDraftPrinter:
    """Handles printing mock draft results in table format."""
    
    @staticmethod
    def print_mock_draft_summary(draft_result: Dict) -> None:
        """Print a summary of mock draft results."""
        draft = draft_result['draft']
        simulation_results = draft_result.get('simulation_results', {})
        
        print("\n" + "="*80)
        print("MOCK DRAFT SUMMARY")
        print("="*80)
        
        print(f"Draft Name: {draft.name}")
        print(f"Status: {draft.status}")
        print(f"Players Drafted: {simulation_results.get('total_players_drafted', len(draft.drafted_players))}")
        print(f"Rounds Completed: {simulation_results.get('rounds_completed', draft.current_round)}")
        print(f"Teams: {len(draft.teams)}")
        
        if hasattr(draft, 'started_at') and draft.started_at:
            print(f"Started: {draft.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if hasattr(draft, 'completed_at') and draft.completed_at:
            print(f"Completed: {draft.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
    
    @staticmethod
    def print_mock_draft_leaderboard(draft_result: Dict) -> None:
        """Print mock draft leaderboard in table format."""
        draft = draft_result['draft']
        
        # Sort teams by projected points
        teams_sorted = sorted(draft.teams, key=lambda t: t.get_projected_points(), reverse=True)
        
        headers = ["Rank", "Team", "Strategy", "Points", "Spent", "Remaining", "Efficiency", "Players"]
        rows = []
        
        for i, team in enumerate(teams_sorted, 1):
            points = team.get_projected_points()
            spent = team.get_total_spent()
            remaining = team.budget
            efficiency = points / spent if spent > 0 else 0
            strategy_name = team.get_strategy().name if team.get_strategy() else 'None'
            player_count = len(team.roster)
            
            rows.append([
                str(i),
                team.team_name,
                strategy_name,
                TableFormatter.format_points(points),
                TableFormatter.format_currency(spent),
                TableFormatter.format_currency(remaining),
                TableFormatter.format_efficiency(points, spent),
                str(player_count)
            ])
        
        table = TableFormatter.format_table(headers, rows, "MOCK DRAFT LEADERBOARD")
        print(table)
    
    @staticmethod
    def print_winning_roster(draft_result: Dict) -> None:
        """Print the winning team's roster in detail."""
        draft = draft_result['draft']
        
        # Get the winning team
        teams_sorted = sorted(draft.teams, key=lambda t: t.get_projected_points(), reverse=True)
        if not teams_sorted:
            return
            
        winning_team = teams_sorted[0]
        
        print(f"\nWINNING ROSTER: {winning_team.team_name}")
        print(f"Strategy: {winning_team.get_strategy().name if winning_team.get_strategy() else 'None'}")
        print(f"Total Points: {TableFormatter.format_points(winning_team.get_projected_points())}")
        print(f"Total Spent: {TableFormatter.format_currency(winning_team.get_total_spent())}")
        print("-" * 80)
        
        # Group roster by position
        roster_by_pos = {}
        for player in winning_team.roster:
            pos = player.position
            if pos not in roster_by_pos:
                roster_by_pos[pos] = []
            roster_by_pos[pos].append(player)
        
        # Print by position
        for position in ['QB', 'RB', 'WR', 'TE', 'K', 'DST']:
            if position in roster_by_pos:
                players = roster_by_pos[position]
                headers = ["Player", "Team", "Points", "Cost", "Efficiency"]
                rows = []
                
                for player in players:
                    cost = getattr(player, 'drafted_price', 0) or 0
                    efficiency = player.projected_points / cost if cost > 0 else 0
                    
                    rows.append([
                        player.name,
                        player.team,
                        TableFormatter.format_points(player.projected_points),
                        TableFormatter.format_currency(cost),
                        TableFormatter.format_efficiency(player.projected_points, cost)
                    ])
                
                if rows:
                    table = TableFormatter.format_table(headers, rows, f"{position} PLAYERS")
                    print(table)
                    print()

    @staticmethod
    def print_mock_draft(draft_result: Dict, detailed: bool = True) -> None:
        """Print complete mock draft results."""
        MockDraftPrinter.print_mock_draft_summary(draft_result)
        if detailed:
            MockDraftPrinter.print_mock_draft_leaderboard(draft_result)
            MockDraftPrinter.print_winning_roster(draft_result)
            MockDraftPrinter.print_all_team_rosters(draft_result)
    
    @staticmethod
    def print_all_team_rosters(draft_result: Dict) -> None:
        """Print detailed rosters for all teams."""
        draft = draft_result['draft']
        
        print("\n" + "="*80)
        print("DETAILED TEAM ROSTERS")
        print("="*80)
        
        for i, team in enumerate(draft.teams, 1):
            print(f"\n{team.team_name} ({team.strategy.name if team.strategy else 'None'})")
            print(f"Budget: ${team.initial_budget - team.budget:.0f} spent, ${team.budget:.0f} remaining")
            print(f"Projected Points: {team.get_projected_points():.1f}")
            print("-" * 60)
            
            if not team.roster:
                print("  No players drafted")
                continue
            
            # Group players by position
            roster_by_pos = {}
            for player in team.roster:
                pos = player.position
                if pos not in roster_by_pos:
                    roster_by_pos[pos] = []
                roster_by_pos[pos].append(player)
            
            # Print by position
            for position in ['QB', 'RB', 'WR', 'TE', 'K', 'DST']:
                if position in roster_by_pos:
                    players = roster_by_pos[position]
                    print(f"  {position} ({len(players)}):")
                    for player in players:
                        cost = getattr(player, 'drafted_price', 0) or 0
                        efficiency = player.projected_points / cost if cost > 0 else 0
                        print(f"    {player.name} ({player.team}) - ${cost:.0f} - {player.projected_points:.1f} pts - {efficiency:.1f} eff")
        
        print("="*80)


class TournamentPrinter:
    """Handles printing tournament results in table format."""
    
    @staticmethod
    def print_tournament_summary(tournament_result: Dict) -> None:
        """Print tournament summary information."""
        print("\n" + "="*80)
        print("TOURNAMENT SUMMARY")
        print("="*80)
        
        print(f"Tournament: {tournament_result.get('tournament_name', 'Unknown')}")
        print(f"Simulations: {tournament_result.get('completed_simulations', 0)}/{tournament_result.get('num_simulations', 0)}")
        print(f"Strategies Tested: {tournament_result.get('strategies_tested', 0)}")
        
        if 'execution_time' in tournament_result:
            print(f"Execution Time: {tournament_result['execution_time']:.1f} seconds")
        
        if 'created_at' in tournament_result:
            created_at = tournament_result['created_at']
            if isinstance(created_at, str):
                print(f"Created: {created_at}")
            else:
                print(f"Created: {created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    
    @staticmethod
    def print_tournament_rankings(tournament_result: Dict) -> None:
        """Print tournament strategy rankings in table format."""
        results = tournament_result.get('results', {})
        if not results:
            print("No tournament results available.")
            return
        
        # Sort strategies by win rate, then by average points
        strategy_items = list(results.items())
        strategy_items.sort(key=lambda x: (x[1]['win_rate'], x[1]['avg_points']), reverse=True)
        
        headers = ["Rank", "Strategy", "Win Rate", "Avg Points", "Wins", "Sims", "Avg Spent", "Efficiency"]
        rows = []
        
        for i, (strategy_name, stats) in enumerate(strategy_items, 1):
            win_rate = stats.get('win_rate', 0)
            avg_points = stats.get('avg_points', 0)
            wins = stats.get('wins', 0)
            simulations = stats.get('simulations', 0)
            avg_spent = stats.get('avg_spent', 0)
            efficiency = avg_points / avg_spent if avg_spent > 0 else 0
            
            rows.append([
                str(i),
                strategy_name.title(),
                TableFormatter.format_percentage(win_rate),
                TableFormatter.format_points(avg_points),
                str(wins),
                str(simulations),
                TableFormatter.format_currency(avg_spent),
                TableFormatter.format_efficiency(avg_points, avg_spent)
            ])
        
        table = TableFormatter.format_table(headers, rows, "TOURNAMENT RANKINGS")
        print(table)
    
    @staticmethod
    def print_tournament_detailed_stats(tournament_result: Dict) -> None:
        """Print detailed tournament statistics."""
        results = tournament_result.get('results', {})
        if not results:
            return
        
        print("\n" + "="*80)
        print("DETAILED STATISTICS")
        print("="*80)
        
        for strategy_name, stats in results.items():
            print(f"\n{strategy_name.upper()} STRATEGY:")
            print(f"  Simulations: {stats.get('simulations', 0)}")
            print(f"  Wins: {stats.get('wins', 0)}")
            print(f"  Win Rate: {TableFormatter.format_percentage(stats.get('win_rate', 0))}")
            print(f"  Average Points: {TableFormatter.format_points(stats.get('avg_points', 0))}")
            print(f"  Best Points: {TableFormatter.format_points(stats.get('best_points', 0))}")
            print(f"  Worst Points: {TableFormatter.format_points(stats.get('worst_points', 0))}")
            print(f"  Points Std Dev: {stats.get('points_std', 0):.1f}")
            print(f"  Average Spent: {TableFormatter.format_currency(stats.get('avg_spent', 0))}")
            print(f"  Average Remaining: {TableFormatter.format_currency(stats.get('avg_remaining', 0))}")
            print(f"  Average Ranking: {stats.get('avg_ranking', 0):.1f}")
            print(f"  Median Ranking: {stats.get('median_ranking', 0):.1f}")
    
    @staticmethod
    def print_elimination_tournament(tournament_result: Dict) -> None:
        """Print elimination tournament bracket results."""
        if 'tournament_bracket' not in tournament_result:
            TournamentPrinter.print_tournament_rankings(tournament_result)
            return
        
        bracket = tournament_result['tournament_bracket']
        champion = tournament_result.get('champion')
        
        print("\n" + "="*80)
        print("ELIMINATION TOURNAMENT BRACKET")
        print("="*80)
        
        print(f"Champion: {champion.upper() if champion else 'No Champion'}")
        print(f"Total Participants: {bracket.get('total_participants', 0)}")
        print(f"Rounds Completed: {tournament_result.get('rounds_completed', 0)}")
        print(f"Total Drafts: {tournament_result.get('total_drafts', 0)}")
        
        # Print bracket progression
        for round_info in bracket.get('rounds', []):
            round_num = round_info['round_number']
            participants = round_info['participants']
            winners = round_info['winners']
            pools = round_info.get('pools', [])
            
            print(f"\nROUND {round_num}: {len(participants)} → {len(winners)}")
            print(f"  Participants: {', '.join(participants)}")
            print(f"  Pools: {len(pools)} drafts")
            print(f"  Advancing: {', '.join(winners)}")

    def print_tournament(self, tournament_result: Dict, detailed: bool = True) -> None:
        """Print complete tournament results."""
        if tournament_result.get('tournament_type') == 'elimination':
            self.print_elimination_tournament(tournament_result)
        else:
            self.print_tournament_summary(tournament_result)
            if detailed:
                self.print_tournament_detailed_stats(tournament_result)
            self.print_tournament_rankings(tournament_result)


class SleeperDraftPrinter:
    """Handles printing Sleeper draft information in table format."""
    
    @staticmethod
    def print_sleeper_draft_summary(draft_info: Dict) -> None:
        """Print Sleeper draft summary."""
        print("\n" + "="*80)
        print("SLEEPER DRAFT SUMMARY")
        print("="*80)

        # Required key — raises KeyError for empty/invalid input
        draft_id = draft_info['draft_id']
        league_id = draft_info.get('league_id', 'Unknown')
        status = draft_info.get('status', 'unknown')
        draft_type = draft_info.get('type', 'unknown')
        draft_order = draft_info.get('draft_order')
        
        print(f"Draft ID: {draft_id}")
        print(f"League ID: {league_id}")
        print(f"Status: {status.title()}")
        print(f"Type: {draft_type.title()}")
        
        if draft_order:
            print(f"Draft Order: {len(draft_order)} teams")
        
        # Draft settings
        settings = draft_info.get('settings', {})
        if settings:
            print(f"Rounds: {settings.get('rounds', 'Unknown')}")
            print(f"Pick Timer: {settings.get('pick_timer', 'Unknown')} seconds")
            if 'reversal_round' in settings:
                print(f"Reversal Round: {settings['reversal_round']}")
    
    @staticmethod
    def print_sleeper_draft_order(draft_info: Dict, users_info: Optional[Dict] = None) -> None:
        """Print Sleeper draft order in table format."""
        draft_order = draft_info.get('draft_order')
        if not draft_order:
            print("No draft order available.")
            return
        
        headers = ["Pick", "User ID", "Username", "Team Name"]
        rows = []
        
        for i, user_id in enumerate(draft_order, 1):
            username = "Unknown"
            team_name = "Unknown"
            
            if users_info and user_id in users_info:
                user_data = users_info[user_id]
                username = user_data.get('display_name', user_data.get('username', 'Unknown'))
                team_name = user_data.get('metadata', {}).get('team_name', 'Unknown')
            
            rows.append([
                str(i),
                str(user_id),
                username,
                team_name
            ])
        
        table = TableFormatter.format_table(headers, rows, "DRAFT ORDER")
        print(table)
    
    @staticmethod
    def print_sleeper_picks(picks: List[Dict], players_info: Optional[Dict] = None) -> None:
        """Print Sleeper draft picks in traditional draft board format (positions as rows, teams as columns)."""
        if not picks:
            print("No picks available.")
            return
        
        # Sort picks by pick number first
        sorted_picks = sorted(picks, key=lambda x: x.get('pick_no', 0))
        
        # Group picks by owner and organize by position
        teams_rosters = {}
        total_spent = 0
        
        for pick in sorted_picks:
            picked_by = pick.get('picked_by', 'Unknown')
            
            # In mock drafts, picked_by is often empty, so use draft_slot as team identifier
            if not picked_by or picked_by.strip() == '':
                draft_slot = pick.get('draft_slot', 1)
                picked_by = f"Team {draft_slot}"
            
            player_id = pick.get('player_id', '')
            
            # Get bid amount from metadata
            metadata = pick.get('metadata', {})
            bid_amount = metadata.get('amount', '0')
            
            player_name = "Unknown Player"
            position = "UNK"
            team = "UNK"
            
            if players_info and player_id in players_info:
                player_data = players_info[player_id]
                player_name = player_data.get('full_name', 'Unknown')
                position = player_data.get('position', 'UNK')
                team = player_data.get('team', 'UNK')
            
            # Format bid amount
            try:
                bid_value = int(bid_amount)
                total_spent += bid_value
            except (ValueError, TypeError):
                bid_value = 0
            
            # Initialize team roster if not exists
            if picked_by not in teams_rosters:
                teams_rosters[picked_by] = {
                    'total_spent': 0,
                    'positions': {}
                }
            
            # Add player to team's position slots
            player_info = {
                'name': player_name,
                'team': team,
                'bid': bid_value,
                'pick_no': pick.get('pick_no', 0)
            }
            
            teams_rosters[picked_by]['total_spent'] += bid_value
            
            # Add to position slots (allowing multiple at same position)
            if position not in teams_rosters[picked_by]['positions']:
                teams_rosters[picked_by]['positions'][position] = []
            teams_rosters[picked_by]['positions'][position].append(player_info)
        
        # Create traditional draft board layout
        if not teams_rosters:
            print("No teams found in draft.")
            return
        
        # Define roster position order - simplified for readability
        roster_positions = [
            'QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'K', 'DST', 'BN', 'BN', 'BN'
        ]
        
        # Get team names/owners
        team_names = list(teams_rosters.keys())
        team_names.sort()  # Sort for consistent ordering
        
        # Create headers: Position + Team columns
        headers = ['Position'] + [f'Team {i+1}' for i, name in enumerate(team_names)]
        
        # Set column widths for better readability
        position_width = 12
        team_width = 20
        
        # Create rows for each roster position
        rows = []
        position_counts = {}  # Track how many of each position we've used
        used_players = {}  # Track which players have been assigned to prevent duplicates
        
        for team_name in team_names:
            used_players[team_name] = set()
        
        for roster_slot in roster_positions:
            # Track position numbers (RB1, RB2, etc.)
            if roster_slot not in position_counts:
                position_counts[roster_slot] = 0
            position_counts[roster_slot] += 1
            
            if position_counts[roster_slot] == 1:
                position_display = roster_slot
            else:
                position_display = f"{roster_slot}{position_counts[roster_slot]}"
            
            row = [position_display]
            
            # Add player for each team at this position slot
            for team_name in team_names:
                team_roster = teams_rosters[team_name]
                
                # Find best available player for this position slot
                player_cell = ""
                
                if roster_slot in team_roster['positions']:
                    available_players = team_roster['positions'][roster_slot]
                    
                    # Sort by bid value descending and pick the next available
                    available_players.sort(key=lambda x: x['bid'], reverse=True)
                    
                    # Determine which player to show for this slot
                    slot_index = position_counts[roster_slot] - 1
                    if slot_index < len(available_players):
                        player = available_players[slot_index]
                        player_key = f"{player['name']}_{player['bid']}"
                        
                        # Check if this player hasn't been used yet
                        if player_key not in used_players[team_name]:
                            used_players[team_name].add(player_key)
                            # Truncate long names for better table formatting
                            name = player['name']
                            if len(name) > 14:
                                name = name[:12] + ".."
                            player_cell = f"{name} (${player['bid']})"
                
                # Handle FLEX positions - can be RB/WR/TE (only unused players)
                elif roster_slot == 'FLEX':
                    flex_candidates = []
                    for pos in ['RB', 'WR', 'TE']:
                        if pos in team_roster['positions']:
                            pos_players = team_roster['positions'][pos]
                            for player in pos_players:
                                player_key = f"{player['name']}_{player['bid']}"
                                if player_key not in used_players[team_name]:
                                    flex_candidates.append(player)
                    
                    if flex_candidates:
                        flex_candidates.sort(key=lambda x: x['bid'], reverse=True)
                        flex_index = position_counts[roster_slot] - 1
                        if flex_index < len(flex_candidates):
                            player = flex_candidates[flex_index]
                            player_key = f"{player['name']}_{player['bid']}"
                            used_players[team_name].add(player_key)
                            name = player['name']
                            if len(name) > 14:
                                name = name[:12] + ".."
                            player_cell = f"{name} (${player['bid']})"
                
                # Handle BN (bench) - any remaining unused players
                elif roster_slot == 'BN':
                    all_remaining = []
                    
                    # Get all players not yet used
                    for pos, players in team_roster['positions'].items():
                        for player in players:
                            player_key = f"{player['name']}_{player['bid']}"
                            if player_key not in used_players[team_name]:
                                all_remaining.append(player)
                    
                    if all_remaining:
                        all_remaining.sort(key=lambda x: x['bid'], reverse=True)
                        bn_index = position_counts[roster_slot] - 1
                        if bn_index < len(all_remaining):
                            player = all_remaining[bn_index]
                            player_key = f"{player['name']}_{player['bid']}"
                            used_players[team_name].add(player_key)
                            name = player['name']
                            if len(name) > 14:
                                name = name[:12] + ".."
                            player_cell = f"{name} (${player['bid']})"
                
                row.append(player_cell)
            
            rows.append(row)
        
        # Add spending summary row
        spending_row = ['TOTAL SPENT'] + [f"${teams_rosters[name]['total_spent']}" for name in team_names]
        rows.append(spending_row)
        
        # Create custom table for draft board with better formatting
        def format_draft_board_table(headers, rows, title):
            """Custom table formatter for draft board with improved readability."""
            # Calculate column widths
            position_width = 10
            team_width = 20  # Optimized for player names and bid amounts
            
            col_widths = [position_width] + [team_width] * (len(headers) - 1)
            
            # Build table
            result = []
            
            # Title
            total_table_width = sum(col_widths) + len(headers) * 3 + 1
            result.append("=" * total_table_width)
            result.append(f"{title:^{total_table_width}}")
            result.append("=" * total_table_width)
            
            # Header
            header_line = "|"
            for i, header in enumerate(headers):
                header_line += f" {header:^{col_widths[i]}} |"
            result.append(header_line)
            
            # Header separator
            sep_line = "|"
            for width in col_widths:
                sep_line += "-" * (width + 2) + "|"
            result.append(sep_line)
            
            # Data rows
            for row in rows:
                row_line = "|"
                for i, cell in enumerate(row):
                    if i < len(col_widths):
                        if i == 0:  # Position column - center align
                            row_line += f" {str(cell):^{col_widths[i]}} |"
                        else:  # Team columns - left align
                            row_line += f" {str(cell):<{col_widths[i]}} |"
                result.append(row_line)
            
            # Bottom border
            result.append(sep_line)
            
            return "\n".join(result)
        
        table = format_draft_board_table(headers, rows, "AUCTION DRAFT BOARD")
        print(table)
        
        # Add draft summary
        if picks:
            print(f"\n📊 DRAFT SUMMARY")
            print(f"   Teams: {len(teams_rosters)}")
            print(f"   Total picks: {len(picks)}")
            print(f"   Total spent: ${total_spent:,}")
            
            # Show team spending
            print(f"\n   Team spending:")
            for i, team_name in enumerate(team_names):
                spent = teams_rosters[team_name]['total_spent']
                team_display = f"Team {i+1}" if team_name == 'Unknown' else team_name
                print(f"     {team_display}: ${spent:,}")
            
            # Show highest/lowest bids
            bid_values = [int(pick.get('metadata', {}).get('amount', 0)) for pick in picks]
            bid_values = [b for b in bid_values if b > 0]
            if bid_values:
                print(f"\n   Highest bid: ${max(bid_values)}")
                print(f"   Lowest bid: ${min(bid_values)}")
                print(f"   Average bid: ${sum(bid_values)/len(bid_values):.1f}")
    
    @staticmethod
    def print_sleeper_rosters(rosters: List[Dict], users_info: Optional[Dict] = None, 
                            players_info: Optional[Dict] = None) -> None:
        """Print Sleeper league rosters in table format."""
        if not rosters:
            print("No rosters available.")
            return
        
        headers = ["Team", "Wins", "Losses", "Points For", "Points Against", "Roster Size"]
        rows = []
        
        for roster in rosters:
            owner_id = roster.get('owner_id', 'Unknown')
            wins = roster.get('settings', {}).get('wins', 0)
            losses = roster.get('settings', {}).get('losses', 0)
            points_for = roster.get('settings', {}).get('fpts', 0)
            points_against = roster.get('settings', {}).get('fpts_against', 0)
            
            # Get team name
            team_name = "Unknown Team"
            if users_info and owner_id in users_info:
                user_data = users_info[owner_id]
                team_name = user_data.get('metadata', {}).get('team_name', 
                                       user_data.get('display_name', 'Unknown'))
            
            roster_size = len(roster.get('players', []))
            
            rows.append([
                team_name,
                str(wins),
                str(losses),
                f"{points_for:.1f}",
                f"{points_against:.1f}",
                str(roster_size)
            ])
        
        # Sort by wins, then by points for
        rows.sort(key=lambda x: (int(x[1]), float(x[3])), reverse=True)
        
        table = TableFormatter.format_table(headers, rows, "LEAGUE ROSTERS")
        print(table)
    
    def print_sleeper_draft(self, draft_info: Dict, users_info: Optional[Dict] = None,
                           picks: Optional[List[Dict]] = None, 
                           players_info: Optional[Dict] = None) -> None:
        """Print complete Sleeper draft information."""
        self.print_sleeper_draft_summary(draft_info)
        self.print_sleeper_draft_order(draft_info, users_info)
        
        if picks:
            self.print_sleeper_picks(picks, players_info)


# Convenience functions for easy imports
def print_mock_draft(draft_result: Dict, detailed: bool = True) -> None:
    """Print mock draft results."""
    printer = MockDraftPrinter()
    printer.print_mock_draft(draft_result, detailed)


def print_tournament(tournament_result: Dict, detailed: bool = True) -> None:
    """Print tournament results."""
    printer = TournamentPrinter()
    printer.print_tournament(tournament_result, detailed)


def print_sleeper_draft(draft_info: Dict, users_info: Optional[Dict] = None,
                       picks: Optional[List[Dict]] = None, 
                       players_info: Optional[Dict] = None) -> None:
    """Print Sleeper draft information."""
    printer = SleeperDraftPrinter()
    printer.print_sleeper_draft(draft_info, users_info, picks, players_info)


def print_sleeper_league(rosters: List[Dict], users_info: Optional[Dict] = None,
                        players_info: Optional[Dict] = None) -> None:
    """Print Sleeper league information."""
    printer = SleeperDraftPrinter()
    printer.print_sleeper_rosters(rosters, users_info, players_info)
