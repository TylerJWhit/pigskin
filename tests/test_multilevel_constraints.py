#!/usr/bin/env python3
"""
Test multi-level budget constraint enforcement.
Tests that teams cannot bid amounts that would prevent roster completion.
"""

from classes.team import Team
from classes.player import Player
from strategies.value_based_strategy import ValueBasedStrategy

def test_multilevel_budget_constraints():
    """Test that budget constraints are enforced at multiple levels."""
    
    print("Testing Multi-Level Budget Constraint Enforcement")
    print("=" * 50)
    
    # Create a team with limited budget
    team = Team(team_id="test_team", owner_id="test_owner", team_name="Test Team", budget=10)
    
    # Fill some roster spots (leaving 5 empty spots)
    for i in range(10):
        player = Player(
            player_id=f"player_{i}",
            name=f"Player{i}",
            position="WR",
            team="TEST",
            auction_value=8.0
        )
        team.roster.append(player)
    
    print(f"Team budget: ${team.budget}")
    print(f"Roster slots filled: {len(team.roster)}/15")
    print(f"Remaining slots: {15 - len(team.roster)}")
    print(f"Budget needed for completion: ${15 - len(team.roster)}")
    
    # Create strategy and test player
    strategy = ValueBasedStrategy()
    team.strategy = strategy
    
    test_player = Player(
        player_id="expensive_player",
        name="Expensive Player",
        position="QB",
        team="TEST",
        auction_value=15.0
    )
    
    # Test 1: Strategy-level constraint
    print("\n1. Testing Strategy-Level Constraints:")
    max_allowable = strategy.calculate_max_bid(team, team.budget)
    print(f"   Max allowable bid: ${max_allowable}")
    print(f"   Expected: ${team.budget - (15 - len(team.roster) - 1)} = ${team.budget - 4}")
    
    # Test 2: Direct constraint enforcement
    print("\n2. Testing Direct Constraint Enforcement:")
    high_bid = 8.0  # This would leave only $2 for 4 remaining slots
    constrained_bid = strategy._enforce_budget_constraint(high_bid, team, team.budget)
    print(f"   High bid ${high_bid} → constrained to ${constrained_bid}")
    
    # Test 3: Template method constraint
    print("\n3. Testing Template Method Constraints:")
    if hasattr(strategy, 'calculate_bid_with_constraints'):
        # Mock owner for the test
        class MockOwner:
            def __init__(self):
                self.risk_tolerance = 0.7
                self.position_preferences = {}
        
        owner = MockOwner()
        constrained_template_bid = strategy.calculate_bid_with_constraints(
            test_player, team, owner, 1.0, team.budget, []
        )
        print(f"   Template method bid: ${constrained_template_bid}")
        print(f"   Should be ≤ ${max_allowable}")
    else:
        print("   Template method not available")
    
    # Test 4: Verify constraint logic
    print("\n4. Verifying Constraint Logic:")
    remaining_slots = 15 - len(team.roster)
    budget_for_remaining = team.budget - 1  # Reserve $1 for the current bid
    budget_per_remaining_slot = budget_for_remaining / (remaining_slots - 1) if remaining_slots > 1 else team.budget
    
    print(f"   Remaining slots: {remaining_slots}")
    print(f"   Budget after this bid: ${budget_for_remaining}")
    print(f"   Budget per remaining slot: ${budget_per_remaining_slot:.2f}")
    print(f"   Can afford completion: {budget_per_remaining_slot >= 1.0}")
    
    print("\n" + "=" * 50)
    print("Multi-level budget constraint test complete!")

if __name__ == "__main__":
    test_multilevel_budget_constraints()
