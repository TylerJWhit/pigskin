"""Draft simulation internals."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List

_DEBUG_LOG_DIR = "/home/tezell/Documents/code/pigskin/logs"


class SimulationMixin:
    """Mixin providing detailed auction simulation logic."""

    def _run_detailed_simulation(self, draft, primary_strategy: str) -> Dict:
        """Run a detailed draft simulation with proper auction mechanics."""
        print("Starting detailed auction simulation...")

        config = self.config_manager.load_config()
        total_roster_slots = sum(config.roster_positions.values())

        print(f"Target roster size: {total_roster_slots} players per team")
        print("Running competitive auction with strategy-based bidding...")

        from classes.auction import Auction
        from classes import create_strategy

        draft.start_draft()
        auction = Auction(draft)

        for team in draft.teams:
            if team.strategy:
                strategy = team.strategy
            else:
                strategy = create_strategy(primary_strategy)
                team.set_strategy(strategy)
            auction.enable_auto_bid(team.owner_id, strategy)

        print("Teams and strategies:")
        for team in draft.teams:
            strategy_name = team.strategy.name if team.strategy else "None"
            print(f"  {team.team_name}: {strategy_name}")
        print()

        auction.start_auction()

        os.makedirs(_DEBUG_LOG_DIR, exist_ok=True)
        debug_log_file = os.path.join(
            _DEBUG_LOG_DIR,
            f"auction_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        )

        def log_debug(message):
            with open(debug_log_file, "a") as f:
                f.write(f"{message}\n")

        log_debug("=== AUCTION DEBUG LOG ===")
        log_debug(f"Teams: {len(draft.teams)}")
        log_debug(f"Available players: {len(draft.available_players)}")
        log_debug(f"Target roster size: {total_roster_slots}")

        position_counts: Dict[str, int] = {}
        for player in draft.available_players:
            pos = getattr(player, "position", "UNKNOWN")
            position_counts[pos] = position_counts.get(pos, 0) + 1
        log_debug(f"Available players by position: {dict(position_counts)}")

        drafted_players: List = []
        max_iterations = len(draft.available_players) * 2
        iterations = 0
        iterations_without_progress = 0
        last_total_roster_size = 0

        while draft.status == "started" and iterations < max_iterations:
            incomplete_teams = [t for t in draft.teams if len(t.roster) < total_roster_slots]
            if not incomplete_teams:
                print("All teams have complete rosters, ending auction...")
                break

            if iterations > 300:
                print(f"Auction reached iteration limit ({iterations}), forcing completion...")
                for team in incomplete_teams:
                    while len(team.roster) < total_roster_slots and team.budget >= 1:
                        available_players = [p for p in draft.available_players if not p.is_drafted]
                        if available_players:
                            cheapest = min(
                                available_players, key=lambda p: getattr(p, "auction_value", 1.0)
                            )
                            cheapest.mark_as_drafted(1.0, team.owner_id)
                            team.roster.append(cheapest)
                            team.budget -= 1.0
                            if cheapest in draft.available_players:
                                draft.available_players.remove(cheapest)
                        else:
                            break
                break

            incomplete_teams = [t for t in draft.teams if len(t.roster) < total_roster_slots]
            if not incomplete_teams:
                print("All teams have complete rosters, ending auction...")
                break

            teams_that_can_continue = [
                t
                for t in incomplete_teams
                if t.budget >= (total_roster_slots - len(t.roster)) * 1.0
            ]

            if not teams_that_can_continue:
                self._log_budget_debug(draft, incomplete_teams, total_roster_slots)
                print("No teams can afford to complete their rosters, ending auction...")
                break

            if not draft.current_player:
                log_debug(f"\nIteration {iterations}: No current player, forcing nomination...")
                auction._auto_nominate_player()

                if draft.current_player:
                    player = draft.current_player
                    log_debug(
                        f"NOMINATED: {player.name} ({getattr(player, 'position', 'UNKNOWN')}) "
                        f"- Value: ${getattr(player, 'auction_value', 'N/A')}"
                    )
                else:
                    log_debug("NOMINATION FAILED: No player nominated")

                if not draft.current_player:
                    log_debug("No more players available for nomination, ending auction...")
                    print("No more players available for nomination, ending auction...")
                    break

            if draft.current_player:
                player = draft.current_player
                initial_bid = getattr(player, "current_bid", 1.0)
                log_debug(f"AUCTION START: {player.name} - Initial bid: ${initial_bid}")

                for bid_round in range(2):
                    log_debug(
                        f"  BID ROUND {bid_round + 1}: Processing auto-bids for {player.name}"
                    )
                    auction._process_auto_bids()
                    log_debug(
                        f"    After bidding: high_bidder={draft.current_high_bidder}, "
                        f"current_bid=${draft.current_bid}"
                    )

                pre_completion_high_bidder = draft.current_high_bidder
                pre_completion_bid = draft.current_bid

                auction.force_complete_auction()

                if pre_completion_high_bidder:
                    winning_team = next(
                        (t for t in draft.teams if t.owner_id == pre_completion_high_bidder), None
                    )
                    winning_strategy = (
                        winning_team.strategy.name
                        if winning_team and winning_team.strategy
                        else "Unknown"
                    )
                    log_debug(
                        f"AUCTION WON: {player.name} ({getattr(player, 'position', 'UNKNOWN')}) "
                        f"-> {winning_strategy} for ${pre_completion_bid}"
                    )
                else:
                    log_debug(
                        f"AUCTION FAILED: {player.name} - No winning team "
                        f"(high_bidder: {pre_completion_high_bidder}, current_bid: ${pre_completion_bid})"
                    )
                    eligible_teams = [t for t in draft.teams if t.can_bid(player, 1.0)]
                    log_debug(f"  Eligible teams for bidding: {len(eligible_teams)}")
                    for i, team in enumerate(eligible_teams[:3]):
                        strategy_name = team.strategy.name if team.strategy else "No Strategy"
                        log_debug(
                            f"    Team {team.team_name} ({strategy_name}): "
                            f"Budget ${team.budget:.2f}, Roster {len(team.roster)}/{total_roster_slots}"
                        )
                    if not eligible_teams:
                        log_debug("  No teams eligible to bid!")

                current_drafted = len(draft.drafted_players)
                if current_drafted > len(drafted_players):
                    drafted_players = draft.drafted_players.copy()
                    if len(drafted_players) % 25 == 0:
                        print(f"   Auctioned {len(drafted_players)} players...")
                        log_debug(f"PROGRESS: {len(drafted_players)} players drafted")

                incomplete_teams_after = [t for t in draft.teams if len(t.roster) < total_roster_slots]
                if not incomplete_teams_after:
                    print("All teams now have complete rosters, ending auction...")
                    break

                min_reasonable_roster = 12
                teams_with_reasonable_rosters = [
                    t for t in draft.teams if len(t.roster) >= min_reasonable_roster
                ]
                if len(teams_with_reasonable_rosters) == len(draft.teams):
                    remaining_budget_total = sum(t.budget for t in draft.teams)
                    if remaining_budget_total < len(draft.teams) * 5:
                        print(
                            "All teams have reasonable rosters and little budget left, ending auction..."
                        )
                        break

                current_total_roster_size = sum(len(t.roster) for t in draft.teams)
                if current_total_roster_size == last_total_roster_size:
                    iterations_without_progress += 1
                    teams_with_budget = [t for t in draft.teams if t.budget >= 1.0]
                    teams_needing_players = [t for t in draft.teams if len(t.roster) < total_roster_slots]

                    max_stall_iterations = 20
                    if teams_with_budget and teams_needing_players:
                        teams_needing_and_with_budget = [
                            t
                            for t in teams_needing_players
                            if t.budget >= (total_roster_slots - len(t.roster))
                        ]
                        if teams_needing_and_with_budget:
                            max_stall_iterations = 60
                        else:
                            max_stall_iterations = 40

                    if iterations_without_progress > max_stall_iterations:
                        log_debug(
                            f"\nAUCTION STALLED: {max_stall_iterations} iterations without progress"
                        )
                        log_debug(f"Teams with budget >= $1: {len(teams_with_budget)}")
                        log_debug(f"Teams needing players: {len(teams_needing_players)}")

                        print(
                            f"Auction stalled - no progress for {max_stall_iterations} iterations, ending..."
                        )
                        print(f"DEBUG: Teams with budget >= $1: {len(teams_with_budget)}")
                        print(f"DEBUG: Teams needing players: {len(teams_needing_players)}")

                        for team in teams_needing_players:
                            if team.budget >= (total_roster_slots - len(team.roster)):
                                strategy_name = team.strategy.name if team.strategy else "No Strategy"
                                slots_needed = total_roster_slots - len(team.roster)
                                log_debug(
                                    f"FORCE COMPLETE: {team.team_name} ({strategy_name}): "
                                    f"${team.budget:.2f}, needs {slots_needed} players"
                                )
                                print(
                                    f"  FORCE COMPLETE: {team.team_name} ({strategy_name}): "
                                    f"${team.budget:.2f}, needs {slots_needed} players"
                                )

                                for _slot_num in range(slots_needed):
                                    if team.budget >= 1.0:
                                        available_players = [
                                            p for p in draft.available_players if not p.is_drafted
                                        ]
                                        if available_players:
                                            cheapest_player = min(
                                                available_players,
                                                key=lambda p: getattr(p, "auction_value", 1.0),
                                            )
                                            log_debug(
                                                f"  FORCE DRAFT: {cheapest_player.name} "
                                                f"({getattr(cheapest_player, 'position', 'UNKNOWN')}) "
                                                f"-> {team.team_name} for $1.00"
                                            )
                                            cheapest_player.mark_as_drafted(1.0, team.owner_id)
                                            team.roster.append(cheapest_player)
                                            team.budget -= 1.0
                                            if cheapest_player in draft.available_players:
                                                draft.available_players.remove(cheapest_player)
                                            draft.drafted_players.append(cheapest_player)
                                        else:
                                            log_debug(
                                                f"  FORCE DRAFT FAILED: No available players for {team.team_name}"
                                            )
                                            break
                                    else:
                                        log_debug(
                                            f"  FORCE DRAFT STOPPED: {team.team_name} out of budget"
                                        )
                                        break
                        break
                else:
                    iterations_without_progress = 0
                    last_total_roster_size = current_total_roster_size

                if iterations > 200 and iterations % 50 == 0:
                    print(f"Long auction detected (iteration {iterations}), checking for termination...")
                    stuck_teams = [
                        t
                        for t in draft.teams
                        if len(t.roster) >= 12 and t.budget < 5
                    ]
                    if len(stuck_teams) >= len(draft.teams) * 0.8:
                        print(
                            "Most teams have reasonable rosters but little budget, forcing completion..."
                        )
                        break

            iterations += 1

        auction.stop_auction()

        if draft.status == "started":
            draft._complete_draft()

        completed_rosters = len(
            [t for t in draft.teams if len(t.roster) == total_roster_slots]
        )
        print(f"Auction simulation complete! Drafted {len(drafted_players)} players")
        print(f"Teams with complete rosters: {completed_rosters}/{len(draft.teams)}")
        print(f"Auction iterations: {iterations}")

        log_debug("\n=== AUCTION COMPLETE ===")
        log_debug(f"Total iterations: {iterations}")
        log_debug(f"Players drafted: {len(drafted_players)}")
        log_debug(f"Teams with complete rosters: {completed_rosters}/{len(draft.teams)}")

        remaining_players = [p for p in draft.available_players if not p.is_drafted]
        remaining_by_position: Dict[str, int] = {}
        for player in remaining_players:
            pos = getattr(player, "position", "UNKNOWN")
            remaining_by_position[pos] = remaining_by_position.get(pos, 0) + 1
        log_debug(f"Remaining players by position: {dict(remaining_by_position)}")

        for pos in remaining_by_position.keys():
            players_in_pos = [
                p for p in remaining_players if getattr(p, "position", "UNKNOWN") == pos
            ][:5]
            log_debug(f"Sample remaining {pos} players: {[p.name for p in players_in_pos]}")

        log_debug("\n=== FINAL TEAM ROSTERS ===")
        for team in draft.teams:
            strategy_name = team.strategy.name if team.strategy else "No Strategy"
            log_debug(
                f"{team.team_name} ({strategy_name}): "
                f"{len(team.roster)}/{total_roster_slots} players, ${team.budget:.2f} remaining"
            )
            team_positions: Dict[str, int] = {}
            for player in team.roster:
                pos = getattr(player, "position", "UNKNOWN")
                team_positions[pos] = team_positions.get(pos, 0) + 1
            log_debug(f"  Positions: {dict(team_positions)}")

        log_debug(f"\nDebug log saved to: {debug_log_file}")
        print(f"Debug log saved to: {debug_log_file}")

        self._display_final_rosters(draft, total_roster_slots, completed_rosters, drafted_players, iterations)

        return {
            "total_players_drafted": len(drafted_players),
            "total_roster_slots": total_roster_slots,
            "completed_rosters": completed_rosters,
            "rounds_completed": (
                len(drafted_players) // len(draft.teams) if draft.teams else 0
            ),
            "round_results": [],
            "primary_strategy": primary_strategy,
        }
