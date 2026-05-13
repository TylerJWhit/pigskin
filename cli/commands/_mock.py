"""Mock draft command handler."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from classes import AVAILABLE_STRATEGIES, Draft  # noqa: F401

if TYPE_CHECKING:
    pass


class MockDraftMixin:
    """Mixin providing mock draft commands."""

    def run_enhanced_mock_draft(self, strategy, num_teams: int = 10) -> Dict:
        """Run a mock draft with enhanced reporting."""
        print("Initializing mock draft simulation...")

        try:
            if isinstance(strategy, str):
                strategies = [strategy]
                if strategy not in AVAILABLE_STRATEGIES:
                    return {
                        "success": False,
                        "error": f"Invalid strategy. Available: {', '.join(AVAILABLE_STRATEGIES)}",
                    }
            else:
                strategies = strategy
                invalid_strategies = [s for s in strategies if s not in AVAILABLE_STRATEGIES]
                if invalid_strategies:
                    return {
                        "success": False,
                        "error": f"Invalid strategies: {', '.join(invalid_strategies)}. Available: {', '.join(AVAILABLE_STRATEGIES)}",
                    }

            config = self.config_manager.load_config()
            import cli.commands as _cli_commands
            _FantasyProsLoader = _cli_commands.FantasyProsLoader

            loader = _FantasyProsLoader(config.data_path)
            players = loader.load_all_players()

            print(f"Loaded {len(players)} players from FantasyPros")

            draft = self._create_mock_draft(config, players, strategies, num_teams)
            simulation_strategy = strategies[0] if isinstance(strategies, list) else strategies
            simulation_results = self._run_detailed_simulation(draft, simulation_strategy)

            winner_strategy = None
            winner_points = 0
            team_results = []

            if simulation_results:
                best_team = None
                best_points = 0

                for team in draft.teams:
                    total_points = 0
                    for player in team.roster:
                        points = getattr(player, "projected_points", 0)
                        if points > 0:
                            total_points += points

                    team_results.append(
                        {
                            "team_name": team.team_name,
                            "strategy": team.strategy.name if team.strategy else "Unknown",
                            "total_points": total_points,
                            "final_budget": team.budget,
                            "roster_size": len(team.roster),
                        }
                    )

                    if total_points > best_points:
                        best_points = total_points
                        best_team = team

                if best_team:
                    winner_strategy = best_team.strategy.name if best_team.strategy else "Unknown"
                    winner_points = best_points

            return {
                "success": True,
                "draft": draft,
                "simulation_results": simulation_results,
                "strategy": strategies,
                "num_teams": num_teams,
                "winner_strategy": winner_strategy,
                "winner_points": winner_points,
                "team_results": team_results,
            }

        except Exception as e:
            return {"success": False, "error": f"Mock draft failed: {str(e)}"}

    def _create_mock_draft(self, config, players: List, strategies, num_teams: int) -> Draft:
        """Create a mock draft with teams and strategy assignment."""
        import cli.commands as _cli_commands
        _Draft = _cli_commands.Draft
        _Team = _cli_commands.Team
        _Owner = _cli_commands.Owner
        _create_strategy = _cli_commands.create_strategy

        if isinstance(strategies, list) and len(strategies) > 1:
            strategy_name = f"Mixed ({len(strategies)} strategies)"
        elif isinstance(strategies, list):
            strategy_name = strategies[0].title()
        else:
            strategy_name = strategies.title()
            strategies = [strategies]

        roster_positions = getattr(config, "roster_positions", None)
        if roster_positions:
            roster_size = sum(roster_positions.values())
        else:
            roster_size = getattr(config, "roster_size", 16)

        draft = _Draft(
            name=f"Mock Draft - {strategy_name} Strategy",
            budget_per_team=getattr(config, "budget_per_team", getattr(config, "budget", 200)),
            roster_size=roster_size,
        )

        draft.add_players(players)

        for i in range(num_teams):
            team_strategy = strategies[i % len(strategies)]
            strategy_obj = _create_strategy(team_strategy)
            if (
                hasattr(strategy_obj, "enable_tournament_mode")
                and "gridiron_sage" in team_strategy.lower()
            ):
                strategy_obj.enable_tournament_mode(True)
            owner = _Owner(f"owner_{i+1}", f"Owner {i+1}", is_human=(i == 0))
            roster_config = getattr(config, "roster_positions", None)
            team = _Team(
                f"team_{i+1}",
                f"owner_{i+1}",
                f"Team {i+1}",
                budget=getattr(config, "budget_per_team", getattr(config, "budget", 200)),
                roster_config=roster_config,
            )
            team.set_strategy(strategy_obj)
            owner.assign_team(team)
            draft.add_team(team)

        return draft

    def _create_test_draft(self, num_teams: int) -> Optional[Draft]:
        """Create a test draft for tournament elimination rounds."""
        try:
            config = self.config_manager.load_config()
            import cli.commands as _cli_commands
            _FantasyProsLoader = _cli_commands.FantasyProsLoader
            _Draft = _cli_commands.Draft
            _Team = _cli_commands.Team
            _Owner = _cli_commands.Owner

            loader = _FantasyProsLoader(config.data_path)
            players = loader.load_all_players()

            if not players:
                return None

            draft = _Draft(
                name=f"Tournament Draft - {num_teams} Teams",
                budget_per_team=getattr(config, "budget_per_team", getattr(config, "budget", 200)),
                roster_size=getattr(config, "roster_size", 16),
            )

            draft.add_players(players)

            for i in range(num_teams):
                owner = _Owner(f"owner_{i+1}", f"Owner {i+1}", is_human=False)
                team = _Team(f"team_{i+1}", f"owner_{i+1}", f"Team {i+1}")
                owner.assign_team(team)
                draft.add_team(team)

            return draft

        except Exception as e:
            print(f"Error creating test draft: {e}")
            return None
