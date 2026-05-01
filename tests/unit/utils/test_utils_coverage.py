"""Tests for utils/market_tracker.py and utils/sleeper_cache.py"""
import json
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open


# ── market_tracker tests ────────────────────────────────────────────────────

class TestMarketTracker:
    def setup_method(self):
        # Reset singleton before each test
        import utils.market_tracker as mt
        mt._market_tracker_instance = None

    def test_get_market_tracker_returns_none_by_default(self):
        from utils.market_tracker import get_market_tracker
        assert get_market_tracker() is None

    def test_set_and_get_market_tracker(self):
        from utils.market_tracker import get_market_tracker, set_market_tracker
        mock_tracker = MagicMock()
        set_market_tracker(mock_tracker)
        assert get_market_tracker() is mock_tracker

    def test_get_dynamic_position_weights_no_tracker(self):
        from utils.market_tracker import get_dynamic_position_weights
        weights = get_dynamic_position_weights()
        assert isinstance(weights, dict)
        assert 'QB' in weights
        assert weights['QB'] == 1.0

    def test_get_dynamic_position_weights_with_tracker(self):
        from utils.market_tracker import get_dynamic_position_weights, set_market_tracker
        mock_tracker = MagicMock()
        mock_tracker.get_position_weights.return_value = {'QB': 1.5, 'RB': 1.2}
        set_market_tracker(mock_tracker)
        weights = get_dynamic_position_weights()
        assert weights == {'QB': 1.5, 'RB': 1.2}

    def test_get_dynamic_position_weights_tracker_raises(self):
        from utils.market_tracker import get_dynamic_position_weights, set_market_tracker
        mock_tracker = MagicMock()
        mock_tracker.get_position_weights.side_effect = Exception('error')
        set_market_tracker(mock_tracker)
        # Should fall back to defaults
        weights = get_dynamic_position_weights()
        assert 'QB' in weights
        assert weights['QB'] == 1.0

    def test_get_dynamic_position_weights_tracker_no_method(self):
        from utils.market_tracker import get_dynamic_position_weights, set_market_tracker
        # Tracker without get_position_weights attribute
        mock_tracker = object()
        set_market_tracker(mock_tracker)
        weights = get_dynamic_position_weights()
        assert 'QB' in weights

    def test_get_dynamic_scarcity_thresholds_no_tracker(self):
        from utils.market_tracker import get_dynamic_scarcity_thresholds
        thresholds = get_dynamic_scarcity_thresholds()
        assert isinstance(thresholds, dict)
        assert 'high' in thresholds

    def test_get_dynamic_scarcity_thresholds_with_tracker(self):
        from utils.market_tracker import get_dynamic_scarcity_thresholds, set_market_tracker
        mock_tracker = MagicMock()
        mock_tracker.get_scarcity_thresholds.return_value = {'high': 2.0, 'medium': 1.5, 'low': 1.0}
        set_market_tracker(mock_tracker)
        thresholds = get_dynamic_scarcity_thresholds()
        assert thresholds == {'high': 2.0, 'medium': 1.5, 'low': 1.0}

    def test_get_dynamic_scarcity_thresholds_tracker_raises(self):
        from utils.market_tracker import get_dynamic_scarcity_thresholds, set_market_tracker
        mock_tracker = MagicMock()
        mock_tracker.get_scarcity_thresholds.side_effect = RuntimeError('fail')
        set_market_tracker(mock_tracker)
        thresholds = get_dynamic_scarcity_thresholds()
        assert 'high' in thresholds


# ── sleeper_cache tests ────────────────────────────────────────────────────

class TestSleeperPlayerCache:
    def setup_method(self):
        # Reset the global cache singleton
        import utils.sleeper_cache as sc
        sc._player_cache = None

    def _make_cache(self, cache_hours=24):
        with patch('utils.sleeper_cache.SleeperAPI'), \
             patch('utils.sleeper_cache.get_data_dir') as mock_gdd, \
             patch('utils.sleeper_cache.ensure_dir_exists'):
            from pathlib import Path
            mock_gdd.return_value = Path('/tmp/pigskin_test')
            from utils.sleeper_cache import SleeperPlayerCache
            c = SleeperPlayerCache(cache_hours=cache_hours)
            c.cache_file = MagicMock()
            c.meta_file = MagicMock()
            return c

    def test_init(self):
        cache = self._make_cache()
        assert cache.cache_hours == 24

    def test_get_cache_metadata_no_file(self):
        cache = self._make_cache()
        cache.meta_file.exists.return_value = False
        meta = cache._get_cache_metadata()
        assert meta['last_updated'] is None

    def test_get_cache_metadata_valid_file(self):
        cache = self._make_cache()
        cache.meta_file.exists.return_value = True
        data = {'last_updated': '2024-01-01T00:00:00', 'player_count': 500}
        m = mock_open(read_data=json.dumps(data))
        with patch('builtins.open', m):
            meta = cache._get_cache_metadata()
        assert meta['player_count'] == 500

    def test_get_cache_metadata_invalid_json(self):
        cache = self._make_cache()
        cache.meta_file.exists.return_value = True
        m = mock_open(read_data='not json{')
        with patch('builtins.open', m):
            meta = cache._get_cache_metadata()
        assert meta['last_updated'] is None

    def test_save_cache_metadata(self):
        cache = self._make_cache()
        m = mock_open()
        with patch('builtins.open', m):
            cache._save_cache_metadata({'last_updated': '2024-01-01', 'player_count': 10})
        m.assert_called_once()

    def test_save_cache_metadata_error(self):
        cache = self._make_cache()
        with patch('builtins.open', side_effect=OSError('disk full')), patch('builtins.print'):
            # Should not raise
            cache._save_cache_metadata({'last_updated': '2024-01-01'})

    def test_is_cache_valid_no_file(self):
        cache = self._make_cache()
        cache.cache_file.exists.return_value = False
        assert cache._is_cache_valid() is False

    def test_is_cache_valid_no_last_updated(self):
        cache = self._make_cache()
        cache.cache_file.exists.return_value = True
        with patch.object(cache, '_get_cache_metadata', return_value={'last_updated': None}):
            assert cache._is_cache_valid() is False

    def test_is_cache_valid_expired(self):
        cache = self._make_cache()
        cache.cache_file.exists.return_value = True
        # Way in the past
        with patch.object(cache, '_get_cache_metadata', return_value={'last_updated': '2020-01-01T00:00:00'}):
            assert cache._is_cache_valid() is False

    def test_is_cache_valid_fresh(self):
        from datetime import datetime
        cache = self._make_cache()
        cache.cache_file.exists.return_value = True
        fresh_time = datetime.now().isoformat()
        with patch.object(cache, '_get_cache_metadata', return_value={'last_updated': fresh_time}):
            assert cache._is_cache_valid() is True

    def test_is_cache_valid_bad_timestamp(self):
        cache = self._make_cache()
        cache.cache_file.exists.return_value = True
        with patch.object(cache, '_get_cache_metadata', return_value={'last_updated': 'bad-date'}):
            assert cache._is_cache_valid() is False

    def test_load_cached_players_no_file(self):
        cache = self._make_cache()
        cache.cache_file.exists.return_value = False
        assert cache._load_cached_players() is None

    def test_load_cached_players_valid(self):
        cache = self._make_cache()
        cache.cache_file.exists.return_value = True
        data = {'p1': {'name': 'Josh Allen'}}
        m = mock_open(read_data=json.dumps(data))
        with patch('builtins.open', m):
            result = cache._load_cached_players()
        assert result['p1']['name'] == 'Josh Allen'

    def test_load_cached_players_invalid_json(self):
        cache = self._make_cache()
        cache.cache_file.exists.return_value = True
        m = mock_open(read_data='not valid json{{')
        with patch('builtins.open', m):
            result = cache._load_cached_players()
        assert result is None

    def test_save_players_to_cache(self):
        cache = self._make_cache()
        players = {'p1': {'name': 'Josh Allen'}}
        m = mock_open()
        with patch('builtins.open', m), \
             patch('os.path.getsize', return_value=1024), \
             patch.object(cache, '_save_cache_metadata'), \
             patch('builtins.print'):
            cache._save_players_to_cache(players)
        assert m.called

    def test_save_players_to_cache_error(self):
        cache = self._make_cache()
        with patch('builtins.open', side_effect=OSError('disk full')), patch('builtins.print'):
            # Should not raise
            cache._save_players_to_cache({'p1': {}})

    def test_get_players_uses_cache(self):
        cache = self._make_cache()
        cached_data = {'p1': {'name': 'Josh'}}
        with patch.object(cache, '_is_cache_valid', return_value=True), \
             patch.object(cache, '_load_cached_players', return_value=cached_data), \
             patch.object(cache, '_get_cache_metadata', return_value={'player_count': 1, 'last_updated': '2024-01-01'}), \
             patch('builtins.print'):
            result = cache.get_players()
        assert result == cached_data

    def test_get_players_cache_empty_fetches_api(self):
        cache = self._make_cache()
        fresh_data = {'p1': {'name': 'Josh'}}
        with patch.object(cache, '_is_cache_valid', return_value=True), \
             patch.object(cache, '_load_cached_players', return_value=None), \
             patch.object(cache, '_save_players_to_cache'), \
             patch('builtins.print'):
            cache.sleeper_api.get_all_players.return_value = fresh_data
            result = cache.get_players()
        assert result == fresh_data

    def test_get_players_force_refresh(self):
        cache = self._make_cache()
        fresh_data = {'p1': {}}
        cache.sleeper_api.get_all_players.return_value = fresh_data
        with patch.object(cache, '_save_players_to_cache'), patch('builtins.print'):
            result = cache.get_players(force_refresh=True)
        assert result == fresh_data

    def test_get_players_api_returns_empty_falls_back_to_cache(self):
        cache = self._make_cache()
        cached_data = {'p1': {}}
        cache.sleeper_api.get_all_players.return_value = {}
        with patch.object(cache, '_load_cached_players', return_value=cached_data), \
             patch('builtins.print'):
            result = cache.get_players(force_refresh=True)
        assert result == cached_data

    def test_get_players_api_returns_empty_no_cache(self):
        cache = self._make_cache()
        cache.sleeper_api.get_all_players.return_value = {}
        with patch.object(cache, '_load_cached_players', return_value=None), \
             patch('builtins.print'):
            result = cache.get_players(force_refresh=True)
        assert result == {}

    def test_get_players_api_exception_falls_back_to_cache(self):
        cache = self._make_cache()
        cached_data = {'p1': {}}
        cache.sleeper_api.get_all_players.side_effect = Exception('network error')
        with patch.object(cache, '_load_cached_players', return_value=cached_data), \
             patch('builtins.print'):
            result = cache.get_players(force_refresh=True)
        assert result == cached_data

    def test_get_players_api_exception_no_cache(self):
        cache = self._make_cache()
        cache.sleeper_api.get_all_players.side_effect = Exception('network error')
        with patch.object(cache, '_load_cached_players', return_value=None), \
             patch('builtins.print'):
            result = cache.get_players(force_refresh=True)
        assert result == {}

    def test_get_cache_info(self):
        cache = self._make_cache()
        cache.cache_file.exists.return_value = False
        with patch.object(cache, '_get_cache_metadata', return_value={'last_updated': None}), \
             patch.object(cache, '_is_cache_valid', return_value=False):
            info = cache.get_cache_info()
        assert 'cache_exists' in info
        assert info['cache_exists'] is False

    def test_get_cache_info_with_file(self):
        cache = self._make_cache()
        cache.cache_file.exists.return_value = True
        # Make cache_file a real path object for stat
        from pathlib import Path
        cache.cache_file = Path('/dev/null')
        with patch.object(cache, '_get_cache_metadata', return_value={'last_updated': None}), \
             patch.object(cache, '_is_cache_valid', return_value=False):
            info = cache.get_cache_info()
        assert 'cache_exists' in info

    def test_clear_cache(self):
        cache = self._make_cache()
        cache.cache_file.exists.return_value = True
        cache.meta_file.exists.return_value = True
        with patch('os.remove') as mock_rm, patch('builtins.print'):
            result = cache.clear_cache()
        assert result is True
        assert mock_rm.call_count == 2

    def test_clear_cache_error(self):
        cache = self._make_cache()
        cache.cache_file.exists.return_value = True
        with patch('os.remove', side_effect=OSError('perm denied')), patch('builtins.print'):
            result = cache.clear_cache()
        assert result is False


class TestGetPlayerCacheSingleton:
    def setup_method(self):
        import utils.sleeper_cache as sc
        sc._player_cache = None

    def test_get_player_cache_creates_instance(self):
        with patch('utils.sleeper_cache.SleeperAPI'), \
             patch('utils.sleeper_cache.get_data_dir') as mock_gdd, \
             patch('utils.sleeper_cache.ensure_dir_exists'):
            from pathlib import Path
            mock_gdd.return_value = Path('/tmp/test')
            from utils.sleeper_cache import get_player_cache
            cache = get_player_cache()
            assert cache is not None

    def test_get_player_cache_returns_same_instance(self):
        with patch('utils.sleeper_cache.SleeperAPI'), \
             patch('utils.sleeper_cache.get_data_dir') as mock_gdd, \
             patch('utils.sleeper_cache.ensure_dir_exists'):
            from pathlib import Path
            mock_gdd.return_value = Path('/tmp/test')
            from utils.sleeper_cache import get_player_cache
            c1 = get_player_cache()
            c2 = get_player_cache()
            assert c1 is c2
