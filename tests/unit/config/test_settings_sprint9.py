"""Sprint 9 QA tests — Issue #162: get_settings() re-reads .env on every call.

Expected outcome:
  - FAILS before fix  (Settings() constructed anew on each call → different objects)
  - PASSES after fix  (@lru_cache or equivalent applied to get_settings())
"""

from unittest.mock import patch


class FakeSettings:
    """Lightweight stand-in so we never touch the real .env file."""
    pass


def _make_unique_factory():
    """Return a side_effect that creates a distinct FakeSettings per call."""
    def _factory(*args, **kwargs):
        return FakeSettings()
    return _factory


class TestGetSettingsCaching:
    """Issue #162: get_settings() must return the same cached object on repeat calls."""

    def setup_method(self):
        """Clear lru_cache between tests if the cache exists (post-fix behaviour)."""
        from config import settings as _settings_mod
        if hasattr(_settings_mod.get_settings, "cache_clear"):
            _settings_mod.get_settings.cache_clear()

    def teardown_method(self):
        """Clear lru_cache after each test to avoid cross-test pollution."""
        from config import settings as _settings_mod
        if hasattr(_settings_mod.get_settings, "cache_clear"):
            _settings_mod.get_settings.cache_clear()

    def test_get_settings_returns_same_instance(self):
        """get_settings() must return the identical object on every invocation.

        Without @lru_cache: Settings() is called twice → two distinct objects → FAILS.
        With    @lru_cache: Settings() is called once  → same object returned → PASSES.
        """
        import config.settings as settings_mod

        with patch.object(settings_mod, "Settings", side_effect=_make_unique_factory()):
            s1 = settings_mod.get_settings()
            s2 = settings_mod.get_settings()

        assert s1 is s2, (
            "get_settings() must return the same cached instance on repeated calls. "
            "Apply @lru_cache (or equivalent) to fix Issue #162."
        )

    def test_get_settings_calls_settings_constructor_once(self):
        """Settings() constructor must be called exactly once across N calls to get_settings().

        Without caching: called N times → FAILS.
        With    caching: called 1 time  → PASSES.
        """
        import config.settings as settings_mod

        call_log: list = []

        def _factory(*args, **kwargs):
            call_log.append(object())
            return FakeSettings()

        with patch.object(settings_mod, "Settings", side_effect=_factory):
            for _ in range(5):
                settings_mod.get_settings()

        assert len(call_log) == 1, (
            f"Settings() was constructed {len(call_log)} time(s); expected exactly 1. "
            "get_settings() must cache its result (Issue #162)."
        )
