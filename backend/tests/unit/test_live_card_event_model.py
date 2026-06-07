"""
LiveCardEvent model validation tests (SB-117).

Covers the updated LiveCardEvent Pydantic model:
  - player_id is now optional (was previously required)
  - player_name accepts free-text up to 200 chars
  - card_type still requires yellow_card or red_card
  - At least one of player_id / player_name must be supplied (validation is
    done at the endpoint level, not the model — so the model accepts both null)

Pure model tests, no database or HTTP client required.

Usage:
    pytest tests/unit/test_live_card_event_model.py -v
"""

import pytest
from pydantic import ValidationError

from models.live_match import LiveCardEvent


@pytest.mark.unit
class TestLiveCardEventPlayerIdOptional:
    """player_id is optional — can be None or a positive int."""

    def test_accepts_player_id_as_int(self):
        event = LiveCardEvent(team_id=1, player_id=42, card_type="yellow_card")
        assert event.player_id == 42

    def test_accepts_player_id_as_none(self):
        event = LiveCardEvent(team_id=1, player_id=None, card_type="yellow_card")
        assert event.player_id is None

    def test_player_id_defaults_to_none_when_omitted(self):
        event = LiveCardEvent(team_id=1, card_type="yellow_card")
        assert event.player_id is None


@pytest.mark.unit
class TestLiveCardEventPlayerNameFreeText:
    """player_name accepts free-text strings up to 200 chars."""

    def test_accepts_player_name_string(self):
        event = LiveCardEvent(team_id=1, player_name="Striker 9", card_type="red_card")
        assert event.player_name == "Striker 9"

    def test_accepts_jersey_number_as_name(self):
        event = LiveCardEvent(team_id=2, player_name="#7", card_type="yellow_card")
        assert event.player_name == "#7"

    def test_accepts_player_name_at_max_length(self):
        long_name = "A" * 200
        event = LiveCardEvent(team_id=1, player_name=long_name, card_type="yellow_card")
        assert event.player_name == long_name

    def test_rejects_player_name_exceeding_max_length(self):
        with pytest.raises(ValidationError):
            LiveCardEvent(team_id=1, player_name="B" * 201, card_type="yellow_card")

    def test_accepts_player_name_as_none(self):
        event = LiveCardEvent(team_id=1, player_name=None, card_type="yellow_card")
        assert event.player_name is None

    def test_player_name_defaults_to_none_when_omitted(self):
        event = LiveCardEvent(team_id=1, card_type="yellow_card")
        assert event.player_name is None


@pytest.mark.unit
class TestLiveCardEventBothPlayerFieldsPresent:
    """Both player_id and player_name may be present simultaneously; the
    endpoint decides precedence.  The model itself must not reject this."""

    def test_accepts_both_player_id_and_player_name(self):
        event = LiveCardEvent(
            team_id=1,
            player_id=5,
            player_name="Alice",
            card_type="yellow_card",
        )
        assert event.player_id == 5
        assert event.player_name == "Alice"

    def test_accepts_neither_player_field(self):
        """Model allows both to be None — endpoint enforces at-least-one rule."""
        event = LiveCardEvent(team_id=1, card_type="red_card")
        assert event.player_id is None
        assert event.player_name is None


@pytest.mark.unit
class TestLiveCardEventCardType:
    """card_type must be yellow_card or red_card (unchanged behaviour)."""

    @pytest.mark.parametrize("card_type", ["yellow_card", "red_card"])
    def test_valid_card_types(self, card_type):
        event = LiveCardEvent(team_id=1, player_id=1, card_type=card_type)
        assert event.card_type == card_type

    @pytest.mark.parametrize("card_type", ["yellow", "red", "blue_card", "", "Yellow_card"])
    def test_invalid_card_types(self, card_type):
        with pytest.raises(ValidationError):
            LiveCardEvent(team_id=1, player_id=1, card_type=card_type)


@pytest.mark.unit
class TestLiveCardEventMessage:
    """message is optional and accepts up to 500 chars."""

    def test_accepts_optional_message(self):
        event = LiveCardEvent(
            team_id=1,
            player_id=3,
            card_type="yellow_card",
            message="Dangerous tackle",
        )
        assert event.message == "Dangerous tackle"

    def test_message_defaults_to_none(self):
        event = LiveCardEvent(team_id=1, player_id=3, card_type="yellow_card")
        assert event.message is None

    def test_rejects_message_over_500_chars(self):
        with pytest.raises(ValidationError):
            LiveCardEvent(
                team_id=1,
                player_id=3,
                card_type="yellow_card",
                message="x" * 501,
            )


@pytest.mark.unit
class TestLiveCardEventTeamId:
    """team_id is required."""

    def test_rejects_missing_team_id(self):
        with pytest.raises(ValidationError):
            LiveCardEvent(player_id=1, card_type="yellow_card")
