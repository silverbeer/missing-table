"""Club-scoped live chat rules (SB-1330) — pure functions, no database."""

import pytest

from services.chat_rooms import ChatRoom, chat_access, is_closed, match_rooms

IFA, NEFC, OTHER = 10, 20, 30
ROOMS = [ChatRoom(IFA, "IFA"), ChatRoom(NEFC, "NEFC")]


@pytest.mark.unit
class TestMatchRooms:
    def test_one_room_per_club(self):
        assert match_rooms(IFA, "IFA", NEFC, "NEFC") == ROOMS

    def test_same_club_both_sides_shares_one_room(self):
        assert match_rooms(IFA, "IFA", IFA, "IFA") == [ChatRoom(IFA, "IFA")]

    def test_a_team_with_no_club_has_no_room(self):
        assert match_rooms(None, None, NEFC, "NEFC") == [ChatRoom(NEFC, "NEFC")]
        assert match_rooms(None, None, None, None) == []


@pytest.mark.unit
class TestChatAccess:
    def test_a_member_gets_their_clubs_room_only(self):
        access = chat_access(is_admin=False, user_club_ids=[NEFC], rooms=ROOMS, closed=False)
        assert access.available and access.club_id == NEFC
        assert access.rooms == [ChatRoom(NEFC, "NEFC")]

    def test_a_user_whose_club_is_not_playing_gets_no_chat(self):
        access = chat_access(is_admin=False, user_club_ids=[OTHER], rooms=ROOMS, closed=False)
        assert not access.available and access.club_id is None and access.rooms == []
        assert not access.can_post

    def test_a_user_with_no_club_gets_no_chat(self):
        assert not chat_access(is_admin=False, user_club_ids=[], rooms=ROOMS, closed=False).available

    def test_first_playing_club_in_preference_order_wins(self):
        access = chat_access(is_admin=False, user_club_ids=[OTHER, NEFC, IFA], rooms=ROOMS, closed=False)
        assert access.club_id == NEFC

    def test_a_non_admin_cannot_pick_another_room(self):
        access = chat_access(
            is_admin=False, user_club_ids=[IFA], rooms=ROOMS, closed=False, requested_club_id=NEFC
        )
        assert access.club_id == IFA

    def test_an_admin_sees_both_rooms_and_defaults_to_home(self):
        access = chat_access(is_admin=True, user_club_ids=[], rooms=ROOMS, closed=False)
        assert access.club_id == IFA and access.rooms == ROOMS

    def test_an_admin_can_switch_rooms(self):
        access = chat_access(is_admin=True, user_club_ids=[], rooms=ROOMS, closed=False, requested_club_id=NEFC)
        assert access.club_id == NEFC

    def test_an_admin_asking_for_a_club_not_playing_gets_home(self):
        access = chat_access(is_admin=True, user_club_ids=[], rooms=ROOMS, closed=False, requested_club_id=OTHER)
        assert access.club_id == IFA

    def test_no_rooms_means_no_chat_even_for_admins(self):
        assert not chat_access(is_admin=True, user_club_ids=[], rooms=[], closed=False).available

    def test_closed_chat_is_readable_not_postable(self):
        access = chat_access(is_admin=False, user_club_ids=[IFA], rooms=ROOMS, closed=True)
        assert access.available and not access.can_post

    def test_to_dict(self):
        access = chat_access(is_admin=False, user_club_ids=[IFA], rooms=ROOMS, closed=False)
        assert access.to_dict() == {
            "available": True,
            "club_id": IFA,
            "rooms": [{"club_id": IFA, "name": "IFA"}],
            "closed": False,
        }


@pytest.mark.unit
class TestIsClosed:
    @pytest.mark.parametrize("status", ["completed", "forfeit", "cancelled", "postponed", "Completed"])
    def test_finished_statuses_close_chat(self, status):
        assert is_closed(status, None)

    @pytest.mark.parametrize("status", ["scheduled", "live", None])
    def test_open_statuses(self, status):
        assert not is_closed(status, None)

    def test_an_end_time_closes_chat(self):
        assert is_closed("live", "2026-10-13T15:00:00Z")
