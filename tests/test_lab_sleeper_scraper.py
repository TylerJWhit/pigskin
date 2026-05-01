"""Tests for SleeperLabClient and SleeperAuctionScraper — issue #235.

All tests use in-memory SQLite (no pigskin_lab.db) and mock HTTP.
No live Sleeper API calls are made.

Scenarios:
  1. get_draft_picks() returns typed AuctionPick dataclasses
  2. Rate limiter: no more than LIMIT calls in WINDOW
  3. Deduplication: scraping same draft twice keeps row count unchanged
  4. Null auction_price pick is skipped with warning
  5. Cache: second call returns cached response without network request
"""

import json
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lab.data.sleeper_client import AuctionPick, SleeperLabClient, _DailyBucket


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_raw_pick(player_id="p1", amount="15", position="WR", team="KC"):
    return {
        "player_id": player_id,
        "pick_no": 1,
        "draft_slot": 3,
        "metadata": {
            "amount": amount,
            "first_name": "Patrick",
            "last_name": "Mahomes",
            "position": position,
            "team": team,
        },
    }


def _make_draft_detail(budget=200, teams=12):
    return {
        "draft_id": "d1",
        "settings": {"budget": budget, "teams": teams, "scoring_format": "ppr"},
        "start_time": 1714600000000,
    }


# ---------------------------------------------------------------------------
# Scenario 1: get_draft_picks returns typed AuctionPick objects
# ---------------------------------------------------------------------------

class TestGetDraftPicksTyped(unittest.TestCase):
    def test_returns_auction_pick_dataclass(self, tmp_path=None):
        import tempfile
        cache_dir = Path(tempfile.mkdtemp())
        client = SleeperLabClient(cache_dir=cache_dir, cache_ttl=0)

        raw_picks = [_make_raw_pick("p1", "15")]
        with patch.object(client, "_get", return_value=raw_picks):
            picks = client.get_draft_picks("draft123")

        self.assertEqual(len(picks), 1)
        self.assertIsInstance(picks[0], AuctionPick)
        self.assertEqual(picks[0].sleeper_player_id, "p1")
        self.assertEqual(picks[0].winner_bid, 15)
        self.assertEqual(picks[0].position, "WR")
        self.assertEqual(picks[0].nfl_team, "KC")

    def test_multiple_picks(self):
        import tempfile
        cache_dir = Path(tempfile.mkdtemp())
        client = SleeperLabClient(cache_dir=cache_dir, cache_ttl=0)
        raw_picks = [
            _make_raw_pick("p1", "50", "QB"),
            _make_raw_pick("p2", "30", "RB"),
        ]
        with patch.object(client, "_get", return_value=raw_picks):
            picks = client.get_draft_picks("d1")
        self.assertEqual(len(picks), 2)
        self.assertEqual(picks[0].winner_bid, 50)


# ---------------------------------------------------------------------------
# Scenario 4: Null/missing auction_price → pick skipped with warning
# ---------------------------------------------------------------------------

class TestNullAuctionPrice(unittest.TestCase):
    def test_missing_amount_skipped(self):
        import tempfile
        cache_dir = Path(tempfile.mkdtemp())
        client = SleeperLabClient(cache_dir=cache_dir, cache_ttl=0)
        raw_picks = [_make_raw_pick("p1", amount=None)]  # no price
        with patch.object(client, "_get", return_value=raw_picks):
            picks = client.get_draft_picks("d1")
        # Pick with no auction price should be skipped (empty result)
        self.assertEqual(picks, [])

    def test_missing_player_id_skipped(self):
        import tempfile
        cache_dir = Path(tempfile.mkdtemp())
        client = SleeperLabClient(cache_dir=cache_dir, cache_ttl=0)
        raw_picks = [{"pick_no": 1, "metadata": {"amount": "10"}}]  # no player_id
        with patch.object(client, "_get", return_value=raw_picks):
            picks = client.get_draft_picks("d1")
        self.assertEqual(picks, [])


# ---------------------------------------------------------------------------
# Scenario 5: Cache — second call returns cached response without HTTP request
# ---------------------------------------------------------------------------

class TestCaching(unittest.TestCase):
    def test_cache_hit_no_network_request(self, tmp_path=None):
        import tempfile
        cache_dir = Path(tempfile.mkdtemp())
        client = SleeperLabClient(cache_dir=cache_dir, cache_ttl=3600)

        payload = [_make_raw_pick("p1", "10")]

        with patch("httpx.get") as mock_get:
            resp_mock = MagicMock()
            resp_mock.raise_for_status.return_value = None
            resp_mock.json.return_value = payload
            mock_get.return_value = resp_mock

            # First call — goes to network
            result1 = client._get("draft/d1/picks")
            self.assertEqual(mock_get.call_count, 1)

            # Second call — should hit cache, no second network call
            result2 = client._get("draft/d1/picks")
            self.assertEqual(mock_get.call_count, 1)  # still 1
            self.assertEqual(result1, result2)

    def test_stale_cache_refetches(self):
        import tempfile
        cache_dir = Path(tempfile.mkdtemp())
        client = SleeperLabClient(cache_dir=cache_dir, cache_ttl=0)  # TTL=0 → always stale

        payload = [_make_raw_pick("p1", "10")]
        with patch("httpx.get") as mock_get:
            resp_mock = MagicMock()
            resp_mock.raise_for_status.return_value = None
            resp_mock.json.return_value = payload
            mock_get.return_value = resp_mock

            client._get("draft/d2/picks")
            client._get("draft/d2/picks")  # second call; TTL expired
            self.assertEqual(mock_get.call_count, 2)


# ---------------------------------------------------------------------------
# Scenario 2: Rate limiter
# ---------------------------------------------------------------------------

class TestRateLimiter(unittest.TestCase):
    def test_acquire_under_limit(self):
        bucket = _DailyBucket()
        for _ in range(5):
            bucket.acquire()
        self.assertEqual(bucket.remaining, _DailyBucket.LIMIT - 5)

    def test_remaining_decreases_with_calls(self):
        bucket = _DailyBucket()
        initial = bucket.remaining
        bucket.acquire()
        self.assertEqual(bucket.remaining, initial - 1)

    def test_request_count_tracked(self):
        import tempfile
        cache_dir = Path(tempfile.mkdtemp())
        bucket = _DailyBucket()
        client = SleeperLabClient(cache_dir=cache_dir, cache_ttl=0, rate_limiter=bucket)

        payload = {"draft_id": "d1"}
        with patch("httpx.get") as mock_get:
            resp_mock = MagicMock()
            resp_mock.raise_for_status.return_value = None
            resp_mock.json.return_value = payload
            mock_get.return_value = resp_mock

            client._get("draft/d1")
            client._get("draft/d2")
            # 2 separate paths → 2 network calls, 2 rate limiter slots consumed
            self.assertEqual(mock_get.call_count, 2)
            self.assertEqual(bucket.remaining, _DailyBucket.LIMIT - 2)


# ---------------------------------------------------------------------------
# Scenario 3: Deduplication — scraping same draft twice keeps row count stable
# ---------------------------------------------------------------------------

class TestDeduplication(unittest.TestCase):
    def _make_scraper(self, tmp_path):
        from lab.data.sleeper_auction_scraper import SleeperAuctionScraper

        db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
        mock_client = MagicMock()
        mock_client.get_league_drafts.return_value = [
            {"draft_id": "d1", "settings": {"budget": 200, "teams": 12}, "start_time": 1714600000000}
        ]
        mock_client.get_draft_detail.return_value = _make_draft_detail()
        mock_client.get_draft_picks.return_value = [
            AuctionPick(
                draft_id="d1",
                sleeper_player_id="p1",
                player_name="Test Player",
                position="WR",
                nfl_team="KC",
                winner_bid=20,
                picked_by_slot=1,
                pick_order=1,
            )
        ]
        return SleeperAuctionScraper(db_url=db_url, client=mock_client)

    def test_idempotent_scrape(self, tmp_path=None):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        scraper = self._make_scraper(tmp)

        result1 = scraper.scrape_league("L1", "2024")
        result2 = scraper.scrape_league("L1", "2024")

        # Second run must not insert new pick rows
        self.assertEqual(result1["picks_inserted"], 1)
        self.assertEqual(result2["picks_inserted"], 0)
        self.assertEqual(result2["picks_skipped"], 1)


if __name__ == "__main__":
    unittest.main()
