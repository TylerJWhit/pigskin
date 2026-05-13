"""Tournament reporting helpers (mock-draft tournament + results formatting)."""
from __future__ import annotations

from typing import Dict, List


class TournamentHelpersMixin:
    """Mixin with mock-draft tournament and results formatting helpers."""

    def _run_mock_draft_tournament(self, strategies: List[str], teams_per_draft: int) -> Dict:
        """Run tournament using mock drafts in a loop."""
        print(f"\nStarting mock draft tournament with {len(strategies)} strategies")

        all_results = []
        round_number = 1
        current_strategies = strategies.copy()

        tournament_bracket = {
            "rounds": [],
            "champion": None,
            "total_participants": len(strategies),
        }

        while len(current_strategies) > 1:
            print(f"\nROUND {round_number}: {len(current_strategies)} strategies competing")
            pools = self._create_tournament_pools(current_strategies, teams_per_draft)
            print(f"   Created {len(pools)} mock draft pools of {teams_per_draft} teams each")

            round_winners = []
            round_results = []

            for pool_idx, pool_strategies in enumerate(pools, 1):
                print(
                    f"   Running Mock Draft {pool_idx}/{len(pools)}: "
                    f"{', '.join(pool_strategies)}"
                )
                mock_result = self.run_enhanced_mock_draft(pool_strategies, teams_per_draft)

                if mock_result.get("success", False):
                    draft = mock_result["draft"]
                    teams_sorted = sorted(
                        draft.teams,
                        key=lambda t: t.get_projected_points(),
                        reverse=True,
                    )

                    if teams_sorted:
                        winning_team = teams_sorted[0]
                        winner_strategy = (
                            winning_team.strategy.name if winning_team.strategy else "Unknown"
                        )
                        winner_key = self._map_strategy_name_to_key(winner_strategy)
                        round_winners.append(winner_key)

                        pool_result = {
                            "pool_id": pool_idx,
                            "strategies": pool_strategies,
                            "winner": winner_key,
                            "winner_points": winning_team.get_projected_points(),
                            "winner_efficiency": winning_team.get_projected_points()
                            / max(1, winning_team.get_total_spent()),
                            "teams_results": [
                                (t.strategy.name, t.get_projected_points(), t.get_total_spent())
                                for t in teams_sorted
                            ],
                        }
                        round_results.append(pool_result)
                        print(
                            f"     Winner: {winner_strategy} "
                            f"({winning_team.get_projected_points():.1f} points)"
                        )
                    else:
                        print("     ERROR: No teams in mock draft result")
                else:
                    print(
                        f"     ERROR: Mock draft failed - "
                        f"{mock_result.get('error', 'Unknown error')}"
                    )

            round_info = {
                "round_number": round_number,
                "participants": current_strategies.copy(),
                "winners": round_winners.copy(),
                "pools": round_results,
            }
            tournament_bracket["rounds"].append(round_info)
            all_results.extend(round_results)
            print(f"   Round {round_number} winners: {', '.join(round_winners)}")

            current_strategies = round_winners
            round_number += 1

            if round_number > 10:
                break

        champion = current_strategies[0] if current_strategies else None
        tournament_bracket["champion"] = champion
        tournament_bracket["rounds_completed"] = round_number - 1

        print("\nTOURNAMENT COMPLETE!")
        print(f"CHAMPION: {champion}")
        print(f"Rounds completed: {round_number - 1}")

        return {
            "success": True,
            "champion": champion,
            "tournament_bracket": tournament_bracket,
            "all_results": all_results,
            "rounds_completed": round_number - 1,
            "total_participants": len(strategies),
        }

    def _analyze_tournament_performance(self, rankings: List[Dict]) -> Dict:
        """Analyze tournament performance patterns."""
        if not rankings:
            return {}

        avg_points = sum(r["avg_points"] for r in rankings) / len(rankings)
        avg_efficiency = sum(r["avg_value_efficiency"] for r in rankings) / len(rankings)

        best_points = max(rankings, key=lambda r: r["avg_points"])
        best_efficiency = max(rankings, key=lambda r: r["avg_value_efficiency"])
        most_consistent = min(rankings, key=lambda r: r.get("std_dev", float("inf")))

        return {
            "avg_points_across_strategies": avg_points,
            "avg_efficiency_across_strategies": avg_efficiency,
            "best_points_strategy": best_points["strategy"],
            "best_efficiency_strategy": best_efficiency["strategy"],
            "most_consistent_strategy": most_consistent["strategy"],
            "performance_spread": (
                max(r["avg_points"] for r in rankings)
                - min(r["avg_points"] for r in rankings)
            ),
        }

    def _generate_strategy_recommendations(self, rankings: List[Dict]) -> Dict:
        """Generate strategy recommendations based on tournament results."""
        if not rankings:
            return {}

        top_strategy = rankings[0]
        recommendations: Dict = {
            "primary_recommendation": top_strategy["strategy"],
            "reasoning": [],
        }

        if top_strategy["avg_points"] > 1200:
            recommendations["reasoning"].append("High scoring potential")
        if top_strategy["avg_value_efficiency"] > 1.1:
            recommendations["reasoning"].append("Excellent value efficiency")
        if top_strategy["wins"] > len(rankings) * 0.3:
            recommendations["reasoning"].append("High win rate")

        recommendations["alternatives"] = [
            {
                "strategy": r["strategy"],
                "reason": (
                    "Balanced performance"
                    if r["avg_value_efficiency"] > 1.0
                    else "High upside potential"
                ),
            }
            for r in rankings[1:3]
        ]

        return recommendations

    def _format_tournament_results_for_display(
        self, all_results: List[Dict], strategies: List[str]
    ) -> Dict:
        """Format tournament results for consistent display."""
        results = {
            strategy: {
                "wins": 0,
                "simulations": 0,
                "total_points": 0,
                "total_spent": 0,
                "avg_points": 0,
                "avg_spent": 0,
                "win_rate": 0,
                "efficiency": 0,
            }
            for strategy in strategies
        }

        for draft_result in all_results:
            teams = draft_result.get("draft_data", {}).get("teams", [])
            if not teams:
                continue

            best_points = 0
            winner_strategy = None

            for team in teams:
                strategy_name = team.get("strategy_display_name", team.get("strategy", ""))
                strategy_key = self._map_strategy_name_to_key(strategy_name)

                if strategy_key in results:
                    results[strategy_key]["simulations"] += 1
                    points = team.get("projected_points", 0)
                    spent = team.get("total_spent", 0)
                    results[strategy_key]["total_points"] += points
                    results[strategy_key]["total_spent"] += spent

                    if points > best_points:
                        best_points = points
                        winner_strategy = strategy_key

            if winner_strategy:
                results[winner_strategy]["wins"] += 1

        for strategy_key in results:
            stats = results[strategy_key]
            sims = max(stats["simulations"], 1)
            stats["avg_points"] = stats["total_points"] / sims
            stats["avg_spent"] = stats["total_spent"] / sims
            stats["win_rate"] = stats["wins"] / sims if sims > 0 else 0
            stats["efficiency"] = stats["avg_points"] / max(stats["avg_spent"], 1)

        return results
