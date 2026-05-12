"""Promotion executor for graduating lab strategies to production.

Applies the promotion gate result to copy a validated strategy from the lab
package into the core ``strategies/`` package. Implementation tracked by #227.
"""

from __future__ import annotations


def promote_strategy(strategy_name: str, dry_run: bool = False) -> None:
    """Promote a lab strategy to the core production package.

    Copies strategy source, updates ``strategies/__init__.py`` registration,
    and records promotion metadata.

    Args:
        strategy_name: The registered name of the strategy to promote.
        dry_run: If ``True``, validate without making filesystem changes.

    Raises:
        NotImplementedError: Until issue #227 is implemented.
    """
    raise NotImplementedError("promote_strategy — tracked by #227")
