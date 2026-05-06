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


class TestScraperExtraCoverage(unittest.TestCase):
    """Cover remaining uncovered paths in sleeper_auction_scraper.py."""

    def _make_scraper(self, tmp_path=None):
        import tempfile
        from lab.data.sleeper_auction_scraper import SleeperAuctionScraper
        from lab.data.sleeper_client import SleeperLabClient
        from pathlib import Path
        cache_dir = Path(tempfile.mkdtemp() if tmp_path is None else tmp_path)
        mock_engine = MagicMock()
        # Make async context manager
        mock_conn = MagicMock()
        mock_conn.__aenter__ = MagicMock(return_value=mock_conn)
        mock_conn.__aexit__ = MagicMock(return_value=None)
        mock_engine.begin.return_value = mock_conn
        client = MagicMock(spec=SleeperLabClient)
        scraper = SleeperAuctionScraper.__new__(SleeperAuctionScraper)
        scraper._client = client
        scraper._engine = mock_engine
        return scraper, client

    def test_scrape_league_season_no_drafts(self):
        """Cover lines 82-83: no drafts found returns early."""
        import asyncio
        from lab.data.sleeper_auction_scraper import SleeperAuctionScraper
        scraper, client = self._make_scraper()
        client.get_league_drafts.return_value = []

        result = asyncio.run(scraper._scrape_league_async("league1", "2024"))
        self.assertEqual(result["drafts_processed"], 0)

    def test_scrape_draft_missing_draft_id(self):
        """Cover line 95: draft meta with no draft_id is skipped."""
        import asyncio
        from lab.data.sleeper_auction_scraper import SleeperAuctionScraper
        scraper, client = self._make_scraper()
        # Return one draft meta without draft_id
        client.get_league_drafts.return_value = [{"no_draft_id": "x"}]

        # Need to mock the engine begin context manager properly
        import unittest.mock as um
        mock_ctx = um.AsyncMock()
        mock_ctx.__aenter__ = um.AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = um.AsyncMock(return_value=None)
        scraper._engine.begin.return_value = mock_ctx

        result = asyncio.run(scraper._scrape_league_async("league1", "2024"))
        # Should process 0 (skipped the invalid entry)
        self.assertEqual(result["drafts_processed"], 0)

    def test_get_or_create_draft_invalid_date(self):
        """Cover lines 174-175: invalid draft date is caught and set to None."""
        import asyncio
        from unittest.mock import AsyncMock
        from lab.data.sleeper_auction_scraper import SleeperAuctionScraper
        scraper, client = self._make_scraper()

        draft_meta = {
            "draft_id": "d1",
            "start_time": "not_a_number",  # will trigger ValueError in int()
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        async def _run():
            return await scraper._get_or_create_draft(
                mock_session, "d1", "league1", "2024", draft_meta
            )

        result = asyncio.run(_run())
        # Should succeed with draft_date=None (exception caught at lines 174-175)
        self.assertIsNotNone(result)

    def test_scrape_draft_get_or_create_returns_none(self):
        """Cover line 124: _get_or_create_draft returns None → return 0, 0."""
        import asyncio
        from unittest.mock import AsyncMock
        from lab.data.sleeper_auction_scraper import SleeperAuctionScraper
        scraper, client = self._make_scraper()

        # Patch _session_factory to return a context manager with async session
        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        scraper._session_factory = MagicMock(return_value=mock_ctx)

        # Patch _get_or_create_draft to return None
        scraper._get_or_create_draft = AsyncMock(return_value=None)

        async def _run():
            return await scraper._scrape_draft('d1', 'league1', '2024', {'draft_id': 'd1'})

        inserted, skipped = asyncio.run(_run())
        self.assertEqual(inserted, 0)
        self.assertEqual(skipped, 0)


class TestSleeperClientExtraCoverage(unittest.TestCase):
    """Cover remaining uncovered paths in sleeper_client.py."""

    def _make_client(self, tmp_path=None):
        import tempfile
        from lab.data.sleeper_client import SleeperLabClient
        from pathlib import Path
        cache_dir = Path(tempfile.mkdtemp() if tmp_path is None else tmp_path)
        return SleeperLabClient(cache_dir=cache_dir, cache_ttl=0)

    def test_rate_limiter_sleep_on_limit(self):
        """Cover lines 70-72: rate limit reached triggers sleep."""
        from lab.data.sleeper_client import _DailyBucket
        import time as time_mod
        bucket = _DailyBucket()
        # Fill up the bucket to limit
        now = time_mod.monotonic()
        bucket._calls = [now] * bucket.LIMIT

        with patch("time.sleep") as mock_sleep, \
             patch("time.monotonic", return_value=now):
            bucket.acquire()
        mock_sleep.assert_called_once()

    def test_get_raises_on_http_status_error(self):
        """Cover lines 169-172: HTTPStatusError becomes RuntimeError."""
        import httpx
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("httpx.get", side_effect=httpx.HTTPStatusError("err", request=MagicMock(), response=mock_resp)):
            with self.assertRaises(RuntimeError, msg="Sleeper API error"):
                client._get("some/endpoint")

    def test_get_raises_on_request_error(self):
        """Cover lines 173-174: RequestError becomes RuntimeError."""
        import httpx
        client = self._make_client()
        with patch("httpx.get", side_effect=httpx.RequestError("conn failed")):
            with self.assertRaises(RuntimeError, msg="Network error"):
                client._get("some/endpoint")

    def test_get_draft_picks_returns_list(self):
        """Cover line 115: get_draft_picks returns AuctionPick list."""
        client = self._make_client()
        raw_pick = {
            'player_id': 'p1', 'picked_by': 'owner1', 'amount': 50,
            'metadata': {'position': 'QB', 'first_name': 'Test', 'last_name': 'Player'}
        }
        with patch.object(client, '_get', return_value=[raw_pick]):
            picks = client.get_draft_picks('draft_001')
        self.assertIsInstance(picks, list)

    def test_get_draft_detail_returns_dict(self):
        """Cover line 143: get_draft_detail returns raw draft dict."""
        client = self._make_client()
        fake_detail = {'draft_id': 'draft_001', 'type': 'auction', 'settings': {'budget': 200}}
        with patch.object(client, '_get', return_value=fake_detail):
            result = client.get_draft_detail('draft_001')
        self.assertEqual(result['draft_id'], 'draft_001')

    def test_get_league_drafts_returns_list(self):
        """Cover line 115 (get_league_drafts): returns list of draft dicts."""
        client = self._make_client()
        fake_drafts = [{'draft_id': 'd1'}, {'draft_id': 'd2'}]
        with patch.object(client, '_get', return_value=fake_drafts):
            result = client.get_league_drafts('league_001')
        self.assertEqual(len(result), 2)
