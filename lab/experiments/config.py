"""Experiment configuration loader for named lab experiments.

Provides :class:`ExperimentConfig`, which loads experiment parameters from
a YAML or JSON config file. Closes #188.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class ExperimentConfig:
    """Configuration for a named lab experiment loaded from a YAML or JSON file."""

    REQUIRED_FIELDS = ("name", "strategies", "num_simulations")

    def __init__(self, name: str, strategies: List[str], num_simulations: int, **extra: Any) -> None:
        self.name = name
        self.strategies = strategies
        self.num_simulations = num_simulations
        self._extra = extra

    @classmethod
    def load_from_file(cls, path: str) -> "ExperimentConfig":
        """Load experiment config from a YAML (.yaml/.yml) or JSON (.json) file.

        Args:
            path: Filesystem path to the config file.

        Returns:
            A populated :class:`ExperimentConfig` instance.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If required fields are missing or invalid.
            ImportError: If PyYAML is not installed for YAML files.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        raw: Dict[str, Any]
        suffix = file_path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            try:
                import yaml  # type: ignore[import]
            except ImportError as exc:
                raise ImportError(
                    "PyYAML is required for YAML config files: pip install pyyaml"
                ) from exc
            with open(file_path) as f:
                raw = yaml.safe_load(f) or {}
        elif suffix == ".json":
            with open(file_path) as f:
                raw = json.load(f)
        else:
            raise ValueError(f"Unsupported config format: {suffix!r}. Use .yaml or .json")

        return cls._validate_and_build(raw)

    @classmethod
    def _validate_and_build(cls, raw: Dict[str, Any]) -> "ExperimentConfig":
        """Validate raw config dict and return an :class:`ExperimentConfig`."""
        for field_name in cls.REQUIRED_FIELDS:
            if field_name not in raw:
                raise ValueError(f"Missing required field: {field_name!r}")

        num_sim = raw["num_simulations"]
        if not isinstance(num_sim, int) or num_sim <= 0:
            raise ValueError(f"num_simulations must be a positive integer, got {num_sim!r}")

        strategies = raw["strategies"]
        if not isinstance(strategies, list) or not strategies:
            raise ValueError("strategies must be a non-empty list")

        extra = {k: v for k, v in raw.items() if k not in cls.REQUIRED_FIELDS}
        return cls(name=raw["name"], strategies=strategies, num_simulations=num_sim, **extra)
