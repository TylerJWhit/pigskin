"""Strategy imports for backwards compatibility."""

import os
import sys

# Add the parent directory to the path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import everything from the strategies module
from strategies import (
    Strategy,
    ValueBasedStrategy,
    AggressiveStrategy,
    ConservativeStrategy,
    SigmoidStrategy,
    AVAILABLE_STRATEGIES,
    create_strategy,
    list_available_strategies,
    get_strategy_info
)

# Backwards compatibility exports
__all__ = [
    'Strategy',
    'ValueBasedStrategy',
    'AggressiveStrategy',
    'ConservativeStrategy',
    'SigmoidStrategy',
    'AVAILABLE_STRATEGIES',
    'create_strategy',
    'list_available_strategies',
    'get_strategy_info'
]
