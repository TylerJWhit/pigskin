#!/usr/bin/env python3
"""
Strategy Spending Analysis Tool

Analyzes strategies to identify those that are underspending their budgets.
"""


def analyze_spending_patterns():
    """Analyze strategies based on the recent tournament data."""
    
    print("Strategy Spending Analysis")
    print("=" * 60)
    print("Based on recent verbose tournament results:")
    print()
    
    # Data from the tournament results
    spending_data = {
        # Group 1 - Average spending patterns observed
        'value': {'avg_spent': 78, 'max_budget': 200, 'typical_players': 8},
        'aggressive': {'avg_spent': 159, 'max_budget': 200, 'typical_players': 14},
        'conservative': {'avg_spent': 181, 'max_budget': 200, 'typical_players': 13},
        'sigmoid': {'avg_spent': 153, 'max_budget': 200, 'typical_players': 11},
        'improved_value': {'avg_spent': 195, 'max_budget': 200, 'typical_players': 10},
        'adaptive': {'avg_spent': 196, 'max_budget': 200, 'typical_players': 9},
        'vor': {'avg_spent': 198, 'max_budget': 200, 'typical_players': 6},
        'random': {'avg_spent': 196, 'max_budget': 200, 'typical_players': 5},
        
        # Group 2 - Average spending patterns observed  
        'balanced': {'avg_spent': 136, 'max_budget': 200, 'typical_players': 14},
        'basic': {'avg_spent': 187, 'max_budget': 200, 'typical_players': 11},
        'elite_hybrid': {'avg_spent': 196, 'max_budget': 200, 'typical_players': 9},
        'value_random': {'avg_spent': 197, 'max_budget': 200, 'typical_players': 7},
        'value_smart': {'avg_spent': 197, 'max_budget': 200, 'typical_players': 5},
        'hybrid_improved_value': {'avg_spent': 196, 'max_budget': 200, 'typical_players': 4},
        'league': {'avg_spent': 199, 'max_budget': 200, 'typical_players': 5},
        'refined_value_random': {'avg_spent': 197, 'max_budget': 200, 'typical_players': 4},
    }
    
    # Calculate spending efficiency metrics
    strategies_analysis = []
    
    for strategy_name, data in spending_data.items():
        budget_usage = (data['avg_spent'] / data['max_budget']) * 100
        efficiency = data['typical_players'] / max(data['avg_spent'], 1) * 100
        
        strategies_analysis.append({
            'strategy': strategy_name,
            'avg_spent': data['avg_spent'],
            'budget_usage': budget_usage,
            'typical_players': data['typical_players'],
            'efficiency': efficiency,
            'underspending': 200 - data['avg_spent']
        })
    
    # Sort by budget usage (ascending = most underspending first)
    strategies_analysis.sort(key=lambda x: x['budget_usage'])
    
    print("SPENDING ANALYSIS RESULTS:")
    print("-" * 80)
    print(f"{'Strategy':<20} {'Avg Spent':<12} {'Budget %':<10} {'Players':<8} {'Underspend':<12}")
    print("-" * 80)
    
    major_underspenders = []
    moderate_underspenders = []
    efficient_spenders = []
    
    for analysis in strategies_analysis:
        strategy = analysis['strategy']
        spent = analysis['avg_spent']
        budget_pct = analysis['budget_usage']
        players = analysis['typical_players']
        underspend = analysis['underspending']
        
        status = ""
        if budget_pct < 50:
            status = "🔴 MAJOR UNDERSPEND"
            major_underspenders.append(strategy)
        elif budget_pct < 75:
            status = "🟡 MODERATE UNDERSPEND" 
            moderate_underspenders.append(strategy)
        elif budget_pct < 95:
            status = "🟢 EFFICIENT"
            efficient_spenders.append(strategy)
        else:
            status = "⚫ MAXED OUT"
        
        print(f"{strategy:<20} ${spent:<11} {budget_pct:<9.1f}% {players:<8} ${underspend:<11} {status}")
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS FOR MORE AGGRESSIVE BIDDING:")
    print("="*80)
    
    print("\n🔴 MAJOR UNDERSPENDERS (need significant aggression increase):")
    for strategy in major_underspenders:
        print(f"  • {strategy.upper()}: Currently spending ~${spending_data[strategy]['avg_spent']}/200")
        print(f"    - Has ${200-spending_data[strategy]['avg_spent']} unused budget")
        print(f"    - Only getting {spending_data[strategy]['typical_players']} players")
        print("    - Should increase bid multipliers by 50-100%")
        print()
    
    print("🟡 MODERATE UNDERSPENDERS (need moderate aggression increase):")
    for strategy in moderate_underspenders:
        print(f"  • {strategy.upper()}: Currently spending ~${spending_data[strategy]['avg_spent']}/200")
        print(f"    - Has ${200-spending_data[strategy]['avg_spent']} unused budget") 
        print(f"    - Getting {spending_data[strategy]['typical_players']} players")
        print("    - Should increase bid multipliers by 20-30%")
        print()
    
    print("🟢 EFFICIENT SPENDERS (minor tweaks only):")
    for strategy in efficient_spenders:
        print(f"  • {strategy.upper()}: Currently spending ~${spending_data[strategy]['avg_spent']}/200")
        print(f"    - Getting {spending_data[strategy]['typical_players']} players") 
        print("    - Well balanced, minor adjustments may help")
        print()

def suggest_specific_improvements():
    """Suggest specific code changes for underspending strategies."""
    
    print("\n" + "="*80)
    print("SPECIFIC STRATEGY IMPROVEMENT SUGGESTIONS:")
    print("="*80)
    
    improvements = {
        'value': {
            'current_multiplier': 0.85,
            'suggested_multiplier': 1.3,
            'reason': 'Extremely conservative, needs to bid more aggressively',
            'file': 'value_based_strategy.py'
        },
        'balanced': {
            'current_multiplier': 'varies',
            'suggested_multiplier': 1.2,
            'reason': 'Good roster building but underspending significantly',
            'file': 'balanced_strategy.py'
        },
        'sigmoid': {
            'current_multiplier': 'calculated', 
            'suggested_multiplier': 'increase base',
            'reason': 'Complex calculation but result is too conservative',
            'file': 'sigmoid_strategy.py'
        }
    }
    
    for strategy, data in improvements.items():
        print(f"\n{strategy.upper()} STRATEGY:")
        print(f"  File: strategies/{data['file']}")
        print(f"  Issue: {data['reason']}")
        print(f"  Current: {data['current_multiplier']}")
        print(f"  Suggested: {data['suggested_multiplier']}")
        print("  Expected outcome: Increase spending by $50-100, get 3-5 more players")

if __name__ == "__main__":
    analyze_spending_patterns()
    suggest_specific_improvements()
