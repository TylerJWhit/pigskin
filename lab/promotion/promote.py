#!/usr/bin/env python3
"""Lab strategy promotion script.

Evaluates a lab strategy against a benchmark threshold and optionally copies
it from ``lab/strategies/`` into the production ``strategies/`` package.
Real benchmark score integration is deferred to Sprint 12 (issue #227).

Usage:
    python lab/promotion/promote.py --dry-run
    python lab/promotion/promote.py --dry-run --strategy my_strategy
    python lab/promotion/promote.py --strategy my_strategy --threshold 0.75
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def promote_strategy(strategy_name: str, threshold: float, dry_run: bool = False) -> bool:
    """Evaluate and optionally promote a lab strategy to main strategies/.

    Args:
        strategy_name: The registered name of the strategy to promote.
        threshold: Minimum efficiency score required for promotion.
        dry_run: If ``True``, print what would happen without modifying files.

    Returns:
        ``True`` if promotion criteria are met (or dry-run succeeds), ``False`` otherwise.
    """
    lab_path = Path("lab/strategies") / f"{strategy_name}.py"
    prod_path = Path("strategies") / f"{strategy_name}.py"

    if not lab_path.exists():
        print(f"ERROR: Lab strategy not found: {lab_path}", file=sys.stderr)
        return False

    if dry_run:
        print(f"[DRY RUN] Would evaluate {strategy_name} against threshold {threshold}")
        print(f"[DRY RUN] Source: {lab_path}")
        print(f"[DRY RUN] Target: {prod_path}")
        print("[DRY RUN] No files modified.")
        return True

    # Placeholder: fetch benchmark score from results_db (Sprint 12 / #227)
    print("ERROR: Live promotion not yet implemented — use --dry-run (tracked by #227)", file=sys.stderr)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Lab strategy promotion tool")
    parser.add_argument("--strategy", default=None, help="Strategy name to promote")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.70,
        help="Minimum efficiency threshold (default: 0.70)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making changes",
    )
    args = parser.parse_args()

    if args.dry_run:
        if args.strategy:
            promote_strategy(args.strategy, args.threshold, dry_run=True)
        else:
            print("[DRY RUN] No strategy specified. Pass --strategy <name> to evaluate.")
        sys.exit(0)

    if not args.strategy:
        print("ERROR: --strategy is required in non-dry-run mode", file=sys.stderr)
        sys.exit(1)

    success = promote_strategy(args.strategy, args.threshold, dry_run=False)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
