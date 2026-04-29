#!/usr/bin/env python3
"""
Strategy Analysis Tool

Analyzes strategies to identify issues preventing them from bidding effectively.
"""

from classes import create_strategy, AVAILABLE_STRATEGIES
from classes.player import Player
from classes.team import Team  
from classes.owner import Owner
from data.fantasypros_loader import FantasyProsLoader
from config.config_manager import ConfigManager

def test_strategy_bidding():
    """Test all strategies to see if they can bid."""
    print("Strategy Bidding Analysis")
    print("=" * 50)
    
    # Setup test environment
    config = ConfigManager().load_config()
    loader = FantasyProsLoader(config.data_path)
    players = loader.load_all_players()
    
    if not players:
        print("ERROR: No players loaded")
        return
    
    # Create test player
    test_player = players[0]  # Use first player as test
    
    # Create test team and owner
    owner = Owner("test_owner", "Test Owner")
    team = Team("test_team", "test_owner", "Test Team")
    owner.assign_team(team)
    
    print(f"Testing with player: {test_player.name} ({test_player.position})")
    print(f"Player auction value: {getattr(test_player, 'auction_value', 'N/A')}")
    print()
    
    for strategy_name in AVAILABLE_STRATEGIES:
        print(f"Testing {strategy_name}:")
        
        try:
            strategy = create_strategy(strategy_name)
            team.set_strategy(strategy)
            
            # Test bidding
            bid = strategy.calculate_bid(
                player=test_player,
                team=team,
                owner=owner,
                current_bid=5.0,
                remaining_budget=200.0,
                remaining_players=players[:50]  # Sample remaining players
            )
            
            # Test nomination
            should_nominate = strategy.should_nominate(
                player=test_player,
                team=team,
                owner=owner,
                remaining_budget=200.0
            )
            
            print(f"  ✓ Bid: ${bid:.1f}")
            print(f"  ✓ Would nominate: {should_nominate}")
            
            if bid == 0:
                print("  ⚠️  WARNING: Strategy bids $0 - may not participate in auctions")
            
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")
        
        print()

def analyze_winning_strategies():
    """Analyze what makes winning strategies successful."""
    print("\nWinning Strategy Analysis")
    print("=" * 50)
    
    winning_strategies = ['basic', 'improved_value', 'league']
    
    for strategy_name in winning_strategies:
        print(f"\nAnalyzing {strategy_name}:")
        
        try:
            strategy = create_strategy(strategy_name)
            print(f"  Name: {strategy.name}")
            print(f"  Description: {strategy.description}")
            
            # Check for key attributes
            key_features = []
            
            if hasattr(strategy, 'aggression'):
                key_features.append(f"Aggression: {strategy.aggression}")
            
            if hasattr(strategy, 'scarcity_weight'):
                key_features.append(f"Scarcity weight: {strategy.scarcity_weight}")
                
            if hasattr(strategy, 'randomness'):
                key_features.append(f"Randomness: {strategy.randomness}")
            
            if key_features:
                print(f"  Key features: {', '.join(key_features)}")
            else:
                print("  Key features: None identified")
                
        except Exception as e:
            print(f"  ERROR: {str(e)}")

if __name__ == "__main__":
    test_strategy_bidding()
    analyze_winning_strategies()
