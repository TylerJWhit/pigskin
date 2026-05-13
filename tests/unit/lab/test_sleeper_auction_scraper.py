"""Failing tests for SleeperAuctionScraper — acceptance criteria for issue #195.

These tests define the required public API after implementation.  They are
intentionally written to fail against the current stub so that a red/green
cycle can be used to drive the implementation.
"""

from unittest.mock import patch

from lab.data.sleeper_auction_scraper import SleeperAuctionScraper


REQUIRED_KEYS = {"player_name", "position", "auction_value", "actual_price"}


# ---------------------------------------------------------------------------
# 1. Instantiation with (league_id, season)
# ---------------------------------------------------------------------------

class TestSleeperAuctionScraperInstantiation:
    """SleeperAuctionScraper must accept (league_id, season) as its primary
    constructor signature (issue #195).  The current stub takes (db_url, client)
    which is a different shape — these tests will fail until the API is updated.
    """

    def test_instantiation_with_league_id_and_season(self):
        """SleeperAuctionScraper(league_id, season) can be constructed."""
        scraper = SleeperAuctionScraper(league_id="123456789", season="2024")
        assert scraper is not None

    def test_instantiation_stores_league_id(self):
        """Constructed instance exposes the league_id it was given."""
        scraper = SleeperAuctionScraper(league_id="999", season="2023")
        assert scraper.league_id == "999"

    def test_instantiation_stores_season(self):
        """Constructed instance exposes the season it was given."""
        scraper = SleeperAuctionScraper(league_id="999", season="2023")
        assert scraper.season == "2023"


# ---------------------------------------------------------------------------
# 2. fetch() returns a list of dicts
# ---------------------------------------------------------------------------

class TestSleeperAuctionScraperFetch:
    """fetch() must return a list of dicts with the required schema."""

    def _make_scraper(self):
        return SleeperAuctionScraper(league_id="123456789", season="2024")

    def test_fetch_returns_list(self):
        """`fetch()` must return a list."""
        scraper = self._make_scraper()
        with patch.object(scraper, "_fetch_from_api", return_value=_sample_picks()):
            result = scraper.fetch()
        assert isinstance(result, list)

    def test_fetch_returns_list_of_dicts(self):
        """`fetch()` must return a list of dicts."""
        scraper = self._make_scraper()
        with patch.object(scraper, "_fetch_from_api", return_value=_sample_picks()):
            result = scraper.fetch()
        assert all(isinstance(row, dict) for row in result)

    def test_fetch_dicts_have_required_keys(self):
        """Every dict returned by `fetch()` must contain the required keys."""
        scraper = self._make_scraper()
        with patch.object(scraper, "_fetch_from_api", return_value=_sample_picks()):
            result = scraper.fetch()
        assert len(result) > 0, "fetch() returned an empty list — cannot validate keys"
        for row in result:
            missing = REQUIRED_KEYS - row.keys()
            assert not missing, f"Missing keys in fetch() result: {missing}"


# ---------------------------------------------------------------------------
# 3. Invalid league_id raises ValueError or returns []
# ---------------------------------------------------------------------------

class TestSleeperAuctionScraperInvalidLeague:
    """fetch() with a bad league_id must either raise ValueError or return []."""

    def test_invalid_league_id_raises_or_returns_empty(self):
        """fetch() with an invalid league_id raises ValueError or returns []."""
        scraper = SleeperAuctionScraper(league_id="INVALID_LEAGUE_XYZ", season="2024")
        with patch.object(scraper, "_fetch_from_api", return_value=[]):
            try:
                result = scraper.fetch()
                assert result == [], (
                    "Expected fetch() to raise ValueError or return [] for an "
                    f"invalid league, but got: {result!r}"
                )
            except ValueError:
                pass  # acceptable


# ---------------------------------------------------------------------------
# 4. Caching — second call must not re-fetch from the API
# ---------------------------------------------------------------------------

class TestSleeperAuctionScraperCaching:
    """Results must be cached; a second call to fetch() must not hit the API."""

    def test_second_fetch_uses_cache(self):
        """fetch() called twice hits the underlying API only once."""
        scraper = SleeperAuctionScraper(league_id="123456789", season="2024")

        with patch.object(
            scraper, "_fetch_from_api", return_value=_sample_picks()
        ) as mock_api:
            scraper.fetch()
            scraper.fetch()

        mock_api.assert_called_once()

    def test_cache_returns_same_data(self):
        """Cached fetch() returns identical data on both calls."""
        scraper = SleeperAuctionScraper(league_id="123456789", season="2024")

        with patch.object(scraper, "_fetch_from_api", return_value=_sample_picks()):
            first = scraper.fetch()
            second = scraper.fetch()

        assert first == second


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_picks():
    """Return a minimal set of valid auction pick dicts."""
    return [
        {
            "player_name": "Josh Allen",
            "position": "QB",
            "auction_value": 45,
            "actual_price": 52,
        },
        {
            "player_name": "Christian McCaffrey",
            "position": "RB",
            "auction_value": 70,
            "actual_price": 68,
        },
    ]
