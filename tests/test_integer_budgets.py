#!/usr/bin/env python3
"""Quick test to verify integer budgets and bidding are working correctly."""

from classes.team import Team
from classes.player import Player

def test_integer_budgets():
    """Test that budgets remain integer throughout operations."""
    print("=== Testing Integer Budget Operations ===")
    
    # Create a team with integer budget
    team = Team("test_team", "owner1", "Test Team", 200)
    print(f"Initial budget: ${team.budget} (type: {type(team.budget).__name__})")
    assert isinstance(team.budget, int), f"Budget should be int, got {type(team.budget)}"
    
    # Create a test player
    player = Player("test_player", "Test Player", "RB", "SEA")
    player.auction_value = 25
    player.projected_points = 150
    
    # Test adding player with integer price
    price = 25
    print(f"Adding player for ${price} (type: {type(price).__name__})")
    success = team.add_player(player, price)
    print(f"Player added: {success}")
    print(f"Budget after purchase: ${team.budget} (type: {type(team.budget).__name__})")
    assert isinstance(team.budget, int), f"Budget should remain int, got {type(team.budget)}"
    assert team.budget == 175, f"Expected budget 175, got {team.budget}"
    
    # Test removing player
    success = team.remove_player(player)
    print(f"Player removed: {success}")
    print(f"Budget after removal: ${team.budget} (type: {type(team.budget).__name__})")
    assert isinstance(team.budget, int), f"Budget should remain int, got {type(team.budget)}"
    assert team.budget == 200, f"Expected budget 200, got {team.budget}"
    
    print("✅ All integer budget tests passed!")
    
    # Test with float input to ensure conversion
    print("\n=== Testing Float to Integer Conversion ===")
    team2 = Team("test_team2", "owner2", "Test Team 2", 200.0)  # Float input
    print(f"Team2 budget: ${team2.budget} (type: {type(team2.budget).__name__})")
    assert isinstance(team2.budget, int), f"Budget should be converted to int, got {type(team2.budget)}"
    
    # Test adding player with float price (should be converted)
    float_price = 30.0
    print(f"Adding player for ${float_price} (type: {type(float_price).__name__})")
    success = team2.add_player(player, float_price)
    print(f"Budget after float purchase: ${team2.budget} (type: {type(team2.budget).__name__})")
    assert isinstance(team2.budget, int), f"Budget should remain int after float operation, got {type(team2.budget)}"
    assert team2.budget == 170, f"Expected budget 170, got {team2.budget}"
    
    print("✅ All float conversion tests passed!")

if __name__ == "__main__":
    test_integer_budgets()
    print("\n🎉 All tests passed! Integer budgets are working correctly.")
