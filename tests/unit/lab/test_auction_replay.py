"""Failing tests for AuctionBacktester — acceptance criteria for issue #196.

`lab/backtest/auction_replay.py` does not exist yet.  All tests are marked
xfail(strict=True): they are expected to fail until #196 is implemented.
Remove the pytestmark (and verify green) once AuctionBacktester is available.
"""

# Graceful import — module does not exist yet; tests fail at runtime, not at
# collection time, which keeps the full suite collectable.
try:
    from lab.backtest.auction_replay import AuctionBacktester
    _AUCTION_REPLAY_AVAILABLE = True
except ModuleNotFoundError:
    AuctionBacktester = None  # type: ignore[assignment,misc]
    _AUCTION_REPLAY_AVAILABLE = False

# run() is now implemented — xfail mark removed.
_RUN_NOT_IMPLEMENTED = lambda cls: cls  # no-op: was xfail before issue #196


# ---------------------------------------------------------------------------
# Sample data helpers
# ---------------------------------------------------------------------------

def _sample_player_data():
    """Minimal player data list for test fixtures."""
    return [
        {"player_name": "Josh Allen", "position": "QB", "auction_value": 45, "actual_price": 52},
        {"player_name": "Christian McCaffrey", "position": "RB", "auction_value": 70, "actual_price": 68},
        {"player_name": "Tyreek Hill", "position": "WR", "auction_value": 55, "actual_price": 50},
    ]


def _sample_strategy():
    """Return a minimal duck-typed strategy object."""
    class _MinimalStrategy:
        name = "test_strategy"

        def bid(self, player, budget):
            return min(player.get("auction_value", 1), budget)

    return _MinimalStrategy()


# ---------------------------------------------------------------------------
# 1. Instantiation
# ---------------------------------------------------------------------------

class TestAuctionBacktesterInstantiation:
    """AuctionBacktester(strategy, player_data) must be constructible."""

    def test_instantiation_succeeds(self):
        """AuctionBacktester can be constructed with a strategy and player_data."""
        bt = AuctionBacktester(strategy=_sample_strategy(), player_data=_sample_player_data())
        assert bt is not None

    def test_instantiation_stores_strategy(self):
        """Constructed instance exposes the strategy it was given."""
        strategy = _sample_strategy()
        bt = AuctionBacktester(strategy=strategy, player_data=_sample_player_data())
        assert bt.strategy is strategy

    def test_instantiation_stores_player_data(self):
        """Constructed instance exposes the player_data it was given."""
        data = _sample_player_data()
        bt = AuctionBacktester(strategy=_sample_strategy(), player_data=data)
        assert bt.player_data == data


# ---------------------------------------------------------------------------
# 2. run() return shape
# ---------------------------------------------------------------------------

@_RUN_NOT_IMPLEMENTED
class TestAuctionBacktesterRun:
    """run() must return a dict with the three required keys."""

    REQUIRED_KEYS = {"efficiency_score", "total_spend", "total_value"}

    def _make_backtester(self):
        return AuctionBacktester(strategy=_sample_strategy(), player_data=_sample_player_data())

    def test_run_returns_dict(self):
        """run() returns a dict."""
        bt = self._make_backtester()
        result = bt.run()
        assert isinstance(result, dict)

    def test_run_result_has_required_keys(self):
        """run() result contains 'efficiency_score', 'total_spend', 'total_value'."""
        bt = self._make_backtester()
        result = bt.run()
        missing = self.REQUIRED_KEYS - result.keys()
        assert not missing, f"run() result is missing keys: {missing}"

    def test_efficiency_score_is_between_0_and_1(self):
        """efficiency_score is a float in [0.0, 1.0]."""
        bt = self._make_backtester()
        result = bt.run()
        score = result["efficiency_score"]
        assert isinstance(score, float), f"efficiency_score must be float, got {type(score)}"
        assert 0.0 <= score <= 1.0, f"efficiency_score out of range: {score}"

    def test_total_spend_is_non_negative(self):
        """total_spend must be >= 0."""
        bt = self._make_backtester()
        result = bt.run()
        assert result["total_spend"] >= 0

    def test_total_value_is_non_negative(self):
        """total_value must be >= 0."""
        bt = self._make_backtester()
        result = bt.run()
        assert result["total_value"] >= 0


# ---------------------------------------------------------------------------
# 3. Empty player_data edge case
# ---------------------------------------------------------------------------

@_RUN_NOT_IMPLEMENTED
class TestAuctionBacktesterEmptyData:
    """run() with empty player_data must return efficiency_score=0.0 or raise ValueError."""

    def test_empty_player_data_handled(self):
        """run() with empty player_data returns efficiency_score=0.0 or raises ValueError."""
        bt = AuctionBacktester(strategy=_sample_strategy(), player_data=[])
        try:
            result = bt.run()
            assert result["efficiency_score"] == 0.0, (
                f"Expected efficiency_score=0.0 for empty data, got {result['efficiency_score']}"
            )
        except ValueError:
            pass  # also acceptable


# ---------------------------------------------------------------------------
# 4. Strategy is consulted during run()
# ---------------------------------------------------------------------------

class TestAuctionBacktesterStrategyConsulted:
    """run() must invoke the strategy for every player in player_data."""

    def test_strategy_is_consulted(self):
        """run() calls strategy.bid() exactly once per player."""
        from unittest.mock import MagicMock
        mock_strategy = MagicMock()
        mock_strategy.bid.return_value = 100  # always high enough to win
        data = _sample_player_data()
        bt = AuctionBacktester(strategy=mock_strategy, player_data=data)
        bt.run()
        assert mock_strategy.bid.call_count == len(data), (
            f"Expected strategy.bid() called {len(data)} times, "
            f"got {mock_strategy.bid.call_count}"
        )


# ---------------------------------------------------------------------------
# 5. Determinism — same input → same output
# ---------------------------------------------------------------------------

@_RUN_NOT_IMPLEMENTED
class TestAuctionBacktesterDeterminism:
    """run() must be deterministic for the same input."""

    def test_run_is_deterministic(self):
        """Two successive run() calls with the same data return identical results."""
        data = _sample_player_data()
        strategy = _sample_strategy()

        bt1 = AuctionBacktester(strategy=strategy, player_data=data)
        bt2 = AuctionBacktester(strategy=strategy, player_data=data)

        result1 = bt1.run()
        result2 = bt2.run()

        assert result1 == result2, (
            f"run() is not deterministic:\n  first:  {result1}\n  second: {result2}"
        )
