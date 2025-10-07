"""
End-to-end tests for the invite system.
These tests require a running Supabase instance and test the full invite workflow.
"""

import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json
from datetime import datetime


@pytest.mark.e2e
@pytest.mark.backend
@pytest.mark.invite
@pytest.mark.slow
@pytest.mark.server
@pytest.mark.database
class TestInviteWorkflowE2E:
    """Test complete invite workflow end-to-end."""
    
    @pytest.fixture
    def admin_user_mock(self):
        """Mock admin user for testing."""
        return {
            "user_id": "test-admin-123",
            "email": "admin@test.com", 
            "role": "admin",
            "team_id": None,
            "display_name": "Test Admin"
        }
    
    @pytest.fixture
    def team_manager_user_mock(self):
        """Mock team manager user for testing."""
        return {
            "user_id": "test-manager-456",
            "email": "manager@test.com",
            "role": "team_manager", 
            "team_id": 1,
            "display_name": "Test Manager"
        }

    @pytest.fixture
    def mock_invite_service(self):
        """Mock invite service responses."""
        mock_service = MagicMock()
        
        # Mock successful invite creation
        mock_service.create_invitation.return_value = {
            "id": "invite-123",
            "invite_code": "ABC123DEF456",  # pragma: allowlist secret
            "invite_type": "team_manager",
            "team_id": 1,
            "age_group_id": 1,
            "email": "newuser@example.com",
            "status": "pending",
            "expires_at": "2024-01-08T00:00:00Z",
            "created_at": "2024-01-01T00:00:00Z"
        }
        
        # Mock invite validation
        mock_service.validate_invite_code.return_value = {
            "valid": True,
            "id": "invite-123", 
            "invite_type": "team_manager",
            "team_id": 1,
            "team_name": "Test Team",
            "age_group_id": 1,
            "age_group_name": "U12",
            "email": "newuser@example.com"
        }
        
        # Mock user invitations list
        mock_service.get_user_invitations.return_value = [
            {
                "id": "invite-123",
                "invite_code": "ABC123DEF456",  # pragma: allowlist secret 
                "invite_type": "team_manager",
                "team_id": 1,
                "age_group_id": 1,
                "email": "newuser@example.com",
                "status": "pending",
                "expires_at": "2024-01-08T00:00:00Z",
                "created_at": "2024-01-01T00:00:00Z",
                "teams": {"name": "Test Team"},
                "age_groups": {"name": "U12"}
            }
        ]
        
        return mock_service

    def test_admin_create_team_manager_invite(self, test_client, admin_user_mock, mock_invite_service):
        """Test admin creating a team manager invite."""
        with patch('api.invites.get_current_user_required', return_value=admin_user_mock), \
             patch('services.InviteService') as mock_service_class:
            
            mock_service_class.return_value = mock_invite_service
            
            invite_data = {
                "invite_type": "team_manager",
                "team_id": 1,
                "age_group_id": 1, 
                "email": "newmanager@example.com"
            }
            
            response = test_client.post("/api/invites/admin/team-manager", json=invite_data)
            
            # Should succeed with proper auth
            assert response.status_code == 200
            data = response.json()
            assert data["invite_code"] == "ABC123DEF456"  # pragma: allowlist secret
            assert data["invite_type"] == "team_manager"
            assert data["email"] == "newuser@example.com"

    def test_admin_create_team_fan_invite(self, test_client, admin_user_mock, mock_invite_service):
        """Test admin creating a team fan invite.""" 
        with patch('api.invites.get_current_user_required', return_value=admin_user_mock), \
             patch('services.InviteService') as mock_service_class:
            
            mock_service_class.return_value = mock_invite_service
            
            invite_data = {
                "invite_type": "team_fan",
                "team_id": 1,
                "age_group_id": 1,
                "email": "newfan@example.com"
            }
            
            response = test_client.post("/api/invites/admin/team-fan", json=invite_data)
            assert response.status_code == 200
            
    def test_validate_invite_code_public(self, test_client, mock_invite_service):
        """Test public invite code validation."""
        with patch('services.InviteService') as mock_service_class:
            mock_service_class.return_value = mock_invite_service
            
            response = test_client.get("/api/invites/validate/ABC123DEF456")  # pragma: allowlist secret
            
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
            assert data["invite_type"] == "team_manager"
            assert data["team_name"] == "Test Team"
            assert data["age_group_name"] == "U12"

    def test_validate_invalid_invite_code(self, test_client, mock_invite_service):
        """Test validation of invalid invite code."""
        with patch('services.InviteService') as mock_service_class:
            mock_service_class.return_value = mock_invite_service
            mock_invite_service.validate_invite_code.return_value = None
            
            response = test_client.get("/api/invites/validate/INVALID123")
            
            assert response.status_code == 404
            data = response.json()
            assert "Invalid or expired" in data["detail"]

    def test_admin_list_their_invites(self, test_client, admin_user_mock, mock_invite_service):
        """Test admin listing their created invites."""
        with patch('api.invites.get_current_user_required', return_value=admin_user_mock), \
             patch('services.InviteService') as mock_service_class:
            
            mock_service_class.return_value = mock_invite_service
            
            response = test_client.get("/api/invites/my-invites")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["invite_code"] == "ABC123DEF456"  # pragma: allowlist secret
            assert data[0]["status"] == "pending"

    def test_admin_list_invites_with_status_filter(self, test_client, admin_user_mock, mock_invite_service):
        """Test admin listing invites with status filter."""
        with patch('api.invites.get_current_user_required', return_value=admin_user_mock), \
             patch('services.InviteService') as mock_service_class:
            
            mock_service_class.return_value = mock_invite_service
            
            response = test_client.get("/api/invites/my-invites?status=pending")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["status"] == "pending"

    def test_team_manager_create_team_fan_invite(self, test_client, team_manager_user_mock, mock_invite_service):
        """Test team manager creating team fan invite."""
        with patch('api.invites.get_current_user_required', return_value=team_manager_user_mock), \
             patch('services.InviteService') as mock_service_class, \
             patch('services.TeamManagerService') as mock_tm_service_class:
            
            mock_service_class.return_value = mock_invite_service
            mock_tm_service = MagicMock()
            mock_tm_service.can_manage_team.return_value = True
            mock_tm_service_class.return_value = mock_tm_service
            
            invite_data = {
                "invite_type": "team_fan",
                "team_id": 1,
                "age_group_id": 1
            }
            
            response = test_client.post("/api/invites/team-manager/team-fan", json=invite_data)
            assert response.status_code == 200

    def test_team_manager_cannot_create_invite_for_other_team(self, test_client, team_manager_user_mock, mock_invite_service):
        """Test team manager cannot create invite for team they don't manage."""
        with patch('api.invites.get_current_user_required', return_value=team_manager_user_mock), \
             patch('services.InviteService') as mock_service_class, \
             patch('services.TeamManagerService') as mock_tm_service_class:
            
            mock_service_class.return_value = mock_invite_service
            mock_tm_service = MagicMock()
            mock_tm_service.can_manage_team.return_value = False  # Cannot manage this team
            mock_tm_service_class.return_value = mock_tm_service
            
            invite_data = {
                "invite_type": "team_fan",
                "team_id": 2,  # Different team
                "age_group_id": 1
            }
            
            response = test_client.post("/api/invites/team-manager/team-fan", json=invite_data)
            assert response.status_code == 403
            assert "only create invites for teams you manage" in response.json()["detail"]

    def test_cancel_invite(self, test_client, admin_user_mock, mock_invite_service):
        """Test cancelling an invite."""
        with patch('api.invites.get_current_user_required', return_value=admin_user_mock), \
             patch('services.InviteService') as mock_service_class:
            
            mock_service_class.return_value = mock_invite_service
            mock_invite_service.cancel_invitation.return_value = True
            
            response = test_client.delete("/api/invites/invite-123")
            
            assert response.status_code == 200
            data = response.json()
            assert "cancelled successfully" in data["message"]

    def test_non_admin_cannot_create_team_manager_invite(self, test_client, team_manager_user_mock):
        """Test that non-admin users cannot create team manager invites."""
        with patch('api.invites.get_current_user_required', return_value=team_manager_user_mock):
            
            invite_data = {
                "invite_type": "team_manager",
                "team_id": 1,
                "age_group_id": 1
            }
            
            response = test_client.post("/api/invites/admin/team-manager", json=invite_data)
            assert response.status_code == 403
            assert "Only admins" in response.json()["detail"]


@pytest.mark.e2e 
class TestInviteValidationE2E:
    """Test invite validation and error handling."""
    
    def test_invalid_invite_type_validation(self, test_client):
        """Test validation of invalid invite types."""
        invite_data = {
            "invite_type": "invalid_type",
            "team_id": 1,
            "age_group_id": 1
        }
        
        response = test_client.post("/api/invites/admin/team-manager", json=invite_data)
        assert response.status_code in [401, 422]  # Auth or validation error
        
    def test_missing_required_fields_validation(self, test_client):
        """Test validation when required fields are missing."""
        incomplete_data_sets = [
            {},  # All fields missing
            {"invite_type": "team_manager"},  # Missing team_id, age_group_id
            {"team_id": 1},  # Missing invite_type, age_group_id  
            {"age_group_id": 1},  # Missing invite_type, team_id
            {"invite_type": "team_manager", "team_id": 1},  # Missing age_group_id
            {"invite_type": "team_manager", "age_group_id": 1},  # Missing team_id
        ]
        
        for data in incomplete_data_sets:
            response = test_client.post("/api/invites/admin/team-manager", json=data)
            assert response.status_code in [401, 422]  # Auth or validation error

    def test_invalid_data_types_validation(self, test_client):
        """Test validation with invalid data types."""
        invalid_data_sets = [
            {"invite_type": "team_manager", "team_id": "not_a_number", "age_group_id": 1},
            {"invite_type": "team_manager", "team_id": 1, "age_group_id": "not_a_number"},
            {"invite_type": "team_manager", "team_id": -1, "age_group_id": 1},  # Negative ID
            {"invite_type": "team_manager", "team_id": 1, "age_group_id": -1},  # Negative ID
        ]
        
        for data in invalid_data_sets:
            response = test_client.post("/api/invites/admin/team-manager", json=data)
            assert response.status_code in [401, 422]  # Auth or validation error


@pytest.mark.integration
class TestInviteIntegration:
    """Integration tests for invite system without full mocking."""
    
    def test_invite_endpoints_exist(self, test_client):
        """Test that all expected invite endpoints exist and respond appropriately."""
        endpoints = [
            ("GET", "/api/invites/validate/TESTCODE", [404, 400]),  # Public endpoint
            ("GET", "/api/invites/my-invites", [401]),  # Requires auth
            ("POST", "/api/invites/admin/team-manager", [401, 422]),  # Requires auth + validation
            ("POST", "/api/invites/admin/team-fan", [401, 422]),  # Requires auth + validation
            ("POST", "/api/invites/admin/team-player", [401, 422]),  # Requires auth + validation
            ("POST", "/api/invites/team-manager/team-fan", [401, 422]),  # Requires auth + validation
            ("POST", "/api/invites/team-manager/team-player", [401, 422]),  # Requires auth + validation
            ("GET", "/api/invites/team-manager/assignments", [401]),  # Requires auth
            ("DELETE", "/api/invites/test-id", [401]),  # Requires auth
        ]
        
        for method, endpoint, expected_codes in endpoints:
            if method == "GET":
                response = test_client.get(endpoint)
            elif method == "POST":
                response = test_client.post(endpoint, json={"test": "data"})
            elif method == "DELETE":
                response = test_client.delete(endpoint)
            
            assert response.status_code in expected_codes, f"Endpoint {method} {endpoint} returned unexpected status {response.status_code}"
            # Ensure it's not a 404 (endpoint doesn't exist)
            assert response.status_code != 404, f"Endpoint {method} {endpoint} not found"