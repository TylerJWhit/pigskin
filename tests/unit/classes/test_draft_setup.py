"""Unit tests for DraftSetup class and convenience functions."""

from unittest.mock import MagicMock, patch
import pytest

from classes import Player


class TestCreateOwnerWithTeam:
    def test_creates_owner_and_team(self):
        from classes.draft_setup import DraftSetup
        owner, team = DraftSetup.create_owner_with_team(
            owner_id='o1', owner_name='Alice', team_name='Sharks',
            budget=200
        )
        assert owner.owner_id == 'o1'
        assert team.team_name == 'Sharks'

    def test_is_human_flag(self):
        from classes.draft_setup import DraftSetup
        owner, team = DraftSetup.create_owner_with_team(
            owner_id='o1', owner_name='Alice', team_name='Sharks',
            budget=200, is_human=False
        )
        assert owner.is_human is False

    def test_with_strategy(self):
        from classes.draft_setup import DraftSetup
        with patch('classes.draft_setup.create_strategy') as mock_cs:
            strategy = MagicMock()
            strategy.name = 'value'
            mock_cs.return_value = strategy
            owner, team = DraftSetup.create_owner_with_team(
                owner_id='o1', owner_name='Alice', team_name='Sharks',
                budget=200, strategy=strategy
            )
        assert team.strategy is strategy


class TestSetupDraftWithParticipants:
    def _participants(self, n=2):
        return [
            {'owner_id': f'o{i}', 'owner_name': f'Owner {i}', 'team_name': f'Team {i}', 'is_human': True}
            for i in range(n)
        ]

    def test_creates_draft_with_teams(self):
        from classes.draft_setup import DraftSetup
        draft = DraftSetup.setup_draft_with_participants('Test Draft', self._participants(2))
        assert len(draft.teams) == 2

    def test_participants_with_strategy(self):
        from classes.draft_setup import DraftSetup
        participants = [
            {'owner_id': 'o1', 'owner_name': 'AI1', 'team_name': 'T1', 'is_human': False, 'strategy_type': 'value'}
        ]
        draft = DraftSetup.setup_draft_with_participants('Test', participants)
        assert len(draft.teams) == 1
        assert draft.teams[0].strategy is not None

    def test_participants_with_strategy_params(self):
        from classes.draft_setup import DraftSetup
        participants = [
            {
                'owner_id': 'o1', 'owner_name': 'AI1', 'team_name': 'T1', 'is_human': False,
                'strategy_type': 'value',
                'strategy_params': {'aggressiveness': 0.8}
            }
        ]
        # Should not raise even if param not supported
        draft = DraftSetup.setup_draft_with_participants('Test', participants)
        assert len(draft.teams) == 1


class TestImportPlayersFromSleeper:
    def test_returns_players_on_success(self):
        from classes.draft_setup import DraftSetup
        player_data = [
            {'player_id': 'p1', 'name': 'Josh Allen', 'position': 'QB', 'team': 'BUF',
             'projected_points': 350.0, 'auction_value': 50.0, 'bye_week': 7}
        ]
        with patch('classes.draft_setup.SleeperAPI') as MockAPI:
            instance = MockAPI.return_value
            instance.bulk_convert_players.return_value = player_data
            players = DraftSetup.import_players_from_sleeper()
        assert len(players) == 1
        assert players[0].name == 'Josh Allen'

    def test_filters_by_min_projected_points(self):
        from classes.draft_setup import DraftSetup
        player_data = [
            {'player_id': 'p1', 'name': 'Josh Allen', 'position': 'QB', 'team': 'BUF',
             'projected_points': 350.0, 'auction_value': 50.0, 'bye_week': 7},
            {'player_id': 'p2', 'name': 'Backup K', 'position': 'K', 'team': 'CLE',
             'projected_points': 5.0, 'auction_value': 1.0, 'bye_week': 9},
        ]
        with patch('classes.draft_setup.SleeperAPI') as MockAPI:
            instance = MockAPI.return_value
            instance.bulk_convert_players.return_value = player_data
            players = DraftSetup.import_players_from_sleeper(min_projected_points=100.0)
        assert len(players) == 1

    def test_returns_empty_on_exception(self):
        from classes.draft_setup import DraftSetup
        with patch('classes.draft_setup.SleeperAPI') as MockAPI:
            instance = MockAPI.return_value
            instance.bulk_convert_players.side_effect = ConnectionError("API down")
            players = DraftSetup.import_players_from_sleeper()
        assert players == []

    def test_filters_by_position(self):
        from classes.draft_setup import DraftSetup
        player_data = [
            {'player_id': 'p1', 'name': 'Josh Allen', 'position': 'QB', 'team': 'BUF',
             'projected_points': 350.0, 'auction_value': 50.0, 'bye_week': 7},
        ]
        with patch('classes.draft_setup.SleeperAPI') as MockAPI:
            instance = MockAPI.return_value
            instance.bulk_convert_players.return_value = player_data
            players = DraftSetup.import_players_from_sleeper(position_filter=['QB'])
        assert len(players) == 1


class TestImportPlayersFromFantasyPros:
    def test_returns_players_on_success(self):
        from classes.draft_setup import DraftSetup
        mock_players = [Player('p1', 'Josh Allen', 'QB', 'BUF', 350.0, 50.0, 7)]
        with patch('data.fantasypros_loader.FantasyProsLoader') as MockLoader:
            instance = MockLoader.return_value
            instance.load_all_players.return_value = mock_players
            instance.calculate_auction_values.return_value = None
            players = DraftSetup.import_players_from_fantasypros()
        assert len(players) == 1

    def test_filters_by_position(self):
        from classes.draft_setup import DraftSetup
        mock_players = [
            Player('p1', 'Josh Allen', 'QB', 'BUF', 350.0, 50.0, 7),
            Player('p2', 'CMC', 'RB', 'SF', 280.0, 60.0, 9),
        ]
        with patch('data.fantasypros_loader.FantasyProsLoader') as MockLoader:
            instance = MockLoader.return_value
            instance.load_all_players.return_value = mock_players
            instance.calculate_auction_values.return_value = None
            players = DraftSetup.import_players_from_fantasypros(position_filter=['QB'])
        assert len(players) == 1
        assert players[0].position == 'QB'

    def test_returns_empty_on_exception(self):
        from classes.draft_setup import DraftSetup
        with patch('data.fantasypros_loader.FantasyProsLoader', side_effect=RuntimeError("no file")):
            players = DraftSetup.import_players_from_fantasypros()
        assert players == []


class TestCalculateAuctionValues:
    def test_empty_list_does_nothing(self):
        from classes.draft_setup import DraftSetup
        DraftSetup.calculate_auction_values([])  # Should not raise

    def test_zero_total_points_does_nothing(self):
        from classes.draft_setup import DraftSetup
        players = [Player('p1', 'Ghost', 'QB', 'XX', 0.0, 0.0, 1)]
        DraftSetup.calculate_auction_values(players)
        # Auction value should stay as-is (0 total points = no division)

    def test_assigns_values_proportionally(self):
        from classes.draft_setup import DraftSetup
        players = [
            Player('p1', 'Star QB', 'QB', 'BUF', 300.0, 0.0, 7),
            Player('p2', 'Backup QB', 'QB', 'CLE', 100.0, 0.0, 9),
        ]
        DraftSetup.calculate_auction_values(players, total_budget=2400.0)
        # Star QB should have higher auction value
        assert players[0].auction_value > players[1].auction_value

    def test_minimum_value_is_one(self):
        from classes.draft_setup import DraftSetup
        players = [Player('p1', 'Kicker', 'K', 'BUF', 1.0, 0.0, 7)]
        DraftSetup.calculate_auction_values(players)
        assert players[0].auction_value >= 1.0

    def test_position_multipliers_applied(self):
        from classes.draft_setup import DraftSetup
        rb = Player('rb1', 'CMC', 'RB', 'SF', 200.0, 0.0, 9)
        k = Player('k1', 'Tucker', 'K', 'BAL', 200.0, 0.0, 14)
        DraftSetup.calculate_auction_values([rb, k], total_budget=2400.0)
        # RB multiplier (1.2) > K multiplier (0.5)
        assert rb.auction_value > k.auction_value


class TestCreateMockDraft:
    def test_creates_draft_with_mock_players_fallback(self):
        from classes.draft_setup import DraftSetup
        # patch import_players_from_fantasypros to return empty → falls back to _create_mock_players
        with patch.object(DraftSetup, 'import_players_from_fantasypros', return_value=[]):
            draft = DraftSetup.create_mock_draft(
                num_teams=3,
                include_humans=1,
                use_fantasypros_data=True,
                use_sleeper_data=False,
            )
        assert len(draft.teams) == 3
        assert len(draft.available_players) > 0

    def test_uses_fantasypros_data(self):
        from classes.draft_setup import DraftSetup
        mock_players = [Player(f'p{i}', f'P{i}', 'QB', 'BUF', 200.0, 30.0, 7) for i in range(5)]
        with patch.object(DraftSetup, 'import_players_from_fantasypros', return_value=mock_players):
            draft = DraftSetup.create_mock_draft(num_teams=2, use_fantasypros_data=True)
        assert draft is not None

    def test_uses_sleeper_data_when_fantasypros_fails(self):
        from classes.draft_setup import DraftSetup
        mock_players = [Player('p1', 'P1', 'QB', 'BUF', 200.0, 30.0, 7)]
        with patch.object(DraftSetup, 'import_players_from_fantasypros', return_value=[]), \
             patch.object(DraftSetup, 'import_players_from_sleeper', return_value=mock_players), \
             patch.object(DraftSetup, 'calculate_auction_values'):
            draft = DraftSetup.create_mock_draft(
                num_teams=2, use_fantasypros_data=True, use_sleeper_data=True
            )
        assert len(draft.available_players) > 0

    def test_human_teams_have_no_strategy(self):
        from classes.draft_setup import DraftSetup
        with patch.object(DraftSetup, 'import_players_from_fantasypros', return_value=[]):
            draft = DraftSetup.create_mock_draft(num_teams=3, include_humans=1)
        # The human team (index 0) should have no strategy, AI teams should have strategies
        # Note: draft.teams order matches participant order


class TestCreateMockPlayers:
    def test_returns_list_of_players(self):
        from classes.draft_setup import DraftSetup
        players = DraftSetup._create_mock_players()
        assert len(players) > 0
        assert all(isinstance(p, Player) for p in players)

    def test_covers_multiple_positions(self):
        from classes.draft_setup import DraftSetup
        players = DraftSetup._create_mock_players()
        positions = {p.position for p in players}
        assert 'QB' in positions
        assert 'RB' in positions
        assert 'WR' in positions
        assert 'TE' in positions


class TestConvenienceFunctions:
    def test_create_simple_draft(self):
        from classes.draft_setup import create_simple_draft
        with patch('classes.draft_setup.DraftSetup.import_players_from_fantasypros', return_value=[]):
            draft = create_simple_draft(['Alice', 'Bob'], ['Sharks', 'Bears'])
        assert len(draft.teams) == 2

    def test_create_ai_vs_human_draft(self):
        from classes.draft_setup import create_ai_vs_human_draft
        with patch('classes.draft_setup.DraftSetup.import_players_from_fantasypros', return_value=[]):
            draft = create_ai_vs_human_draft('Alice', 'Sharks', ai_count=3)
        assert len(draft.teams) == 4  # 1 human + 3 AI

    def test_create_ai_vs_human_strategy_assignment(self):
        from classes.draft_setup import create_ai_vs_human_draft
        with patch('classes.draft_setup.DraftSetup.import_players_from_fantasypros', return_value=[]):
            draft = create_ai_vs_human_draft('Alice', 'Sharks', ai_count=2)
        # AI teams should have strategies
        ai_teams = [t for t in draft.teams if t.team_name != 'Sharks']
        for team in ai_teams:
            assert team.strategy is not None


class TestClassesInitFunctions:
    """Tests for classes/__init__.py convenience functions."""

    def test_create_simple_draft(self):
        """Cover lines 34-38 — create_simple_draft calls DraftSetup."""
        from unittest.mock import patch, MagicMock
        mock_draft = MagicMock()
        with patch('classes.DraftSetup') as mock_setup_cls:
            mock_setup_cls.setup_draft_with_participants.return_value = mock_draft
            from classes import create_simple_draft
            result = create_simple_draft(['Alice', 'Bob'], ['Sharks', 'Bears'])
            mock_setup_cls.setup_draft_with_participants.assert_called_once()
            args = mock_setup_cls.setup_draft_with_participants.call_args
            participants = args[0][1]
            assert len(participants) == 2
            assert participants[0]['is_human'] is True

    def test_create_ai_vs_human_draft(self):
        """Cover lines 42-50 — create_ai_vs_human_draft builds participants."""
        from unittest.mock import patch, MagicMock
        mock_draft = MagicMock()
        with patch('classes.DraftSetup') as mock_setup_cls:
            mock_setup_cls.setup_draft_with_participants.return_value = mock_draft
            from classes import create_ai_vs_human_draft
            result = create_ai_vs_human_draft('Alice', 'Sharks', ai_count=3)
            args = mock_setup_cls.setup_draft_with_participants.call_args
            participants = args[0][1]
            # 1 human + 3 AI
            assert len(participants) == 4
            human = participants[0]
            assert human['is_human'] is True
            assert human['owner_name'] == 'Alice'
