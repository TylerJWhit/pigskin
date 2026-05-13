"""Comprehensive statistical tournament (Phase 1 groups + Phase 2 championship)."""
from __future__ import annotations

from typing import Dict, List


class TournamentStatsMixin:
    """Mixin with comprehensive statistical tournament logic."""

    def _run_comprehensive_statistical_tournament(
        self,
        strategies: List[str],
        teams_per_draft: int = 10,
        verbose: bool = False,
    ) -> Dict:
        """Run comprehensive tournament with statistical significance."""
        print(f"\nStarting comprehensive statistical tournament with {len(strategies)} strategies")
        print(f"Format: {teams_per_draft} teams per draft, 10 runs per group")

        all_results = []
        phase_1_results = {}

        print("\n=== PHASE 1: QUALIFYING ROUNDS ===")
        print(f"Testing all {len(strategies)} strategies in groups of {teams_per_draft}")

        strategy_groups = self._create_tournament_pools(strategies, teams_per_draft)

        for group_idx, group_strategies in enumerate(strategy_groups, 1):
            print(f"\nGROUP {group_idx}/{len(strategy_groups)}: {', '.join(group_strategies)}")
            print("   Running 10 drafts for statistical significance...")

            group_stats = {
                strategy: {
                    "wins": 0,
                    "total_points": 0,
                    "total_spent": 0,
                    "simulations": 0,
                    "points_history": [],
                }
                for strategy in group_strategies
            }

            for run_num in range(1, 11):
                if verbose:
                    print(f"     Draft {run_num}/10:", end=" ")
                else:
                    print(f"     Draft {run_num}/10...", end=" ")

                draft_result = self.run_enhanced_mock_draft(
                    group_strategies, len(group_strategies)
                )

                if draft_result.get("success", False):
                    draft = draft_result.get("draft")
                    teams = []
                    if draft and hasattr(draft, "teams"):
                        for team in draft.teams:
                            teams.append(
                                {
                                    "strategy": team.strategy.name if team.strategy else "Unknown",
                                    "points": team.get_starter_projected_points(),
                                    "spent": team.get_total_spent(),
                                    "roster_size": len(team.roster),
                                }
                            )

                    if teams:
                        best_points = 0
                        winner_strategy = None
                        if verbose:
                            print("\n       Team Results:")

                        for team in teams:
                            strategy_name = team.get("strategy", "")
                            strategy_key = self._map_strategy_name_to_key(strategy_name)
                            if strategy_key in group_stats:
                                stats = group_stats[strategy_key]
                                points = team.get("points", 0)
                                spent = team.get("spent", 0)
                                stats["simulations"] += 1
                                stats["total_points"] += points
                                stats["total_spent"] += spent
                                stats["points_history"].append(points)
                                if verbose:
                                    print(
                                        f"         {strategy_key}: {points:.1f} pts, "
                                        f"${spent:.0f} spent, {team.get('roster_size', 0)} players"
                                    )
                                if points > best_points:
                                    best_points = points
                                    winner_strategy = strategy_key

                        if winner_strategy and winner_strategy in group_stats:
                            group_stats[winner_strategy]["wins"] += 1
                            if verbose:
                                print(f"       Winner: {winner_strategy} ({best_points:.1f} pts)")
                            else:
                                print(f"Winner: {winner_strategy} ({best_points:.1f} pts)")
                        else:
                            print("No winner determined")
                    else:
                        print("No team data")
                else:
                    print(f"Failed: {draft_result.get('error', 'Unknown error')}")

                all_results.append(draft_result)

            print(f"\n   GROUP {group_idx} RESULTS:")
            group_rankings = []
            for strategy_key, stats in group_stats.items():
                if stats["simulations"] > 0:
                    avg_points = stats["total_points"] / stats["simulations"]
                    avg_spent = stats["total_spent"] / stats["simulations"]
                    win_rate = stats["wins"] / stats["simulations"]
                    efficiency = avg_points / max(avg_spent, 1)

                    points_variance = 0.0
                    if len(stats["points_history"]) > 1:
                        mean_pts = avg_points
                        points_variance = sum(
                            (p - mean_pts) ** 2 for p in stats["points_history"]
                        ) / len(stats["points_history"])

                    group_rankings.append(
                        {
                            "strategy": strategy_key,
                            "avg_points": avg_points,
                            "win_rate": win_rate,
                            "wins": stats["wins"],
                            "avg_spent": avg_spent,
                            "efficiency": efficiency,
                            "variance": points_variance,
                            "simulations": stats["simulations"],
                        }
                    )
                    print(
                        f"     {strategy_key}: {win_rate:.1%} wins "
                        f"({stats['wins']}/10), {avg_points:.1f} avg pts"
                    )

            group_rankings.sort(key=lambda x: (x["win_rate"], x["avg_points"]), reverse=True)

            if group_rankings:
                group_winner = group_rankings[0]
                phase_1_results[f"group_{group_idx}_winner"] = group_winner
                print(f"   GROUP {group_idx} CHAMPION: {group_winner['strategy'].upper()}")

        champions = [result["strategy"] for result in phase_1_results.values()]

        if len(champions) < 2:
            print("\n=== TOURNAMENT COMPLETE ===")
            print(
                f"Only one group competed, champion is: {champions[0] if champions else 'No winner'}"
            )
            return {
                "success": True,
                "tournament_winner": champions[0] if champions else None,
                "phase_1_results": phase_1_results,
                "championship_results": None,
                "message": "Single group tournament - no championship round needed",
            }

        print("\n=== PHASE 2: CHAMPIONSHIP ROUND ===")
        print(f"Champions from each group: {', '.join(champions)}")
        print("Running 10 championship drafts...")

        championship_strategies = champions.copy()
        while len(championship_strategies) < teams_per_draft:
            championship_strategies.extend(champions)
        championship_strategies = championship_strategies[:teams_per_draft]

        championship_stats = {
            strategy: {
                "wins": 0,
                "total_points": 0,
                "total_spent": 0,
                "simulations": 0,
                "points_history": [],
            }
            for strategy in set(championship_strategies)
        }

        for run_num in range(1, 11):
            if verbose:
                print(f"   Championship Draft {run_num}/10:", end=" ")
            else:
                print(f"   Championship Draft {run_num}/10...", end=" ")

            draft_result = self.run_enhanced_mock_draft(
                championship_strategies, len(championship_strategies)
            )

            if draft_result.get("success", False):
                draft = draft_result.get("draft")
                teams = []
                if draft and hasattr(draft, "teams"):
                    for team in draft.teams:
                        teams.append(
                            {
                                "strategy": team.strategy.name if team.strategy else "Unknown",
                                "points": team.get_starter_projected_points(),
                                "spent": team.get_total_spent(),
                                "roster_size": len(team.roster),
                            }
                        )

                if teams:
                    best_points = 0
                    winner_strategy = None
                    if verbose:
                        print("\n     Championship Team Results:")

                    for team in teams:
                        strategy_name = team.get("strategy", "")
                        strategy_key = self._map_strategy_name_to_key(strategy_name)
                        if strategy_key in championship_stats:
                            stats = championship_stats[strategy_key]
                            points = team.get("points", 0)
                            spent = team.get("spent", 0)
                            stats["simulations"] += 1
                            stats["total_points"] += points
                            stats["total_spent"] += spent
                            stats["points_history"].append(points)
                            if verbose:
                                print(
                                    f"       {strategy_key}: {points:.1f} pts, "
                                    f"${spent:.0f} spent, {team.get('roster_size', 0)} players"
                                )
                            if points > best_points:
                                best_points = points
                                winner_strategy = strategy_key

                    if winner_strategy:
                        championship_stats[winner_strategy]["wins"] += 1
                        if verbose:
                            print(
                                f"     Championship Winner: {winner_strategy} ({best_points:.1f} pts)"
                            )
                        else:
                            print(f"Winner: {winner_strategy} ({best_points:.1f} pts)")
                    else:
                        print("No winner")
                else:
                    print("No teams")
            else:
                print(f"Failed: {draft_result.get('error', 'Unknown')}")

            all_results.append(draft_result)

        championship_rankings = []
        for strategy_key, stats in championship_stats.items():
            if stats["simulations"] > 0:
                avg_points = stats["total_points"] / stats["simulations"]
                avg_spent = stats["total_spent"] / stats["simulations"]
                win_rate = stats["wins"] / stats["simulations"]
                efficiency = avg_points / max(avg_spent, 1)
                championship_rankings.append(
                    {
                        "strategy": strategy_key,
                        "avg_points": avg_points,
                        "win_rate": win_rate,
                        "wins": stats["wins"],
                        "avg_spent": avg_spent,
                        "efficiency": efficiency,
                        "simulations": stats["simulations"],
                    }
                )

        championship_rankings.sort(
            key=lambda x: (x["win_rate"], x["avg_points"]), reverse=True
        )

        print("\n=== CHAMPIONSHIP RESULTS ===")
        for i, result in enumerate(championship_rankings, 1):
            print(
                f"   {i}. {result['strategy']}: {result['win_rate']:.1%} wins "
                f"({result['wins']}/10), {result['avg_points']:.1f} avg pts"
            )

        tournament_champion = (
            championship_rankings[0]["strategy"] if championship_rankings else None
        )

        if tournament_champion:
            print(f"\nTOURNAMENT CHAMPION: {tournament_champion.upper()}")
            print(f"   Championship win rate: {championship_rankings[0]['win_rate']:.1%}")
            print(f"   Average points: {championship_rankings[0]['avg_points']:.1f}")
            print(f"   Total drafts: {len(all_results)}")

        return {
            "success": True,
            "tournament_type": "comprehensive_statistical",
            "champion": tournament_champion,
            "phase_1_results": phase_1_results,
            "championship_results": championship_rankings,
            "total_drafts": len(all_results),
            "all_draft_results": all_results,
            "group_count": len(strategy_groups),
            "strategies_tested": len(strategies),
        }
