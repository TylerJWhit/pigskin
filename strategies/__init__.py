"""Strategies module for auction draft tool."""

from .base_strategy import Strategy
from .value_based_strategy import ValueBasedStrategy
from .aggressive_strategy import AggressiveStrategy
from .conservative_strategy import ConservativeStrategy
from .sigmoid_strategy import SigmoidStrategy
from .improved_value_strategy import ImprovedValueStrategy
from .adaptive_strategy import AdaptiveStrategy
from .vor_strategy import VorStrategy
from .random_strategy import RandomStrategy
# from .smart_strategy import SmartStrategy  # Temporarily disabled

# New imported strategies
from .balanced_strategy import BalancedStrategy
from .basic_strategy import BasicStrategy
from .elite_hybrid_strategy import EliteHybridStrategy
from .hybrid_strategies import ValueRandomStrategy, ValueSmartStrategy, ImprovedValueStrategy as HybridImprovedValueStrategy
from .league_strategy import LeagueStrategy
from .refined_value_random_strategy import RefinedValueRandomStrategy

# Strategy factory
AVAILABLE_STRATEGIES = {
    'value': ValueBasedStrategy,
    'aggressive': AggressiveStrategy,
    'conservative': ConservativeStrategy,
    'sigmoid': SigmoidStrategy,
    'improved_value': ImprovedValueStrategy,
    'adaptive': AdaptiveStrategy,
    'vor': VorStrategy,
    'random': RandomStrategy,
    # 'smart': SmartStrategy  # Temporarily disabled
    
    # New imported strategies
    'balanced': BalancedStrategy,
    'basic': BasicStrategy,
    'elite_hybrid': EliteHybridStrategy,
    'value_random': ValueRandomStrategy,
    'value_smart': ValueSmartStrategy,
    'hybrid_improved_value': HybridImprovedValueStrategy,
    'league': LeagueStrategy,
    'refined_value_random': RefinedValueRandomStrategy,
}


def create_strategy(strategy_type: str) -> Strategy:
    """Create a strategy instance by type."""
    if strategy_type in AVAILABLE_STRATEGIES:
        return AVAILABLE_STRATEGIES[strategy_type]()
    else:
        raise ValueError(f"Unknown strategy type: {strategy_type}. Available: {list(AVAILABLE_STRATEGIES.keys())}")


def list_available_strategies() -> list:
    """Return list of available strategy types."""
    return list(AVAILABLE_STRATEGIES.keys())


def get_strategy_info(strategy_type: str) -> dict:
    """Get information about a strategy."""
    if strategy_type not in AVAILABLE_STRATEGIES:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
    
    strategy_class = AVAILABLE_STRATEGIES[strategy_type]
    instance = strategy_class()
    
    return {
        'name': instance.name,
        'description': instance.description,
        'parameters': instance.parameters.copy()
    }


__all__ = [
    'Strategy',
    'ValueBasedStrategy',
    'AggressiveStrategy', 
    'ConservativeStrategy',
    'SigmoidStrategy',
    'ImprovedValueStrategy',
    'AdaptiveStrategy',
    'VorStrategy',
    'RandomStrategy',
    # 'SmartStrategy',
    
    # New imported strategies
    'BalancedStrategy',
    'BasicStrategy',
    'EliteHybridStrategy',
    'ValueRandomStrategy',
    'ValueSmartStrategy',
    'HybridImprovedValueStrategy',
    'LeagueStrategy',
    'RefinedValueRandomStrategy',
    
    'AVAILABLE_STRATEGIES',
    'create_strategy',
    'list_available_strategies',
    'get_strategy_info'
]
