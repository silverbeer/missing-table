"""Per-account user preferences (SB-1286).

Stored as one jsonb object on ``user_profiles.preferences``. This module owns
its shape: a new preference is a field on ``UserPreferences``, not a
migration. Absent key means "no preference" - readers fall through to their
own default, never to a zero value.
"""

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict


class UserPreferences(BaseModel):
    """A partial preferences update. Only fields the client sends are applied;
    an explicit ``null`` clears that preference."""

    model_config = ConfigDict(extra="forbid")

    default_age_group_id: int | None = None


class UnknownAgeGroupError(ValueError):
    """The requested default age group does not exist."""


def read_preferences(raw: Any) -> dict:
    """Preferences as stored, or ``{}`` for a row that predates the column."""
    return dict(raw) if isinstance(raw, dict) else {}


def merge_preferences(current: Any, update: UserPreferences, known_age_group_ids: Iterable[int]) -> dict:
    """Apply ``update`` on top of the stored preferences.

    Keys the client did not send are kept; ``None`` removes the key.
    Raises UnknownAgeGroupError for an age group id that does not exist.
    """
    changes = update.model_dump(exclude_unset=True)

    age_group_id = changes.get("default_age_group_id")
    if age_group_id is not None and age_group_id not in set(known_age_group_ids):
        raise UnknownAgeGroupError(f"Unknown age group: {age_group_id}")

    merged = read_preferences(current)
    for key, value in changes.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged
