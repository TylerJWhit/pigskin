"""
Auction Draft Tool Classes

This package contains all the core classes for running fantasy football auction drafts:

- Player: Represents a fantasy football player
- Team: Represents a fantasy team with roster and budget management
- Owner: Represents a participant in the draft (human or AI)
- Strategy: Abstract base class and implementations for draft strategies
- Draft: Manages the overall draft state and flow
- Auction: Handles real-time auction mechanics with timers and auto-bidding
- Tournament: Runs multiple simulations to test and compare strategies
- DraftSetup: Utilities for creating drafts and importing data from Sleeper API

Relationships:
- Owner owns a Team
- Team contains roster spots that hold Players
- Team can have a Strategy assigned to handle bidding logic
- When Team.calculate_bid() is called, it uses the assigned Strategy
"""

from .player import Player
from .team import Team
from .owner import Owner
from .strategy import Strategy, ValueBasedStrategy, AggressiveStrategy, ConservativeStrategy, create_strategy, AVAILABLE_STRATEGIES  # noqa: F401
from .draft import Draft
from .auction import Auction
from .tournament import Tournament, run_strategy_comparison
from .draft_setup import DraftSetup

# Convenience functions (imported dynamically to avoid circular imports)
def create_simple_draft(owner_names, team_names):
    """Create a simple draft with human participants."""
    return DraftSetup.setup_draft_with_participants(
        "Simple Draft", 
        [{'owner_id': f"owner_{i+1}", 'owner_name': name, 'team_name': team_name, 'is_human': True}
         for i, (name, team_name) in enumerate(zip(owner_names, team_names))]
    )

def create_ai_vs_human_draft(human_name, human_team, ai_count=7):
    """Create a draft with one human vs multiple AI opponents."""
    participants = [{'owner_id': 'human_1', 'owner_name': human_name, 'team_name': human_team, 'is_human': True}]
    strategies = ['value', 'aggressive', 'conservative']
    for i in range(ai_count):
        strategy_type = strategies[i % len(strategies)]
        participants.append({
            'owner_id': f'ai_{i+1}', 'owner_name': f'AI {strategy_type.title()} {i+1}',
            'team_name': f'AI Team {i+1}', 'is_human': False, 'strategy_type': strategy_type
        })
    return DraftSetup.setup_draft_with_participants("Human vs AI Draft", participants)

__all__ = [
    'Player',
    'Team', 
    'Owner',
    'Strategy',
    'ValueBasedStrategy',
    'AggressiveStrategy', 
    'ConservativeStrategy',
    'create_strategy',
    'Draft',
    'Auction',
    'Tournament',
    'run_strategy_comparison',
    'DraftSetup',
    'create_simple_draft',
    'create_ai_vs_human_draft'
]

__version__ = '1.0.0'
