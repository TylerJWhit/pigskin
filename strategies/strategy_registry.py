"""StrategyRegistry — strategy factory with YAML/dict loading (issue #259).

Security: ``base_class`` is resolved only from ``_BASE_CLASS_ALLOWLIST``.
No dynamic imports or ``eval``/``exec`` are used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Type

from .base_strategy import Strategy
from .strategy_config import StrategyConfig

# ---------------------------------------------------------------------------
# Hardcoded allowlist — the ONLY classes that may be instantiated via config.
# Populated from the strategy audit (#255).
# ---------------------------------------------------------------------------
_BASE_CLASS_ALLOWLIST: Dict[str, Type[Strategy]] = {}  # populated at module load


def _build_allowlist() -> Dict[str, Type[Strategy]]:
    """Import all strategy classes and return the allowlist mapping.

    Importing lazily here avoids circular imports (strategies/__init__.py
    imports StrategyRegistry, which would re-import __init__ if done at
    module level).
    """
    from .value_based_strategy import ValueBasedStrategy
    from .aggressive_strategy import AggressiveStrategy
    from .conservative_strategy import ConservativeStrategy
    from .sigmoid_strategy import SigmoidStrategy
    from .improved_value_strategy import ImprovedValueStrategy
    from .adaptive_strategy import AdaptiveStrategy
    from .vor_strategy import VorStrategy
    from .random_strategy import RandomStrategy
    from .smart_strategy import SmartStrategy
    from .balanced_strategy import BalancedStrategy
    from .basic_strategy import BasicStrategy
    from .elite_hybrid_strategy import EliteHybridStrategy
    from .enhanced_vor_strategy import InflationAwareVorStrategy
    from .hybrid_strategies import ValueRandomStrategy, ValueSmartStrategy
    from .league_strategy import LeagueStrategy
    from .refined_value_random_strategy import RefinedValueRandomStrategy

    return {
        cls.__name__: cls
        for cls in [
            ValueBasedStrategy,
            AggressiveStrategy,
            ConservativeStrategy,
            SigmoidStrategy,
            ImprovedValueStrategy,
            AdaptiveStrategy,
            VorStrategy,
            RandomStrategy,
            SmartStrategy,
            BalancedStrategy,
            BasicStrategy,
            EliteHybridStrategy,
            InflationAwareVorStrategy,
            ValueRandomStrategy,
            ValueSmartStrategy,
            LeagueStrategy,
            RefinedValueRandomStrategy,
        ]
    }


class StrategyRegistry:
    """Factory for creating Strategy instances via key, dict, or YAML."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, key: str) -> Strategy:
        """Backwards-compatible creation by strategy key.

        Delegates to AVAILABLE_STRATEGIES for full parity with create_strategy().

        Args:
            key: Strategy key (e.g. 'vor', 'balanced').

        Returns:
            A new Strategy instance.

        Raises:
            ValueError: Unknown key.
        """
        from strategies import AVAILABLE_STRATEGIES  # avoids circular import

        if key not in AVAILABLE_STRATEGIES:
            raise ValueError(
                f"Unknown strategy key: {key!r}. "
                f"Available: {list(AVAILABLE_STRATEGIES.keys())}"
            )
        return AVAILABLE_STRATEGIES[key]()

    @classmethod
    def from_dict(cls, config: dict) -> Strategy:
        """Create a Strategy from a raw configuration dictionary.

        Args:
            config: Must contain at minimum 'name', 'display_name',
                    'description', and 'base_class' keys.

        Returns:
            A new Strategy instance of the class named by 'base_class'.

        Raises:
            ValueError: 'base_class' not in allowlist, or config invalid.
            pydantic.ValidationError: config dict fails schema validation.
        """
        strategy_config = StrategyConfig(**config)
        return cls._instantiate(strategy_config)

    @classmethod
    def from_yaml(cls, path: str | Path) -> Strategy:
        """Create a Strategy from a YAML config file.

        Args:
            path: Path to a YAML file conforming to StrategyConfig schema.

        Returns:
            A new Strategy instance.

        Raises:
            FileNotFoundError: YAML file does not exist.
            ValueError: 'base_class' not in allowlist.
            pydantic.ValidationError: YAML contents fail schema validation.
        """
        try:
            import yaml  # optional dependency
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required for from_yaml(). "
                "Install it with: pip install pyyaml"
            ) from exc

        yaml_path = Path(path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"Strategy config not found: {yaml_path}")

        with yaml_path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        return cls.from_dict(raw)

    @classmethod
    def list_available(cls) -> List[str]:
        """Return sorted list of available strategy keys.

        Replaces list_available_strategies() from strategies/__init__.py.
        """
        from strategies import AVAILABLE_STRATEGIES  # avoids circular import

        return sorted(AVAILABLE_STRATEGIES.keys())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _get_allowlist(cls) -> Dict[str, Type[Strategy]]:
        global _BASE_CLASS_ALLOWLIST
        if not _BASE_CLASS_ALLOWLIST:
            _BASE_CLASS_ALLOWLIST = _build_allowlist()
        return _BASE_CLASS_ALLOWLIST

    @classmethod
    def _instantiate(cls, config: StrategyConfig) -> Strategy:
        allowlist = cls._get_allowlist()
        if config.base_class not in allowlist:
            raise ValueError(
                f"base_class {config.base_class!r} is not in the allowlist. "
                f"Allowed: {sorted(allowlist.keys())}"
            )
        strategy_class = allowlist[config.base_class]
        if config.parameters:
            return strategy_class(**config.parameters)
        return strategy_class()
