#!/usr/bin/env python3
"""
Auction Draft Tool CLI

A command-line interface for managing fantasy football auction drafts.

Usage:
    python cli/main.py <command> [options]

Commands:
    bid <player_name> [current_bid] [sleeper_draft_id]  Calculate bid recommendation for a player
    mock [strategy] [teams]             Run a mock draft simulation
    tournament [rounds] [teams_per_draft] [-v|--verbose]   Run elimination tournament with all strategies
    sleeper <subcommand> [options]      Access Sleeper drafts/leagues (uses config defaults)
    ping                                Test Sleeper API connectivity
    help                                Show this help message

Tournament Command Details:
    - rounds: Number of drafts per group (default: 10)
    - teams_per_draft: Teams per draft (default: 10, strategies duplicated as needed)
    - Each round runs multiple drafts with the same group of strategies
    - Winners advance through elimination rounds until one champion remains

Examples:
    python cli/main.py bid "Josh Allen" 25
    python cli/main.py bid "Josh Allen" 25 1257154391174029312
    python cli/main.py mock value 10
    python cli/main.py tournament           # Default: 10 rounds, 10 teams per draft
    python cli/main.py tournament 5        # 5 rounds per group, 10 teams per draft
    python cli/main.py tournament 10 12    # 10 rounds per group, 12 teams per draft
    python cli/main.py tournament 3 10 -v  # Verbose output
    python cli/main.py ping
"""

import sys
from typing import List, Dict

# Add parent directory to path for imports
from utils.path_utils import setup_project_path
setup_project_path()

from api.sleeper_api import SleeperAPI
from config.config_manager import ConfigManager
from classes import AVAILABLE_STRATEGIES
from cli.commands import CommandProcessor
from utils.print_module import print_mock_draft


class AuctionDraftCLI:
    """Main CLI class for the auction draft tool."""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.sleeper_api = SleeperAPI()
        self.command_processor = CommandProcessor()
        
    def _get_config_default(self, key: str, default=None):
        """Helper to get config values with error handling."""
        try:
            config = self.config_manager.load_config()
            return getattr(config, key, default)
        except Exception:
            return default
            
    def _handle_command_result(self, result: Dict, error_message: str = "Command failed") -> int:
        """Helper to handle standard command result patterns."""
        if not result.get('success', False):
            print(f"ERROR: {result.get('error', error_message)}")
            return 1
        return 0

    def run(self, args: List[str]) -> int:
        """Run the CLI with given arguments."""
        if not args:
            self.show_help()
            return 0
            
        command = args[0].lower()
        
        try:
            if command == 'bid':
                return self.handle_bid_command(args[1:])
            elif command == 'mock':
                return self.handle_mock_command(args[1:])
            elif command == 'tournament':
                return self.handle_tournament_command(args[1:])
            elif command == 'ping':
                return self.handle_ping_command(args[1:])
            elif command == 'sleeper':
                return self.handle_sleeper_command(args[1:])
            elif command == 'help' or command == '--help' or command == '-h':
                self.show_help()
                return 0
            else:
                print(f"ERROR: Unknown command: {command}")
                print("Use 'help' to see available commands")
                return 1
                
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
            return 130
        except Exception as e:
            print(f"ERROR: {e}")
            return 1
    
    def handle_bid_command(self, args: List[str]) -> int:
        """Handle bid recommendation command."""
        if not args:
            print("ERROR: Player name required")
            print("Usage: bid <player_name> [current_bid] [sleeper_draft_id]")
            print("Note: Use quotes for multi-word names: bid 'Josh Allen' 25")
            return 1
        
        # Parse arguments intelligently to handle unquoted multi-word names
        player_name, current_bid, sleeper_draft_id = self._parse_bid_args(args)
        
        print(f"Calculating bid recommendation for '{player_name}'...")
        print(f"Current bid: ${current_bid}")
        if sleeper_draft_id:
            print(f"Using Sleeper draft: {sleeper_draft_id}")
        print("Loading draft data...")
        
        # Get enhanced bid recommendation
        result = self.command_processor.get_bid_recommendation_detailed(player_name, current_bid, sleeper_draft_id)
        
        if result.get('success', False):
            self._display_bid_recommendation(result)
            return 0
        else:
            print(f"ERROR: {result.get('error', 'Failed to get bid recommendation')}")
            return 1
    
    def handle_mock_command(self, args: List[str]) -> int:
        """Handle mock draft command.
        
        Supports positional syntax:  mock <strategy> <num_teams>
        And flag-based syntax:        mock -s <strategy> -n <num_teams>
        """
        # Parse optional -s / -n flags
        strategy_arg = 'value'
        num_teams = 10
        i = 0
        positional = []
        while i < len(args):
            if args[i] in ('-s', '--strategy') and i + 1 < len(args):
                strategy_arg = args[i + 1]
                i += 2
            elif args[i] in ('-n', '--num-teams') and i + 1 < len(args):
                try:
                    num_teams = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                positional.append(args[i])
                i += 1
        if positional:
            strategy_arg = positional[0]
        if len(positional) > 1:
            try:
                num_teams = int(positional[1])
            except ValueError:
                pass
        
        # Parse strategies - support comma-separated list
        if ',' in strategy_arg:
            strategies = [s.strip() for s in strategy_arg.split(',')]
            invalid_strategies = [s for s in strategies if s not in AVAILABLE_STRATEGIES]
            if invalid_strategies:
                print(f"ERROR: Invalid strategies: {', '.join(invalid_strategies)}")
                print(f"Available strategies: {', '.join(AVAILABLE_STRATEGIES)}")
                return 1
            strategy_display = f"{len(strategies)} strategies: {', '.join(strategies)}"
        else:
            strategies = strategy_arg
            if strategy_arg not in AVAILABLE_STRATEGIES:
                print(f"ERROR: Invalid strategy: {strategy_arg}")
                print(f"Available strategies: {', '.join(AVAILABLE_STRATEGIES)}")
                return 1
            strategy_display = strategy_arg
        
        print("Starting mock draft simulation...")
        print(f"Strategy: {strategy_display}")
        print(f"Teams: {num_teams}")
        
        # Run enhanced mock draft
        result = self.command_processor.run_enhanced_mock_draft(strategies, num_teams)
        
        if result.get('success', False):
            self._display_mock_results(result)
            return 0
        else:
            print(f"ERROR: {result.get('error', 'Mock draft failed')}")
            return 1
    
    def handle_tournament_command(self, args: List[str]) -> int:
        """Handle tournament command."""
        # Parse arguments with support for verbose flag
        verbose = False
        filtered_args = []
        
        for arg in args:
            if arg.lower() in ['-v', '--verbose']:
                verbose = True
            else:
                filtered_args.append(arg)
        
        rounds = 10
        teams_per_draft = 10
        if filtered_args:
            try:
                rounds = int(filtered_args[0])
            except ValueError:
                print(f"ERROR: Invalid rounds value '{filtered_args[0]}' — must be an integer")
                return 1
        if len(filtered_args) > 1:
            try:
                teams_per_draft = int(filtered_args[1])
            except ValueError:
                print(f"ERROR: Invalid teams_per_draft value '{filtered_args[1]}' — must be an integer")
                return 1
        
        print("Starting elimination tournament...")
        print(f"Rounds (drafts per group): {rounds}")
        print(f"Teams per draft: {teams_per_draft}")
        print(f"Verbose mode: {'ON' if verbose else 'OFF'}")
        print("This may take a while...")
        
        # Run elimination tournament
        result = self.command_processor.run_elimination_tournament(rounds, teams_per_draft, verbose=verbose)
        
        if result.get('success', False):
            self._display_tournament_results(result)
            return 0
        else:
            print(f"ERROR: Tournament failed: {result.get('error', 'Unknown error')}")
            return 1
    
    def handle_ping_command(self, args: List[str]) -> int:
        """Handle Sleeper API ping command."""
        print("Testing Sleeper API connectivity...")
        
        # Run comprehensive connectivity test
        result = self.command_processor.test_sleeper_connectivity()
        
        # Display results
        self._display_ping_results(result)
        
        return 0 if result.get('success', False) else 1
    
    def handle_sleeper_command(self, args: List[str]) -> int:
        """Handle Sleeper draft commands."""
        if not args:
            print("ERROR: Sleeper command requires subcommand")
            print("Usage: sleeper <subcommand> [options]")
            print("Subcommands: status, draft, league, leagues")
            return 1
        
        subcommand = args[0].lower()
        
        if subcommand == "status":
            return self.handle_sleeper_status(args[1:])
        elif subcommand == "draft":
            return self.handle_sleeper_draft(args[1:])
        elif subcommand == "league":
            return self.handle_sleeper_league(args[1:])
        elif subcommand == "leagues":
            return self.handle_sleeper_leagues(args[1:])
        elif subcommand == "cache":
            return self.handle_sleeper_cache(args[1:])
        else:
            print(f"ERROR: Unknown Sleeper subcommand: {subcommand}")
            print("Available subcommands: status, draft, league, leagues, cache")
            return 1
    
    def handle_sleeper_status(self, args: List[str]) -> int:
        """Handle Sleeper draft status command."""
        # Get default username from config if not provided
        default_username = self._get_config_default('sleeper_username')
        
        if not args and not default_username:
            print("ERROR: Username required (not provided and not set in config)")
            print("Usage: sleeper status <username> [season]")
            print("Or set 'sleeper_username' in config/config.json")
            return 1
        
        username = args[0] if args else default_username
        season = args[1] if len(args) > 1 else "2024"
        
        result = self.command_processor.get_sleeper_draft_status(username, season)
        
        return self._handle_command_result(result, "Failed to get draft status")
    
    def handle_sleeper_draft(self, args: List[str]) -> int:
        """Handle Sleeper draft display command."""
        # Get default draft ID from config if not provided
        config = self.config_manager.load_config()
        default_draft_id = getattr(config, 'sleeper_draft_id', None)
        
        if not args and not default_draft_id:
            print("ERROR: Draft ID required (not provided and not set in config)")
            print("Usage: sleeper draft <draft_id>")
            print("Or set 'sleeper_draft_id' in config/config.json")
            return 1
        
        draft_id = args[0] if args else default_draft_id
        
        result = self.command_processor.display_sleeper_draft(draft_id)
        
        return self._handle_command_result(result, "Failed to display draft")
    
    def handle_sleeper_league(self, args: List[str]) -> int:
        """Handle Sleeper league rosters command."""
        # For league command, we could potentially derive league_id from user's current leagues
        # but for now, require explicit league_id as there's no direct config default
        if not args:
            print("ERROR: League ID required")
            print("Usage: sleeper league <league_id>")
            print("Tip: Use 'sleeper leagues <username>' to find league IDs")
            return 1
        
        league_id = args[0]
        
        result = self.command_processor.display_sleeper_league_rosters(league_id)
        
        return self._handle_command_result(result, "Failed to display league rosters")
    
    def handle_sleeper_leagues(self, args: List[str]) -> int:
        """Handle Sleeper leagues list command."""
        default_username = self._get_config_default('sleeper_username')
        
        if not args and not default_username:
            print("ERROR: Username required (not provided and not set in config)")
            print("Usage: sleeper leagues <username> [season]")
            print("Or set 'sleeper_username' in config/config.json")
            return 1
        
        username = args[0] if args else default_username
        season = args[1] if len(args) > 1 else "2024"
        
        result = self.command_processor.list_sleeper_leagues(username, season)
        return self._handle_command_result(result, "Failed to list leagues")
    
    def handle_sleeper_cache(self, args: List[str]) -> int:
        """Handle Sleeper cache management commands."""
        from utils.sleeper_cache import get_player_cache
        
        if not args:
            # Show cache info
            cache = get_player_cache()
            info = cache.get_cache_info()
            
            print("\nSLEEPER PLAYER CACHE INFO")
            print("="*50)
            print(f"Cache exists: {'Yes' if info['cache_exists'] else 'No'}")
            print(f"Cache valid: {'Yes' if info['cache_valid'] else 'No'}")
            print(f"Cache file: {info['cache_file']}")
            
            if info['cache_exists']:
                meta = info['metadata']
                print(f"Player count: {meta.get('player_count', 0):,}")
                print(f"Last updated: {meta.get('last_updated', 'Unknown')}")
                print(f"File size: {info.get('file_size_mb', 0)} MB")
            
            print("\nCommands:")
            print("  sleeper cache info     - Show this information")
            print("  sleeper cache refresh  - Force refresh player data")
            print("  sleeper cache clear    - Clear cached data")
            return 0
        
        action = args[0].lower()
        cache = get_player_cache()
        
        if action == "info":
            return self.handle_sleeper_cache([])  # Show info
        elif action == "refresh":
            print("Refreshing player cache from Sleeper API...")
            players = cache.get_players(force_refresh=True)
            if players:
                print(f"Successfully refreshed cache with {len(players):,} players")
                return 0
            else:
                print("Failed to refresh player cache")
                return 1
        elif action == "clear":
            if cache.clear_cache():
                print("Player cache cleared successfully")
                return 0
            else:
                print("Failed to clear player cache")
                return 1
        else:
            print(f"ERROR: Unknown cache action: {action}")
            print("Available actions: info, refresh, clear")
            return 1
    
    def show_help(self):
        """Display help information."""
        print(__doc__)
        print("\nDETAILED COMMAND REFERENCE:")
        print("="*60)
        
        print("\nBID COMMAND")
        print("   Calculate bid recommendation for a specific player")
        print("   Usage: bid <player_name> [current_bid]")
        print("   Examples:")
        print("     bid 'Josh Allen' 25")
        print("     bid 'Christian McCaffrey'")
        print("     bid 'Cooper Kupp' 45")
        
        print("\nMOCK COMMAND")
        print("   Run a single mock draft simulation")
        print("   Usage: mock [strategy] [teams]")
        print(f"   Available strategies: {', '.join(AVAILABLE_STRATEGIES)}")
        print("   Examples:")
        print("     mock value 10")
        print("     mock aggressive 12")
        print("     mock sigmoid")
        
        print("\nTOURNAMENT COMMAND")
        print("   Run elimination-style tournament with all strategies")
        print("   Usage: tournament [rounds] [teams_per_draft]")
        print("   - Tests all available strategies in head-to-head competition")
        print("   - Winners advance through elimination rounds")
        print("   - Each draft has exactly 10 teams (strategies duplicated as needed)")
        print("   Examples:")
        print("     tournament      # Default elimination tournament")
        print("     tournament 3    # 3 rounds maximum")
        print("     tournament 4 12 # 4 rounds with 12 teams per draft")
        
        print("\nPING COMMAND")
        print("   Test connectivity to Sleeper API")
        print("   Usage: ping")
        
        print("\nSLEEPER COMMANDS")
        print("   Access Sleeper draft and league information")
        print("   Usage: sleeper <subcommand> [options]")
        print("   Subcommands:")
        print("     status [username] [season] - Show draft status for user")
        print("     draft [draft_id]          - Display draft details")
        print("     league <league_id>        - Show league rosters")
        print("     leagues [username] [season] - List user's leagues")
        print("     cache [action]            - Manage player data cache")
        print("   Note: username and draft_id can be set as defaults in config.json")
        print("   Examples:")
        print("     sleeper status myusername")
        print("     sleeper status              # Uses config default username")
        print("     sleeper draft 123456789")
        print("     sleeper draft               # Uses config default draft_id")
        print("     sleeper league 987654321")
        print("     sleeper leagues myusername 2024")
        print("     sleeper cache refresh       # Update player data")
        
        print("\nHELP COMMAND")
        print("   Show this help message")
        print("   Usage: help")
        
        print("\nCONFIGURATION:")
        print("   Edit config/config.json to customize:")
        print("   - Data source (FantasyPros or Sleeper)")
        print("   - Budget and roster settings")
        print("   - Default strategy preferences")
        print("   - Sleeper defaults: sleeper_username, sleeper_draft_id")
        
        print("="*60)
    
    def _display_bid_recommendation(self, result: Dict):
        """Display simplified bid recommendation results for quick decision making."""
        data_source = result.get('data_source', 'local')
        
        # Key player info
        player_name = result.get('player_name', result.get('name', 'Unknown'))
        player_pos = result.get('player_position', result.get('position', 'N/A'))
        print(f"\n{player_name} - {player_pos}, {result.get('player_team', 'N/A')}")
        if 'projected_points' in result:
            print(f"   Points: {result['projected_points']:.0f}")

        # Current bid context
        current_bid = result.get('current_bid', 0)
        print(f"\nCurrent bid: ${current_bid:.0f}")
        recommendation_level = result.get('recommendation_level', 'N/A')
        confidence = result.get('confidence', 0)
        print(f"   Action: {recommendation_level} ({confidence:.0%} confidence)" if confidence else f"   Action: {recommendation_level}")

        # Budget context
        team_budget = result.get('team_budget', 0)
        recommended_bid = result.get('recommended_bid', 0)
        if team_budget:
            budget_pct = (recommended_bid / team_budget) * 100 if team_budget > 0 else 0
            print(f"   Budget: ${team_budget:.0f} remaining ({budget_pct:.1f}% of budget)")

        # Team needs (if any)
        team_needs = result.get('team_needs', [])
        if team_needs:
            needs_display = ', '.join(team_needs[:3])
            if len(team_needs) > 3:
                needs_display += f" +{len(team_needs)-3} more"
            print(f"   Needs: {needs_display}")

        # Quick reasoning
        if data_source == 'sleeper':
            print("   Live Draft Context")
        else:
            print("   Mock Draft Projection")

        # Value and recommendation
        if 'auction_value' in result:
            print(f"\nValue: ${result['auction_value']:.0f}")
        if recommended_bid:
            print(f"RECOMMENDED BID: ${recommended_bid:.0f}")
        print()
    
    def _display_mock_results(self, result: Dict):
        """Display mock draft results."""
        # Use the new print module for consistent table formatting
        print_mock_draft(result, detailed=True)
    
    def _display_tournament_results(self, result: Dict):
        """Display enhanced tournament results."""
        execution_time = result.get('execution_time', 0)
        if execution_time > 0:
            print(f"\nTournament completed in {execution_time:.1f} seconds")
        
        # Display basic tournament info
        winner = result.get('tournament_winner', 'Unknown')
        rounds = result.get('total_rounds', 'Unknown')
        
        print("\n\U0001f3c6 TOURNAMENT RESULTS")
        print("="*50)
        print(f"Champion: {winner}")
        print(f"Total rounds: {rounds}")
        print("="*50)
    
    def _display_ping_results(self, result: Dict):
        """Display Sleeper API connectivity test results."""
        print("\nCONNECTIVITY TEST RESULTS")
        print("="*50)

        tests = result.get('tests')
        if tests:
            for test in tests:
                status_prefix = "PASS" if test['status'] == 'PASS' else "WARN" if test['status'] == 'WARN' else "FAIL"
                print(f"[{status_prefix}] {test['test']:<20} {test['status']}")
                print(f"       {test['details']}")
        else:
            error_msg = result.get('error', 'No details available')
            print("[FAIL] connectivity_check      ERROR")
            print(f"       {error_msg}")
        
        print("="*50)
        summary = result.get('summary', 'N/A')
        overall_status = result.get('overall_status', 'UNKNOWN')
        print(f"Summary: {summary}")
        print(f"Overall Status: {overall_status}")

        if overall_status == 'HEALTHY':
            print("All systems operational!")
        elif overall_status == 'DEGRADED':
            print("Some features may be limited")
        else:
            print("Connection issues detected")
    
    def _parse_bid_args(self, args: List[str]) -> tuple:
        """
        Parse bid command arguments intelligently to handle unquoted multi-word names.
        
        Args:
            args: Command line arguments
            
        Returns:
            Tuple of (player_name, current_bid, sleeper_draft_id)
        """
        if not args:
            return "", 1.0, None
        
        # Try to find the first numeric argument (current_bid)
        bid_index = None
        for i, arg in enumerate(args):
            try:
                float(arg)
                bid_index = i
                break
            except ValueError:
                continue
        
        if bid_index is None:
            # No numeric arguments found, treat all as player name
            player_name = " ".join(args)
            current_bid = 1.0
            sleeper_draft_id = None
        else:
            # Found numeric argument, everything before it is player name
            player_name = " ".join(args[:bid_index])
            current_bid = float(args[bid_index])
            sleeper_draft_id = args[bid_index + 1] if len(args) > bid_index + 1 else None
        
        return player_name, current_bid, sleeper_draft_id

    def handle_undervalued_command(self, args: List[str]) -> int:
        """Handle undervalued players analysis command."""
        try:
            threshold = float(args[0]) if args else 15.0
        except (ValueError, IndexError):
            threshold = 15.0

        result = self.command_processor.analyze_undervalued_players(threshold)

        if result.get('success', False):
            players = result.get('undervalued_players', [])
            print(f"\nUndervalued players (threshold: {threshold}%):")
            if players:
                for p in players:
                    name = p.get('name', p.get('player_name', 'Unknown'))
                    pct = p.get('undervalued_pct', 0)
                    print(f"  {name} ({pct:.1f}% undervalued)")
            else:
                print("  No undervalued players found.")
            return 0
        else:
            print(f"ERROR: {result.get('error', 'Analysis failed')}")
            return 1


def main():
    """Main entry point for the CLI."""
    import sys

    try:
        cli = AuctionDraftCLI()
        return cli.run(sys.argv[1:])
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
