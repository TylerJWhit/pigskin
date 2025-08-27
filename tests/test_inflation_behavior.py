#!/usr/bin/env python3
"""
Test script to verify VOR strategy inflation/budget adjustment behavior.
"""

import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from classes.player import Player
from classes.team import Team
from classes.owner import Owner
from strategies.vor_strategy import VorStrategy
from strategies.improved_value_strategy import ImprovedValueStrategy


def create_test_player(name: str, position: str, auction_value: float, projected_points: float = None) -> Player:
    """Create a test player."""
    if projected_points is None:
        projected_points = auction_value * 10  # Rough conversion
    
    return Player(
        player_id=name.lower().replace(' ', '_'),
        name=name,
        position=position,
        team="TEST",
        auction_value=auction_value,
        projected_points=projected_points
    )


def create_test_team(budget: float, roster_players: list = None) -> Team:
    """Create a test team with specified budget and roster."""
    team = Team(
        team_id="test_team",
        team_name="Test Team",
        owner_id="test_owner",
        budget=budget
    )
    
    if roster_players:
        for player, price in roster_players:
            team.add_player(player, price)
    
    return team


def create_test_owner() -> Owner:
    """Create a test owner."""
    return Owner(
        owner_id="test_owner",
        name="Test Owner",
        email="test@example.com"
    )


def test_vor_inflation_behavior():
    """Test VOR strategy's response to different market conditions."""
    print("Testing VOR Strategy Inflation/Budget Adjustment Behavior")
    print("=" * 70)
    
    # Create test player
    elite_rb = create_test_player("Elite RB", "RB", 45.0, 280.0)  # High VOR player
    
    # Create remaining players list (fewer good RBs = more scarcity)
    remaining_players_scarce = [
        create_test_player("RB1", "RB", 25.0, 200.0),
        create_test_player("RB2", "RB", 15.0, 160.0),
        create_test_player("WR1", "WR", 30.0, 220.0),
        create_test_player("WR2", "WR", 25.0, 200.0),
    ]
    
    remaining_players_plenty = [
        create_test_player("RB1", "RB", 40.0, 270.0),
        create_test_player("RB2", "RB", 35.0, 250.0),
        create_test_player("RB3", "RB", 30.0, 230.0),
        create_test_player("RB4", "RB", 25.0, 200.0),
        create_test_player("RB5", "RB", 20.0, 180.0),
        create_test_player("WR1", "WR", 30.0, 220.0),
        create_test_player("WR2", "WR", 25.0, 200.0),
    ]
    
    # Create test owner
    owner = create_test_owner()
    
    # Initialize VOR strategy
    vor_strategy = VorStrategy(aggression=1.0, scarcity_weight=0.7)
    
    # Test scenarios
    scenarios = [
        ("High Budget, Few RBs Available", 180, remaining_players_scarce, []),
        ("Low Budget, Few RBs Available", 50, remaining_players_scarce, []),
        ("High Budget, Many RBs Available", 180, remaining_players_plenty, []),
        ("Low Budget, Many RBs Available", 50, remaining_players_plenty, []),
        ("Mid-Draft, Need RB", 80, remaining_players_scarce, [
            (create_test_player("QB Drafted", "QB", 15.0), 15),
            (create_test_player("WR Drafted", "WR", 20.0), 20),
        ]),
        ("Late Draft, Almost Full Roster", 25, remaining_players_scarce, [
            (create_test_player("QB1", "QB", 15.0), 15),
            (create_test_player("QB2", "QB", 5.0), 5),
            (create_test_player("WR1", "WR", 25.0), 25),
            (create_test_player("WR2", "WR", 20.0), 20),
            (create_test_player("WR3", "WR", 15.0), 15),
            (create_test_player("WR4", "WR", 10.0), 10),
            (create_test_player("TE1", "TE", 15.0), 15),
            (create_test_player("TE2", "TE", 5.0), 5),
            (create_test_player("K1", "K", 3.0), 3),
            (create_test_player("DST1", "DST", 3.0), 3),
            (create_test_player("RB1", "RB", 30.0), 30),
            (create_test_player("RB2", "RB", 20.0), 20),
        ]),
    ]
    
    for scenario_name, budget, remaining_players, existing_roster in scenarios:
        print(f"\nScenario: {scenario_name}")
        print("-" * 50)
        
        # Create team for this scenario
        team = create_test_team(budget, existing_roster)
        
        # Test different current bid levels
        current_bids = [1, 10, 20, 30, 40, 50]
        
        print(f"Team Budget: ${budget}")
        print(f"Team Spent: ${team.get_total_spent()}")
        print(f"Team Remaining: ${team.budget}")
        print(f"Roster Size: {len(team.roster)}/15")
        print(f"Remaining Players: {len(remaining_players)} ({len([p for p in remaining_players if p.position == 'RB'])} RBs)")
        print(f"Player Value: ${elite_rb.auction_value} (VOR: {vor_strategy._calculate_vor(elite_rb):.1f})")
        print()
        
        for current_bid in current_bids:
            if current_bid >= team.budget:
                break
                
            recommended_bid = vor_strategy.calculate_bid(
                elite_rb, team, owner, current_bid, team.budget, remaining_players
            )
            
            # Calculate some metrics to understand the strategy's thinking
            vor = vor_strategy._calculate_vor(elite_rb)
            position_priority = vor_strategy._calculate_position_priority(elite_rb, team)
            scarcity_multiplier = vor_strategy._calculate_remaining_scarcity(elite_rb, remaining_players)
            remaining_slots = vor_strategy._get_remaining_roster_slots(team)
            
            print(f"Current Bid: ${current_bid:2d} -> Recommended: ${recommended_bid:5.1f} "
                  f"(VOR: {vor:4.1f}, Priority: {position_priority:.2f}, "
                  f"Scarcity: {scarcity_multiplier:.2f}, Slots Left: {remaining_slots})")
        
        print()


def test_improved_value_inflation_behavior():
    """Test Improved Value strategy's response to different market conditions."""
    print("\nTesting Improved Value Strategy Inflation/Budget Adjustment Behavior")
    print("=" * 70)
    
    # Similar test for improved value strategy
    elite_rb = create_test_player("Elite RB", "RB", 45.0, 280.0)
    owner = create_test_owner()
    
    # Different remaining player scenarios
    remaining_players_scarce = [
        create_test_player("RB1", "RB", 25.0, 200.0),
        create_test_player("RB2", "RB", 15.0, 160.0),
    ]
    
    improved_value_strategy = ImprovedValueStrategy(aggression=1.0, scarcity_weight=0.3)
    
    scenarios = [
        ("High Budget Scenario", 180, []),
        ("Low Budget Scenario", 50, []),
        ("Nearly Full Roster", 25, [
            (create_test_player("QB1", "QB", 15.0), 15),
            (create_test_player("WR1", "WR", 25.0), 25),
            (create_test_player("WR2", "WR", 20.0), 20),
            (create_test_player("TE1", "TE", 15.0), 15),
            (create_test_player("K1", "K", 3.0), 3),
            (create_test_player("DST1", "DST", 3.0), 3),
            (create_test_player("RB1", "RB", 30.0), 30),
            (create_test_player("RB2", "RB", 20.0), 20),
            (create_test_player("RB3", "RB", 15.0), 15),
            (create_test_player("WR3", "WR", 10.0), 10),
            (create_test_player("WR4", "WR", 8.0), 8),
            (create_test_player("TE2", "TE", 5.0), 5),
        ]),
    ]
    
    for scenario_name, budget, existing_roster in scenarios:
        print(f"\nScenario: {scenario_name}")
        print("-" * 40)
        
        team = create_test_team(budget, existing_roster)
        
        current_bids = [1, 10, 20, 30, 40]
        
        print(f"Budget: ${budget}, Spent: ${team.get_total_spent()}, Remaining: ${team.budget}")
        print(f"Roster: {len(team.roster)}/15")
        print()
        
        for current_bid in current_bids:
            if current_bid >= team.budget:
                break
                
            recommended_bid = improved_value_strategy.calculate_bid(
                elite_rb, team, owner, current_bid, team.budget, remaining_players_scarce
            )
            
            priority = improved_value_strategy._calculate_position_priority(elite_rb, team)
            urgency = improved_value_strategy._calculate_position_urgency(elite_rb, team)
            
            print(f"Current Bid: ${current_bid:2d} -> Recommended: ${recommended_bid:5.1f} "
                  f"(Priority: {priority:.2f}, Urgency: {urgency:.2f})")


if __name__ == "__main__":
    test_vor_inflation_behavior()
    test_improved_value_inflation_behavior()
