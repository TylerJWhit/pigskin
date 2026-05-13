"""Display helpers for auction simulation output."""
from __future__ import annotations

from typing import Dict, List


class SimulationDisplayMixin:
    """Mixin with display/debug output helpers for the simulation."""

    def _display_final_rosters(
        self,
        draft,
        total_roster_slots: int,
        completed_rosters: int,
        drafted_players: List,
        iterations: int,
    ) -> None:
        """Display final roster breakdown and tournament summary."""
        print("\n=== FINAL TOURNAMENT ROSTERS ===")
        for i, team in enumerate(draft.teams, 1):
            strategy_name = team.strategy.name if team.strategy else "No Strategy"
            roster_status = (
                "COMPLETE" if len(team.roster) == total_roster_slots else "INCOMPLETE"
            )
            print(f"\n{i}. {team.team_name} ({strategy_name}) - {roster_status}")
            print(f"   Roster: {len(team.roster)}/{total_roster_slots} players")
            print(
                f"   Budget: ${team.budget:.2f} remaining "
                f"(spent: ${200 - team.budget:.2f})"
            )
            print(f"   Projected Points: {team.get_projected_points():.1f}")

            pos_counts: Dict[str, int] = {}
            for player in team.roster:
                pos = getattr(player, "position", "UNKNOWN")
                pos_counts[pos] = pos_counts.get(pos, 0) + 1
            print(f"   Position breakdown: {dict(pos_counts)}")

            if team.roster:
                sorted_roster = sorted(
                    team.roster,
                    key=lambda p: getattr(p, "auction_price", 1.0),
                    reverse=True,
                )
                print("   Top players:")
                for j, player in enumerate(sorted_roster[:5], 1):
                    pos = getattr(player, "position", "UNKNOWN")
                    price = getattr(player, "auction_price", 1.0)
                    points = getattr(player, "projected_points", 0)
                    print(f"     {j}. {player.name} ({pos}) - ${price:.0f}, {points:.1f} pts")

            if len(team.roster) < total_roster_slots:
                missing = total_roster_slots - len(team.roster)
                print(f"   Missing {missing} players")
                if team.budget < missing:
                    print(
                        f"   Insufficient budget: ${team.budget:.2f} < ${missing:.2f} needed"
                    )
                else:
                    available_count = len(
                        [p for p in draft.available_players if not p.is_drafted]
                    )
                    print(
                        f"   Had budget but didn't complete "
                        f"(available players: {available_count})"
                    )

        print("\n=== TOURNAMENT SUMMARY ===")
        print(f"Complete rosters: {completed_rosters}/{len(draft.teams)}")
        total_spent = sum(200 - t.budget for t in draft.teams)
        avg_spent = total_spent / len(draft.teams) if draft.teams else 0
        print(f"Average spent per team: ${avg_spent:.2f}")
        print(f"Total auction iterations: {iterations}")
        print("=== END TOURNAMENT DEBUG ===\n")

    def _log_budget_debug(self, draft, incomplete_teams, total_roster_slots: int) -> None:
        """Log budget debug info when teams can't complete rosters."""
        print("\n=== DEBUGGING: Teams cannot afford to complete rosters ===")
        for team in incomplete_teams:
            remaining_slots = total_roster_slots - len(team.roster)
            min_budget_needed = remaining_slots * 1.0
            print(
                f"\nTeam {team.team_name} "
                f"(Strategy: {getattr(team, 'strategy', 'Unknown')}):"
            )
            print(f"  Current roster size: {len(team.roster)}/{total_roster_slots}")
            print(f"  Remaining slots needed: {remaining_slots}")
            print(f"  Current budget: ${team.budget:.2f}")
            print(
                f"  Budget needed to complete: ${min_budget_needed:.2f} "
                "(minimum bid rate ($1.00/slot))"
            )
            print(f"  Can afford completion: {team.budget >= min_budget_needed}")

            pos_counts: Dict[str, int] = {}
            for player in team.roster:
                pos = getattr(player, "position", "UNKNOWN")
                pos_counts[pos] = pos_counts.get(pos, 0) + 1
            print(f"  Current roster: {dict(pos_counts)}")

            if hasattr(team, "roster_config") and team.roster_config:
                needed_positions = {}
                for pos, required in team.roster_config.items():
                    if pos in ["FLEX", "BN", "BENCH"]:
                        continue
                    current_count = pos_counts.get(pos, 0)
                    if current_count < required:
                        needed_positions[pos] = required - current_count

                total_position_slots = sum(
                    team.roster_config.get(pos, 0)
                    for pos in ["QB", "RB", "WR", "TE", "K", "DST"]
                )
                flex_bench_slots = total_roster_slots - total_position_slots
                filled_flex_bench = len(team.roster) - sum(
                    pos_counts.get(pos, 0)
                    for pos in ["QB", "RB", "WR", "TE", "K", "DST"]
                )
                remaining_flex_bench = max(0, flex_bench_slots - filled_flex_bench)

                if needed_positions:
                    print(f"  Missing required positions: {needed_positions}")
                if remaining_flex_bench > 0:
                    print(f"  Remaining flex/bench slots: {remaining_flex_bench}")
                if not needed_positions and remaining_flex_bench == 0:
                    print("  All requirements met, but total slots calculation seems off")

        print("=== END DEBUGGING ===\n")
