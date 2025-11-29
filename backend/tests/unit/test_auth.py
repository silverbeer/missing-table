import pytest
from unittest.mock import Mock, patch, MagicMock
import jwt
from fastapi.security import HTTPAuthorizationCredentials
from backend.auth import AuthManager, username_to_internal_email, internal_email_to_username

@pytest.mark.unit
class TestAuthManager:
    '''Unit tests for AuthManager class'''

    @patch('backend.auth.jwt.decode')
    def test_verify_token_valid_jwt(self, mock_jwt_decode):
        '''Verify that valid JWT token is decoded correctly'''
        # Arrange
        mock_jwt_decode.return_value = {'sub': 'user123', 'role': 'admin'}
        mock_supabase = Mock()
        mock_response = Mock()
        mock_response.data = [{'id': 'user123', 'username': 'testuser', 'role': 'admin'}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        auth_manager = AuthManager(supabase_client=mock_supabase)

        # Act
        user_data = auth_manager.verify_token('valid_token')

        # Assert
        assert user_data['username'] == 'testuser'
        assert user_data['role'] == 'admin'
        mock_jwt_decode.assert_called_once()

    @patch('backend.auth.jwt.decode', side_effect=jwt.ExpiredSignatureError)
    def test_verify_token_expired(self, mock_jwt_decode):
        '''Verify that expired token returns None (not raises exception)'''
        # Arrange
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.verify_token('expired_token')

        # Assert
        assert result is None

    @patch('backend.auth.jwt.decode', side_effect=jwt.InvalidTokenError)
    def test_verify_token_invalid(self, mock_jwt_decode):
        '''Verify that invalid token returns None'''
        # Arrange
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.verify_token('invalid_token')

        # Assert
        assert result is None

    @patch('backend.auth.jwt.decode')
    def test_verify_token_missing_user(self, mock_jwt_decode):
        '''Verify that token with non-existent user returns None'''
        # Arrange
        mock_jwt_decode.return_value = {'sub': 'nonexistent_user', 'role': 'admin'}
        mock_supabase = Mock()
        mock_response = Mock()
        mock_response.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        auth_manager = AuthManager(supabase_client=mock_supabase)

        # Act
        result = auth_manager.verify_token('missing_user_token')

        # Assert
        assert result is None

    @patch('backend.auth.jwt.decode')
    def test_verify_token_database_error(self, mock_jwt_decode):
        '''Verify that database error during user lookup returns None'''
        # Arrange
        mock_jwt_decode.return_value = {'sub': 'user123', 'role': 'admin'}
        mock_supabase = Mock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception('Database error')
        auth_manager = AuthManager(supabase_client=mock_supabase)

        # Act
        result = auth_manager.verify_token('database_error_token')

        # Assert
        assert result is None

    @patch('backend.auth.AuthManager.verify_token')
    def test_get_current_user_valid_token(self, mock_verify_token):
        '''Verify that valid token returns correct user data'''
        # Arrange
        mock_verify_token.return_value = {'sub': 'user123', 'username': 'testuser', 'role': 'user'}
        mock_supabase = Mock()
        auth_manager = AuthManager(supabase_client=mock_supabase)
        mock_credentials = Mock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = 'valid_token'

        # Act
        user_data = auth_manager.get_current_user(mock_credentials)

        # Assert
        assert user_data['username'] == 'testuser'
        assert user_data['role'] == 'user'
        mock_verify_token.assert_called_once_with('valid_token')

    def test_get_current_user_no_token(self):
        '''Verify that no token raises HTTPException'''
        # Arrange
        auth_manager = AuthManager(supabase_client=Mock())

        # Act & Assert
        with pytest.raises(Exception):  # HTTPException from FastAPI
            auth_manager.get_current_user(None)

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_can_manage_team_admin(self, mock_get_team_club_id):
        '''Verify that admin can manage any team'''
        # Arrange
        user_data = {'role': 'admin', 'team_id': 1}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_manage_team(user_data, team_id=999)

        # Assert
        assert result is True

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_can_manage_team_team_manager(self, mock_get_team_club_id):
        '''Verify that team manager can manage their own team'''
        # Arrange
        user_data = {'role': 'team-manager', 'team_id': 5}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_manage_team(user_data, team_id=5)

        # Assert
        assert result is True

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_can_manage_team_team_manager_different_team(self, mock_get_team_club_id):
        '''Verify that team manager cannot manage different team'''
        # Arrange
        user_data = {'role': 'team-manager', 'team_id': 5}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_manage_team(user_data, team_id=99)

        # Assert
        assert result is False

    @patch('backend.auth.AuthManager._get_team_club_id', return_value=10)
    def test_can_manage_team_club_manager(self, mock_get_team_club_id):
        '''Verify that club manager can manage teams in their club'''
        # Arrange
        user_data = {'role': 'club_manager', 'club_id': 10}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_manage_team(user_data, team_id=5)

        # Assert
        assert result is True
        mock_get_team_club_id.assert_called_once_with(5)

    def test_create_service_account_token(self):
        '''Verify that service account token is created correctly'''
        # Arrange
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        token = auth_manager.create_service_account_token(
            service_name='test_service',
            permissions=['manage_matches', 'read_data'],
            expires_days=30
        )

        # Assert
        assert token is not None
        assert isinstance(token, str)
        # Verify token can be decoded
        decoded = jwt.decode(
            token,
            auth_manager.service_account_secret,
            algorithms=['HS256'],
            audience='service-account'
        )
        assert decoded['service_name'] == 'test_service'
        assert decoded['permissions'] == ['manage_matches', 'read_data']
        assert decoded['role'] == 'service_account'

    @patch('backend.auth.jwt.decode')
    def test_verify_service_account_token_valid(self, mock_jwt_decode):
        '''Verify that valid service account token is decoded correctly'''
        # Arrange
        mock_jwt_decode.return_value = {
            'sub': 'service_account',
            'role': 'service_account',
            'service_name': 'test_service',
            'permissions': ['manage_matches']
        }
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.verify_service_account_token('valid_service_token')

        # Assert
        assert result is not None
        assert result['role'] == 'service_account'
        assert result['service_name'] == 'test_service'

    @patch('backend.auth.jwt.decode', side_effect=jwt.InvalidTokenError)
    def test_verify_service_account_token_invalid(self, mock_jwt_decode):
        '''Verify that invalid service account token returns None'''
        # Arrange
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.verify_service_account_token('invalid_service_token')

        # Assert
        assert result is None

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_can_edit_match_authorized_user(self, mock_get_team_club_id):
        '''Verify that authorized user can edit match'''
        # Arrange
        user_data = {'sub': 'user123', 'role': 'admin', 'team_id': 1}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_edit_match(user_data, home_team_id=1, away_team_id=2)

        # Assert
        assert result is True

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_can_edit_match_unauthorized_user(self, mock_get_team_club_id):
        '''Verify that unauthorized user cannot edit match'''
        # Arrange
        user_data = {'sub': 'user123', 'role': 'team-fan', 'team_id': 99}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_edit_match(user_data, home_team_id=1, away_team_id=2)

        # Assert
        assert result is False


@pytest.mark.unit
class TestAuthHelperFunctions:
    '''Unit tests for authentication helper functions'''

    def test_username_to_internal_email(self):
        '''Verify username is converted to internal email format'''
        # Act
        result = username_to_internal_email('gabe_ifa_35')

        # Assert
        assert result == 'gabe_ifa_35@missingtable.local'

    def test_username_to_internal_email_lowercase(self):
        '''Verify username is lowercased in internal email'''
        # Act
        result = username_to_internal_email('GABE_IFA_35')

        # Assert
        assert result == 'gabe_ifa_35@missingtable.local'

    def test_internal_email_to_username(self):
        '''Verify username is extracted from internal email'''
        # Act
        result = internal_email_to_username('gabe_ifa_35@missingtable.local')

        # Assert
        assert result == 'gabe_ifa_35'

    def test_internal_email_to_username_regular_email(self):
        '''Verify regular email returns None'''
        # Act
        result = internal_email_to_username('user@example.com')

        # Assert
        assert result is None

    def test_internal_email_to_username_empty(self):
        '''Verify empty string returns None'''
        # Act
        result = internal_email_to_username('')

        # Assert
        assert result is None
