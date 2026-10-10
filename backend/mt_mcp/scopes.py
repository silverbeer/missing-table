"""Which tools a caller may see and call: role and client → tool tiers (SB-1302).

Pure functions, no I/O. The tier filter is what `tools/list` shows and what
`tools/call` admits; it is not the only check. Tools that act on one team re-check
that team with auth.py (`can_manage_team`, `can_edit_match`) on every call.
"""

from typing import Literal

Tier = Literal["read", "my", "self", "team_write", "admin"]

ALL_TIERS: frozenset[Tier] = frozenset({"read", "my", "self", "team_write", "admin"})

# Canonical role strings, as user_profiles stores them: club_manager is the
# underscore form, the others are hyphenated (see auth.INVITE_TYPE_TO_ROLE).
ROLE_TIERS: dict[str, frozenset[Tier]] = {
    "admin": ALL_TIERS,
    "club_manager": frozenset({"read", "my", "team_write"}),
    "team-manager": frozenset({"read", "my", "team_write"}),
    "team-player": frozenset({"read", "my", "self"}),
    "team-fan": frozenset({"read", "my"}),
    "club-fan": frozenset({"read", "my"}),
}

# A role this table does not know (the legacy default "user", or anything new)
# can read and no more.
DEFAULT_TIERS: frozenset[Tier] = frozenset({"read"})

# Clients that ask for less than the caller's role allows. MT AI never gets
# writes or admin, whatever the role (mt2/ai.md "Auth").
MT_AI_CLIENT = "mt-ai"
CLIENT_CAPS: dict[str, frozenset[Tier]] = {
    MT_AI_CLIENT: frozenset({"read", "my", "self"}),
}

CLIENT_HEADER = "x-mt-client"


def allowed_tiers(role: str | None, client: str | None) -> frozenset[Tier]:
    """The tiers a caller with this role, using this client, may use.

    An unknown client name is treated as no cap: the header only ever narrows,
    so a caller gains nothing by inventing one.
    """
    tiers = ROLE_TIERS.get(role or "", DEFAULT_TIERS)
    cap = CLIENT_CAPS.get((client or "").strip().lower())
    return tiers & cap if cap is not None else tiers
