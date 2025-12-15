"""
Unit tests for InviteService

Tests cover:
- Invite code generation (format, uniqueness)
- Invitation creation (validation rules for different invite types)
- Invite code validation (expired, used, not found)
- Invitation redemption
- Invitation cancellation
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from backend.services.invite_service import InviteService


class TestInviteCodeGeneration:
    """Tests for generate_invite_code method"""

    def test_generates_12_character_code(self):
        """Invite codes should be exactly 12 characters"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        service = InviteService(mock_supabase)
        code = service.generate_invite_code()

        assert len(code) == 12

    def test_uses_only_allowed_characters(self):
        """Invite codes should only use non-ambiguous characters"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        service = InviteService(mock_supabase)
        code = service.generate_invite_code()

        allowed_chars = set('ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
        assert all(c in allowed_chars for c in code)

    def test_excludes_ambiguous_characters(self):
        """Invite codes should not contain ambiguous characters (0, O, 1, I)"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        service = InviteService(mock_supabase)

        # Generate multiple codes to increase confidence
        for _ in range(10):
            code = service.generate_invite_code()
            # Excluded: 0 (zero), O (letter), 1 (one), I (letter)
            # L is allowed as it's less ambiguous than I
            ambiguous_chars = set('0O1I')
            assert not any(c in ambiguous_chars for c in code)

    def test_retries_on_duplicate_code(self):
        """Should retry if generated code already exists"""
        mock_supabase = MagicMock()

        # First call returns existing code, second returns empty (unique)
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[{'id': 1}]),  # First code exists
            MagicMock(data=[]),            # Second code is unique
        ]

        service = InviteService(mock_supabase)
        code = service.generate_invite_code()

        assert len(code) == 12
        assert mock_supabase.table.return_value.select.return_value.eq.return_value.execute.call_count == 2

    def test_raises_after_max_attempts(self):
        """Should raise exception after 100 failed attempts"""
        mock_supabase = MagicMock()
        # All codes already exist
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{'id': 1}]

        service = InviteService(mock_supabase)

        with pytest.raises(Exception, match="Could not generate unique invite code"):
            service.generate_invite_code()


class TestCreateInvitation:
    """Tests for create_invitation method"""

    def test_club_manager_requires_club_id(self):
        """club_manager invite type requires club_id"""
        mock_supabase = MagicMock()
        service = InviteService(mock_supabase)

        with pytest.raises(ValueError, match="club_id is required for club_manager invites"):
            service.create_invitation(
                invited_by_user_id="user-123",
                invite_type="club_manager",
                club_id=None
            )

    def test_club_fan_requires_club_id(self):
        """club_fan invite type requires club_id"""
        mock_supabase = MagicMock()
        service = InviteService(mock_supabase)

        with pytest.raises(ValueError, match="club_id is required for club_fan invites"):
            service.create_invitation(
                invited_by_user_id="user-123",
                invite_type="club_fan",
                club_id=None
            )

    def test_team_manager_requires_team_id(self):
        """team_manager invite type requires team_id"""
        mock_supabase = MagicMock()
        service = InviteService(mock_supabase)

        with pytest.raises(ValueError, match="team_id is required for team-level invites"):
            service.create_invitation(
                invited_by_user_id="user-123",
                invite_type="team_manager",
                team_id=None,
                age_group_id=1
            )

    def test_team_manager_requires_age_group_id(self):
        """team_manager invite type requires age_group_id"""
        mock_supabase = MagicMock()
        service = InviteService(mock_supabase)

        with pytest.raises(ValueError, match="age_group_id is required for team-level invites"):
            service.create_invitation(
                invited_by_user_id="user-123",
                invite_type="team_manager",
                team_id=1,
                age_group_id=None
            )

    def test_team_player_requires_team_id_and_age_group(self):
        """team_player invite type requires both team_id and age_group_id"""
        mock_supabase = MagicMock()
        service = InviteService(mock_supabase)

        with pytest.raises(ValueError, match="team_id is required"):
            service.create_invitation(
                invited_by_user_id="user-123",
                invite_type="team_player",
                team_id=None,
                age_group_id=1
            )

    def test_creates_club_invitation_successfully(self):
        """Should create club invitation with correct data"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{
            'id': 1,
            'invite_code': 'ABC123DEF456',  # pragma: allowlist secret
            'invite_type': 'club_manager',
            'club_id': 10
        }]

        service = InviteService(mock_supabase)
        result = service.create_invitation(
            invited_by_user_id="user-123",
            invite_type="club_manager",
            club_id=10
        )

        assert result['invite_type'] == 'club_manager'
        assert result['club_id'] == 10

    def test_creates_team_invitation_successfully(self):
        """Should create team invitation with correct data"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{
            'id': 1,
            'invite_code': 'ABC123DEF456',  # pragma: allowlist secret
            'invite_type': 'team_player',
            'team_id': 5,
            'age_group_id': 3
        }]

        service = InviteService(mock_supabase)
        result = service.create_invitation(
            invited_by_user_id="user-123",
            invite_type="team_player",
            team_id=5,
            age_group_id=3
        )

        assert result['invite_type'] == 'team_player'
        assert result['team_id'] == 5
        assert result['age_group_id'] == 3

    def test_club_invite_nullifies_team_fields(self):
        """Club invites should have team_id and age_group_id set to None"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{'id': 1}]

        service = InviteService(mock_supabase)
        service.create_invitation(
            invited_by_user_id="user-123",
            invite_type="club_manager",
            club_id=10,
            team_id=5,  # Should be ignored
            age_group_id=3  # Should be ignored
        )

        # Check the data passed to insert
        insert_call = mock_supabase.table.return_value.insert.call_args
        insert_data = insert_call[0][0]
        assert insert_data['team_id'] is None
        assert insert_data['age_group_id'] is None
        assert insert_data['club_id'] == 10

    def test_team_invite_nullifies_club_id(self):
        """Team invites should have club_id set to None"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{'id': 1}]

        service = InviteService(mock_supabase)
        service.create_invitation(
            invited_by_user_id="user-123",
            invite_type="team_player",
            team_id=5,
            age_group_id=3,
            club_id=10  # Should be ignored
        )

        insert_call = mock_supabase.table.return_value.insert.call_args
        insert_data = insert_call[0][0]
        assert insert_data['club_id'] is None
        assert insert_data['team_id'] == 5
        assert insert_data['age_group_id'] == 3


class TestValidateInviteCode:
    """Tests for validate_invite_code method"""

    def test_returns_none_for_nonexistent_code(self):
        """Should return None if code doesn't exist"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        service = InviteService(mock_supabase)
        result = service.validate_invite_code("NONEXISTENT1")

        assert result is None

    def test_returns_none_for_used_code(self):
        """Should return None if code has already been used"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
            'id': 1,
            'invite_code': 'USEDCODE1234',
            'status': 'used',
            'expires_at': (datetime.now(UTC) + timedelta(days=1)).isoformat()
        }]

        service = InviteService(mock_supabase)
        result = service.validate_invite_code("USEDCODE1234")

        assert result is None

    def test_returns_none_for_expired_code(self):
        """Should return None and update status if code is expired"""
        mock_supabase = MagicMock()
        expired_time = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
            'id': 1,
            'invite_code': 'EXPIREDCODE1',
            'status': 'pending',
            'expires_at': expired_time
        }]

        service = InviteService(mock_supabase)
        result = service.validate_invite_code("EXPIREDCODE1")

        assert result is None
        # Verify status was updated to expired
        mock_supabase.table.return_value.update.assert_called()

    def test_returns_valid_invitation_details(self):
        """Should return invitation details for valid code"""
        mock_supabase = MagicMock()
        future_time = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
            'id': 1,
            'invite_code': 'VALIDCODE123',
            'status': 'pending',
            'invite_type': 'team_player',
            'team_id': 5,
            'age_group_id': 3,
            'club_id': None,
            'email': 'test@example.com',
            'expires_at': future_time,
            'teams': {'name': 'FC Academy'},
            'age_groups': {'name': 'U14'},
            'clubs': None
        }]

        service = InviteService(mock_supabase)
        result = service.validate_invite_code("VALIDCODE123")

        assert result is not None
        assert result['valid'] is True
        assert result['invite_type'] == 'team_player'
        assert result['team_id'] == 5
        assert result['team_name'] == 'FC Academy'
        assert result['age_group_id'] == 3
        assert result['age_group_name'] == 'U14'
        assert result['email'] == 'test@example.com'

    def test_handles_timezone_z_suffix(self):
        """Should handle ISO timestamps with Z suffix"""
        mock_supabase = MagicMock()
        future_time = (datetime.now(UTC) + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
            'id': 1,
            'invite_code': 'VALIDCODE123',
            'status': 'pending',
            'invite_type': 'team_player',
            'team_id': 5,
            'age_group_id': 3,
            'club_id': None,
            'email': None,
            'expires_at': future_time,
            'teams': {'name': 'FC Academy'},
            'age_groups': {'name': 'U14'},
            'clubs': None
        }]

        service = InviteService(mock_supabase)
        result = service.validate_invite_code("VALIDCODE123")

        assert result is not None
        assert result['valid'] is True


class TestRedeemInvitation:
    """Tests for redeem_invitation method"""

    def test_returns_false_for_invalid_code(self):
        """Should return False if code validation fails"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        service = InviteService(mock_supabase)
        result = service.redeem_invitation("INVALIDCODE1", "user-123")

        assert result is False

    def test_updates_status_on_successful_redemption(self):
        """Should update invitation status to 'used' on success"""
        mock_supabase = MagicMock()
        future_time = (datetime.now(UTC) + timedelta(days=5)).isoformat()

        # Mock validation response
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
            'id': 1,
            'invite_code': 'VALIDCODE123',
            'status': 'pending',
            'invite_type': 'team_player',
            'team_id': 5,
            'age_group_id': 3,
            'club_id': None,
            'email': None,
            'expires_at': future_time,
            'teams': {'name': 'FC Academy'},
            'age_groups': {'name': 'U14'},
            'clubs': None
        }]

        # Mock update response
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{'id': 1}]

        service = InviteService(mock_supabase)
        result = service.redeem_invitation("VALIDCODE123", "user-456")

        assert result is True


class TestCancelInvitation:
    """Tests for cancel_invitation method"""

    def test_returns_false_for_nonexistent_invitation(self):
        """Should return False if invitation doesn't exist"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = None

        service = InviteService(mock_supabase)
        result = service.cancel_invitation("invite-123", "user-123")

        assert result is False

    def test_returns_false_for_non_pending_invitation(self):
        """Should return False if invitation is not pending"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            'invited_by_user_id': 'user-123',
            'status': 'used'
        }

        service = InviteService(mock_supabase)
        result = service.cancel_invitation("invite-123", "user-123")

        assert result is False

    def test_cancels_pending_invitation_successfully(self):
        """Should cancel pending invitation"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            'invited_by_user_id': 'user-123',
            'status': 'pending'
        }
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{'id': 1}]

        service = InviteService(mock_supabase)
        result = service.cancel_invitation("invite-123", "user-123")

        assert result is True


class TestExpireOldInvitations:
    """Tests for expire_old_invitations method"""

    def test_returns_zero_when_no_expired_invitations(self):
        """Should return 0 if no invitations to expire"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value.data = []

        service = InviteService(mock_supabase)
        result = service.expire_old_invitations()

        assert result == 0

    def test_expires_old_pending_invitations(self):
        """Should expire all old pending invitations"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value.data = [
            {'id': 1},
            {'id': 2},
            {'id': 3}
        ]
        mock_supabase.table.return_value.update.return_value.in_.return_value.execute.return_value.data = [
            {'id': 1}, {'id': 2}, {'id': 3}
        ]

        service = InviteService(mock_supabase)
        result = service.expire_old_invitations()

        assert result == 3
