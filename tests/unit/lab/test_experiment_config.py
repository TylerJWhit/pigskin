"""Unit tests for ExperimentConfig — QA Phase 1 — closes #188."""
from __future__ import annotations

import json
import os
import tempfile
import unittest


class TestExperimentConfigLoad(unittest.TestCase):
    """ExperimentConfig.load_from_file() supports YAML and JSON."""

    def _write_temp(self, content: str, suffix: str) -> str:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
        f.write(content)
        f.flush()
        f.close()
        return f.name

    def test_load_from_yaml_returns_experiment_config(self):
        from lab.experiments.config import ExperimentConfig

        yaml_content = (
            "name: test_experiment\n"
            "strategies:\n"
            "  - balanced\n"
            "  - basic\n"
            "num_simulations: 10\n"
        )
        path = self._write_temp(yaml_content, ".yaml")
        try:
            config = ExperimentConfig.load_from_file(path)
            self.assertIsInstance(config, ExperimentConfig)
            self.assertEqual(config.name, "test_experiment")
            self.assertEqual(config.num_simulations, 10)
            self.assertIn("balanced", config.strategies)
        finally:
            os.unlink(path)

    def test_load_from_json_returns_experiment_config(self):
        from lab.experiments.config import ExperimentConfig

        data = {"name": "json_exp", "strategies": ["balanced"], "num_simulations": 5}
        path = self._write_temp(json.dumps(data), ".json")
        try:
            config = ExperimentConfig.load_from_file(path)
            self.assertIsInstance(config, ExperimentConfig)
            self.assertEqual(config.name, "json_exp")
        finally:
            os.unlink(path)


class TestExperimentConfigValidation(unittest.TestCase):
    """Missing or invalid fields raise ValueError."""

    def test_missing_name_raises_value_error(self):
        from lab.experiments.config import ExperimentConfig

        raw = {"strategies": ["balanced"], "num_simulations": 5}
        with self.assertRaises(ValueError):
            ExperimentConfig._validate_and_build(raw)

    def test_missing_strategies_raises_value_error(self):
        from lab.experiments.config import ExperimentConfig

        raw = {"name": "test", "num_simulations": 5}
        with self.assertRaises(ValueError):
            ExperimentConfig._validate_and_build(raw)

    def test_num_simulations_zero_raises_value_error(self):
        from lab.experiments.config import ExperimentConfig

        raw = {"name": "test", "strategies": ["balanced"], "num_simulations": 0}
        with self.assertRaises(ValueError):
            ExperimentConfig._validate_and_build(raw)

    def test_num_simulations_negative_raises_value_error(self):
        from lab.experiments.config import ExperimentConfig

        raw = {"name": "test", "strategies": ["balanced"], "num_simulations": -1}
        with self.assertRaises(ValueError):
            ExperimentConfig._validate_and_build(raw)
