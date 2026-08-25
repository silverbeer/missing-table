"""Exceptions that distinguish permanent ingest failures from transient ones.

`process_match_data` retries on any exception with exponential backoff, which
is right for a database blip and wrong for a name that does not exist. An
unknown team is not going to become known by waiting ten minutes; retrying it
three times only delays the moment anyone finds out.

Raising one of these marks the failure as permanent. The task's
`dont_autoretry_for` skips the retry wrapper for it, and the handler records
the name in `ingest_failures` so it is reported once, with a count, instead of
disappearing into a worker log.
"""

from __future__ import annotations


class UnresolvedNameError(Exception):
    """A name in the feed does not correspond to anything in the database.

    Attributes:
        kind: What kind of name it was — 'team', 'division', 'league' or
            'invalid'. Matches ingest_failures.kind.
        raw_name: The string exactly as the feed sent it. Kept verbatim
            because the fix is `mt team alias add <team> "<raw_name>"`, and a
            normalised copy would not be the string that needs aliasing.
        league: The league as the feed named it, or None.
        sample: One example of the match that was dropped, for the alert.
    """

    def __init__(
        self,
        kind: str,
        raw_name: str,
        *,
        league: str | None = None,
        sample: str | None = None,
    ) -> None:
        self.kind = kind
        self.raw_name = raw_name
        self.league = league
        self.sample = sample
        scope = f" (league={league})" if league else ""
        super().__init__(f"{kind.capitalize()} not found: {raw_name}{scope}")
