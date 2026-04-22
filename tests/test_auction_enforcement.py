#!/usr/bin/env python3
"""Test auction-level budget constraint enforcement."""

from classes.draft import Draft
from classes.team import Team
from classes.owner import Owner
from strategies.value_based_strategy import ValueBasedStrategy
from strategies.basic_strategy import BasicStrategy
from data.fantasypros_loader import FantasyProsLoader
from config.config_manager import ConfigManager
from classes.auction import Auction

def test_auction_budget_enforcement():
    """Test that auction-level budget constraints prevent overspending."""
    print("=== Testing Auction-Level Budget Enforcement ===")
    
    # Setup
    config_manager = ConfigManager()
    config = config_manager.load_config()
    loader = FantasyProsLoader()
    players = loader.load_all_players()[:50]  # Use fewer players for speed
    
    draft = Draft('test')
    strategies = {}
    
    for i in range(2):
        strategy = ValueBasedStrategy() if i == 0 else BasicStrategy()
        owner = Owner(f'owner_{i+1}', f'Owner {i+1}')
        team = Team(f'team_{i+1}', f'owner_{i+1}', f'Team {i+1}', 200, config.roster_positions)
        team.set_strategy(strategy)
        owner.assign_team(team)
        draft.add_team(team)
        strategies[team.owner_id] = strategy
    
    auction = Auction(draft, players, strategies)
    
    print("Running auction with budget constraint enforcement...")
    
    # Run auction rounds
    for round_num in range(15):
        if draft.current_player:
            auction._nominate_next_player()
            auction._process_auto_bids()
        else:
            print(f"No current player at round {round_num}, stopping")
            break
    
    print("\n=== Results ===")
    for team in draft.teams:
        remaining = 15 - len(team.roster)
        can_complete = team.budget >= remaining
        
        print(f"{team.team_name}: {len(team.roster)}/15 roster, ${team.budget} budget, {remaining} slots left")
        if remaining > 0:
            print(f"  Budget per remaining slot: ${team.budget / remaining:.2f}")
            if team.budget < remaining:
                print(f"  ❌ Cannot complete roster! Need ${remaining - team.budget} more")
            else:
                print(f"  ✅ Can complete roster")
        else:
            print(f"  ✅ Roster complete!")

if __name__ == "__main__":
    test_auction_budget_enforcement()
