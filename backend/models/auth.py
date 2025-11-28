"""
Authentication and user-related Pydantic models.
"""
import re
from pydantic import BaseModel, field_validator


class UserSignup(BaseModel):
    """Model for user signup requests."""
    username: str  # Primary login credential (e.g., gabe_ifa_35)
    password: str
    email: str | None = None  # Optional for notifications
    phone_number: str | None = None  # Optional for SMS
    display_name: str | None = None
    invite_code: str | None = None

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Validate username format: 3-50 chars, alphanumeric and underscores only."""
        if not re.match(r'^[a-zA-Z0-9_]{3,50}$', v):
            raise ValueError(
                'Username must be 3-50 characters long and contain only letters, numbers, and underscores'
            )
        return v.lower()  # Store usernames in lowercase for consistency

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Validate email format if provided."""
        # Convert empty string to None
        if v == '':
            return None
        if v is not None and '@' not in v:
            raise ValueError('Invalid email format')
        return v


class UserLogin(BaseModel):
    """Model for user login requests."""
    username: str  # Changed from email
    password: str

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Ensure username is lowercase for lookup."""
        return v.lower()


class UserProfile(BaseModel):
    """Model for user profile data."""
    display_name: str | None = None
    email: str | None = None
    role: str | None = None
    team_id: int | None = None
    player_number: int | None = None
    positions: list[str] | None = None


class RoleUpdate(BaseModel):
    """Model for updating user roles."""
    user_id: str
    role: str
    team_id: int | None = None


class UserProfileUpdate(BaseModel):
    """Model for updating user profile information."""
    user_id: str
    username: str | None = None
    display_name: str | None = None
    email: str | None = None


class RefreshTokenRequest(BaseModel):
    """Model for refresh token requests."""
    refresh_token: str

