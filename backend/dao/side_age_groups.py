"""Per-side age groups on matches (SB-1444).

A match has one ``age_group_id``. When one side plays up — IFA U15 against the
New England Revolution U16 in a friendly — that side's own age group is stored
in ``home_age_group_id`` / ``away_age_group_id``. NULL means "same as the
match", which is every scraped match and almost every manual one, so writers
that know nothing about playing up change nothing.
"""


def side_age_group(side_age_group_id: int | None, match_age_group_id: int | None) -> int | None:
    """Value to store for one side: NULL unless it differs from the match.

    Storing the match's own age group again would make two spellings of
    "same age group", and every reader would have to treat them alike.
    """
    if side_age_group_id is None or side_age_group_id == match_age_group_id:
        return None
    return side_age_group_id


def effective_side_age_groups(match: dict) -> tuple[int | None, int | None]:
    """(home, away) age group each side fielded, resolving NULL to the match's."""
    match_age = match.get("age_group_id")
    return (
        match.get("home_age_group_id") or match_age,
        match.get("away_age_group_id") or match_age,
    )


def team_age_group_filter(team_id: int, age_group_id: int) -> str:
    """PostgREST ``or`` filter: matches where ``team_id`` fielded ``age_group_id``.

    A side's age group is its own column when set, else the match's. PostgREST
    has no COALESCE, so each side is two branches: the override equals the age
    group, or there is no override and the match's age group does.
    """
    t, a = int(team_id), int(age_group_id)
    return ",".join(
        [
            f"and(home_team_id.eq.{t},home_age_group_id.eq.{a})",
            f"and(home_team_id.eq.{t},home_age_group_id.is.null,age_group_id.eq.{a})",
            f"and(away_team_id.eq.{t},away_age_group_id.eq.{a})",
            f"and(away_team_id.eq.{t},away_age_group_id.is.null,age_group_id.eq.{a})",
        ]
    )
