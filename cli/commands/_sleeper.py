"""Sleeper API command handler."""
from __future__ import annotations

import asyncio
from typing import Dict


class SleeperMixin:
    """Mixin providing Sleeper API commands."""

    def test_sleeper_connectivity(self) -> Dict:
        """Test Sleeper API with comprehensive connectivity check."""
        print("Running comprehensive Sleeper API connectivity test...")

        tests = []

        print("Testing basic API connectivity...")
        try:
            players = self.sleeper_api.get_all_players()
            if players:
                tests.append(
                    {
                        "test": "Basic Connectivity",
                        "status": "PASS",
                        "details": f"Retrieved {len(players)} NFL players",
                    }
                )
            else:
                tests.append(
                    {"test": "Basic Connectivity", "status": "FAIL", "details": "No data returned"}
                )
        except Exception as e:
            tests.append({"test": "Basic Connectivity", "status": "FAIL", "details": str(e)})

        print("Testing rate limiting...")
        try:
            import time

            start_time = time.time()
            for _ in range(3):
                self.sleeper_api.get_all_players()
            elapsed = time.time() - start_time
            tests.append(
                {
                    "test": "Rate Limiting",
                    "status": "PASS",
                    "details": f"3 requests in {elapsed:.2f}s",
                }
            )
        except Exception as e:
            tests.append({"test": "Rate Limiting", "status": "FAIL", "details": str(e)})

        print("Testing data quality...")
        try:
            players = self.sleeper_api.get_all_players()
            if players:
                sample_player = next(iter(players.values()))
                required_fields = ["full_name", "position", "team"]
                missing_fields = [f for f in required_fields if f not in sample_player]

                if not missing_fields:
                    tests.append(
                        {
                            "test": "Data Quality",
                            "status": "PASS",
                            "details": "All required fields present",
                        }
                    )
                else:
                    tests.append(
                        {
                            "test": "Data Quality",
                            "status": "WARN",
                            "details": f"Missing fields: {missing_fields}",
                        }
                    )
            else:
                tests.append(
                    {
                        "test": "Data Quality",
                        "status": "FAIL",
                        "details": "No player data available",
                    }
                )
        except Exception as e:
            tests.append({"test": "Data Quality", "status": "FAIL", "details": str(e)})

        passed_tests = sum(1 for test in tests if test["status"] == "PASS")
        total_tests = len(tests)

        return {
            "success": passed_tests > 0,
            "tests": tests,
            "summary": f"{passed_tests}/{total_tests} tests passed",
            "overall_status": (
                "HEALTHY"
                if passed_tests == total_tests
                else "DEGRADED"
                if passed_tests > 0
                else "FAILED"
            ),
        }

    def get_sleeper_draft_status(self, username: str, season: str = "2024") -> Dict:
        """Get current draft status for a Sleeper user."""
        print(f"Fetching draft status for '{username}' in {season}...")
        try:
            result = asyncio.run(
                self.sleeper_draft_service.get_current_draft_status(username, season)
            )
            return result
        except Exception as e:
            return {"success": False, "error": f"Failed to get draft status: {e}"}

    def display_sleeper_draft(self, draft_id: str) -> Dict:
        """Display detailed Sleeper draft information."""
        print(f"Fetching draft information for ID: {draft_id}...")
        try:
            result = asyncio.run(self.sleeper_draft_service.display_draft_info(draft_id))
            return result
        except Exception as e:
            return {"success": False, "error": f"Failed to display draft: {e}"}

    def display_sleeper_league_rosters(self, league_id: str) -> Dict:
        """Display Sleeper league rosters."""
        print(f"Fetching league rosters for ID: {league_id}...")
        try:
            result = asyncio.run(self.sleeper_draft_service.display_league_rosters(league_id))
            return result
        except Exception as e:
            return {"success": False, "error": f"Failed to display league rosters: {e}"}

    def list_sleeper_leagues(self, username: str, season: str = "2024") -> Dict:
        """List all leagues for a Sleeper user."""
        print(f"Fetching leagues for '{username}' in {season}...")
        try:
            result = asyncio.run(self.sleeper_draft_service.list_user_leagues(username, season))
            return result
        except Exception as e:
            return {"success": False, "error": f"Failed to list leagues: {e}"}
