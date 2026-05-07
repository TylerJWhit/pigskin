"""Bid recommendation service for the auction draft tool."""

import asyncio
from typing import Optional, Dict, Any, List

from classes import Player, Team, Owner, Strategy, create_strategy, Draft
from config.config_manager import ConfigManager
from .draft_loading_service import DraftLoadingService


class BidRecommendationService:
    """Service for recommending bids based on strategy and configuration."""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the bid recommendation service.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or ConfigManager()
        self.draft_service = DraftLoadingService(config_manager)
        self._strategy_cache: Dict[str, Strategy] = {}
        
        # Initialize Sleeper integration
        try:
            from api.sleeper_api import SleeperAPI
            from services.sleeper_draft_service import SleeperDraftService
            from utils.sleeper_cache import get_sleeper_players
            self.sleeper_api = SleeperAPI()
            self.sleeper_draft_service = SleeperDraftService()
            self.get_sleeper_players = get_sleeper_players
            self.sleeper_available = True
        except ImportError:
            self.sleeper_available = False
        
    def recommend_bid(
        self,
        player_name: str,
        current_bid: float,
        team_context: Optional[Dict[str, Any]] = None,
        strategy_override: Optional[str] = None,
        sleeper_draft_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Recommend a bid for a specific player.
        
        Args:
            player_name: Name of the player to bid on
            current_bid: Current highest bid
            team_context: Optional team context (budget, roster, etc.)
            strategy_override: Override the strategy from config
            sleeper_draft_id: Optional Sleeper draft ID for live draft context
            
        Returns:
            Dictionary with bid recommendation and reasoning
        """
        try:
            config = self.config_manager.load_config()
            strategy_type = strategy_override or config.strategy_type
            
            # Get or create strategy
            strategy = self._get_strategy(strategy_type)
            
            # Try to get Sleeper draft context first
            sleeper_context = None
            if self.sleeper_available and sleeper_draft_id:
                sleeper_context = asyncio.run(self._get_sleeper_draft_context(sleeper_draft_id, player_name))
            
            # If no sleeper_draft_id provided, try to get from config
            if self.sleeper_available and not sleeper_context and not sleeper_draft_id:
                default_draft_id = getattr(config, 'sleeper_draft_id', None)
                if default_draft_id:
                    sleeper_context = asyncio.run(self._get_sleeper_draft_context(default_draft_id, player_name))
            
            # Use Sleeper context if available, otherwise fallback to local draft
            if sleeper_context and sleeper_context.get('success'):
                return self._recommend_bid_with_sleeper_context(
                    player_name, current_bid, strategy, sleeper_context, team_context
                )
            else:
                # Fallback to existing FantasyPros functionality
                return self._recommend_bid_with_local_context(
                    player_name, current_bid, strategy, team_context, config
                )
                
        except Exception as e:
            return self._error_response(f"Error generating bid recommendation: {e}")
    
    def recommend_nomination(
        self,
        strategy_override: Optional[str] = None,
        position_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Recommend a player to nominate.
        
        Args:
            strategy_override: Override the strategy from config
            position_filter: Filter by specific positions
            
        Returns:
            Dictionary with nomination recommendation
        """
        try:
            config = self.config_manager.load_config()
            strategy_type = strategy_override or config.strategy_type
            
            # Get strategy
            strategy = self._get_strategy(strategy_type)
            
            # Load current draft
            draft = self.draft_service.load_current_draft()
            if not draft:
                return self._error_response("Could not load draft")
            
            # Get team context
            team = self._get_team_context(draft, None, config)
            owner = self._get_owner_context(draft, team)
            
            # Get available players
            available_players = [p for p in draft.available_players if not p.is_drafted]
            if position_filter:
                available_players = [p for p in available_players if p.position in position_filter]
            
            # Find best nomination candidates
            candidates = []
            for player in available_players:
                should_nominate = strategy.should_nominate(player, team, owner, team.budget)
                if should_nominate:
                    # Calculate potential bid to gauge interest
                    potential_bid = strategy.calculate_bid(
                        player, team, owner, 1.0, team.budget, available_players
                    )
                    candidates.append({
                        'player': player,
                        'potential_bid': potential_bid,
                        'value_score': player.auction_value - potential_bid
                    })
            
            if not candidates:
                # Fall back to highest value players
                candidates = [
                    {
                        'player': player,
                        'potential_bid': 1.0,
                        'value_score': player.auction_value
                    }
                    for player in sorted(available_players, key=lambda p: p.auction_value, reverse=True)[:10]
                ]
            
            # Sort by value score (higher is better)
            candidates.sort(key=lambda c: c['value_score'], reverse=True)
            
            if candidates:
                best_candidate = candidates[0]
                player = best_candidate['player']
                
                return {
                    'success': True,
                    'recommended_player': player.name,
                    'player_position': player.position,
                    'player_team': player.team,
                    'projected_points': player.projected_points,
                    'auction_value': player.auction_value,
                    'suggested_opening_bid': 1.0,
                    'strategy_used': strategy.name,
                    'reasoning': self._generate_nomination_reasoning(player, strategy, team),
                    'alternatives': [
                        {
                            'name': c['player'].name,
                            'position': c['player'].position,
                            'auction_value': c['player'].auction_value
                        }
                        for c in candidates[1:6]  # Top 5 alternatives
                    ]
                }
            else:
                return self._error_response("No suitable players found for nomination")
                
        except Exception as e:
            return self._error_response(f"Error generating nomination recommendation: {e}")
    
    def analyze_team_value(self, team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze team value and provide insights.
        
        Args:
            team_context: Optional team context
            
        Returns:
            Dictionary with team analysis
        """
        try:
            config = self.config_manager.load_config()
            draft = self.draft_service.load_current_draft()
            if not draft:
                return self._error_response("Could not load draft")
            
            team = self._get_team_context(draft, team_context, config)
            
            # Calculate team metrics
            total_value = sum(p.auction_value for p in team.roster)
            total_spent = team.get_total_spent()
            value_efficiency = (total_value / total_spent) if total_spent > 0 else 0
            
            # Position analysis
            position_analysis = {}
            for position in ['QB', 'RB', 'WR', 'TE', 'K', 'DST']:
                players = team.get_players_by_position(position)
                if players:
                    position_analysis[position] = {
                        'count': len(players),
                        'total_points': sum(p.projected_points for p in players),
                        'total_value': sum(p.auction_value for p in players),
                        'total_spent': sum(p.drafted_price or 0 for p in players),
                        'top_player': max(players, key=lambda p: p.projected_points).name
                    }
                else:
                    position_analysis[position] = {
                        'count': 0,
                        'total_points': 0,
                        'total_value': 0,
                        'total_spent': 0,
                        'top_player': None
                    }
            
            return {
                'success': True,
                'team_name': team.team_name,
                'total_projected_points': team.get_projected_points(),
                'budget_remaining': team.budget,
                'budget_spent': total_spent,
                'total_auction_value': total_value,
                'value_efficiency': value_efficiency,
                'roster_complete': team.is_roster_complete(),
                'remaining_needs': team.get_needs(),
                'position_analysis': position_analysis,
                'recommendations': self._generate_team_recommendations(team, config)
            }
            
        except Exception as e:
            return self._error_response(f"Error analyzing team value: {e}")
    
    def _get_strategy(self, strategy_type: str) -> Strategy:
        """Get or create strategy instance."""
        if strategy_type not in self._strategy_cache:
            self._strategy_cache[strategy_type] = create_strategy(strategy_type)
        return self._strategy_cache[strategy_type]
    
    def _find_player(self, draft: Draft, player_name: str) -> Optional[Player]:
        """Find player by name in draft."""
        for player in draft.available_players:
            if player.name.lower() == player_name.lower():
                return player
        
        # Try partial match
        for player in draft.available_players:
            if player_name.lower() in player.name.lower():
                return player
        
        return None
    
    def _get_team_context(self, draft: Draft, team_context: Optional[Dict], config) -> Team:
        """Get or create team context."""
        if team_context and 'team_id' in team_context:
            # Find existing team
            for team in draft.teams:
                if team.team_id == team_context['team_id']:
                    return team
        
        # Create mock team or use first human team
        for team in draft.teams:
            owner = draft._get_owner_by_id(team.owner_id)
            if owner and owner.is_human:
                return team
        
        # Fallback to first team
        if draft.teams:
            return draft.teams[0]
        
        # Create mock team
        from classes import Team
        return Team("mock_team", "mock_owner", "Mock Team", config.budget)
    
    def _get_owner_context(self, draft: Draft, team: Team) -> Owner:
        """Get or create owner context."""
        owner = draft._get_owner_by_id(team.owner_id)
        if owner:
            return owner
        
        # Create mock owner
        from classes import Owner
        return Owner(team.owner_id, "Mock Owner", is_human=True)
    
    def _generate_explanation(
        self, player: Player, recommended_bid: float, current_bid: float,
        strategy: Strategy, team: Team, owner: Owner
    ) -> str:
        """Generate explanation for bid recommendation."""
        if recommended_bid <= current_bid:
            return f"Strategy '{strategy.name}' suggests not bidding higher. Player value (${player.auction_value:.2f}) doesn't justify exceeding ${current_bid:.2f}."
        
        value_diff = player.auction_value - recommended_bid
        budget_pct = (recommended_bid / team.budget) * 100 if team.budget > 0 else 0
        
        explanation_parts = [
            f"Strategy '{strategy.name}' recommends bidding ${recommended_bid:.2f}.",
            f"Player value: ${player.auction_value:.2f} ({'+' if value_diff > 0 else ''}${value_diff:.2f} vs recommendation).",
            f"This represents {budget_pct:.1f}% of remaining budget."
        ]
        
        # Add position need context
        needs = team.get_needs()
        if player.position in needs:
            explanation_parts.append(f"Team needs {player.position} players.")
        
        return " ".join(explanation_parts)
    
    def _generate_nomination_reasoning(self, player: Player, strategy: Strategy, team: Team) -> str:
        """Generate reasoning for nomination recommendation."""
        reasons = []
        
        # Position need
        needs = team.get_needs()
        if player.position in needs:
            reasons.append(f"Team needs {player.position}")
        
        # Value assessment
        if player.auction_value > 20:
            reasons.append("High-value player")
        elif player.auction_value < 5:
            reasons.append("Low-cost option")
        
        # Strategy-specific reasoning
        if strategy.name == "Aggressive":
            reasons.append("Aggressive strategy targets elite players")
        elif strategy.name == "Conservative":
            reasons.append("Conservative strategy seeks value picks")
        else:
            reasons.append("Value-based strategy assessment")
        
        return "; ".join(reasons) if reasons else "Strategic nomination"
    
    def _generate_team_recommendations(self, team: Team, config) -> List[str]:
        """Generate recommendations for team improvement."""
        recommendations = []
        
        needs = team.get_needs()
        if needs:
            recommendations.append(f"Priority positions to fill: {', '.join(set(needs))}")
        
        budget_pct = (team.budget / team.initial_budget) if team.initial_budget > 0 else 0
        if budget_pct > 0.7:
            recommendations.append("Consider targeting premium players with remaining budget")
        elif budget_pct < 0.2:
            recommendations.append("Focus on value picks with limited budget")
        
        if not team.is_roster_complete():
            recommendations.append("Complete minimum roster requirements")
        
        return recommendations
    
    def _calculate_confidence(self, player: Player, recommended_bid: float, team: Team) -> float:
        """Calculate confidence score for recommendation."""
        factors = []
        
        # Value alignment
        value_ratio = recommended_bid / player.auction_value if player.auction_value > 0 else 0
        if 0.8 <= value_ratio <= 1.2:
            factors.append(0.3)  # Good value alignment
        elif value_ratio < 0.8:
            factors.append(0.2)  # Conservative bid
        else:
            factors.append(0.1)  # Aggressive bid
        
        # Position need
        needs = team.get_needs()
        if player.position in needs:
            factors.append(0.3)  # High need
        else:
            factors.append(0.1)  # Lower need
        
        # Budget consideration
        budget_impact = recommended_bid / team.budget if team.budget > 0 else 1
        if budget_impact < 0.2:
            factors.append(0.2)  # Low budget impact
        elif budget_impact < 0.5:
            factors.append(0.15)  # Moderate budget impact
        else:
            factors.append(0.1)  # High budget impact
        
        # Player quality
        if player.projected_points > 200:
            factors.append(0.2)  # High quality
        elif player.projected_points > 100:
            factors.append(0.15)  # Medium quality
        else:
            factors.append(0.1)  # Lower quality
        
        return min(sum(factors), 1.0)
    
    def _error_response(self, message: str) -> Dict[str, Any]:
        """Generate error response."""
        return {
            'success': False,
            'error': message,
            'recommended_bid': 0.0,
            'should_bid': False
        }
    
    async def _get_sleeper_draft_context(self, draft_id: str, player_name: str) -> Dict[str, Any]:
        """Get context from a live Sleeper draft."""
        try:
            # Get draft info
            draft_info = await self.sleeper_api.get_draft(draft_id)
            if not draft_info:
                return {'success': False, 'error': 'Draft not found'}
            
            # Get draft picks to see what's already been drafted
            picks = await self.sleeper_api.get_draft_picks(draft_id)
            drafted_player_ids = {pick.get('player_id') for pick in picks if pick.get('player_id')}
            
            # Get player data from cache
            players_data = self.get_sleeper_players()
            if not players_data:
                return {'success': False, 'error': 'Could not load player data'}
            
            # Find the target player
            target_player = None
            for player_id, player_data in players_data.items():
                if player_data.get('full_name', '').lower() == player_name.lower():
                    target_player = {**player_data, 'player_id': player_id}
                    break
            
            if not target_player:
                # Try partial match
                for player_id, player_data in players_data.items():
                    if player_name.lower() in player_data.get('full_name', '').lower():
                        target_player = {**player_data, 'player_id': player_id}
                        break
            
            if not target_player:
                return {'success': False, 'error': f"Player '{player_name}' not found in Sleeper data"}
            
            # Check if player is already drafted
            is_drafted = target_player['player_id'] in drafted_player_ids
            
            # Get user's team info if available
            user_id = getattr(self.config_manager.load_config(), 'sleeper_user_id', None)
            user_budget = self.config_manager.load_config().budget
            user_roster = []
            
            if user_id and picks:
                # Find user's picks
                user_picks = [pick for pick in picks if pick.get('picked_by') == user_id]
                user_roster = []
                total_spent = 0
                
                for pick in user_picks:
                    player_id = pick.get('player_id')
                    if player_id in players_data:
                        player_info = players_data[player_id]
                        bid_amount = pick.get('metadata', {}).get('amount', 0)
                        try:
                            bid_value = int(bid_amount)
                            total_spent += bid_value
                        except (ValueError, TypeError):
                            bid_value = 0
                        
                        user_roster.append({
                            'name': player_info.get('full_name', ''),
                            'position': player_info.get('position', ''),
                            'team': player_info.get('team', ''),
                            'bid': bid_value
                        })
                
                user_budget = max(0, user_budget - total_spent)
            
            # Get remaining available players
            available_players = []
            for player_id, player_data in players_data.items():
                if player_id not in drafted_player_ids:
                    available_players.append({
                        'name': player_data.get('full_name', ''),
                        'position': player_data.get('position', ''),
                        'team': player_data.get('team', ''),
                        'player_id': player_id
                    })
            
            return {
                'success': True,
                'draft_id': draft_id,
                'draft_info': draft_info,
                'target_player': target_player,
                'is_drafted': is_drafted,
                'user_budget': user_budget,
                'user_roster': user_roster,
                'available_players': available_players,
                'total_picks': len(picks),
                'data_source': 'sleeper'
            }
            
        except Exception as e:
            return {'success': False, 'error': f"Error getting Sleeper draft context: {e}"}
    
    def _recommend_bid_with_sleeper_context(
        self, 
        player_name: str, 
        current_bid: float, 
        strategy: Strategy, 
        sleeper_context: Dict, 
        team_context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Generate bid recommendation using live Sleeper draft context."""
        try:
            target_player = sleeper_context['target_player']
            
            # Check if player is already drafted
            if sleeper_context['is_drafted']:
                return {
                    'success': False,
                    'error': f"Player '{player_name}' has already been drafted",
                    'data_source': 'sleeper'
                }
            
            # Convert Sleeper player to auction tool format
            player = self._convert_sleeper_player_to_auction_format(target_player)
            
            # Create team context from Sleeper data
            team = self._create_team_from_sleeper_context(sleeper_context, team_context)
            
            # Create owner context
            from classes import Owner
            owner = Owner("sleeper_user", "Sleeper User", is_human=True)
            
            # Get remaining players in auction format
            remaining_players = []
            for available_player in sleeper_context['available_players']:
                remaining_players.append(self._convert_sleeper_player_to_auction_format(available_player))
            
            # Calculate bid recommendation
            recommended_bid = strategy.calculate_bid(
                player=player,
                team=team,
                owner=owner,
                current_bid=current_bid,
                remaining_budget=team.budget,
                remaining_players=remaining_players
            )
            
            # Generate explanation
            explanation = self._generate_explanation(
                player, recommended_bid, current_bid, strategy, team, owner
            )
            
            # Add Sleeper-specific context to explanation
            sleeper_explanation = f" [Live Sleeper Draft - {sleeper_context['total_picks']} picks made, ${team.budget} budget remaining]"
            
            return {
                'success': True,
                'player_name': player.name,
                'player_position': player.position,
                'player_team': player.team,
                'projected_points': player.projected_points,
                'auction_value': player.auction_value,
                'current_bid': current_bid,
                'recommended_bid': recommended_bid,
                'bid_difference': recommended_bid - current_bid,
                'should_bid': recommended_bid > current_bid,
                'strategy_used': strategy.name,
                'explanation': explanation + sleeper_explanation,
                'team_budget': team.budget,
                'team_needs': team.get_needs(),
                'confidence': self._calculate_confidence(player, recommended_bid, team),
                'data_source': 'sleeper',
                'draft_id': sleeper_context['draft_id']
            }
            
        except Exception as e:
            return self._error_response(f"Error with Sleeper draft context: {e}")
    
    def _recommend_bid_with_local_context(
        self, 
        player_name: str, 
        current_bid: float, 
        strategy: Strategy, 
        team_context: Optional[Dict], 
        config
    ) -> Dict[str, Any]:
        """Generate bid recommendation using local FantasyPros data (fallback)."""
        try:
            # Load current draft to get player and context
            draft = self.draft_service.load_current_draft()
            if not draft:
                return self._error_response("Could not load draft")
            
            # Find the player
            player = self._find_player(draft, player_name)
            if not player:
                return self._error_response(f"Player '{player_name}' not found")
            
            # Get team context
            team = self._get_team_context(draft, team_context, config)
            owner = self._get_owner_context(draft, team)
            
            # Calculate bid recommendation
            remaining_players = [p for p in draft.available_players if not p.is_drafted]
            recommended_bid = strategy.calculate_bid(
                player=player,
                team=team,
                owner=owner,
                current_bid=current_bid,
                remaining_budget=team.budget,
                remaining_players=remaining_players
            )
            
            # Generate recommendation explanation
            explanation = self._generate_explanation(
                player, recommended_bid, current_bid, strategy, team, owner
            )
            
            # Add fallback context to explanation
            fallback_explanation = " [Using FantasyPros projections - mock draft context]"
            
            return {
                'success': True,
                'player_name': player.name,
                'player_position': player.position,
                'player_team': player.team,
                'projected_points': player.projected_points,
                'auction_value': player.auction_value,
                'current_bid': current_bid,
                'recommended_bid': recommended_bid,
                'bid_difference': recommended_bid - current_bid,
                'should_bid': recommended_bid > current_bid,
                'strategy_used': strategy.name,
                'explanation': explanation + fallback_explanation,
                'team_budget': team.budget,
                'team_needs': team.get_needs(),
                'confidence': self._calculate_confidence(player, recommended_bid, team),
                'data_source': 'fantasypros'
            }
            
        except Exception as e:
            return self._error_response(f"Error with local context: {e}")
    
    def _convert_sleeper_player_to_auction_format(self, sleeper_player: Dict) -> 'Player':
        """Convert Sleeper player data to auction tool Player format."""
        from classes import Player
        
        # Extract player info
        player_id = sleeper_player.get('player_id', 'unknown')
        name = sleeper_player.get('full_name', sleeper_player.get('name', 'Unknown'))
        position = sleeper_player.get('position', 'UNK')
        team = sleeper_player.get('team', 'UNK')
        
        # Use actual projection data when available, falling back to defaults only if absent
        projected_points = float(sleeper_player.get('projected_points') or 100.0)
        auction_value = float(sleeper_player.get('auction_value') or 10.0)
        
        # Create Player object
        player = Player(
            player_id=player_id,
            name=name,
            position=position,
            team=team,
            projected_points=projected_points,
            auction_value=auction_value
        )
        
        return player
    
    def _create_team_from_sleeper_context(self, sleeper_context: Dict, team_context: Optional[Dict]) -> 'Team':
        """Create a team object from Sleeper draft context."""
        from classes import Team
        
        # Use provided team context or create from Sleeper data
        team_name = "Your Team"
        budget = sleeper_context.get('user_budget', 200)
        
        if team_context:
            team_name = team_context.get('team_name', team_name)
            budget = team_context.get('budget', budget)
        
        # Create team
        team = Team(
            team_id="sleeper_user",
            owner_id="user_id",
            team_name=team_name,
            budget=budget,
        )
        
        # Add existing roster from Sleeper
        user_roster = sleeper_context.get('user_roster', [])
        for roster_player in user_roster:
            # Convert to Player object and add to team
            from classes import Player
            player = Player(
                player_id=f"sleeper_{roster_player['name'].replace(' ', '_')}",
                name=roster_player['name'],
                position=roster_player['position'],
                team=roster_player['team'],
                projected_points=100.0,  # Default
                auction_value=roster_player['bid']
            )
            player.drafted_price = roster_player['bid']
            team.roster.append(player)
        
        return team


# Convenience functions

def recommend_bid(
    player_name: str,
    current_bid: float,
    config_dir: str = "config",
    strategy_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to recommend a bid.
    
    Args:
        player_name: Name of the player
        current_bid: Current highest bid
        config_dir: Configuration directory
        strategy_override: Override strategy
        
    Returns:
        Bid recommendation dictionary
    """
    config_manager = ConfigManager(config_dir)
    service = BidRecommendationService(config_manager)
    return service.recommend_bid(player_name, current_bid, strategy_override=strategy_override)


def recommend_nomination(
    config_dir: str = "config",
    strategy_override: Optional[str] = None,
    position_filter: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Convenience function to recommend a nomination.
    
    Args:
        config_dir: Configuration directory
        strategy_override: Override strategy
        position_filter: Filter by positions
        
    Returns:
        Nomination recommendation dictionary
    """
    config_manager = ConfigManager(config_dir)
    service = BidRecommendationService(config_manager)
    return service.recommend_nomination(strategy_override, position_filter)


# Convenience functions for easy access

def get_bid_recommendation(
    player_name: str,
    current_bid: float,
    config_dir: str = "config",
    strategy_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to get a bid recommendation.
    
    Args:
        player_name: Name of the player to bid on
        current_bid: Current bid amount
        config_dir: Configuration directory
        strategy_override: Override strategy from config
        
    Returns:
        Bid recommendation dictionary
    """
    config_manager = ConfigManager(config_dir)
    service = BidRecommendationService(config_manager)
    return service.recommend_bid(player_name, current_bid, strategy_override=strategy_override)


def get_nomination_recommendation(
    config_dir: str = "config",
    strategy_override: Optional[str] = None,
    position_filter: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Convenience function to get a nomination recommendation.
    
    Args:
        config_dir: Configuration directory
        strategy_override: Override strategy
        position_filter: Filter by positions
        
    Returns:
        Nomination recommendation dictionary
    """
    config_manager = ConfigManager(config_dir)
    service = BidRecommendationService(config_manager)
    return service.recommend_nomination(strategy_override, position_filter)
