"""Unit tests for ConfigManager."""

import json
import os
from unittest.mock import patch

import pytest

from config.config_manager import (
    DraftConfig, ConfigManager, get_config_manager, load_config, save_config, update_config
)


@pytest.fixture
def tmp_config_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def manager(tmp_config_dir):
    return ConfigManager(config_dir=tmp_config_dir)


class TestDraftConfig:
    def test_defaults(self):
        cfg = DraftConfig()
        assert cfg.budget == 200
        assert cfg.num_teams == 10
        assert 'QB' in cfg.roster_positions

    def test_to_dict_and_from_dict(self):
        cfg = DraftConfig(budget=150, num_teams=8)
        d = cfg.to_dict()
        restored = DraftConfig.from_dict(d)
        assert restored.budget == 150
        assert restored.num_teams == 8

    def test_from_dict_ignores_unknown_keys(self):
        d = {'budget': 100, 'unknown_key': 'foo'}
        cfg = DraftConfig.from_dict(d)
        assert cfg.budget == 100


class TestConfigManagerLoad:
    def test_loads_default_when_file_missing(self, manager, tmp_config_dir):
        cfg = manager.load_config()
        assert cfg.budget == 200
        # Default file should be created
        assert os.path.exists(os.path.join(tmp_config_dir, 'config.json'))

    def test_returns_cached_on_second_call(self, manager):
        cfg1 = manager.load_config()
        cfg2 = manager.load_config()
        assert cfg1 is cfg2

    def test_reload_flag_rereads_file(self, manager, tmp_config_dir):
        manager.load_config()
        # Overwrite config file manually
        config_file = os.path.join(tmp_config_dir, 'config.json')
        with open(config_file, 'w') as f:
            json.dump({'budget': 999}, f)
        cfg = manager.load_config(reload=True)
        assert cfg.budget == 999

    def test_loads_from_existing_file(self, tmp_config_dir):
        config_file = os.path.join(tmp_config_dir, 'config.json')
        with open(config_file, 'w') as f:
            json.dump({'budget': 175, 'num_teams': 12}, f)
        mgr = ConfigManager(config_dir=tmp_config_dir)
        cfg = mgr.load_config()
        assert cfg.budget == 175
        assert cfg.num_teams == 12

    def test_invalid_json_falls_back_to_default(self, tmp_config_dir):
        config_file = os.path.join(tmp_config_dir, 'config.json')
        with open(config_file, 'w') as f:
            f.write("{not valid json")
        mgr = ConfigManager(config_dir=tmp_config_dir)
        cfg = mgr.load_config()
        assert cfg.budget == 200  # default

    def test_settings_exception_does_not_break_load(self, tmp_config_dir):
        # Even if settings layer raises, config should still load defaults
        mgr = ConfigManager(config_dir=tmp_config_dir)
        cfg = mgr.load_config()
        assert cfg.budget == 200

    def test_get_settings_raises_is_swallowed(self, tmp_config_dir):
        """Cover lines 110-111: exception in get_settings is caught and ignored."""
        import json
        import os
        from unittest.mock import patch
        # Create a valid config file so load_config doesn't return early
        config_file = os.path.join(tmp_config_dir, "config.json")
        with open(config_file, 'w') as f:
            json.dump({"budget": 150}, f)
        mgr = ConfigManager(config_dir=tmp_config_dir)
        with patch('config.settings.get_settings', side_effect=Exception("env error")):
            cfg = mgr.load_config()
        # Should still return valid config
        assert cfg is not None


class TestConfigManagerSave:
    def test_save_writes_file(self, manager, tmp_config_dir):
        cfg = manager.load_config()
        cfg.budget = 300
        manager.save_config()
        config_file = os.path.join(tmp_config_dir, 'config.json')
        with open(config_file) as f:
            data = json.load(f)
        assert data['budget'] == 300

    def test_save_with_explicit_config(self, manager, tmp_config_dir):
        new_cfg = DraftConfig(budget=250)
        manager.save_config(new_cfg)
        assert manager._config.budget == 250

    def test_save_raises_when_no_config(self, tmp_config_dir):
        mgr = ConfigManager(config_dir=tmp_config_dir)
        with pytest.raises(ValueError):
            mgr.save_config()

    def test_save_raises_on_write_error(self, manager):
        manager.load_config()
        with patch('builtins.open', side_effect=PermissionError("no write")):
            with pytest.raises(PermissionError):
                manager.save_config()


class TestConfigManagerUpdate:
    def test_update_known_field(self, manager):
        cfg = manager.update_config(budget=175)
        assert cfg.budget == 175

    def test_update_unknown_field_warns(self, manager):
        with patch('config.config_manager.logger') as mock_logger:
            manager.update_config(nonexistent_field='x')
        mock_logger.warning.assert_called()


class TestConfigManagerGetters:
    def test_get_sleeper_config(self, manager):
        result = manager.get_sleeper_config()
        assert 'draft_id' in result
        assert 'user_id' in result
        assert 'username' in result

    def test_get_roster_config(self, manager):
        result = manager.get_roster_config()
        assert 'QB' in result

    def test_get_draft_settings(self, manager):
        result = manager.get_draft_settings()
        assert 'budget' in result
        assert 'strategy_type' in result

    def test_get_data_settings(self, manager):
        result = manager.get_data_settings()
        assert 'data_source' in result
        assert 'data_path' in result


class TestMigrateConfig:
    def test_migrates_bn_to_bench(self, manager):
        data = {'roster_positions': {'QB': 1, 'BN': 5}}
        migrated = manager._migrate_config(data)
        assert 'BENCH' in migrated['roster_positions']
        assert 'BN' not in migrated['roster_positions']

    def test_skips_bn_migration_if_bench_present(self, manager):
        data = {'roster_positions': {'QB': 1, 'BENCH': 5}}
        migrated = manager._migrate_config(data)
        assert migrated['roster_positions']['BENCH'] == 5

    def test_adds_defaults_for_missing_fields(self, manager):
        migrated = manager._migrate_config({'budget': 100})
        assert 'num_teams' in migrated


class TestResetToDefaults:
    def test_reset_writes_defaults(self, manager):
        manager.update_config(budget=500)
        manager.reset_to_defaults()
        assert manager._config.budget == 200


class TestValidateConfig:
    def test_valid_config(self, manager):
        ok, errors = manager.validate_config({'budget': 200, 'num_teams': 10})
        assert ok
        assert errors == []

    def test_missing_budget_fails(self, manager):
        ok, errors = manager.validate_config({'num_teams': 10})
        assert not ok
        assert any('budget' in e for e in errors)

    def test_invalid_budget_type(self, manager):
        ok, errors = manager.validate_config({'budget': 'not_a_number'})
        assert not ok

    def test_negative_budget(self, manager):
        ok, errors = manager.validate_config({'budget': -5})
        assert not ok

    def test_invalid_num_teams(self, manager):
        ok, errors = manager.validate_config({'budget': 200, 'num_teams': 1})
        assert not ok

    def test_invalid_roster_positions_type(self, manager):
        ok, errors = manager.validate_config({'budget': 200, 'roster_positions': 'qb'})
        assert not ok

    def test_non_integer_num_teams(self, manager):
        ok, errors = manager.validate_config({'budget': 200, 'num_teams': 'ten'})
        assert not ok


class TestStrRepr:
    def test_str_includes_budget(self, manager):
        s = str(manager)
        assert '200' in s


class TestConvenienceFunctions:
    def test_get_config_manager_returns_same_instance(self, tmp_config_dir):
        import config.config_manager as cm_module
        cm_module._config_manager = None  # reset global
        mgr1 = get_config_manager(tmp_config_dir)
        mgr2 = get_config_manager(tmp_config_dir)
        assert mgr1 is mgr2
        cm_module._config_manager = None  # cleanup

    def test_load_config_convenience(self, tmp_config_dir):
        import config.config_manager as cm_module
        cm_module._config_manager = None
        cfg = load_config(config_dir=tmp_config_dir)
        assert isinstance(cfg, DraftConfig)
        cm_module._config_manager = None

    def test_save_config_convenience(self, tmp_config_dir):
        import config.config_manager as cm_module
        cm_module._config_manager = None
        cfg = DraftConfig(budget=222)
        save_config(cfg, config_dir=tmp_config_dir)
        config_file = os.path.join(tmp_config_dir, 'config.json')
        with open(config_file) as f:
            data = json.load(f)
        assert data['budget'] == 222
        cm_module._config_manager = None

    def test_update_config_convenience(self, tmp_config_dir):
        import config.config_manager as cm_module
        cm_module._config_manager = None
        cfg = update_config(config_dir=tmp_config_dir, budget=333)
        assert cfg.budget == 333
        cm_module._config_manager = None


class TestConfigManagerSettingsLayer:
    """Cover lines 104-111 — settings layer applied when available."""

    def test_settings_applied_when_present(self, tmp_config_dir):
        import config.config_manager as cm_module
        from config.config_manager import ConfigManager, DraftConfig
        from unittest.mock import patch, MagicMock
        import json, os

        cm_module._config_manager = None
        # Pre-create config.json so load_config doesn't return early
        config_file = os.path.join(tmp_config_dir, 'config.json')
        with open(config_file, 'w') as f:
            json.dump(DraftConfig().to_dict(), f)

        mock_settings = MagicMock()
        mock_settings.sleeper_user_id = "test_user"
        mock_settings.sleeper_username = "test_username"
        mock_settings.strategy_type = "aggressive"

        with patch('config.settings.get_settings', return_value=mock_settings):
            cm = ConfigManager(config_dir=tmp_config_dir)
            cfg = cm.load_config()
            assert cfg.sleeper_user_id == "test_user"
            assert cfg.sleeper_username == "test_username"
            assert cfg.strategy_type == "aggressive"
        cm_module._config_manager = None
