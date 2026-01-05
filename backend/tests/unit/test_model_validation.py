"""
Pydantic Model Validation Tests

Tests validators in models/auth.py for input validation at API boundaries.

Usage:
    pytest tests/unit/test_model_validation.py -v
"""

import pytest
from pydantic import ValidationError

from models.auth import (
    UserSignup,
    ProfilePhotoSlot,
    PlayerCustomization,
    PlayerHistoryCreate,
)


@pytest.mark.unit
class TestUsernameValidation:
    """Test UserSignup.username validation (3-50 chars, alphanumeric + underscore)."""

    @pytest.mark.parametrize("username,expected", [
        ("abc", "abc"),  # Minimum length
        ("ABC", "abc"),  # Uppercase converted to lowercase
        ("player_23", "player_23"),  # Typical format
        ("MixedCase_99", "mixedcase_99"),  # Mixed case lowercased
        ("a" * 50, "a" * 50),  # Maximum length
    ])
    def test_valid_usernames(self, username, expected):
        result = UserSignup(username=username, password="Test123!")
        assert result.username == expected

    @pytest.mark.parametrize("username", [
        "ab",  # Too short
        "",  # Empty
        "a" * 51,  # Too long
        "user@name",  # Invalid char @
        "user name",  # Space
        "user-name",  # Hyphen
    ])
    def test_invalid_usernames(self, username):
        with pytest.raises(ValidationError):
            UserSignup(username=username, password="Test123!")


@pytest.mark.unit
class TestHexColorValidation:
    """Test PlayerCustomization color validation (#RRGGBB format)."""

    @pytest.mark.parametrize("color", [
        "#3B82F6",  # Standard hex
        "#FFFFFF",  # White
        "#000000",  # Black
        "#abcdef",  # Lowercase
        None,  # Optional field
    ])
    def test_valid_colors(self, color):
        result = PlayerCustomization(primary_color=color)
        assert result.primary_color == color

    @pytest.mark.parametrize("color", [
        "3B82F6",  # Missing #
        "#3B82F",  # Too short
        "#3B82F6A",  # Too long
        "#GGG000",  # Invalid hex char
        "#FFF",  # 3-digit shorthand
        "blue",  # Color name
    ])
    def test_invalid_colors(self, color):
        with pytest.raises(ValidationError):
            PlayerCustomization(primary_color=color)


@pytest.mark.unit
class TestJerseyNumberValidation:
    """Test PlayerHistoryCreate.jersey_number validation (1-99)."""

    @pytest.mark.parametrize("number", [1, 99, 10, 23, 50, None])
    def test_valid_jersey_numbers(self, number):
        result = PlayerHistoryCreate(team_id=1, season_id=1, jersey_number=number)
        assert result.jersey_number == number

    @pytest.mark.parametrize("number", [0, 100, -1, 999])
    def test_invalid_jersey_numbers(self, number):
        with pytest.raises(ValidationError):
            PlayerHistoryCreate(team_id=1, season_id=1, jersey_number=number)


@pytest.mark.unit
class TestPhotoSlotValidation:
    """Test ProfilePhotoSlot.slot validation (1, 2, or 3)."""

    @pytest.mark.parametrize("slot", [1, 2, 3])
    def test_valid_slots(self, slot):
        result = ProfilePhotoSlot(slot=slot)
        assert result.slot == slot

    @pytest.mark.parametrize("slot", [0, 4, -1, 100])
    def test_invalid_slots(self, slot):
        with pytest.raises(ValidationError):
            ProfilePhotoSlot(slot=slot)


@pytest.mark.unit
class TestOverlayStyleValidation:
    """Test PlayerCustomization.overlay_style validation (badge/jersey/caption/none)."""

    @pytest.mark.parametrize("style", ["badge", "jersey", "caption", "none", None])
    def test_valid_styles(self, style):
        result = PlayerCustomization(overlay_style=style)
        assert result.overlay_style == style

    @pytest.mark.parametrize("style", ["Banner", "BADGE", "Badge", "", "default"])
    def test_invalid_styles(self, style):
        with pytest.raises(ValidationError):
            PlayerCustomization(overlay_style=style)


@pytest.mark.unit
class TestSocialHandleValidation:
    """Test PlayerCustomization social handle validation (max 30 chars, @ stripped)."""

    @pytest.mark.parametrize("handle,expected", [
        ("player_23", "player_23"),
        ("@player_23", "player_23"),  # @ stripped
        ("john.doe", "john.doe"),  # Period allowed
        ("a" * 30, "a" * 30),  # Max length
        (None, None),  # Optional
    ])
    def test_valid_handles(self, handle, expected):
        result = PlayerCustomization(instagram_handle=handle)
        assert result.instagram_handle == expected

    @pytest.mark.parametrize("handle", [
        "a" * 31,  # Too long
        "player@name",  # @ in middle
        "player name",  # Space
        "player-name",  # Hyphen
    ])
    def test_invalid_handles(self, handle):
        with pytest.raises(ValidationError):
            PlayerCustomization(instagram_handle=handle)
