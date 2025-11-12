import pytest
from unittest.mock import Mock, patch
import jwt
from backend.auth import AuthManager

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
        mock_verify_token.return_value = {'sub': 'user123', 'role': 'user'}
        mock_supabase = Mock()
        mock_response = Mock()
        mock_response.data = [{'id': 'user123', 'username': 'testuser', 'role': 'user'}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        auth_manager = AuthManager(supabase_client=mock_supabase)

        # Act
        user_data = auth_manager.get_current_user('valid_token')

        # Assert
        assert user_data['username'] == 'testuser'
        assert user_data['role'] == 'user'

    @patch('backend.auth.AuthManager.verify_token', return_value=None)
    def test_get_current_user_no_token(self, mock_verify_token):
        '''Verify that no token returns None'''
        # Arrange
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.get_current_user(None)

        # Assert
        assert result is None

    @patch('backend.auth.AuthManager.get_current_user')
    def test_require_role_valid_role(self, mock_get_current_user):
        '''Verify that user with correct role passes'''
        # Arrange
        mock_get_current_user.return_value = {'sub': 'user123', 'role': 'admin'}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.require_role('admin')

        # Assert
        assert result is True

    @patch('backend.auth.AuthManager.get_current_user')
    def test_require_role_invalid_role(self, mock_get_current_user):
        '''Verify that user with incorrect role raises exception'''
        # Arrange
        mock_get_current_user.return_value = {'sub': 'user123', 'role': 'user'}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act & Assert
        with pytest.raises(PermissionError):
            auth_manager.require_role('admin')

    @patch('backend.auth.AuthManager.get_current_user')
    def test_require_match_management_permission_valid(self, mock_get_current_user):
        '''Verify that user with management permission passes'''
        # Arrange
        mock_get_current_user.return_value = {'sub': 'user123', 'role': 'manager'}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.require_match_management_permission()

        # Assert
        assert result is True

    @patch('backend.auth.AuthManager.get_current_user')
    def test_require_match_management_permission_invalid(self, mock_get_current_user):
        '''Verify that user without management permission raises exception'''
        # Arrange
        mock_get_current_user.return_value = {'sub': 'user123', 'role': 'user'}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act & Assert
        with pytest.raises(PermissionError):
            auth_manager.require_match_management_permission()

    @patch('backend.auth.jwt.decode')
    def test_verify_service_account_token_valid(self, mock_jwt_decode):
        '''Verify that valid service account token is decoded correctly'''
        # Arrange
        mock_jwt_decode.return_value = {'sub': 'service_account', 'role': 'service'}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.verify_service_account_token('valid_service_token')

        # Assert
        assert result['role'] == 'service'

    @patch('backend.auth.jwt.decode', side_effect=jwt.InvalidTokenError)
    def test_verify_service_account_token_invalid(self, mock_jwt_decode):
        '''Verify that invalid service account token returns None'''
        # Arrange
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.verify_service_account_token('invalid_service_token')

        # Assert
        assert result is None

    @patch('backend.auth.AuthManager.get_current_user')
    def test_can_edit_match_authorized_user(self, mock_get_current_user):
        '''Verify that authorized user can edit match'''
        # Arrange
        mock_get_current_user.return_value = {'sub': 'user123', 'role': 'editor'}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_edit_match()

        # Assert
        assert result is True

    @patch('backend.auth.AuthManager.get_current_user')
    def test_can_edit_match_unauthorized_user(self, mock_get_current_user):
        '''Verify that unauthorized user cannot edit match'''
        # Arrange
        mock_get_current_user.return_value = {'sub': 'user123', 'role': 'viewer'}
        auth_manager = AuthManager(supabase_client=Mock())

        # Act
        result = auth_manager.can_edit_match()

        # Assert
        assert result is False
