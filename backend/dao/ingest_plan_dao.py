"""Planning and applying a tournament's teams and aliases against the database (SB-1763).

`plan` reads; `apply` writes, and only what a reviewer approved. The rules for
what to propose are pure and live in `dao.ingest_plan`; whether a name
resolves is asked of `TeamDAO.resolve_tournament_team`, the resolver ingest
uses, so a plan cannot disagree with ingest about what "resolved" means.

Ingest calls none of this. A team is only ever created here, by an admin,
from a plan a person has read.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from dao.base_dao import BaseDAO, clear_cache
from dao.club_dao import CLUBS_CACHE_PATTERN
from dao.ingest_plan import (
    ALIAS,
    UNKNOWN_AGE_GROUP,
    Verdict,
    World,
    action_error,
    build_plan,
    is_approved,
    name_key,
    normalise,
    parse_brackets_input,
    parse_teams_input,
    plan_id_for,
    side_label,
)
from dao.team_dao import TEAMS_CACHE_PATTERN, TeamDAO, like_literal
from dao.team_sides import (
    MISSING,
    RESOLVED,
    WRONG_SIDE,
    Candidate,
    classify,
    league_named,
    sides_at_age,
    team_sides,
    top_level_league,
)

logger = structlog.get_logger()

APPLIED = "applied"
WOULD_APPLY = "would_apply"
ALREADY_APPLIED = "already_applied"
REFUSED = "refused"
SKIPPED = "skipped"
FAILED = "failed"

NOT_APPROVED = "not approved"

# PostgREST returns at most this many rows a request (supabase/config.toml).
_PAGE = 1000

# team_aliases.source says which system a spelling came from; for an alias
# made here that is the plan, by name, so the row can be traced to its review.
ALIAS_SOURCE_PREFIX = "ingest-plan:"


class _SnapshotTeamDAO(TeamDAO):
    """`resolve_tournament_team` over rows read once, instead of per name.

    A tournament is some fifteen hundred names, and the resolver asks the
    database two or three questions about each. Only the two row lookups are
    replaced here — every rule, their order and the side guard are TeamDAO's
    own code — and `found` keeps the teams the last lookup returned, which for
    a name on the wrong side is the team that owns it.
    """

    def __init__(self, teams: list[dict], aliases: list[dict]):
        # Deliberately no BaseDAO.__init__: there is no client to hold.
        self._by_id = {row["id"]: row for row in teams}
        self._by_name: dict[str, list[dict]] = {}
        for row in teams:
            self._by_name.setdefault((row.get("name") or "").casefold(), []).append(row)
        self._aliases: dict[str, list[dict]] = {}
        for row in aliases:
            self._aliases.setdefault((row.get("external_name") or "").casefold(), []).append(row)
        self.found: list[dict] = []

    def _side_rows(self, *, name: str | None = None, ids: list[int] | None = None) -> list[dict]:
        if ids is not None:
            rows = [self._by_id[team_id] for team_id in ids if team_id in self._by_id]
        else:
            rows = list(self._by_name.get((name or "").casefold(), []))
        self.found = rows
        return rows

    def _exact_alias_rows(self, normalized: str) -> list[dict]:
        return list(self._aliases.get(normalized.casefold(), []))

    def _log_unresolved(self, normalized, hint, age_group_id, resolution) -> None:
        """Nothing: a plan reports every unresolved name itself, in one place.

        Ingest's resolver warns once per name per message, which is right for
        a message. Here it would be a warning for each of an event's fifteen
        hundred names, on every plan and every apply.
        """


@dataclass
class _Context:
    """What MT holds at one moment, and the resolver over it."""

    world: World
    league_rows: list[dict]
    resolver: _SnapshotTeamDAO

    def verdict(self, name: str, age_group: str | None, league: str | None) -> Verdict:
        age_group_id = self.world.age_group_id(age_group)
        if age_group_id is None:
            return Verdict(UNKNOWN_AGE_GROUP, reason=f"unknown age group '{age_group or ''}'")
        return self.resolve(name, age_group_id, league)

    def resolve(self, name: str, age_group_id: int | None, league: str | None) -> Verdict:
        self.resolver.found = []
        team, resolution = self.resolver.resolve_tournament_team(name, age_group_id, league, leagues=self.league_rows)
        return Verdict(
            status=resolution.status,
            team_id=team["id"] if team else None,
            reason=resolution.reason,
            candidate_ids=tuple(row["id"] for row in self.resolver.found),
        )


@dataclass
class _Result:
    outcome: str
    detail: str | None = None
    steps: list[str] = field(default_factory=list)
    ids: dict = field(default_factory=dict)


@dataclass
class _Todo:
    """What one action still needs written.

    `steps` are `(description, write)`; each write is handed `ids` and adds
    what it made to it — the club, team, alias and registration ids that are
    the record of what an apply touched. `claims` are run instead of the
    writes in a dry run, to tell later actions what this one would have made.
    """

    steps: list = field(default_factory=list)
    claims: list = field(default_factory=list)
    ids: dict = field(default_factory=dict)


@dataclass
class _Request:
    """One apply request.

    The `pending_*` fields are filled only by a dry run: what earlier actions
    of the request would have created, so that a later action sharing a new
    team, club or alias is judged as the real run — which finds those rows in
    the database — would judge it.
    """

    plan_id: str
    dry_run: bool
    user_id: str | None
    context: _Context | None = None
    current: str | None = None
    pending_teams: dict = field(default_factory=dict)
    pending_clubs: set = field(default_factory=set)
    pending_aliases: dict = field(default_factory=dict)


class _Refused(Exception):
    """An action's precondition does not hold. The text is for the admin."""


class PlanDatabaseError(ValueError):
    """The plan was not made against this database. The text is for the admin."""


class IngestPlanDAO(BaseDAO):
    """Plan, and apply, the teams and aliases a tournament's names need."""

    def __init__(self, connection_holder, *, team_dao, club_dao, ingest_failures_dao):
        super().__init__(connection_holder)
        self.team_dao = team_dao
        self.club_dao = club_dao
        self.ingest_failures_dao = ingest_failures_dao

    def database_fingerprint(self) -> str:
        """A short name for the database this server is connected to.

        A digest of the project URL: an identifier, not a secret, and not the
        URL. A plan carries it so that apply can refuse a plan made against
        another database, where the same ids are different teams and clubs.
        """
        url = (getattr(self.connection_holder, "url", None) or "").strip().rstrip("/").lower()
        return hashlib.sha256(url.encode()).hexdigest()[:12]

    # === Reading ===

    def _all(self, table: str, columns: str) -> list[dict]:
        rows: list[dict] = []
        while True:
            page = (
                self.client.table(table).select(columns).order("id").range(len(rows), len(rows) + _PAGE - 1).execute()
            ).data or []
            rows.extend(page)
            if len(page) < _PAGE:
                return rows

    def _context(self) -> _Context:
        """Every team, alias, club, league, conference and age group, read once."""
        team_rows = self._all("teams", TeamDAO._SIDE_COLUMNS)
        alias_rows = self._all("team_aliases", "id, team_id, league_id, source, external_name")
        league_rows = self.team_dao.league_rows()
        world = World(
            teams=[
                {
                    "id": row["id"],
                    "name": row.get("name"),
                    "club_id": row.get("club_id"),
                    "league_id": row.get("league_id"),
                    "mappings": [
                        (mapping.get("age_group_id"), (mapping.get("divisions") or {}).get("league_id"))
                        for mapping in row.get("team_mappings") or []
                    ],
                }
                for row in team_rows
            ],
            clubs={row["id"]: row.get("name") for row in self._all("clubs", "id, name")},
            leagues={row["id"]: row for row in league_rows},
            divisions=self._all("divisions", "id, name, league_id"),
            age_groups={row["id"]: row.get("name") for row in self._all("age_groups", "id, name")},
        )
        return _Context(world=world, league_rows=league_rows, resolver=_SnapshotTeamDAO(team_rows, alias_rows))

    def _near_matches(self, name: str) -> list[dict]:
        """Teams a person might recognise this name as. Shown, never acted on."""
        result = (self.team_dao.reconcile_names([name]) or [{}])[0]
        if result.get("status") in ("known", "alias"):
            return [{"team_id": result.get("team_id"), "team_name": result.get("team_name"), "via": result["status"]}]
        return [
            {"team_id": row.get("id"), "team_name": row.get("name"), "club_id": row.get("club_id")}
            for row in result.get("similar") or []
        ]

    def plan(self, teams: Any, brackets: Any = None) -> dict:
        """What a tournament's names resolve to, and what to do about the rest.

        Read-only: nothing is written, whatever the input. Raises
        PlanInputError for input it cannot read. Returns
        `{"plan_id", "database", "report", "actions"}`, `database` being the
        fingerprint apply will ask for.
        """
        entries, matches = parse_teams_input(teams)
        bracket_rows = parse_brackets_input(brackets)
        context = self._context()
        verdicts = {entry.key: context.verdict(entry.name, entry.age_group, entry.league) for entry in entries}
        plan = build_plan(entries, matches, verdicts, context.world, bracket_rows, near_matches=self._near_matches)
        plan_id = plan_id_for(plan["actions"], datetime.now(UTC).isoformat())
        logger.info(
            "Ingest plan built",
            plan_id=plan_id,
            entries=len(entries),
            matches=len(matches),
            actions=len(plan["actions"]),
        )
        return {"plan_id": plan_id, "database": self.database_fingerprint(), **plan}

    # === Applying ===

    def apply(
        self,
        plan_id: str,
        actions: list[Any],
        *,
        database: str | None,
        dry_run: bool = False,
        user_id: str | None = None,
    ) -> dict:
        """Ensure each approved action of a reviewed plan. Idempotent.

        `database` is the fingerprint the plan was made against. A plan with
        none, or with another database's, is refused whole (PlanDatabaseError)
        before any action is looked at: its ids name different rows here.

        Every action is then judged on its own: `applied`, `already_applied`,
        `refused` (a precondition no longer holds, or it would duplicate a
        team name), `skipped` (not approved) or `failed`. One refusal does not
        stop the rest. With `dry_run` every check is made and nothing is
        written; what would be written is reported as `would_apply`. An action
        that wrote anything reports the ids it created or touched in `ids`.

        Afterwards, if anything was applied, the teams cache is cleared and
        the open `team` ingest failures for the names just applied are closed
        when they now resolve, with the plan named in the note.
        """
        own = self.database_fingerprint()
        if not database:
            raise PlanDatabaseError(
                "The plan does not say which database it was made against. Plan again with a current mt."
            )
        if database != own:
            raise PlanDatabaseError(
                f"The plan was made against another database ({database}); this one is {own}. Plan again here."
            )

        request = _Request(plan_id=plan_id, dry_run=dry_run, user_id=user_id)
        results: list[dict] = []
        applied: list[dict] = []
        wrote = False
        for index, action in enumerate(actions):
            row = {
                "id": action.get("id") if isinstance(action, dict) else None,
                "type": action.get("type") if isinstance(action, dict) else None,
                "external_name": action.get("external_name") if isinstance(action, dict) else None,
            }
            if not is_approved(action):
                result = _Result(SKIPPED, NOT_APPROVED)
            else:
                error = action_error(action)
                if error:
                    result = _Result(REFUSED, error)
                else:
                    if request.context is None:
                        request.context = self._context()
                    result = self._apply_one(action, request)
            wrote = wrote or result.outcome in (APPLIED, FAILED)
            if result.outcome == APPLIED:
                applied.append(action)
            results.append({**row, "index": index, "outcome": result.outcome, "detail": result.detail})
            if result.steps:
                results[-1]["steps"] = result.steps
            if result.outcome in (APPLIED, FAILED):
                results[-1]["ids"] = result.ids

        closed: list[dict] = []
        if wrote:
            clear_cache(TEAMS_CACHE_PATTERN)
            clear_cache(CLUBS_CACHE_PATTERN)
        if applied:
            closed = self._close_resolved_failures(plan_id, user_id, applied)

        summary = dict.fromkeys((APPLIED, WOULD_APPLY, ALREADY_APPLIED, REFUSED, SKIPPED, FAILED), 0)
        for row in results:
            summary[row["outcome"]] += 1
        logger.info("Ingest plan applied", plan_id=plan_id, dry_run=dry_run, user_id=user_id, **summary)
        return {
            "plan_id": plan_id,
            "dry_run": dry_run,
            "results": results,
            "summary": summary,
            "failures_closed": closed,
        }

    def _apply_one(self, action: dict, request: _Request) -> _Result:
        plan_id = request.plan_id
        try:
            ensure = self._ensure_alias if action["type"] == ALIAS else self._ensure_team
            todo = ensure(action, request)
        except _Refused as exc:
            return _Result(REFUSED, str(exc))
        except Exception:
            logger.exception("Could not check an ingest plan action", plan_id=plan_id, action_id=action.get("id"))
            return _Result(FAILED, "could not check this action")

        if not todo.steps:
            return _Result(ALREADY_APPLIED)
        described = [text for text, _ in todo.steps]
        if request.dry_run:
            # What this action would make, for the actions after it in the request.
            for claim in todo.claims:
                claim()
            return _Result(WOULD_APPLY, steps=described)

        done: list[str] = []
        try:
            for text, write in todo.steps:
                write(todo.ids)
                done.append(text)
        except Exception:
            # Each step is an ensure, so applying the plan again finishes the rest.
            logger.exception(
                "Ingest plan action failed part-way",
                plan_id=plan_id,
                action_id=action.get("id"),
                done=done,
                ids=todo.ids,
            )
            detail = f"stopped after {len(done)} of {len(todo.steps)} steps; apply again to finish"
            return _Result(FAILED, detail, done, todo.ids)
        logger.info(
            "Ingest plan action applied",
            plan_id=plan_id,
            action_id=action.get("id"),
            action_type=action["type"],
            user_id=request.user_id,
            steps=done,
            ids=todo.ids,
        )
        return _Result(APPLIED, steps=done, ids=todo.ids)

    # -- preconditions --

    def _league_id(self, league: str | None, context: _Context) -> int | None:
        if league is None:
            return None
        league_id = league_named(league, context.world.leagues)
        if league_id is None:
            raise _Refused(f"MT has no league named '{league}'")
        return league_id

    def _check_fixes(self, action: dict, context: _Context) -> tuple[int, set[int | None]]:
        """Each entry the action fixes, against the database as it is now.

        Every entry must either still fail the way the plan recorded or
        resolve; anything else refuses the action. Returns how many still
        fail, and the teams the rest now resolve to — for the caller to tell
        "already done" from "done differently by someone else".
        """
        fixes = action.get("fixes") or []
        if not fixes:
            raise _Refused("the action lists no entries it fixes, so there is nothing to check it against")
        resolved_to: set[int | None] = set()
        failing = 0
        for fix in fixes:
            verdict = context.verdict(fix["name"], fix["age_group"], fix.get("league"))
            where = f"'{fix['name']}' ({fix['age_group']}, {side_label(fix.get('league'))})"
            if verdict.status == RESOLVED:
                resolved_to.add(verdict.team_id)
                continue
            expected = fix.get("status")
            if expected not in (WRONG_SIDE, MISSING):
                raise _Refused(f"{where} has no recorded status to check against")
            if verdict.status != expected:
                detail = f" ({verdict.reason})" if verdict.reason else ""
                raise _Refused(f"{where} no longer fails as {expected}: it is now {verdict.status}{detail}")
            failing += 1
        return failing, resolved_to

    def _on_side_at_each_age(self, team: dict, action: dict, side: str, context: _Context) -> None:
        """Refuse unless the team is the resolver's answer for `side` at every age the action fixes.

        The resolver's own guard, one age group at a time: a team registered
        on the other side at that age, or on both, is not a team an alias may
        point that age group's fixtures at — whatever it is at other ages.
        """
        mappings = [
            (mapping.get("age_group_id"), (mapping.get("divisions") or {}).get("league_id"))
            for mapping in team.get("team_mappings") or []
        ]
        leagues = context.world.leagues
        for age_group in sorted({fix["age_group"] for fix in action.get("fixes") or []}):
            age_group_id = context.world.age_group_id(age_group)
            if age_group_id is None:
                raise _Refused(f"MT has no age group '{age_group}'")
            candidate = Candidate(
                team_id=team["id"],
                sides=team_sides(mappings, team.get("league_id"), age_group_id, leagues),
                sides_at_age=sides_at_age(mappings, age_group_id, leagues),
            )
            if classify([candidate], side).status != RESOLVED:
                found = ", ".join(sorted(candidate.sides)) or "no side"
                raise _Refused(
                    f"team {team['id']} ('{team.get('name')}') is not on the {side} side at {age_group}: "
                    f"it is {found} there"
                )

    def _alias_steps(
        self,
        request: _Request,
        name: str,
        league_id: int,
        league: str,
        team_id: int | None,
        target: str,
        describe: str,
        claims: list,
    ) -> list[tuple[str, Any]]:
        """The write that makes `name` an alias in this league, if it is not one.

        `team_id` is None for a team this request has yet to create; the
        write reads the id from the ids gathered by the steps before it.
        `target` names the team for a dry run, where it may have no id yet.
        """
        in_league = {
            row["team_id"] for row in self.team_dao._exact_alias_rows(name) if row.get("league_id") == league_id
        }
        if team_id is not None and in_league == {team_id}:
            return []
        if in_league:
            ids = ", ".join(str(other) for other in sorted(in_league))
            raise _Refused(f"'{name}' is already a {league} alias for team {ids}")
        pending = request.pending_aliases.get((name_key(name), league_id))
        if pending:
            if pending["target"] == target:
                return []
            raise _Refused(f"'{name}' is already made a {league} alias by action {pending['action']} in this plan")
        conflict = self.team_dao.alias_conflict(name, team_id or 0, league_id)
        if conflict:
            raise _Refused(f"'{name}' already reaches team {conflict.get('id')} in {league}")

        def write(ids: dict) -> None:
            row = self.team_dao.add_team_alias(
                ids["team_id"],
                name,
                source=f"{ALIAS_SOURCE_PREFIX}{request.plan_id}",
                kind="feed_variant",
                league_id=league_id,
            )
            ids["alias_id"] = row.get("id")

        claims.append(
            lambda: request.pending_aliases.setdefault(
                (name_key(name), league_id), {"target": target, "action": request.current}
            )
        )
        return [(describe, write)]

    def _ensure_alias(self, action: dict, request: _Request) -> _Todo:
        context = request.context
        request.current = action.get("id")
        name, team_id = normalise(action["external_name"]), action["team_id"]
        league_id = self._league_id(action["league"], context)
        league = context.world.leagues[league_id]["name"]

        rows = self.team_dao._side_rows(ids=[team_id])
        if not rows:
            raise _Refused(f"team {team_id} does not exist")
        team = rows[0]
        if name_key(team.get("name")) != name_key(action["team_name"]):
            raise _Refused(f"team {team_id} is '{team.get('name')}', not '{normalise(action['team_name'])}'")
        self._on_side_at_each_age(team, action, top_level_league(league_id, context.world.leagues), context)

        todo = _Todo(ids={"team_id": team_id})
        steps = self._alias_steps(
            request,
            name,
            league_id,
            league,
            team_id,
            f"team:{team_id}",
            f"alias '{name}' ({league}) → team {team_id}",
            todo.claims,
        )
        if not steps:
            return todo
        failing, resolved_to = self._check_fixes(action, context)
        others = resolved_to - {team_id}
        if others:
            ids = ", ".join(str(other) for other in sorted(others, key=str))
            raise _Refused(f"'{name}' now resolves to team {ids}, not {team_id}")
        if failing:
            todo.steps = steps
        return todo

    def _club(self, action: dict, request: _Request) -> dict | None:
        """The club an action names: the row, or None for one still to create.

        In a dry run a club an earlier action of the request would create is
        returned with no id, as the real run would find it made.
        """
        if action.get("club_id") is not None:
            rows = self.client.table("clubs").select("id, name").eq("id", action["club_id"]).limit(1).execute().data
            if not rows:
                raise _Refused(f"club {action['club_id']} does not exist")
            if name_key(rows[0].get("name")) != name_key(action["club_name"]):
                raise _Refused(
                    f"club {action['club_id']} is '{rows[0].get('name')}', not '{normalise(action['club_name'])}'"
                )
            return rows[0]
        wanted = normalise(action["new_club_name"])
        rows = (self.client.table("clubs").select("id, name").ilike("name", like_literal(wanted)).execute().data) or []
        rows = [row for row in rows if name_key(row.get("name")) == name_key(wanted)]
        if rows:
            return rows[0]
        if name_key(wanted) in request.pending_clubs:
            return {"id": None, "name": wanted}
        return None

    def _placement_ids(self, action: dict, league_id: int | None, context: _Context) -> list[tuple[int, int, str]]:
        """Each placement as (age group id, division id, description).

        A conference MT does not have refuses the action: it is never created
        here. So does one on the other side — a registration there is what
        makes a team answer to both.
        """
        placements = action.get("placements") or []
        if placements and league_id is None:
            raise _Refused("a team with no league cannot be placed in a conference")
        side = top_level_league(league_id, context.world.leagues)
        found = []
        for placement in placements:
            where = f"{placement['league']} {placement['conference']} ({placement['age_group']})"
            placed_league = league_named(placement["league"], context.world.leagues)
            if placed_league is None:
                raise _Refused(f"MT has no league named '{placement['league']}'")
            if top_level_league(placed_league, context.world.leagues) != side:
                raise _Refused(f"{where} is not a {side} conference")
            division = next(
                (
                    row
                    for row in context.world.divisions
                    if row.get("league_id") == placed_league
                    and name_key(row.get("name")) == name_key(placement["conference"])
                ),
                None,
            )
            if division is None:
                raise _Refused(f"MT has no conference '{placement['conference']}' in {placement['league']}")
            age_group_id = context.world.age_group_id(placement["age_group"])
            if age_group_id is None:
                raise _Refused(f"MT has no age group '{placement['age_group']}'")
            if (age_group_id, division["id"], where) not in found:
                found.append((age_group_id, division["id"], where))
        return found

    def _ensure_team(self, action: dict, request: _Request) -> _Todo:
        context = request.context
        request.current = action.get("id")
        plan_id = request.plan_id
        team_name, external_name = normalise(action["team_name"]), normalise(action["external_name"])
        league_id = self._league_id(action.get("league"), context)
        league = context.world.leagues[league_id]["name"] if league_id is not None else None
        if league_id is not None and context.world.leagues[league_id].get("parent_league_id") is not None:
            side = top_level_league(league_id, context.world.leagues)
            raise _Refused(f"{league} is not a top-level league: a team's league is its side, {side}")
        wants_alias = name_key(team_name) != name_key(external_name)
        if wants_alias and league_id is None:
            raise _Refused("a team with no league cannot take a league-scoped alias: name it as the feed does")

        placements = self._placement_ids(action, league_id, context)
        club = self._club(action, request)
        club_key = (
            ("id", club["id"]) if club and club["id"] is not None else ("new", name_key(action.get("new_club_name")))
        )
        existing = self.team_dao._side_rows(name=team_name)
        if len(existing) > 1:
            ids = ", ".join(str(row["id"]) for row in existing)
            raise _Refused(f"the name '{team_name}' is already taken by teams {ids}")
        failing, resolved_to = self._check_fixes(action, context)

        todo = _Todo()
        pending = request.pending_teams.get(name_key(team_name))
        if existing:
            team = existing[0]
            if club is None or team.get("club_id") != club["id"] or team.get("league_id") != league_id:
                raise _Refused(f"the name '{team_name}' is already taken by team {team['id']}")
            # The same team in the same club and league: this action's own,
            # from an earlier apply — if what it fixes agrees. A name that now
            # resolves to some other team is not this action's to move.
            others = resolved_to - {team["id"]}
            if others:
                ids = ", ".join(str(other) for other in sorted(others, key=str))
                raise _Refused(f"'{external_name}' now resolves to team {ids}, not to '{team_name}' ({team['id']})")
            todo.ids.update(club_id=club["id"], team_id=team["id"])
            target = f"team:{team['id']}"
            registered = {
                (mapping.get("age_group_id"), mapping.get("division_id"))
                for mapping in self.client.table("team_mappings")
                .select("age_group_id, division_id")
                .eq("team_id", team["id"])
                .execute()
                .data
                or []
            }
        elif pending:
            # A dry run: an earlier action of this request would have made it.
            if pending["club"] != club_key or pending["league_id"] != league_id:
                raise _Refused(
                    f"the name '{team_name}' is already taken by the team action {pending['action']} creates"
                )
            if resolved_to:
                raise _Refused(f"'{external_name}' now resolves without this team")
            target = f"new:{name_key(team_name)}"
            registered = pending["registered"]
        else:
            if resolved_to:
                raise _Refused(f"'{external_name}' now resolves without this team")
            target = f"new:{name_key(team_name)}"
            registered = set()
            if club is None:
                club_name = normalise(action["new_club_name"])

                def create_club(ids: dict) -> None:
                    created = self.club_dao.create_club(
                        name=club_name, city="", description=f"Created by mt ingest plan {plan_id}"
                    )
                    ids.update(club_id=created["id"], club_created=True)

                todo.steps.append((f"create club '{club_name}'", create_club))
                todo.claims.append(lambda: request.pending_clubs.add(name_key(club_name)))
            elif club["id"] is not None:
                todo.ids["club_id"] = club["id"]

            def create_team(ids: dict) -> None:
                row = {"name": team_name, "club_id": ids["club_id"], "league_id": league_id}
                created = self.client.table("teams").insert(row).execute().data
                if not created:
                    raise RuntimeError("team insert returned no row")
                ids.update(team_id=created[0]["id"], team_created=True)
                # Names are looked up through the cache; the next action must see this one.
                clear_cache(TEAMS_CACHE_PATTERN)

            todo.steps.append((f"create team '{team_name}' ({league or 'no league'})", create_team))
            claimed = {"club": club_key, "league_id": league_id, "action": action.get("id"), "registered": set()}
            todo.claims.append(lambda: request.pending_teams.setdefault(name_key(team_name), claimed))
            pending = claimed

        for age_group_id, division_id, where in placements:
            if (age_group_id, division_id) in registered:
                continue

            def register(ids: dict, age_group_id: int = age_group_id, division_id: int = division_id) -> None:
                self.team_dao.ensure_team_mapping(ids["team_id"], age_group_id, division_id)
                found = (
                    self.client.table("team_mappings")
                    .select("id")
                    .eq("team_id", ids["team_id"])
                    .eq("age_group_id", age_group_id)
                    .eq("division_id", division_id)
                    .limit(1)
                    .execute()
                ).data
                # ensure_team_mapping never raises; a row that is not there is the failure.
                if not found:
                    raise RuntimeError("team mapping was not written")
                ids.setdefault("mapping_ids", []).append(found[0]["id"])

            todo.steps.append((f"register in {where}", register))
            if pending:
                # For a dry run: a later action sharing the team does not register it twice.
                todo.claims.append(lambda key=(age_group_id, division_id): pending["registered"].add(key))

        if wants_alias:
            todo.steps += self._alias_steps(
                request,
                external_name,
                league_id,
                league,
                todo.ids.get("team_id"),
                target,
                f"alias '{external_name}' ({league}) → '{team_name}'",
                todo.claims,
            )
        return todo

    # -- afterwards --

    def _close_resolved_failures(self, plan_id: str, user_id: str | None, applied: list[dict]) -> list[dict]:
        """Close the open `team` failures for the names just applied, if they now resolve.

        Only rows for an applied action's own name and league: a row this
        request did not fix is not this plan's to close. A failure row carries
        no age group of its own; the one in its sample match is used, and a
        row whose sample has none is left open — without an age group the
        resolver cannot say what ingest would do. Read after the writes, from
        the database as it now is.
        """
        try:
            names = {(name_key(action["external_name"]), name_key(action.get("league"))) for action in applied}
            open_rows = [
                row
                for row in self.ingest_failures_dao.open_failures(limit=_PAGE, kinds=["team"])
                if row.get("kind") == "team" and (name_key(row.get("raw_name")), name_key(row.get("league"))) in names
            ]
            if not open_rows:
                return []
            context = self._context()
            closed = []
            for row in open_rows:
                age_group_id = _sample_age_group_id(row.get("sample"), context.world)
                if age_group_id is None:
                    continue
                verdict = context.resolve(row.get("raw_name") or "", age_group_id, row.get("league"))
                if verdict.status != RESOLVED:
                    continue
                done = self.ingest_failures_dao.resolve_by_id(row["id"], resolved_by=user_id, note=f"plan {plan_id}")
                if done:
                    closed.append(
                        {
                            "id": row["id"],
                            "raw_name": row.get("raw_name"),
                            "league": row.get("league"),
                            "team_id": verdict.team_id,
                        }
                    )
            return closed
        except Exception:
            # The teams and aliases are written; a failure row left open closes
            # itself the next time ingest sees the name.
            logger.exception("Could not close resolved ingest failures", plan_id=plan_id)
            return []


def _sample_age_group_id(sample: str | None, world: World) -> int | None:
    """The age group of a failure's sample match, or None if it names none.

    Ingest writes the sample as "Home vs Away, 2026-12-02 U15", then the
    resolver's reason in square brackets.
    """
    text = (sample or "").split(" [")[0].split()
    return world.age_group_id(text[-1]) if text else None
