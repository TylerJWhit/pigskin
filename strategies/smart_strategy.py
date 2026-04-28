"""SmartStrategy — placeholder implementation.

This strategy currently delegates to the ValueBasedStrategy. It exists to
prevent import errors while a full implementation is developed separately.
"""

from .value_based_strategy import ValueBasedStrategy


class SmartStrategy(ValueBasedStrategy):
    """Smart bidding strategy (placeholder — uses value-based logic).

    A proper implementation should be developed in a future sprint. See
    GitHub issue #63 for context.
    """
    pass
