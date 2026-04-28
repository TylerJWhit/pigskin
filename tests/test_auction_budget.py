#!/usr/bin/env python3
"""Quick test to verify budget constraints work in actual auction."""

from classes.draft import Draft
from classes.team import Team
from classes.owner import Owner
from classes.player import Player
from classes.auction import Auction
from strategies.value_based_strategy import ValueBasedStrategy
from strategies.basic_strategy import BasicStrategy
from data.fantasypros_loader import FantasyProsLoader
from config.config_manager import ConfigManager

def test_budget_constraint_in_auction():
    """Test budget constraints in a real auction scenario."""
    print("=== Testing Budget Constraints in Auction ===")
    
    # Load data
    loader = FantasyProsLoader()
    players = loader.load_all_players()
    print(f"Loaded {len(players)} players")
    
    # Create draft with proper config
    config_manager = ConfigManager()
    config = config_manager.load_config()
    draft = Draft("test_draft")
    
    # Create teams with proper roster config
    roster_config = config.roster_positions
    teams = []
    for i in range(2):
        strategy = ValueBasedStrategy() if i == 0 else BasicStrategy()
        owner = Owner(f"owner_{i+1}", f"Owner {i+1}")
        team = Team(f"team_{i+1}", f"owner_{i+1}", f"Team {i+1}", 200, roster_config)
        team.set_strategy(strategy)
        owner.assign_team(team)
        draft.add_team(team)
        teams.append(team)
    
    # Create auction
    strategies = {team.owner_id: team.strategy for team in teams}
    auction = Auction(draft, players, strategies)
    
    print(f"Starting auction with {len(teams)} teams")
    print(f"Team roster config: {teams[0].roster_config}")
    print(f"Total roster slots: {sum(teams[0].roster_config.values())}")
    
    # Run a few rounds and check budgets
    for round_num in range(10):
        auction._auto_nominate_player()
        auction._process_auto_bids()
        
        # Check team budgets every few rounds
        if round_num % 3 == 0:
            print(f"\n--- Round {round_num + 1} ---")
            for team in teams:
                roster_size = len(team.roster)
                total_slots = sum(team.roster_config.values())
                remaining_slots = total_slots - roster_size
                budget_per_slot = team.budget / max(1, remaining_slots) if remaining_slots > 0 else 0
                
                print(f"{team.team_name}: {roster_size}/{total_slots} players, ${team.budget} budget")
                if remaining_slots > 0:
                    print(f"  ${budget_per_slot:.2f} per remaining slot")
                    if team.budget < remaining_slots:
                        print(f"  ⚠️  BUDGET RISK: ${team.budget} < {remaining_slots} remaining slots")
                
                # Check what the strategy would allow for max bid
                if remaining_slots > 0:
                    max_bid = team.strategy.calculate_max_bid(team, team.budget)
                    print(f"  Max bid allowed: ${max_bid}")
    
    print(f"\n=== Final Results ===")
    for team in teams:
        roster_size = len(team.roster)
        total_slots = sum(team.roster_config.values())
        remaining_slots = total_slots - roster_size
        can_complete = team.budget >= remaining_slots
        
        print(f"{team.team_name}:")
        print(f"  Roster: {roster_size}/{total_slots}")
        print(f"  Budget: ${team.budget}")
        print(f"  Can complete: {'✅' if can_complete else '❌'}")

if __name__ == "__main__":
    test_budget_constraint_in_auction()
