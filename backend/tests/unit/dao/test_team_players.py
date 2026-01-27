"""
Unit tests for get_team_players DAO method.

Tests the player_team_history-based player retrieval for team rosters.
"""
from unittest.mock import Mock, patch

import pytest


def create_mock_dao(mock_client):
    """Create a PlayerDAO with mocked SupabaseConnection."""
    from backend.dao.match_dao import SupabaseConnection
    from backend.dao.player_dao import PlayerDAO

    # Create mock SupabaseConnection
    mock_connection = Mock(spec=SupabaseConnection)
    mock_connection.get_client.return_value = mock_client

    # Patch the isinstance check to allow our mock
    with patch.object(PlayerDAO, '__init__', lambda self, conn: None):
        dao = PlayerDAO(mock_connection)
        dao.connection_holder = mock_connection
        dao.client = mock_client

    return dao


@pytest.mark.unit
class TestGetTeamPlayers:
    """Tests for get_team_players method using player_team_history."""

    def test_returns_players_from_history_table(self):
        """Verify players are fetched from player_team_history, not user_profiles.team_id."""
        # Arrange
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            {
                'player_id': 'user-123',
                'jersey_number': 35,
                'positions': ['FWD', 'MID'],
                'user_profiles': {
                    'id': 'user-123',
                    'display_name': 'Gabe',
                    'player_number': 10,  # Different from history
                    'positions': ['GK'],  # Different from history
                    'photo_1_url': 'http://example.com/photo.jpg',
                    'photo_2_url': None,
                    'photo_3_url': None,
                    'profile_photo_slot': 1,
                    'overlay_style': 'badge',
                    'primary_color': '#3B82F6',
                    'text_color': '#FFFFFF',
                    'accent_color': '#1D4ED8',
                    'instagram_handle': 'gabe35',
                    'snapchat_handle': None,
                    'tiktok_handle': None,
                }
            }
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        dao = create_mock_dao(mock_client)

        # Act
        players = dao.get_team_players(team_id=1)

        # Assert
        assert len(players) == 1
        assert players[0]['id'] == 'user-123'
        assert players[0]['display_name'] == 'Gabe'
        # Should use jersey_number from history, not player_number from profile
        assert players[0]['player_number'] == 35
        # Should use positions from history
        assert players[0]['positions'] == ['FWD', 'MID']

    def test_falls_back_to_profile_when_history_values_missing(self):
        """Verify fallback to profile values when history doesn't have them."""
        # Arrange
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            {
                'player_id': 'user-456',
                'jersey_number': None,  # Not set in history
                'positions': None,  # Not set in history
                'user_profiles': {
                    'id': 'user-456',
                    'display_name': 'Alex',
                    'player_number': 7,
                    'positions': ['DEF'],
                    'photo_1_url': None,
                    'photo_2_url': None,
                    'photo_3_url': None,
                    'profile_photo_slot': None,
                    'overlay_style': 'jersey',
                    'primary_color': '#FF0000',
                    'text_color': '#FFFFFF',
                    'accent_color': '#000000',
                    'instagram_handle': None,
                    'snapchat_handle': None,
                    'tiktok_handle': None,
                }
            }
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        dao = create_mock_dao(mock_client)

        # Act
        players = dao.get_team_players(team_id=1)

        # Assert
        assert len(players) == 1
        # Should fall back to profile values
        assert players[0]['player_number'] == 7
        assert players[0]['positions'] == ['DEF']

    def test_filters_by_is_current_true(self):
        """Verify only current team members are returned."""
        # Arrange
        mock_client = Mock()
        mock_select = Mock()
        mock_eq_team = Mock()
        mock_eq_current = Mock()

        mock_client.table.return_value.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq_team
        mock_eq_team.eq.return_value = mock_eq_current
        mock_eq_current.execute.return_value = Mock(data=[])

        dao = create_mock_dao(mock_client)

        # Act
        dao.get_team_players(team_id=5)

        # Assert - verify both filters are applied
        mock_client.table.assert_called_once_with('player_team_history')
        mock_select.eq.assert_called_once_with('team_id', 5)
        mock_eq_team.eq.assert_called_once_with('is_current', True)

    def test_returns_empty_list_on_error(self):
        """Verify empty list returned on database error."""
        # Arrange
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.side_effect = Exception("DB error")

        dao = create_mock_dao(mock_client)

        # Act
        players = dao.get_team_players(team_id=1)

        # Assert
        assert players == []

    def test_sorts_by_player_number(self):
        """Verify players are sorted by player_number."""
        # Arrange
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            {
                'player_id': 'user-1',
                'jersey_number': 99,
                'positions': None,
                'user_profiles': {
                    'id': 'user-1',
                    'display_name': 'Player 99',
                    'player_number': None,
                    'positions': None,
                    'photo_1_url': None,
                    'photo_2_url': None,
                    'photo_3_url': None,
                    'profile_photo_slot': None,
                    'overlay_style': 'badge',
                    'primary_color': '#000',
                    'text_color': '#FFF',
                    'accent_color': '#000',
                    'instagram_handle': None,
                    'snapchat_handle': None,
                    'tiktok_handle': None,
                }
            },
            {
                'player_id': 'user-2',
                'jersey_number': 1,
                'positions': None,
                'user_profiles': {
                    'id': 'user-2',
                    'display_name': 'Player 1',
                    'player_number': None,
                    'positions': None,
                    'photo_1_url': None,
                    'photo_2_url': None,
                    'photo_3_url': None,
                    'profile_photo_slot': None,
                    'overlay_style': 'badge',
                    'primary_color': '#000',
                    'text_color': '#FFF',
                    'accent_color': '#000',
                    'instagram_handle': None,
                    'snapchat_handle': None,
                    'tiktok_handle': None,
                }
            },
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        dao = create_mock_dao(mock_client)

        # Act
        players = dao.get_team_players(team_id=1)

        # Assert - should be sorted by player_number ascending
        assert players[0]['player_number'] == 1
        assert players[1]['player_number'] == 99

    def test_handles_missing_user_profile(self):
        """Verify players without profile data are skipped."""
        # Arrange
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            {
                'player_id': 'user-orphan',
                'jersey_number': 10,
                'positions': ['MID'],
                'user_profiles': None  # No profile data
            },
            {
                'player_id': 'user-valid',
                'jersey_number': 7,
                'positions': ['FWD'],
                'user_profiles': {
                    'id': 'user-valid',
                    'display_name': 'Valid Player',
                    'player_number': None,
                    'positions': None,
                    'photo_1_url': None,
                    'photo_2_url': None,
                    'photo_3_url': None,
                    'profile_photo_slot': None,
                    'overlay_style': 'badge',
                    'primary_color': '#000',
                    'text_color': '#FFF',
                    'accent_color': '#000',
                    'instagram_handle': None,
                    'snapchat_handle': None,
                    'tiktok_handle': None,
                }
            }
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        dao = create_mock_dao(mock_client)

        # Act
        players = dao.get_team_players(team_id=1)

        # Assert - only valid player returned
        assert len(players) == 1
        assert players[0]['id'] == 'user-valid'
