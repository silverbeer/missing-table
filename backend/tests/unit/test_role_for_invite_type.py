"""Canonical role per invite_type (SB-798).

This mapping lived in four places and one of them disagreed: the email/OAuth
signup path mapped club_fan -> "club_fan" while the other three mapped it to
"club-fan". Both spellings satisfy user_profiles_role_check, so nothing ever
failed — the database quietly accumulated the same role under two names
depending on which signup door a user came through, and every exact-match
comparison downstream then covered only half of them.

Two club_fan rows in production came from that divergent path.
"""

import pytest

from auth import DEFAULT_ROLE, INVITE_TYPE_TO_ROLE, role_for_invite_type


@pytest.mark.unit
class TestRoleForInviteType:
    @pytest.mark.parametrize(
        ("invite_type", "expected"),
        [
            ("club_manager", "club_manager"),
            ("club_fan", "club-fan"),
            ("team_manager", "team-manager"),
            ("team_player", "team-player"),
            ("team_fan", "team-fan"),
        ],
    )
    def test_each_invite_type_maps_to_its_canonical_role(self, invite_type, expected):
        assert role_for_invite_type(invite_type) == expected

    def test_club_fan_is_hyphenated(self):
        # The specific divergence that created the inconsistent rows. Worth its
        # own test rather than only a parametrized row, because reverting it
        # would silently resume producing two spellings.
        assert role_for_invite_type("club_fan") == "club-fan"
        assert role_for_invite_type("club_fan") != "club_fan"

    def test_club_manager_stays_underscored(self):
        # Deliberately asymmetric: "club-manager" is not permitted by the role
        # check constraint, so normalising it to a hyphen would produce a value
        # the database rejects.
        assert role_for_invite_type("club_manager") == "club_manager"

    def test_unknown_invite_type_falls_back_to_the_default(self):
        assert role_for_invite_type("nonsense") == DEFAULT_ROLE
        assert role_for_invite_type(None) == DEFAULT_ROLE
        assert role_for_invite_type("") == DEFAULT_ROLE

    def test_every_produced_role_is_one_the_constraint_allows(self):
        # Mirrors user_profiles_role_check. A mapping that emits anything else
        # would fail at insert time, in the signup path, for a real person.
        allowed = {
            "admin",
            "club_manager",
            "club-fan",
            "club_fan",
            "team-manager",
            "team_manager",
            "team-player",
            "team_player",
            "team-fan",
            "team_fan",
        }
        assert set(INVITE_TYPE_TO_ROLE.values()) <= allowed
        assert DEFAULT_ROLE in allowed

    def test_no_two_invite_types_share_a_role(self):
        roles = list(INVITE_TYPE_TO_ROLE.values())
        assert len(roles) == len(set(roles))
