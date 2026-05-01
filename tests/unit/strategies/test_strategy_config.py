"""Tests for StrategyConfig Pydantic model and StrategyRegistry — issue #259."""

import pytest
from pathlib import Path

from strategies.strategy_config import StrategyConfig
from strategies.strategy_registry import StrategyRegistry
from strategies.base_strategy import Strategy


# ---------------------------------------------------------------------------
# StrategyConfig model
# ---------------------------------------------------------------------------

class TestStrategyConfig:
    def test_valid_config(self):
        cfg = StrategyConfig(
            name="vor",
            display_name="Value Over Replacement",
            description="Bids based on VOR.",
            base_class="VorStrategy",
        )
        assert cfg.name == "vor"
        assert cfg.version == "1.0.0"
        assert cfg.parameters == {}
        assert cfg.tags == []

    def test_all_fields(self):
        cfg = StrategyConfig(
            name="custom",
            display_name="Custom",
            description="Test",
            base_class="BalancedStrategy",
            version="2.0.0",
            parameters={"threshold": 0.5},
            tags=["lab", "benchmark"],
        )
        assert cfg.version == "2.0.0"
        assert cfg.parameters["threshold"] == 0.5
        assert "lab" in cfg.tags

    def test_empty_name_raises(self):
        with pytest.raises(Exception):
            StrategyConfig(
                name="  ",
                display_name="X",
                description="X",
                base_class="VorStrategy",
            )

    def test_empty_base_class_raises(self):
        with pytest.raises(Exception):
            StrategyConfig(
                name="vor",
                display_name="X",
                description="X",
                base_class="  ",
            )

    def test_missing_required_field_raises(self):
        with pytest.raises(Exception):
            StrategyConfig(name="vor", display_name="X", description="X")


# ---------------------------------------------------------------------------
# StrategyRegistry.create (backward-compatible key-based creation)
# ---------------------------------------------------------------------------

class TestStrategyRegistryCreate:
    def test_create_known_key(self):
        strategy = StrategyRegistry.create("vor")
        assert isinstance(strategy, Strategy)

    def test_create_balanced(self):
        strategy = StrategyRegistry.create("balanced")
        assert isinstance(strategy, Strategy)

    def test_create_unknown_key_raises(self):
        with pytest.raises(ValueError, match="Unknown strategy key"):
            StrategyRegistry.create("nonexistent_strategy_xyz")

    def test_list_available_returns_sorted_list(self):
        available = StrategyRegistry.list_available()
        assert isinstance(available, list)
        assert len(available) > 0
        assert available == sorted(available)
        assert "vor" in available
        assert "balanced" in available
        assert "inflation_vor" in available


# ---------------------------------------------------------------------------
# StrategyRegistry.from_dict
# ---------------------------------------------------------------------------

class TestStrategyRegistryFromDict:
    def _vor_dict(self):
        return {
            "name": "vor",
            "display_name": "Value Over Replacement",
            "description": "Bids based on VOR.",
            "base_class": "VorStrategy",
        }

    def test_from_dict_creates_strategy(self):
        strategy = StrategyRegistry.from_dict(self._vor_dict())
        assert isinstance(strategy, Strategy)

    def test_from_dict_unknown_base_class_raises(self):
        d = self._vor_dict()
        d["base_class"] = "os.system"
        with pytest.raises(ValueError, match="not in the allowlist"):
            StrategyRegistry.from_dict(d)

    def test_from_dict_arbitrary_class_not_allowed(self):
        d = self._vor_dict()
        d["base_class"] = "builtins.eval"
        with pytest.raises(ValueError, match="not in the allowlist"):
            StrategyRegistry.from_dict(d)

    def test_from_dict_invalid_config_raises(self):
        with pytest.raises(Exception):
            StrategyRegistry.from_dict({"name": "vor"})  # missing required fields


# ---------------------------------------------------------------------------
# StrategyRegistry.from_yaml
# ---------------------------------------------------------------------------

class TestStrategyRegistryFromYaml:
    def test_from_yaml_vor(self, tmp_path):
        yaml_content = (
            "name: vor\n"
            "display_name: Value Over Replacement\n"
            "description: Bids based on VOR.\n"
            "base_class: VorStrategy\n"
        )
        f = tmp_path / "vor.yaml"
        f.write_text(yaml_content)
        strategy = StrategyRegistry.from_yaml(f)
        assert isinstance(strategy, Strategy)

    def test_from_yaml_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            StrategyRegistry.from_yaml(tmp_path / "missing.yaml")

    def test_from_yaml_invalid_base_class_raises(self, tmp_path):
        yaml_content = (
            "name: evil\n"
            "display_name: Evil\n"
            "description: Bad.\n"
            "base_class: subprocess.Popen\n"
        )
        f = tmp_path / "evil.yaml"
        f.write_text(yaml_content)
        with pytest.raises(ValueError, match="not in the allowlist"):
            StrategyRegistry.from_yaml(f)

    def test_from_yaml_bundled_vor_config(self):
        """The bundled lab/strategies/configs/vor.yaml must load successfully."""
        configs_dir = (
            Path(__file__).resolve().parents[3]
            / "lab" / "strategies" / "configs" / "vor.yaml"
        )
        if not configs_dir.exists():
            pytest.skip("Bundled YAML config not found")
        strategy = StrategyRegistry.from_yaml(configs_dir)
        assert isinstance(strategy, Strategy)
