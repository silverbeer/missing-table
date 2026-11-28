"""
Club Data Access Object.

Handles all database operations related to clubs including:
- Club CRUD operations
- Club-team associations
- Club queries and filters
"""

from collections import Counter
from urllib.parse import urlparse

import structlog

from dao.base_dao import BaseDAO, clear_cache, dao_cache, invalidates_cache

logger = structlog.get_logger()

# Cache pattern for invalidation
CLUBS_CACHE_PATTERN = "mt:dao:clubs:*"

_PAGE = 1000

LOGO_MISSING = "missing"
LOGO_EXTERNAL = "external"
LOGO_HOSTED = "hosted"


def club_logo_prefix(supabase_url: str | None) -> str | None:
    """The public URL every crest we host starts with, or None if unknown.

    Derived from SUPABASE_URL rather than hardcoded, so local, prod and any
    future project each recognise their own bucket (SB-1815).
    """
    base = (supabase_url or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/storage/v1/object/public/club-logos/"


def classify_logo(logo_url: str | None, prefix: str) -> str:
    """missing, external (hot-linked from someone else's site), or hosted.

    Scheme and host compare case-insensitively; the path does not, because
    storage paths are case-sensitive.
    """
    url = (logo_url or "").strip()
    if not url:
        return LOGO_MISSING
    parsed, expected = urlparse(url), urlparse(prefix)
    same_origin = (parsed.scheme.lower(), parsed.netloc.lower()) == (
        expected.scheme.lower(),
        expected.netloc.lower(),
    )
    return LOGO_HOSTED if same_origin and parsed.path.startswith(expected.path) else LOGO_EXTERNAL


def build_logo_gaps(
    teams: list[dict],
    clubs: list[dict],
    match_counts: dict[int, int],
    prefix: str,
    scoped: bool = True,
) -> dict:
    """The three crest gaps, from rows already read (SB-1815).

    With `scoped`, only teams with at least one match count, and only clubs
    with at least one such team: a gap nobody sees is not the one to fix
    first. Test clubs (is_test) and their teams are left out too — their
    fixtures are real rows, so the match count alone does not exclude them.
    Unscoped, every team and club is reported.
    """
    test_clubs = {c["id"] for c in clubs if c.get("is_test")}
    in_scope = [
        t for t in teams if not scoped or (match_counts.get(t["id"], 0) > 0 and t.get("club_id") not in test_clubs)
    ]

    teams_without_club = sorted(
        (
            {"id": t["id"], "name": t.get("name"), "match_count": match_counts.get(t["id"], 0)}
            for t in in_scope
            if t.get("club_id") is None
        ),
        key=lambda row: (-row["match_count"], row["name"] or ""),
    )

    club_ids = {t["club_id"] for t in in_scope if t.get("club_id") is not None}
    clubs_without_logo: list[dict] = []
    clubs_external_logo: list[dict] = []
    for club in sorted(clubs, key=lambda c: c.get("name") or ""):
        if scoped and club["id"] not in club_ids:
            continue
        status = classify_logo(club.get("logo_url"), prefix)
        if status == LOGO_MISSING:
            clubs_without_logo.append({"id": club["id"], "name": club.get("name")})
        elif status == LOGO_EXTERNAL:
            url = club["logo_url"].strip()
            clubs_external_logo.append(
                {"id": club["id"], "name": club.get("name"), "logo_url": url, "host": urlparse(url).hostname or ""}
            )

    return {
        "teams_without_club": teams_without_club,
        "clubs_without_logo": clubs_without_logo,
        "clubs_external_logo": clubs_external_logo,
    }


class ClubDAO(BaseDAO):
    """Data access object for club operations."""

    # === Club Query Methods ===

    @dao_cache("clubs:all:{include_team_counts}")
    def get_all_clubs(self, include_team_counts: bool = True) -> list[dict]:
        """Get all clubs with their associated teams count.

        Args:
            include_team_counts: If True, include team_count field for each club

        Returns:
            List of clubs from the clubs table.
        """
        response = self.client.table("clubs").select("*").order("name").execute()
        clubs = response.data

        if include_team_counts:
            # Enrich with team counts (single query instead of N+1)
            teams_response = self.client.table("teams").select("club_id").not_.is_("club_id", "null").execute()
            team_counts = Counter(team["club_id"] for team in teams_response.data if team.get("club_id"))
            for club in clubs:
                club["team_count"] = team_counts.get(club["id"], 0)

        return clubs

    @dao_cache("clubs:for_team:{team_id}")
    def get_club_for_team(self, team_id: int) -> dict | None:
        """Get the club for a team.

        Args:
            team_id: The team ID

        Returns:
            Club dict if team belongs to a club, None otherwise
        """
        # Get the team to find its club_id
        team_response = self.client.table("teams").select("club_id").eq("id", team_id).execute()
        if not team_response.data or len(team_response.data) == 0:
            return None

        club_id = team_response.data[0].get("club_id")
        if not club_id:
            return None

        # Get the club details
        club_response = self.client.table("clubs").select("*").eq("id", club_id).execute()
        if club_response.data and len(club_response.data) > 0:
            return club_response.data[0]
        return None

    def get_club_by_name(self, name: str) -> dict | None:
        """Get a club by name (exact match, case-sensitive).

        Matches the clubs_name_unique DB constraint, which is `UNIQUE (name)`
        case-sensitively. Used by the create-club endpoint to recover the
        existing row when the DB raises that unique violation. Returns the
        full club row if found, None otherwise.
        """
        response = self.client.table("clubs").select("*").eq("name", name).limit(1).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    # === Club CRUD Methods ===

    @invalidates_cache(CLUBS_CACHE_PATTERN)
    def create_club(
        self,
        name: str,
        city: str,
        website: str | None = None,
        description: str | None = None,
        logo_url: str | None = None,
        primary_color: str | None = None,
        secondary_color: str | None = None,
        pro_academy: bool = False,
    ) -> dict:
        """Create a new club.

        Args:
            name: Club name
            city: Club city/location
            website: Optional website URL
            description: Optional description
            logo_url: Optional URL to club logo in Supabase Storage
            primary_color: Optional primary brand color (hex code)
            secondary_color: Optional secondary brand color (hex code)
            pro_academy: True for an MLS/professional club academy. Teams in
                such a club field no U15 side — that cohort plays up into U16
                — so a ragged age list is expected rather than a scrape gap.

        Returns:
            Created club dict

        Raises:
            ValueError: If club creation fails
        """
        club_data = {"name": name, "city": city}
        if website:
            club_data["website"] = website
        if description:
            club_data["description"] = description
        if logo_url:
            club_data["logo_url"] = logo_url
        if primary_color:
            club_data["primary_color"] = primary_color
        if secondary_color:
            club_data["secondary_color"] = secondary_color
        # Written unconditionally, unlike the optional strings above: False is
        # a real answer here, not an absent one.
        club_data["pro_academy"] = pro_academy

        result = self.client.table("clubs").insert(club_data).execute()

        if not result.data or len(result.data) == 0:
            raise ValueError("Failed to create club")

        return result.data[0]

    @invalidates_cache(CLUBS_CACHE_PATTERN)
    def update_club(
        self,
        club_id: int,
        name: str | None = None,
        city: str | None = None,
        website: str | None = None,
        description: str | None = None,
        logo_url: str | None = None,
        primary_color: str | None = None,
        secondary_color: str | None = None,
        pro_academy: bool | None = None,
    ) -> dict | None:
        """Update an existing club.

        Args:
            club_id: ID of club to update
            name: Optional new name
            city: Optional new city/location
            website: Optional new website URL
            description: Optional new description
            logo_url: Optional URL to club logo in Supabase Storage
            primary_color: Optional primary brand color (hex code)
            secondary_color: Optional secondary brand color (hex code)

        Returns:
            Updated club dict or None if not found
        """
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if city is not None:
            update_data["city"] = city
        if website is not None:
            update_data["website"] = website
        if description is not None:
            update_data["description"] = description
        if logo_url is not None:
            update_data["logo_url"] = logo_url
        if primary_color is not None:
            update_data["primary_color"] = primary_color
        if secondary_color is not None:
            update_data["secondary_color"] = secondary_color
        if pro_academy is not None:
            update_data["pro_academy"] = pro_academy

        if not update_data:
            return None

        result = self.client.table("clubs").update(update_data).eq("id", club_id).execute()

        if not result.data or len(result.data) == 0:
            return None

        return result.data[0]

    @invalidates_cache(CLUBS_CACHE_PATTERN)
    def delete_club(self, club_id: int) -> bool:
        """Delete a club.

        Args:
            club_id: The club ID to delete

        Returns:
            True if deleted successfully

        Raises:
            Exception: If deletion fails

        Note:
            This will fail if there are teams still associated with this club
            due to ON DELETE RESTRICT constraint.
            Invitations referencing this club are deleted first.
        """
        # Delete invitations referencing this club first (FK constraint)
        self.client.table("invitations").delete().eq("club_id", club_id).execute()
        # Now delete the club
        self.client.table("clubs").delete().eq("id", club_id).execute()
        return True

    def merge_club(self, from_id: int, into_id: int, dry_run: bool = True) -> dict:
        """Fold a duplicate club into its canonical club (SB-1822).

        One transaction in the database (merge_club RPC): every reference is
        repointed, the target's empty crest/colours are filled from the source,
        and the source is deleted. A dry run reports the same counts and
        changes nothing. A real run raises while the dry run lists blockers.
        """
        response = self.client.rpc("merge_club", {"p_from": from_id, "p_into": into_id, "p_dry_run": dry_run}).execute()
        if not dry_run:
            # Teams carry their club's crest and colours into every cached
            # read, so nothing cached about either club is trustworthy now.
            clear_cache("mt:dao:*")
        return response.data or {}

    # === Crest coverage (SB-1815) ===

    def _paged(self, query_fn) -> list[dict]:
        """Every row of a query, a page at a time (PostgREST caps a response)."""
        rows: list[dict] = []
        while True:
            page = query_fn().order("id").range(len(rows), len(rows) + _PAGE - 1).execute().data or []
            rows.extend(page)
            if len(page) < _PAGE:
                return rows

    def logo_gaps(self, season_id: int | None) -> dict:
        """Teams with no club, clubs with no crest, clubs whose crest is hot-linked.

        `season_id` scopes the report to teams that played in that season and
        their clubs; None reports every team and club.
        """
        prefix = club_logo_prefix(getattr(self.connection_holder, "url", None))
        if prefix is None:
            raise ValueError("SUPABASE_URL is not configured; cannot tell hosted crests from hot-linked ones")

        teams = self._paged(lambda: self.client.table("teams").select("id, name, club_id"))
        clubs = self._paged(lambda: self.client.table("clubs").select("id, name, logo_url, is_test"))

        def matches_query():
            query = self.client.table("matches").select("id, home_team_id, away_team_id")
            return query.eq("season_id", season_id) if season_id is not None else query

        match_counts: Counter = Counter()
        for match in self._paged(matches_query):
            match_counts[match["home_team_id"]] += 1
            match_counts[match["away_team_id"]] += 1

        report = build_logo_gaps(teams, clubs, match_counts, prefix, scoped=season_id is not None)
        return {"season_id": season_id, **report}

    # === Team-Club Association Methods ===

    def update_team_club(self, team_id: int, club_id: int | None) -> dict:
        """Update the club for a team.

        Args:
            team_id: The team ID to update
            club_id: The club ID to assign (or None to remove club association)

        Returns:
            Updated team dict

        Raises:
            ValueError: If team update fails
        """
        result = self.client.table("teams").update({"club_id": club_id}).eq("id", team_id).execute()
        if not result.data or len(result.data) == 0:
            raise ValueError(f"Failed to update club for team {team_id}")
        return result.data[0]

    def get_all_parent_club_entities(self) -> list[dict]:
        """Get all parent club entities (teams with no club_id).

        This includes clubs that don't have children yet.
        Used for dropdowns where users need to select a parent club.
        """
        try:
            # Get all teams that could be parent clubs (no club_id)
            response = self.client.table("teams").select("*").is_("club_id", "null").execute()
            return response.data
        except Exception:
            logger.exception("Error querying parent club entities")
            return []
