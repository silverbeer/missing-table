"""Remembered Table/Matches filters, per account (SB-1715).

Stored on ``user_profiles.filter_memory`` as one object per view::

    {"table": {"filters": {...}, "panel_open": true, "saved_at": 1731600000000}}

The browser keeps its own copy (``useFilterMemory``) and whichever was saved
later wins, so ``saved_at`` is the client's clock in milliseconds.

The filters themselves are opaque to the backend: the component that saved
them is the one that checks every id against what it fetched before applying
any (SB-1112). This module only bounds their size and shape, because the
column is written on every filter change and read on every page load.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

View = Literal["table", "matches", "ranking"]

MAX_KEYS = 16
MAX_LIST = 50
MAX_STRING = 64


def _valid_scalar(value: Any) -> bool:
    if value is None or isinstance(value, bool | int):
        return True
    if isinstance(value, float):
        return value == value and abs(value) != float("inf")  # no NaN/inf
    return isinstance(value, str) and len(value) <= MAX_STRING


def validate_filters(filters: dict) -> dict:
    """Return ``filters`` if every value is a small scalar or list of them.

    Raises ValueError otherwise — a nested object or a long string is not a
    filter, and is not something this column should grow to hold.
    """
    if len(filters) > MAX_KEYS:
        raise ValueError(f"at most {MAX_KEYS} filter keys")
    for key, value in filters.items():
        if not isinstance(key, str) or len(key) > MAX_STRING:
            raise ValueError("filter keys must be short strings")
        if isinstance(value, list):
            if len(value) > MAX_LIST or not all(_valid_scalar(v) for v in value):
                raise ValueError(f"{key}: list of up to {MAX_LIST} scalars")
        elif not _valid_scalar(value):
            raise ValueError(f"{key}: must be a scalar or a list of scalars")
    return filters


class FilterMemoryUpdate(BaseModel):
    """One view's patch. Unsent fields are kept; ``filters: null`` forgets them."""

    model_config = ConfigDict(extra="forbid")

    filters: dict[str, Any] | None = None
    panel_open: bool | None = None
    saved_at: int

    @field_validator("filters")
    @classmethod
    def _check_filters(cls, value: dict | None) -> dict | None:
        return None if value is None else validate_filters(value)

    def to_patch(self) -> dict:
        """The jsonb merged into the view's entry: only what the client sent."""
        return self.model_dump(exclude_unset=True)


def read_filter_memory(raw: Any) -> dict:
    """Stored memory, or ``{}`` for a row that has none (the normal state)."""
    return dict(raw) if isinstance(raw, dict) else {}
