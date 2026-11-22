# Planning a tournament's teams: `mt ingest plan` / `mt ingest apply`

Tournament ingest never creates a team. A name it cannot place on the
message's side becomes an `ingest_failures` row and the match waits
([Which team a name means](match-scraper.md#which-team-a-name-means)). That is
deliberate — silent creation is how a duplicate IFA once appeared — but an
event the size of MLS NEXT Fest names hundreds of teams MT does not hold on
the right side, most of them a club's Academy team that MT only has as its
Homegrown team.

`mt ingest plan` and `mt ingest apply` are the reviewed bulk step (SB-1763):

1. **Plan** — read-only. Put every name the tournament uses through the
   resolver ingest uses, report what resolves, and write the proposed aliases
   and teams to a plan file.
2. **Review** — a person reads the file and marks the actions to apply
   `approved`. The file is the provenance record: commit it.
3. **Apply** — admin only, idempotent. The server re-checks every approved
   action and ensures its rows. What each action created is written to an
   applied log beside the plan: commit that too.

**Ingest calls none of this.** A team is only ever created from a plan a
person has read.

```bash
match-scraper-agent scrape-event --event 75 --json > fest-2026.json   # dry run, in match-scraper
mt ingest plan --teams fest-2026.json --brackets brackets.json -o fest-2026-plan.json
# review fest-2026-plan.json: set "status": "approved" on what should be applied
mt ingest apply fest-2026-plan.json --dry-run
mt ingest apply fest-2026-plan.json
```

Both are ordinary `mt` commands: `--env` and the "→ prod" announcement work
as for every other command.

**Never run two applies at the same time**, of the same plan or of different
ones. The database does not enforce that team names or club names are unique
without regard to case, nor that a name has one alias per league; apply
checks each of those and then writes, and two applies checking at once can
both pass and create duplicates. One person, one apply, wait for it to end.

## Inputs

### `--teams`

A JSON list. Each item is either:

- **a scraper message**, as `match-scraper-agent scrape-event --json` prints
  them. Read from it: `home_team`, `away_team`, `age_group`, `league`
  (`Homegrown`, `Academy`, or absent) and `competition`. Every other field is
  ignored, and is not sent to the server.
- **a hand-made entry**: `{"name": "...", "age_group": "U15", "league": "Academy"}`,
  `league` optional.

The two can be mixed. The plan works on the distinct *(name, age group,
league)* entries, compared without case or extra whitespace. Only messages
give a "matches that would land" count; a list of names has no matches, and
the report says so rather than printing zero.

### `--brackets` (optional)

Which conference each team plays its league season in — the league standings
brackets:

```json
[
  {"league": "Academy", "conference": "New England", "age_group": "U15",
   "teams": ["FC Greater Boston Bolts", "IFA"]}
]
```

`league` and `conference` are matched **by name** to MT's leagues and
divisions; a conference is looked up inside its own league (Homegrown
`Florida` and Flex `Florida` are different rows). A league, conference or age
group MT does not have is listed in the report as a bracket not used. It is
never created.

Without the file, or for a team no bracket names, a created team is
**unplaced**: see [What a created team gets](#what-a-created-team-gets). The
scraper-side exporter for this file is not built yet; the format is fixed
here so it can be.

## The report

Per side — `Homegrown`, `Academy`, `no hint` — every entry is exactly one of:

| Count | Meaning |
|-------|---------|
| `resolved` | ingest will find the team |
| `ambiguous` | more than one team could be meant; listed with the resolver's reason. **No action is proposed** — fix the registration |
| `missing` | the resolver's `wrong side` and `missing` together, split three ways below |
| `unknown_league` / `unknown_age_group` | the message's league or age group is not one MT has; ingest drops the match |

`missing` is split by what would fix it:

| Split | Meaning |
|-------|---------|
| `alias_fixable` | the team exists on this side under another name; an alias fixes it |
| `needs_create` | no team for it on this side; a team has to be created |
| `unknown` | nothing is proposed: a placeholder (`TBD`, a select side such as `East AD One`), or a team by that name registered nowhere |

`resolver` carries the raw `wrong_side` / `missing` counts, for comparing with
`ingest_failures` reasons.

Also reported:

- **Matches that would land** — both teams resolve — now, and if every action
  in the plan were applied.
- **Conference placed** — per league and conference, how many teams to create
  were found in a bracket, and how many are unplaced.

"Resolved" here is what ingest will do, not an approximation of it: the plan
classifies each entry with `TeamDAO.resolve_tournament_team` itself, over the
teams and aliases read once instead of once per name.

## The plan file

```json
{
  "plan_id": "plan-20261122T212938-24830cbf",
  "generated_at": "2026-11-22T21:29:38+00:00",
  "generated_by": "tom",
  "environment": "local",
  "database": "<12-character fingerprint>",
  "inputs": {"teams": "fest-2025.json", "brackets": null},
  "review": "Nothing here is applied as generated. Set \"status\" to \"approved\" …",
  "report": { "…": "as above" },
  "actions": [
    {
      "id": "a085",
      "type": "alias",
      "status": "proposed",
      "reason": "'FC Greater Boston Bolts' is team 17 on the other side; FC Greater Boston Bolts has one Academy team, 'FC Greater Boston Bolts Academy' (178).",
      "external_name": "FC Greater Boston Bolts",
      "league": "Academy",
      "team_id": 178,
      "team_name": "FC Greater Boston Bolts Academy",
      "candidates": [{"team_id": 178, "team_name": "FC Greater Boston Bolts Academy", "registered_age_groups": ["U13", "U14"]}],
      "fixes": [
        {"name": "FC Greater Boston Bolts", "age_group": "U17", "league": "Academy", "status": "wrong_side"},
        {"name": "FC Greater Boston Bolts", "age_group": "U19", "league": "Academy", "status": "wrong_side"}
      ]
    },
    {
      "id": "a007",
      "type": "create_team",
      "status": "proposed",
      "reason": "'Ironbound Soccer Club' is team 33 on the other side; Ironbound Soccer Club has no Academy team.",
      "external_name": "Ironbound Soccer Club",
      "league": "Academy",
      "club_id": 159,
      "club_name": "Ironbound Soccer Club",
      "new_club_name": null,
      "team_name": "Ironbound Soccer Club Academy",
      "age_groups": ["U13", "U14", "U15", "U16", "U17", "U19"],
      "placements": [],
      "fixes": [{"name": "Ironbound Soccer Club", "age_group": "U13", "league": "Academy", "status": "wrong_side"}]
    }
  ]
}
```

`environment` is the `mt` environment the plan was made in, for people.
`database` is a fingerprint the **server** computed from the database it is
connected to (a digest of the project URL — an identifier, not a secret, and
not the URL). Apply sends it back and the server refuses the whole plan if it
is missing or is not its own: team and club ids are per database, so a plan
made against one names different rows in another. Neither field may be
removed; a plan without them is refused, not trusted.

Every action carries a `status`, a human-readable `reason`, and `fixes` — the
entries it would make resolve, each with the way it fails today. `fixes` is
what apply checks against, so leave it alone: an action with no `fixes`, or
with `fixes` for some other name than its `external_name`, is refused.

An id never travels alone. `team_id` comes with `team_name` and `club_id`
with `club_name`, and apply refuses an action whose id is, in the database,
a team or club by another name. Change one, change the other.

### `alias`

`{external_name, league, team_id}`: make the feed's name mean this team **in
this league**. A league-scoped alias is rule 1 of the resolver and is trusted
as it stands, at every age group.

Proposed when the name belongs to a team on the other side, and the **same
club** has a team on the hinted side.

- Exactly one such team → `proposed`.
- More than one (a club with several Academy teams) → `needs_review`, with
  `team_id` null and the `candidates` listed with the age groups each is
  registered at. Pick one, set `team_id` **and** `team_name`, then approve.
- `needs_review` too if the name already resolves on that side at another age
  group: the alias would move that one as well.

### `create_team`

`{club_id | new_club_name, team_name, league, external_name, placements,
age_groups}`.

- **The club exists only on the other side** → its Academy team is proposed
  as `<Club> Academy`, the existing convention (`IFA Academy`,
  `FC Greater Boston Bolts Academy`). `proposed` when that name is free;
  `needs_review` when it is taken, when the club's own name already ends in
  "Academy", when the team that owns the name has no club, or when the side
  is Homegrown (there is no naming convention for that).
- **The name is entirely unknown** → a new club and a team under the feed's
  own name, **always `needs_review`**, with `near_matches`: teams sharing a
  significant word. They are evidence for the reviewer and are never acted
  on. If one is the same club under another spelling, rewrite the action as
  an `alias` to it (`"type": "alias"`, `"team_id": …`, `"team_name": …`)
  rather than creating a second team.
- **Two actions proposing the same new team name, or the same new club** →
  the later one is `needs_review` and names the action it clashes with.
  Applied as they stand, the second shares the first one's row if the club
  and league are the same, and is refused if they are not.

A created team's `league` is always its **side** — `Homegrown` or `Academy`,
never a child league such as `Flex`; apply refuses anything else, so
`teams.league_id` always says which side a team is on. A name the feed sends
as `Flex` is planned as a Homegrown team, for review.

Team names stay globally unique, without regard to case — `get_team_by_name`
returns one row, so a duplicate name makes league resolution
nondeterministic. That is why the new team gets its own stored name plus a
league-scoped alias from the feed's name, instead of a second team called
the same thing.

`placements` is a list of `{age_group, league, conference}`, from the
brackets input: the team's home conference at each age group the tournament
names it at. `age_groups` is every age group the feed uses the name at, for
the reviewer; it creates nothing.

### Reviewing

A freshly generated plan applies **nothing**. Only `"status": "approved"` —
exactly that word — is applied; `proposed` and `needs_review` are both
skipped, and `mt ingest apply` says how many were. Approving is editing the
file. Editing other fields is expected for `needs_review` actions (a
`team_id`, a `club_id`, a better `team_name`); the server checks whatever it
is sent.

## Applying

```bash
mt ingest apply fest-2026-plan.json --dry-run   # every check, no write
mt ingest apply fest-2026-plan.json
```

Each action is judged on its own and one refusal does not stop the rest:

| Outcome | Meaning |
|---------|---------|
| `applied` | its rows were written; `ids` lists what it created or touched |
| `would_apply` | `--dry-run`: it passed every check; the steps it would take are listed |
| `already_applied` | everything it asks for is already there — applying a plan twice changes nothing |
| `refused` | a precondition no longer holds, or it would duplicate a team name; the reason is given |
| `skipped` | not approved |
| `failed` | a write failed part-way; every step is an "ensure", so apply again to finish |

The command exits non-zero if anything was refused or failed.

Before any action is looked at, the server compares the plan's `database`
fingerprint with its own and refuses the whole request — a dry run included —
if it is missing or different.

Then, for each approved action, against the database as it is at that moment:

- every entry in `fixes` still fails the way the plan recorded (`wrong_side`
  or `missing`). If the name now resolves, or fails differently, the plan is
  stale: plan again;
- an alias's `team_id` still exists **and is still the team `team_name`
  says**; that team is the one the resolver would pick for the alias's side
  **at each age group in `fixes`** — a team on the other side at that age, or
  registered on both sides at it, is refused whatever it is at other ages;
  the name is not already an alias for a different team in that league, and
  does not already reach another team there (`alias_conflict`);
- a new team's name is still free, and its `league` is a top-level league. A
  team by that name in the same club and league is taken to be this action's
  own, from an earlier apply — but only if every entry in `fixes` either
  still fails as recorded or already resolves to *that* team. If the name now
  resolves to any other team the action is refused: nothing is aliased to,
  or registered on, a team the action did not make;
- `club_id` still exists and is still the club `club_name` says; every
  placement's league, conference and age group exist, and the conference is
  on the team's own side.

Afterwards, **if anything was applied**: the teams cache is cleared, and the
open `team` rows in `ingest_failures` for the names just applied — same name,
same league — are closed when they now resolve, through the same path as
`mt ingest resolve`, with the note `plan <plan_id>`. A row for any other name
is left alone, and so is a row whose sample names no age group: without one
the resolver cannot say what ingest would do.

### A long plan

A real apply is sent **10 actions at a time**, each batch reported as it
returns, with a 3-minute timeout per request. If a batch does not come back —
a timeout, a dropped connection, a 5xx — the command says which batch, how
many completed before it, and stops. **The interrupted batch may have been
partly applied**: the server carries on after the client stops waiting. Run
the same command again. Apply is idempotent, so what is there is reported as
`already_applied` and the rest is finished.

A dry run is one request, so that two actions sharing a new club or team are
judged together, the way the real run — which finds the first one's rows in
the database — judges them.

### The applied log

Each batch that wrote anything is appended to `<plan>.applied.json` beside
the plan file (`fest-2026-plan.json` → `fest-2026-plan.applied.json`), saved
after every batch:

```json
{
  "plan_id": "plan-20261122T212938-24830cbf",
  "environment": "local",
  "database": "<12-character fingerprint>",
  "batches": [
    {
      "batch": 1,
      "applied_at": "2026-11-22T21:40:02+00:00",
      "actions": [
        {"id": "a007", "type": "create_team", "external_name": "Ironbound Soccer Club", "outcome": "applied",
         "ids": {"club_id": 159, "team_id": 1130, "team_created": true, "alias_id": 12, "mapping_ids": [2701]},
         "steps": ["create team 'Ironbound Soccer Club Academy' (Academy)", "…"]}
      ],
      "failures_closed": [{"id": 41, "raw_name": "Ironbound Soccer Club", "league": "Academy", "team_id": 1130}]
    }
  ]
}
```

`ids` holds `team_id` and `club_id` (with `team_created` / `club_created`
when this action made them, rather than found them), `alias_id` and
`mapping_ids`. `teams` and `team_mappings` have no creator column, so **this
file is the only complete record of which rows a plan made**. Commit it with
the plan. A `failed` action is logged too, with the ids of the steps that
did run.

### What a created team gets

| Row | Value |
|-----|-------|
| `teams` | the new name, the club, and `league_id` = the side's league. `division_id` is left null |
| `team_mappings` | one row per placement — **only** its home conference, at the age groups the brackets name it at |
| `team_aliases` | the feed's name → the team, scoped to the league, `source` = `ingest-plan:<plan_id>` |
| `clubs` | only for an unknown name: a new club, `description` naming the plan |

A team that could not be placed gets **no `team_mappings` row at all**. It
still resolves — `teams.league_id` gives it a side — but it is in no
age-group or division picker, since those read `team_mappings`, and in no
league table, since those are built from the matches filed to a division. It
is never given a null-division registration, which is what
`get_or_create_opponent_team` writes and what put tournament opponents into
age-group pickers.

Provenance: the alias's `source` names the plan, a new club's `description`
names it, the applying admin is logged with the plan id and the ids for each
action, and the applied log holds every id. `teams` has no creator column.

## Undoing a plan

**There is no undo command.** Undoing is deleting the rows a plan made, by
hand, from the record of what it made.

### What a plan writes, and where each is recorded

| Written | How to find it afterwards |
|---------|---------------------------|
| `team_aliases` rows | `source = 'ingest-plan:<plan_id>'`; `alias_id` in the applied log |
| `teams` rows | `team_id` with `"team_created": true` in the applied log. Nothing on the row says so |
| `team_mappings` rows | `mapping_ids` in the applied log. Nothing on the row says so |
| `clubs` rows (unknown names only) | `description = 'Created by mt ingest plan <plan_id>'`; `club_id` with `"club_created": true` in the applied log |
| closed `ingest_failures` rows | `resolution_note = 'plan <plan_id>'`; `failures_closed` in the applied log |

The server also logs one `Ingest plan action applied` line per action, with
the plan id, the admin's user id and the same ids — the fallback if the
applied log is lost. Only ids marked `team_created` / `club_created` are
this plan's to delete; an id without the flag is a row the plan found.

### The hazard: deleting a team deletes its matches

`matches.home_team_id` and `away_team_id` are `ON DELETE CASCADE`, and so
are a team's players, lineups, follows and manager assignments. Once ingest
has filed matches on a created team, deleting the team **deletes those
matches**.

So a wrong team must be fixed **before ingest files matches on it** — which
is why the plan is applied, and checked, before the event is submitted. Count
first:

```sql
select count(*) from matches where home_team_id = <id> or away_team_id = <id>;
```

If that is not zero, do not delete. **Repoint instead**: delete the plan's
alias so the name fails again, plan again, and approve an `alias` action
pointing at the right team (`mt team alias add` cannot do this — it makes
aliases with no league). Then move or re-scrape the matches, and delete the
wrong team only when nothing references it.

### Order

For a team with no matches, from the applied log:

1. the **alias** (`alias_id`) — the feed's name stops resolving to the team,
   so ingest cannot file anything new on it while the rest is removed;
2. the **registrations** (`mapping_ids`);
3. the **team** (`team_id`, only if `team_created`);
4. the **club** (`club_id`, only if `club_created`, and only once it has no
   teams — the foreign key refuses otherwise);
5. clear the teams cache: `DELETE /api/admin/cache`.

The closed `ingest_failures` rows need nothing: with the alias gone the name
fails again, and the next message for it reopens the row.

## API

Both admin only — not service accounts.

| Endpoint | |
|----------|-|
| `POST /api/admin/ingest-plan` | body `{teams, brackets}`; read-only (a POST because the input is large); returns `{plan_id, database, report, actions}` |
| `POST /api/admin/ingest-plan/apply` | body `{plan_id, database, actions, dry_run}`; returns `{results, summary, failures_closed}`; `409` if `database` is missing or is not this server's |

Code: the rules are pure, in `backend/dao/ingest_plan.py`; the database side
is `backend/dao/ingest_plan_dao.py`.
