#!/usr/bin/env python3
"""Test to verify all strategies return integer bids."""

import sys
sys.path.append('.')

from classes.team import Team
from classes.player import Player
from classes.owner import Owner
from strategies.value_based_strategy import ValueBasedStrategy
from strategies.basic_strategy import BasicStrategy
from strategies.aggressive_strategy import AggressiveStrategy

def test_strategy_integer_bids():
    """Test that all strategies return integer bids."""
    print("=== Testing Strategy Integer Bids ===")
    
    # Create test objects
    team = Team("test_team", "owner1", "Test Team", 200)
    player = Player("test_player", "Test Player", "RB", "SEA")
    player.auction_value = 25.5  # Float value from data
    player.projected_points = 150.75  # Float value from data
    owner = Owner("owner1", "Test Owner")
    
    # Test strategies
    strategies = [
        ValueBasedStrategy(),
        BasicStrategy(),
        AggressiveStrategy()
    ]
    
    for strategy in strategies:
        print(f"\nTesting {strategy.name}...")
        
        # Test get_bid_for_player
        current_bid = 15
        remaining_budget = 100
        
        bid = strategy.get_bid_for_player(player, current_bid, team, remaining_budget)
        print(f"  Bid: {bid} (type: {type(bid).__name__})")
        
        if bid > 0:
            assert isinstance(bid, int), f"{strategy.name} should return int bid, got {type(bid)}"
            assert bid >= 1, f"{strategy.name} should return minimum $1 bid, got {bid}"
        
        print(f"  ✅ {strategy.name} bid test passed!")
    
    print("\n🎉 All strategy bid tests passed!")

if __name__ == "__main__":
    test_strategy_integer_bids()
