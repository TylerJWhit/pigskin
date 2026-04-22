#!/usr/bin/env python3
"""
Test script to demonstrate market inflation adjustment in VOR strategies.
Shows how strategies adapt when league money is running low.
"""

from classes.player import Player
from classes.team import Team
from classes.owner import Owner
from strategies.vor_strategy import VorStrategy


def create_test_player(name: str, position: str, auction_value: float, projected_points: float = None) -> Player:
    """Create a test player."""
    if projected_points is None:
        projected_points = auction_value * 6  # Rough conversion
    
    return Player(
        player_id=name.lower().replace(' ', '_'),
        name=name,
        position=position,
        team="TEST",
        auction_value=auction_value,
        projected_points=projected_points
    )


def simulate_league_inflation_scenario():
    """Simulate how VOR strategy adapts to league-wide budget constraints."""
    print("Market Inflation Simulation: How VOR Strategy Adapts to League Budget Constraints")
    print("=" * 90)
    
    # Test player: solid RB worth ~$25 in normal market
    test_player = create_test_player("Solid RB", "RB", 25.0, 180.0)  # VOR ~30
    
    vor_strategy = VorStrategy(aggression=1.0, scarcity_weight=0.5)
    
    # Simulate different league money scenarios
    # In real auctions, teams start with ~$200 each, so $2000 total for 10 teams
    # As draft progresses, total available money decreases
    
    scenarios = [
        # (scenario_name, my_budget, my_roster_size, league_context)
        ("Early Draft - Plenty of Money", 180, 1, "League has ~$1800 left total"),
        ("Mid Draft - Some Money Spent", 120, 5, "League has ~$1200 left total"),  
        ("Late Draft - Money Getting Tight", 60, 10, "League has ~$600 left total"),
        ("Very Late - Budget Crunch", 25, 13, "League has ~$250 left total"),
        ("End Game - Scraping Bottom", 8, 14, "League has ~$80 left total"),
    ]
    
    print(f"Test Player: {test_player.name} (${test_player.auction_value} value, VOR: {vor_strategy._calculate_vor(test_player):.1f})")
    print()
    
    for scenario_name, budget, roster_size, league_context in scenarios:
        print(f"Scenario: {scenario_name}")
        print(f"  {league_context}")
        print("-" * 60)
        
        # Create team with current budget and roster size
        team = Team("test_team", "Test Team", "test_owner", budget)
        
        # Fill roster with dummy players to simulate draft progress
        for i in range(roster_size):
            dummy_player = create_test_player(f"Drafted_{i}", "WR", 10.0)
            team.add_player(dummy_player, 10.0)
        
        team.budget = budget  # Reset budget to desired level
        
        # Create owner
        owner = Owner("test_owner", "Test Owner", "test@example.com")
        
        # Simulate remaining players pool getting smaller and lower quality
        remaining_players = []
        
        if scenario_name.startswith("Early"):
            # Lots of good players still available
            remaining_players = [
                create_test_player("Elite RB", "RB", 45.0, 300.0),
                create_test_player("Good RB1", "RB", 30.0, 220.0),
                create_test_player("Good RB2", "RB", 28.0, 210.0),
                create_test_player("Decent RB", "RB", 20.0, 180.0),
                create_test_player("Elite WR", "WR", 40.0, 280.0),
            ]
        elif scenario_name.startswith("Mid"):
            # Some good players left, but fewer
            remaining_players = [
                create_test_player("Good RB", "RB", 30.0, 220.0),
                create_test_player("Decent RB1", "RB", 20.0, 180.0),
                create_test_player("Decent RB2", "RB", 18.0, 170.0),
                create_test_player("Good WR", "WR", 25.0, 200.0),
            ]
        elif scenario_name.startswith("Late"):
            # Mostly mediocre players left
            remaining_players = [
                create_test_player("Decent RB", "RB", 20.0, 180.0),
                create_test_player("OK RB1", "RB", 15.0, 160.0),
                create_test_player("OK RB2", "RB", 12.0, 150.0),
                create_test_player("Meh WR", "WR", 10.0, 140.0),
            ]
        elif scenario_name.startswith("Very"):
            # Mostly scrubs left
            remaining_players = [
                create_test_player("OK RB", "RB", 15.0, 160.0),
                create_test_player("Backup RB1", "RB", 8.0, 130.0),
                create_test_player("Backup RB2", "RB", 6.0, 120.0),
                create_test_player("Bench WR", "WR", 5.0, 110.0),
            ]
        else:  # End game
            # Only scrubs left
            remaining_players = [
                create_test_player("Backup RB", "RB", 8.0, 130.0),
                create_test_player("Handcuff RB1", "RB", 3.0, 100.0),
                create_test_player("Handcuff RB2", "RB", 2.0, 95.0),
                create_test_player("Waiver WR", "WR", 1.0, 80.0),
            ]
        
        # Test at different bid levels
        current_bids = [1, 5, 10, 15, 20, 25, 30]
        
        print(f"My Team: ${budget} budget, {roster_size} players, {15-roster_size} slots left")
        print(f"Player Pool: {len(remaining_players)} players, {len([p for p in remaining_players if p.position == 'RB'])} RBs")
        print()
        
        for current_bid in current_bids:
            if current_bid >= budget:
                break
                
            recommended_bid = vor_strategy.calculate_bid(
                test_player, team, owner, current_bid, budget, remaining_players
            )
            
            # Show how strategy is thinking
            vor = vor_strategy._calculate_vor(test_player)
            position_priority = vor_strategy._calculate_position_priority(test_player, team)
            scarcity_factor = vor_strategy._calculate_remaining_scarcity(test_player, remaining_players)
            remaining_slots = vor_strategy._get_remaining_roster_slots(team)
            
            # Calculate implied inflation (how much above auction value we're willing to pay)
            auction_value = test_player.auction_value
            inflation_factor = recommended_bid / auction_value if auction_value > 0 else 1.0
            
            if recommended_bid > 0:
                print(f"  Bid ${current_bid:2d} -> Recommend ${recommended_bid:5.1f} "
                      f"({inflation_factor:4.1f}x value, VOR:{vor:3.0f}, "
                      f"Priority:{position_priority:.2f}, Scarcity:{scarcity_factor:.2f})")
            else:
                print(f"  Bid ${current_bid:2d} -> PASS (won't bid higher)")
        
        print()


if __name__ == "__main__":
    simulate_league_inflation_scenario()
