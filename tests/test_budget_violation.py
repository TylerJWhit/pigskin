#!/usr/bin/env python3
"""Test to identify when teams violate budget constraints."""

from classes.team import Team
from classes.player import Player
from strategies.value_based_strategy import ValueBasedStrategy
from config.config_manager import ConfigManager

def test_budget_constraint_violation():
    """Simulate a scenario where a team should run out of budget."""
    print("=== Testing Budget Constraint Violation ===")
    
    # Create team with proper config
    config = ConfigManager()
    roster_config = {
        "QB": 1, "RB": 2, "WR": 2, "TE": 1, 
        "FLEX": 2, "K": 1, "DST": 1, "BN": 5
    }
    
    team = Team("test_team", "owner1", "Test Team", 200, roster_config)
    strategy = ValueBasedStrategy()
    
    print(f"Team starts with ${team.budget} budget")
    print(f"Roster config: {team.roster_config}")
    print(f"Total slots: {sum(team.roster_config.values())}")
    
    # Simulate buying expensive players
    expensive_players = [
        ("Josh Allen", "QB", 45),
        ("Christian McCaffrey", "RB", 65),
        ("Cooper Kupp", "WR", 55),
        ("Davante Adams", "WR", 50),
        ("Travis Kelce", "TE", 40),
    ]
    
    for name, pos, price in expensive_players:
        player = Player(f"player_{name}", name, pos, "SEA")
        player.auction_value = price
        
        # Check what the strategy would allow before buying
        remaining_budget = team.budget
        max_bid = strategy.calculate_max_bid(team, remaining_budget)
        
        print(f"\nAttempting to buy {name} ({pos}) for ${price}")
        print(f"Strategy max bid allowed: ${max_bid}")
        
        if price <= max_bid:
            team.add_player(player, price)
            print(f"✅ Purchase allowed - budget now ${team.budget}")
        else:
            print(f"❌ Purchase blocked by budget constraint")
            break
    
    # Show final state
    current_roster_size = len(team.roster)
    total_slots = sum(team.roster_config.values())
    remaining_slots = total_slots - current_roster_size
    
    print(f"\n=== Final State ===")
    print(f"Roster: {current_roster_size}/{total_slots}")
    print(f"Budget: ${team.budget}")
    print(f"Remaining slots: {remaining_slots}")
    print(f"Budget per remaining slot: ${team.budget / max(1, remaining_slots):.2f}")
    
    if team.budget >= remaining_slots:
        print("✅ Team can complete roster")
    else:
        print("❌ Team CANNOT complete roster!")

if __name__ == "__main__":
    test_budget_constraint_violation()
