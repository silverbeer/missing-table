# Featured matches: Match of the Week and Match of the Day

Two editorial picks, one table each. Both are admin-picked today; agent suggestions
(SB-1545 for MOTW, SB-1562 for Match of the Day) post to Slack for approval and then
call the same admin endpoints.

| | Match of the Week (SB-1010) | Tournament Match of the Day (SB-1559) |
|---|---|---|
| Table | `match_of_the_week` | `tournament_match_of_the_day` |
| One pick per | calendar week (Monday start), pool and age group (SB-1638) | tournament **and** day |
| Uniqueness | `UNIQUE(week_start, pool, age_group_id)` | `UNIQUE(tournament_id, match_date)` |
| Key derived from | the match's date → its Monday; its age group; its division → pool | the match's own date |
| Extra fields | `blurb`, `reasons` (SB-1552) | `blurb`, `reasons` |
| Read | `GET /api/motw?week_start=&age_group_id=&pool=` | `GET /api/tournaments/{id}/motd?date=` |
| Write | `POST /api/admin/motw` | `POST /api/admin/tournaments/{id}/motd` |
| Clear | `DELETE /api/admin/motw/{week_start}?age_group_id=&pool=` | `DELETE /api/admin/tournaments/{id}/motd/{date}` |

They are separate tables on purpose: MOTW's slot uniqueness and its pick ordinal
("Week 6") would both have to loosen to admit tournament rows.

## Rules both follow

- **No pick is `200` with `null`, never `404`.** Most weeks and days start unpicked.
- **The slot comes from the match, not from today.** Picking a future fixture fills its
  own week or day instead of overwriting the current one.
- **Re-picking is an upsert that replaces the whole pick.** Fields you omit on a re-pick
  are cleared, not kept — with one exception: MOTW `reasons` (below).
- **`reasons` is a list of `{text, kind}`, at most 6.** `null` = never provided, `[]` =
  provided and empty; the database keeps them distinct (MOTW enforces "array or null"
  with a CHECK). On screen both render no "Why" list.
- **A pick whose match the viewer cannot see reads as no pick** (a test match picked by
  an admin, read by a visitor).
- **`selected_by` is provenance, not a foreign key**, so deleting an admin does not erase
  editorial history.

## Match of the Week specifics

- **One pick per slot (SB-1638).** A slot is (week, pool, age group). Pool `main` is
  Homegrown Northeast League plus Flex Empire, New England and Turnpike, U15/U16/U17/U19;
  pool `pathway` is the Northeast Pro Player Pathway, U16/U17/U19. That makes 7 picks a
  week. SB-1010 started with one global pick; the product changed to one per age group.
  A match's pool comes from its division name (`pool_for_match`), as the migration's
  backfill does.
- **`GET /api/motw`** returns `picks` (every slot's pick, main pool first, then by age
  group) and `motw`: the slot named by `age_group_id` and `pool`, or with no age group
  the week's first pick, which is what apps released before SB-1638 show.
- **The pick ordinal counts within the slot**: U16's "Week 3" is the third U16 pick.

- **Omitted `reasons` on a re-pick of the same match keeps them** (SB-1552). The hero's
  blurb editor re-posts `{match_id, blurb}`, and must not wipe a "Why" list the agent
  or an admin wrote. Picking a *different* match for the week clears them: another
  match's reasons are wrong for this one. Send `reasons: null` to clear explicitly.
- `MotwHero` shows the reasons under the blurb as "Why this is the Match of the Week",
  only once the strip is opened. The same list (`MotwReasons.vue`) shows on the match
  detail page when that match is the pick, so "Preview" keeps it (SB-1577).
- **Kinds** (`utils/featuredReasons.js`): `standings` 📊, `form` 🔥, `stakes` 🏆,
  `rivalry` ⚔️, `storyline` 📖. `kind` is free text on the API, so an unknown kind
  gets the default ▸ marker rather than an error.
- **Admins edit reasons in place** (`MotwReasonsEditor.vue`): add, remove, reorder,
  max 6, 200 chars each. Save re-POSTs `{match_id, blurb, reasons}` — the blurb rides
  along, since omitting it would clear it. Removing every row saves `[]`, not `null`.

### Suggesting candidates (SB-1550)

`backend/mt_tools/motw_candidates.py` ranks a week's fixtures for the pick. Pure scoring
functions plus one gathering function, `suggest_motw_candidates(deps, week, picks=...)`,
over the MT AI `ToolDeps` protocols and public data only.

- **Pools** (`POOLS`): `main` is Homegrown Northeast League and Flex Empire, New England
  and Turnpike, U15-U19 (SB-1635); `pathway` is Northeast (Pro Player Pathway) League,
  U16/U17/U19. `age_group` narrows a run to one slot; the slot's own pick is
  `current_pick`, and only that slot's earlier picks count as recently featured.
  Eligible: status scheduled/tbd, dated in the week and not before today (New York
  time). A pool name MT does not have is an error, never a smaller pool.
- **Score** = 0.40 quality + 0.25 closeness + 0.20 stakes + 0.15 form, ×0.5 when a team
  was in either of the last two picks. Strength is a team's percentile in the fixture's
  own table (PPG and GD per game), so tables of different ages compare; under 3 games it
  is damped towards 0.5 and flagged `low_sample`. Stakes: adjacent, top of table, or both
  in contention at a rank a **qualification rule** selects. Only a Flex conference table
  has such a line (conference winner); the Northeast table has none, because no source
  ties a league finish to a Cup place. Form: last five League/Flex results at that age.
- **History is per age group.** A team row is a club in a league and plays every age,
  so IFA U16's results must not leak into IFA U15's form.
- **Facts**: ids `<match_id>:<slug>` for position, points gap, streaks, scoring rate,
  last meeting, common opponents, games left and each applicable rule (unconfirmed
  rules are prefixed "Unconfirmed:"). Every reason the agent writes cites one. No player
  facts: goals are user data.
- **Coverage**: fixtures in the week, how many were eligible, and how many teams had too
  few games. An empty week is `candidates: []` with a `reason`; a failed read is an
  `error`, never an empty list. An existing pick is returned as `current_pick`.
- **Where to get them** (SB-1551): mt-mcp tool `suggest_motw_candidates(week, limit)`
  (read tier, so the sb-agents MOTW agent's public account can call it), the admin API
  `GET /api/admin/motw/candidates?week=&limit=`, and `mt motw suggest [--week] [--facts]
  [--json]`. All three return the same result.

## Match of the Day specifics

- The match must belong to the tournament (`matches.tournament_id`), else **400**. An
  optional `match_date` in the body guards against picking a match from the wrong day.
- `GET` without `date` returns every pick as `picks`, oldest first, so the tournament
  page chooses "today" in the viewer's timezone. Tournaments have no timezone column,
  and Fest (Mesa, `America/Phoenix`) is 2–3 hours behind most viewers.
- `reasons` is the "Why this is the Match of the Day" list: up to 6 items of
  `{text, kind}`. `null` means never provided; `[]` means provided and empty. The
  distinction is kept in the data; on screen both render no "Why" list.

### On the tournament page (SB-1560)

`TournamentMatchCenter` fetches `GET /api/tournaments/{id}/motd` alongside the
tournament, and again on each refresh. Picks are decoration: a failed fetch is
logged and the page renders as if there were none.

- **Banner** (`TournamentMotdBanner.vue`): today's pick only, where "today" is the
  viewer's local date (`localDateKey`), shown above every view (list, bracket,
  standings). No pick for today renders nothing — no placeholder. The score comes
  from the tournament's own copy of the match, which realtime keeps current; an
  unplayed match shows "vs", never 0–0.
- **List**: every picked match (any day) carries an amber `◆ Match of the Day` chip.
- **Bracket**: every picked match gets an amber ring.

## Picking by hand

```bash
mt tournament motd show  -T 12                 # every pick in tournament 12
mt tournament motd show  -T 12 -d 2026-12-04   # one day
mt tournament motd set   -T 12 -m 501 -b "Northeast leaders meet in the desert" \
                         -r "Both unbeaten in league play" -r "First ever meeting"
mt tournament motd clear -T 12 -d 2026-12-04
```

`set` accepts `--date` as a guard: it refuses if the match is on a different day.

## The MOTW agent's account (SB-1553)

The automated Match of the Week flow (sb-agents: motw-agent suggests, sb-support writes
the approved pick) authenticates as a **service account** with one permission,
`manage_motw`:

- `POST /api/admin/motw` accepts admins and service accounts holding `manage_motw`
  (`auth.require_motw_editor`). Everything else stays admin-only: `DELETE
  /api/admin/motw/{week}`, every other `/api/admin/*` route (they check
  `role == "admin"`, which a service account never has), and match management (which
  needs `manage_matches`).
- Provenance: a service account has no user row, so its pick records
  `selected_by_service` (e.g. `motw-agent`) with `selected_by` null. An admin pick sets
  `selected_by` and clears `selected_by_service`.
- The token is a service-account JWT, not revocable before it expires. Keep the expiry
  short and rotate by minting a new one. Mint it in a human terminal with prod's
  `SERVICE_ACCOUNT_SECRET` in the environment, save it to the 1Password `agents` vault
  as item `mt-motw-agent` (field `token`), then delete the file:

```bash
cd backend && umask 077 && uv run python scripts/utilities/create_service_account_token.py \
  --service-name motw-agent --permissions manage_motw --expires-days 180 \
  --output-file /tmp/mt-motw-agent.token
# copy into 1Password, then: rm /tmp/mt-motw-agent.token
```

  sb-agents reads it as `MT_MOTW_TOKEN` from `op://agents/mt-motw-agent/token`.

## Seeing the ranking

```bash
scripts/motw.sh test                    # scoring unit tests, no network
scripts/motw.sh rank                    # this checkout's ranking on prod data, read-only
scripts/motw.sh rank --week 2026-11-16 --top 10
scripts/motw.sh rank --rematches        # only fixtures flagged rematch
scripts/motw.sh live                    # the last ranking prod actually ran, from its logs
```

`rank` previews a scoring change before it deploys. It connects with the anon key, so
row-level security refuses any write. It needs `backend/.env.prod`, so run it from the
main checkout. `live` reads the `motw_candidates_scored` line, and pod logs reset on each
deploy.
