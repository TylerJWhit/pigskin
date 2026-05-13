"""Tournament command handler — core elimination and pool logic."""
from __future__ import annotations

from typing import Dict, List

from classes import AVAILABLE_STRATEGIES


class TournamentMixin:
    """Mixin providing tournament commands."""

    def run_elimination_tournament(
        self,
        rounds_per_group: int = 10,
        teams_per_draft: int = 10,
        verbose: bool = False,
    ) -> Dict:
        """Run a proper elimination tournament."""
        print("Starting elimination tournament with all available strategies...")
        print(
            f"Tournament format: {teams_per_draft} teams per draft, "
            f"{rounds_per_group} rounds per group"
        )
        all_strategies = list(AVAILABLE_STRATEGIES.keys())
        print(f"Available strategies: {', '.join(all_strategies)}")
        return self._run_elimination_rounds(all_strategies, rounds_per_group, teams_per_draft, verbose)

    def _run_elimination_rounds(
        self,
        strategies: List[str],
        rounds_per_group: int,
        teams_per_draft: int,
        verbose: bool,
    ) -> Dict:
        """Run elimination rounds until we have a winner."""
        round_number = 1
        current_strategies = strategies.copy()

        while len(current_strategies) > 1:
            print(f"\n=== ELIMINATION ROUND {round_number} ===")
            print(f"Competing strategies: {len(current_strategies)}")

            groups = self._create_tournament_pools(current_strategies, teams_per_draft)
            print(f"Created {len(groups)} groups of {teams_per_draft} teams each")

            round_winners = []
            for group_num, group_strategies in enumerate(groups, 1):
                print(f"\nGROUP {group_num}/{len(groups)}: {', '.join(set(group_strategies))}")
                print(f"Running {rounds_per_group} drafts...")

                group_stats = {
                    strategy: {"wins": 0, "total_points": 0, "drafts": 0}
                    for strategy in set(group_strategies)
                }

                for draft_num in range(1, rounds_per_group + 1):
                    if verbose:
                        print(f"   Draft {draft_num}/{rounds_per_group}:", end=" ")
                    else:
                        print(f"   Draft {draft_num}/{rounds_per_group}...", end=" ")

                    draft_result = self.run_enhanced_mock_draft(group_strategies, teams_per_draft)

                    if draft_result.get("success", False):
                        winner_strategy = draft_result.get("winner_strategy", "unknown")
                        winner_points = draft_result.get("winner_points", 0)

                        if verbose:
                            print(f"Winner: {winner_strategy} ({winner_points:.1f} pts)")
                        else:
                            print("✓")

                        if winner_strategy in group_stats:
                            group_stats[winner_strategy]["wins"] += 1

                        for team_result in draft_result.get("team_results", []):
                            strategy_name = team_result.get("strategy", "unknown")
                            points = team_result.get("total_points", 0)
                            if strategy_name in group_stats:
                                group_stats[strategy_name]["total_points"] += points
                                group_stats[strategy_name]["drafts"] += 1
                    else:
                        print(f"Failed: {draft_result.get('error', 'Unknown error')}")

                group_winner = max(
                    group_stats.keys(),
                    key=lambda s: (
                        group_stats[s]["wins"],
                        group_stats[s]["total_points"] / max(1, group_stats[s]["drafts"]),
                    ),
                )
                round_winners.append(group_winner)
                wins = group_stats[group_winner]["wins"]
                avg_points = group_stats[group_winner]["total_points"] / max(
                    1, group_stats[group_winner]["drafts"]
                )
                print(
                    f"   GROUP {group_num} WINNER: {group_winner} "
                    f"({wins}/{rounds_per_group} wins, {avg_points:.1f} avg pts)"
                )

            current_strategies = round_winners
            round_number += 1

            if len(current_strategies) == 1:
                break

        tournament_winner = current_strategies[0] if current_strategies else "No winner"
        print(f"\nTOURNAMENT CHAMPION: {tournament_winner}")

        return {
            "success": True,
            "tournament_winner": tournament_winner,
            "total_rounds": round_number - 1,
        }

    def run_comprehensive_tournament(
        self,
        num_rounds: int = 3,
        teams_per_draft: int = 10,
        verbose: bool = False,
    ) -> Dict:
        """Run comprehensive tournament (delegates to elimination tournament)."""
        return self.run_elimination_tournament(num_rounds, teams_per_draft, verbose)

    def _run_elimination_tournament(self, strategies: List[str], teams_per_draft: int) -> Dict:
        """Run elimination-style tournament with advancing winners."""
        print(f"\nStarting elimination tournament with {len(strategies)} strategies")

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
            print(f"   Created {len(pools)} draft pools of {teams_per_draft} teams each")

            round_winners = []
            round_results = []

            for pool_idx, pool_strategies in enumerate(pools, 1):
                print(
                    f"   Running Draft Pool {pool_idx}/{len(pools)}: "
                    f"{', '.join(pool_strategies)}"
                )
                pool_result = self._run_elimination_draft(pool_strategies)

                if pool_result.get("success", False):
                    winner = pool_result["winner"]
                    round_winners.append(winner)
                    round_results.append(pool_result)
                    print(f"      Pool {pool_idx} Winner: {winner['strategy']}")
                    print(
                        f"      Score: {winner['points']:.1f} pts, "
                        f"Efficiency: {winner['efficiency']:.2f}"
                    )
                else:
                    print(
                        f"      Pool {pool_idx} failed: "
                        f"{pool_result.get('error', 'Unknown error')}"
                    )

            tournament_bracket["rounds"].append(
                {
                    "round_number": round_number,
                    "participants": current_strategies.copy(),
                    "pools": pools,
                    "winners": [w["strategy"] for w in round_winners],
                    "detailed_results": round_results,
                }
            )

            all_results.extend(round_results)
            current_strategies = [winner["strategy"] for winner in round_winners]
            print(f"   Round {round_number} complete! {len(current_strategies)} strategies advance")
            if current_strategies:
                print(f"   Advancing: {', '.join(current_strategies)}")

            round_number += 1

            if round_number > 10:
                print("   Maximum rounds reached, ending tournament")
                break

        champion = current_strategies[0] if current_strategies else None
        tournament_bracket["champion"] = champion

        if champion:
            print(f"\nTOURNAMENT CHAMPION: {champion.upper()}")
            print(f"Total rounds: {round_number - 1}")
            print(f"Total drafts conducted: {len(all_results)}")

        return {
            "success": True,
            "tournament_type": "elimination",
            "tournament_name": "Mock Draft Elimination Tournament",
            "champion": champion,
            "tournament_bracket": tournament_bracket,
            "rounds_completed": round_number - 1,
            "total_drafts": len(all_results),
            "all_draft_results": all_results,
            "completed_simulations": len(all_results),
            "num_simulations": len(all_results),
            "strategies_tested": len(strategies),
            "results": self._format_tournament_results_for_display(all_results, strategies),
        }

    def _map_strategy_name_to_key(self, strategy_name: str) -> str:
        """Map strategy display name back to key."""
        name_to_key = {
            "Value-Based": "value",
            "Aggressive": "aggressive",
            "Conservative": "conservative",
            "Balanced": "balanced",
            "Sigmoid": "sigmoid",
            "VOR": "vor",
            "Basic": "basic",
            "Adaptive": "adaptive",
            "Improved Value": "improved_value",
            "Elite Hybrid": "elite_hybrid",
            "Value Random": "value_random",
            "Value Smart": "value_smart",
            "Inflation VOR": "inflation_vor",
            "League": "league",
            "Refined Value Random": "refined_value_random",
        }
        return name_to_key.get(strategy_name, strategy_name.lower().replace(" ", "_"))

    def _create_tournament_pools(
        self, strategies: List[str], teams_per_draft: int
    ) -> List[List[str]]:
        """Create pools for elimination tournament."""
        pools = []

        if len(strategies) <= teams_per_draft:
            pool = self._create_single_pool_with_duplicates(strategies, teams_per_draft)
            pools.append(pool)
        else:
            remaining_strategies = strategies.copy()

            while len(remaining_strategies) >= teams_per_draft:
                pool = remaining_strategies[:teams_per_draft]
                remaining_strategies = remaining_strategies[teams_per_draft:]
                pools.append(pool)

            if remaining_strategies:
                if pools:
                    last_pool = pools[-1]
                    if len(last_pool) + len(remaining_strategies) <= teams_per_draft + 2:
                        last_pool.extend(remaining_strategies)
                    else:
                        new_pool = self._create_single_pool_with_duplicates(
                            remaining_strategies, teams_per_draft
                        )
                        pools.append(new_pool)

        return pools

    def _create_single_pool_with_duplicates(
        self, strategies: List[str], teams_per_draft: int
    ) -> List[str]:
        """Create a single pool with strategy duplicates to fill teams_per_draft."""
        pool = list(strategies)
        while len(pool) < teams_per_draft:
            pool.append(strategies[len(pool) % len(strategies)])
        return pool

    def _run_elimination_draft(self, strategies: List[str], verbose: bool = False) -> Dict:
        """Run a single elimination draft with given strategies."""
        try:
            draft = self._create_test_draft(len(strategies))

            if not draft:
                return {"success": False, "error": "Failed to create draft"}

            from classes.auction import Auction
            from classes import create_strategy

            draft.start_draft()
            auction = Auction(draft)

            team_strategies = {}
            for i, team in enumerate(draft.teams):
                strategy_name = strategies[i % len(strategies)]
                strategy = create_strategy(strategy_name)
                if (
                    hasattr(strategy, "enable_tournament_mode")
                    and "gridiron_sage" in strategy_name.lower()
                ):
                    strategy.enable_tournament_mode(True)
                team.set_strategy(strategy)
                auction.enable_auto_bid(team.owner_id, strategy)
                team_strategies[team.team_name] = strategy_name

            auction.start_auction()

            max_iterations = len(draft.available_players) * 2
            iterations = 0

            while draft.status == "started" and iterations < max_iterations:
                if not draft.current_player:
                    auction._auto_nominate_player()

                if draft.current_player:
                    for _ in range(3):
                        auction._process_auto_bids()
                    auction.force_complete_auction()

                iterations += 1

                if len(draft.drafted_players) >= len(draft.teams) * 12:
                    break

            auction.stop_auction()

            if draft.status == "started":
                draft._complete_draft()

            if not draft.teams:
                return {"success": False, "error": "No teams in draft"}

            team_results = []
            for team in draft.teams:
                strategy_name = team_strategies.get(team.team_name, "unknown")
                points = team.get_projected_points()
                spent = team.get_total_spent()
                efficiency = points / spent if spent > 0 else 0

                team_results.append(
                    {
                        "team_name": team.team_name,
                        "strategy": strategy_name,
                        "points": points,
                        "spent": spent,
                        "efficiency": efficiency,
                        "roster_size": len(team.roster),
                    }
                )

            team_results.sort(key=lambda x: x["points"], reverse=True)

            return {
                "success": True,
                "winner": team_results[0],
                "all_teams": team_results,
                "total_players_drafted": len(draft.drafted_players),
                "iterations": iterations,
            }

        except Exception as e:
            return {"success": False, "error": f"Draft simulation failed: {str(e)}"}
