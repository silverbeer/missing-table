"""mt_mcp.scopes (SB-1302): role and client → tool tiers."""

import pytest

from mt_mcp.scopes import ALL_TIERS, MT_AI_CLIENT, allowed_tiers

pytestmark = [pytest.mark.unit, pytest.mark.backend]


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", ALL_TIERS),
        ("club_manager", {"read", "my", "team_write"}),
        ("team-manager", {"read", "my", "team_write"}),
        ("team-player", {"read", "my", "self"}),
        ("team-fan", {"read", "my"}),
        ("club-fan", {"read", "my"}),
        # Unknown or legacy roles read and nothing else.
        ("user", {"read"}),
        ("service_account", {"read"}),
        (None, {"read"}),
        # Not a canonical spelling: club_manager is the underscore form.
        ("club-manager", {"read"}),
    ],
)
def test_role_tiers_without_a_client_cap(role, expected):
    assert allowed_tiers(role, None) == frozenset(expected)


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", {"read", "my", "self"}),
        ("club_manager", {"read", "my"}),
        ("team-manager", {"read", "my"}),
        ("team-player", {"read", "my", "self"}),
        ("team-fan", {"read", "my"}),
        ("user", {"read"}),
    ],
)
def test_mt_ai_never_gets_writes_or_admin_whatever_the_role(role, expected):
    tiers = allowed_tiers(role, MT_AI_CLIENT)

    assert tiers == frozenset(expected)
    assert "team_write" not in tiers
    assert "admin" not in tiers


@pytest.mark.parametrize("client", [" MT-AI ", "mt-ai", "Mt-Ai"])
def test_client_name_is_normalised(client):
    assert "admin" not in allowed_tiers("admin", client)


@pytest.mark.parametrize("client", ["claude-code", "anything", ""])
def test_an_unknown_client_neither_narrows_nor_widens(client):
    assert allowed_tiers("admin", client) == ALL_TIERS
    assert allowed_tiers("team-fan", client) == frozenset({"read", "my"})
