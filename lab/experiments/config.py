"""Experiment configuration loader for named lab experiments.

Provides :class:`ExperimentConfig`, which loads experiment parameters from
a YAML or JSON config file. Implementation tracked by issue #226.
"""

from __future__ import annotations


class ExperimentConfig:
    """Configuration for a named lab experiment.

    Attributes will be populated from a config file by :meth:`load_from_file`.
    """

    def __init__(self) -> None:
        self.name: str = ""
        self.params: dict = {}

    @classmethod
    def load_from_file(cls, path: str) -> "ExperimentConfig":
        """Load experiment configuration from a YAML or JSON file.

        Args:
            path: Filesystem path to the config file.

        Returns:
            A populated :class:`ExperimentConfig` instance.

        Raises:
            NotImplementedError: Until issue #226 is implemented.
        """
        raise NotImplementedError("ExperimentConfig.load_from_file — tracked by #226")
