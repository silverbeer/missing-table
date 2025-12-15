import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from backend.auth import (
    AuthManager,
    username_to_internal_email,
    internal_email_to_username,
    is_internal_email,
    check_username_available,
)

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

    def test_is_internal_email_true(self):
        '''Verify internal email is detected'''
        # Act
        result = is_internal_email('user@missingtable.local')

        # Assert
        assert result is True

    def test_is_internal_email_false(self):
        '''Verify regular email returns False'''
        # Act
        result = is_internal_email('user@example.com')

        # Assert
        assert result is False


@pytest.mark.unit
class TestCheckUsernameAvailable:
    '''Unit tests for check_username_available function'''

    @pytest.mark.asyncio
    async def test_username_available(self):
        '''Verify available username returns True'''
        # Arrange
        mock_supabase = Mock()
        mock_response = Mock()
        mock_response.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        # Act
        result = await check_username_available(mock_supabase, 'newuser')

        # Assert
        assert result is True
        mock_supabase.table.assert_called_with('user_profiles')

    @pytest.mark.asyncio
    async def test_username_taken(self):
        '''Verify taken username returns False'''
        # Arrange
        mock_supabase = Mock()
        mock_response = Mock()
        mock_response.data = [{'id': 'existing-user-id'}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        # Act
        result = await check_username_available(mock_supabase, 'existinguser')

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_username_check_lowercased(self):
        '''Verify username is lowercased before checking'''
        # Arrange
        mock_supabase = Mock()
        mock_response = Mock()
        mock_response.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        # Act
        await check_username_available(mock_supabase, 'UPPERCASE')

        # Assert
        mock_supabase.table.return_value.select.return_value.eq.assert_called_with('username', 'uppercase')

    @pytest.mark.asyncio
    async def test_username_check_database_error(self):
        '''Verify database error is raised'''
        # Arrange
        mock_supabase = Mock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception('DB error')

        # Act & Assert
        with pytest.raises(Exception, match='DB error'):
            await check_username_available(mock_supabase, 'testuser')


@pytest.mark.unit
class TestAuthManagerInit:
    '''Unit tests for AuthManager initialization'''

    def test_init_missing_jwt_secret(self):
        '''Verify error when JWT secret is missing'''
        # Arrange
        with patch.dict('os.environ', {}, clear=True):
            with patch('backend.auth.os.getenv', return_value=None):
                # Act & Assert
                with pytest.raises(ValueError, match='SUPABASE_JWT_SECRET environment variable is required'):
                    AuthManager(supabase_client=Mock())


@pytest.mark.unit
class TestVerifyTokenEdgeCases:
    '''Additional edge case tests for verify_token'''

    @patch('backend.auth.jwt.decode')
    def test_verify_token_no_sub_in_payload(self, mock_jwt_decode):
        '''Verify token without sub claim returns None'''
        # Arrange
        mock_jwt_decode.return_value = {'email': 'user@example.com'}  # No 'sub'
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.verify_token('token_without_sub')

        # Assert
        assert result is None

    @patch('backend.auth.jwt.decode')
    def test_verify_token_multiple_profiles_uses_first(self, mock_jwt_decode):
        '''Verify that multiple profiles logs warning and uses first'''
        # Arrange
        mock_jwt_decode.return_value = {'sub': 'user123', 'email': 'user@missingtable.local'}
        mock_supabase = Mock()
        mock_response = Mock()
        mock_response.data = [
            {'id': 'user123', 'username': 'firstuser', 'role': 'admin'},
            {'id': 'user123', 'username': 'seconduser', 'role': 'user'}
        ]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        auth_manager = AuthManager(supabase_client=mock_supabase)

        # Act
        result = auth_manager.verify_token('multi_profile_token')

        # Assert
        assert result['username'] == 'firstuser'
        assert result['role'] == 'admin'

    @patch('backend.auth.jwt.decode')
    def test_verify_token_internal_email_extracts_username(self, mock_jwt_decode):
        '''Verify internal email format extracts username correctly'''
        # Arrange
        mock_jwt_decode.return_value = {'sub': 'user123', 'email': 'testuser@missingtable.local'}
        mock_supabase = Mock()
        mock_response = Mock()
        mock_response.data = [{'id': 'user123', 'username': None, 'role': 'user', 'email': 'real@email.com'}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        auth_manager = AuthManager(supabase_client=mock_supabase)

        # Act
        result = auth_manager.verify_token('internal_email_token')

        # Assert
        assert result['username'] == 'testuser'
        assert result['email'] == 'real@email.com'

    @patch('backend.auth.jwt.decode')
    def test_verify_token_legacy_user_with_real_email(self, mock_jwt_decode):
        '''Verify legacy user with real email in JWT'''
        # Arrange
        mock_jwt_decode.return_value = {'sub': 'user123', 'email': 'legacy@example.com'}
        mock_supabase = Mock()
        mock_response = Mock()
        mock_response.data = [{'id': 'user123', 'username': 'legacyuser', 'role': 'user'}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        auth_manager = AuthManager(supabase_client=mock_supabase)

        # Act
        result = auth_manager.verify_token('legacy_token')

        # Assert
        assert result['username'] == 'legacyuser'
        assert result['email'] == 'legacy@example.com'


@pytest.mark.unit
class TestVerifyServiceAccountTokenEdgeCases:
    '''Additional edge case tests for verify_service_account_token'''

    @patch('backend.auth.jwt.decode')
    def test_verify_service_account_no_service_name(self, mock_jwt_decode):
        '''Verify token without service_name returns None'''
        # Arrange
        mock_jwt_decode.return_value = {'sub': 'service-test', 'permissions': ['read']}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.verify_service_account_token('no_service_name_token')

        # Assert
        assert result is None

    @patch('backend.auth.jwt.decode', side_effect=jwt.ExpiredSignatureError)
    def test_verify_service_account_expired(self, mock_jwt_decode):
        '''Verify expired service account token returns None'''
        # Arrange
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.verify_service_account_token('expired_service_token')

        # Assert
        assert result is None

    @patch('backend.auth.jwt.decode', side_effect=Exception('Unexpected error'))
    def test_verify_service_account_general_exception(self, mock_jwt_decode):
        '''Verify general exception returns None'''
        # Arrange
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.verify_service_account_token('error_token')

        # Assert
        assert result is None


@pytest.mark.unit
class TestGetCurrentUserServiceAccount:
    '''Tests for get_current_user with service accounts'''

    @patch('backend.auth.AuthManager.verify_token', return_value=None)
    @patch('backend.auth.AuthManager.verify_service_account_token')
    def test_falls_back_to_service_account(self, mock_verify_service, mock_verify_token):
        '''Verify fallback to service account when user token fails'''
        # Arrange
        mock_verify_service.return_value = {
            'service_id': 'service-scraper',
            'service_name': 'scraper',
            'permissions': ['manage_matches'],
            'role': 'service_account',
            'is_service_account': True
        }
        auth_manager = AuthManager(supabase_client=Mock())
        mock_credentials = Mock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = 'service_account_token'

        # Act
        result = auth_manager.get_current_user(mock_credentials)

        # Assert
        assert result['is_service_account'] is True
        assert result['service_name'] == 'scraper'

    @patch('backend.auth.AuthManager.verify_token', return_value=None)
    @patch('backend.auth.AuthManager.verify_service_account_token', return_value=None)
    def test_raises_when_both_fail(self, mock_verify_service, mock_verify_token):
        '''Verify HTTPException when both token types fail'''
        # Arrange
        auth_manager = AuthManager(supabase_client=Mock())
        mock_credentials = Mock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = 'invalid_token'

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            auth_manager.get_current_user(mock_credentials)
        assert exc_info.value.status_code == 401


@pytest.mark.unit
class TestCanEditMatchExtended:
    '''Extended tests for can_edit_match'''

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_service_account_with_permission(self, mock_get_club):
        '''Verify service account with manage_matches can edit'''
        # Arrange
        user_data = {
            'role': 'service_account',
            'permissions': ['manage_matches']
        }
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_edit_match(user_data, home_team_id=1, away_team_id=2)

        # Assert
        assert result is True

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_service_account_without_permission(self, mock_get_club):
        '''Verify service account without permission cannot edit'''
        # Arrange
        user_data = {
            'role': 'service_account',
            'permissions': ['read_only']
        }
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_edit_match(user_data, home_team_id=1, away_team_id=2)

        # Assert
        assert result is False

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_team_manager_own_team_home(self, mock_get_club):
        '''Verify team manager can edit when their team is home'''
        # Arrange
        user_data = {'role': 'team-manager', 'team_id': 5}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_edit_match(user_data, home_team_id=5, away_team_id=10)

        # Assert
        assert result is True

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_team_manager_own_team_away(self, mock_get_club):
        '''Verify team manager can edit when their team is away'''
        # Arrange
        user_data = {'role': 'team-manager', 'team_id': 5}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_edit_match(user_data, home_team_id=10, away_team_id=5)

        # Assert
        assert result is True

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_club_manager_home_team_in_club(self, mock_get_club):
        '''Verify club manager can edit when home team is in their club'''
        # Arrange
        mock_get_club.side_effect = lambda team_id: 100 if team_id == 1 else 200
        user_data = {'role': 'club_manager', 'club_id': 100}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_edit_match(user_data, home_team_id=1, away_team_id=2)

        # Assert
        assert result is True

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_club_manager_away_team_in_club(self, mock_get_club):
        '''Verify club manager can edit when away team is in their club'''
        # Arrange
        mock_get_club.side_effect = lambda team_id: 200 if team_id == 1 else 100
        user_data = {'role': 'club_manager', 'club_id': 100}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_edit_match(user_data, home_team_id=1, away_team_id=2)

        # Assert
        assert result is True

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_club_manager_neither_team_in_club(self, mock_get_club):
        '''Verify club manager cannot edit when neither team is in their club'''
        # Arrange
        mock_get_club.return_value = 200  # Both teams in different club
        user_data = {'role': 'club_manager', 'club_id': 100}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_edit_match(user_data, home_team_id=1, away_team_id=2)

        # Assert
        assert result is False


@pytest.mark.unit
class TestGetTeamClubId:
    '''Tests for _get_team_club_id helper method'''

    def test_returns_club_id(self):
        '''Verify club_id is returned for valid team'''
        # Arrange
        mock_supabase = Mock()
        mock_response = Mock()
        mock_response.data = [{'club_id': 42}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        auth_manager = AuthManager(supabase_client=mock_supabase)

        # Act
        result = auth_manager._get_team_club_id(team_id=5)

        # Assert
        assert result == 42

    def test_returns_none_for_nonexistent_team(self):
        '''Verify None is returned when team not found'''
        # Arrange
        mock_supabase = Mock()
        mock_response = Mock()
        mock_response.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        auth_manager = AuthManager(supabase_client=mock_supabase)

        # Act
        result = auth_manager._get_team_club_id(team_id=999)

        # Assert
        assert result is None

    def test_returns_none_on_database_error(self):
        '''Verify None is returned on database error'''
        # Arrange
        mock_supabase = Mock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception('DB error')
        auth_manager = AuthManager(supabase_client=mock_supabase)

        # Act
        result = auth_manager._get_team_club_id(team_id=5)

        # Assert
        assert result is None


@pytest.mark.unit
class TestCanManageTeamExtended:
    '''Extended tests for can_manage_team'''

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_club_manager_different_club(self, mock_get_club):
        '''Verify club manager cannot manage team in different club'''
        # Arrange
        mock_get_club.return_value = 200  # Team belongs to club 200
        user_data = {'role': 'club_manager', 'club_id': 100}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_manage_team(user_data, team_id=5)

        # Assert
        assert result is False

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_club_manager_team_has_no_club(self, mock_get_club):
        '''Verify club manager cannot manage team with no club'''
        # Arrange
        mock_get_club.return_value = None  # Team has no club
        user_data = {'role': 'club_manager', 'club_id': 100}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_manage_team(user_data, team_id=5)

        # Assert
        assert result is False

    @patch('backend.auth.AuthManager._get_team_club_id')
    def test_regular_user_cannot_manage(self, mock_get_club):
        '''Verify regular user cannot manage any team'''
        # Arrange
        user_data = {'role': 'team-fan', 'team_id': 5}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_manage_team(user_data, team_id=5)

        # Assert
        assert result is False
