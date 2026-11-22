# Tournaments Tab

**Status:** companion refactor shipped (SB-886), stale-status fix (SB-889), modal fix (SB-890), preview fixes (SB-892) | **Follow-ons:** weather (SB-887), tournament-level IG share (SB-888)

The Tournaments tab is a **companion**, not a schedule dump. It answers "what is
happening with my team this weekend" before it answers "what is in this
tournament".

Entry point: `TournamentMatchCenter.vue`, which owns the filters and the three
view modes (List / Bracket / Standings). How the matches are fetched — and
whether the tournament is too big to fetch at once — lives in
`composables/useTournamentMatches.js` (see [Large tournaments](#large-tournaments)).

## Components

| Component | Job |
|-----------|-----|
| `TournamentMatchCenter.vue` | Fetches seasons + tournaments, owns filters and view mode |
| `composables/useTournamentMatches.js` | Fetches a tournament's matches; the scale switch, server-side filters and paging |
| `TournamentFilters.vue` | Age Group and Group controls of a large tournament |
| `TournamentHeroCard.vue` | Status ribbon, identity, "your next match", quick stats |
| `TournamentMatchRow.vue` | One match row — every list row on the page |
| `ui/ScorePill.vue` | The score, or `vs` when there isn't one |
| `ui/TournamentChip.vue` | Age / round / group chips |
| `ui/MatchStatusLabel.vue` | Scheduled / Live / Final / Cancelled |
| `TournamentBracket.vue` | Knockout bracket view |
| `TournamentStandings.vue` | Group-stage table view |
| `utils/tournamentStatus.js` | Pure date/status logic — all of it unit-tested |
| `utils/tournamentStages.js` | Showcase / placement finals / consolation sections and their titles |

`TournamentMatchRow` exists because the row template used to be **three
byte-identical copies** inside `TournamentMatchCenter` (group stage, knockout,
untagged), so every fix had to be written three times. If you are adding
something to a row, add it there once.

## Tournament status

`tournamentStatus(tournament, matches, now)` returns `{ state, label,
countdownTo }`, computed — never stored.

| State | When | Label examples |
|-------|------|----------------|
| `upcoming` | more than 7 days out | "In 3 weeks", "In 9 days" |
| `soon` | within 7 days | "Starts in 4 days", "Starts tomorrow", "Starts today" |
| `live` | today inside the date range, **or** any match `in_progress` | "Live now", "Happening today" |
| `completed` | past `end_date` | "Completed" |

Two rules worth knowing:

- **A match in progress beats the calendar.** A fixture running past midnight,
  or a stale `end_date`, still reads as live.
- **No dates means no ribbon.** `tournamentStatus` returns `null` rather than
  defaulting to `upcoming` — unknown is not a state, and it renders as absent.

`countdownTo` is deliberately `null` beyond 7 days. A ticking clock on something
three weeks away is decoration, not information.

`compareByStatus` sorts the tournament selector chips: live → soon → upcoming →
completed. Within a state, **anything still ahead sorts soonest-first and
anything finished sorts most-recent-first** — the tournament someone wants to
revisit is the one that just ended.

## Absent is not zero

This page is where the CLAUDE.md rule bit hardest, so it is worth restating.

`ScorePill` renders `vs` unless there is a real result. It takes an optional
`status` prop, and with it a score only renders when `match_status` is one of
`completed`, `in_progress`, `forfeit` **and** both scores are non-null.

The `status` prop exists because of a production incident: `matches.home_score`
and `away_score` carried `DEFAULT 0` in prod (the tracked baseline had no
default, so **local never reproduced it**). Any insert that omitted a score
stored a nil-nil draw, and the Tournaments tab announced `0 – 0` on fixtures
kicking off the next morning. 46 rows across 5 tournaments and the league were
affected.

Migration `20260828000000_match_scores_no_zero_default.sql` drops the defaults
and nulls the placeholder rows. The backfill is scoped to `scheduled`, `tbd` and
`cancelled` — **`completed` is excluded because prod holds 42 genuine 0-0
draws**, and a broader predicate would erase them.

A live match at 0-0 is a real scoreline. That is why `in_progress` is in the
scorable set.

## A past match that never got a result

`Scheduled` is a claim about the future, so it is false on a fixture that
kicked off in June. `isMissingResult(match, now)` catches that case — status
`scheduled` or `tbd`, with a match date strictly before today — and the status
column reads **`Not reported`** instead.

The wording is deliberate. It states only that no score reached us. It does
**not** claim the match was unplayed (there is no evidence of that), and it does
**not** promise a result is coming (the oldest of these dates from December
2024). `cancelled` never flips: that is a real, known outcome.

**The boundary is the calendar day, not kickoff time.** A match that started two
hours ago and has not been updated is normal mid-tournament; flipping it during
the day would be wrong and would flicker while someone is live-scoring.

The tone stays the same muted grey as `Scheduled`, in italic. For most of the
archive this is an expected state, not a fault — painting 81 rows amber would
read as an outage.

At the time of writing prod holds 81 such matches: 45 league (oldest
2024-12-30) and 36 tournament, of which 29 are the 2026 National Academy
Championships. **This makes the gap legible; it does not fill it.** Those
matches are still absent from games-played and standings, since only
`live` / `completed` / `forfeit` count towards season stats.

## Highlighting the viewer's club

`isMyMatch(match, { clubId, teamId })` drives the amber left rail on a row, the
bolder team name, the "Your next match" strip and the "Your matches" stat tile.

Club is checked first — a parent follows a club across age groups — with
`team_id` as the fallback for profiles that only carry that. **Signed out, both
are null and every highlight silently switches off.** There is no signed-out
branch to maintain; the feature just doesn't render.

The "Your matches" tile is omitted entirely when the viewer has no club in this
tournament, rather than rendering "0 Your matches" — that would be a claim about
a club that isn't here.

## Day grouping

Matches group into day bands inside each section, with a relative label (Today /
Tomorrow / Yesterday) beside the date rather than instead of it — a parent still
wants the date they can put in a calendar.

`groupMatchesByDay` preserves the order it is handed, so day order and
within-day order both come from the caller's sort (`byKickoffAsc`). Undated
matches collect under a `null` key so they still render instead of vanishing.

Kickoff time is the row's anchor, in `tabular-nums`, because it is what someone
at a tournament actually scans for. A match with no `scheduled_kickoff` shows
`—`, never a guessed midnight.

## Round keys

A match's `tournament_round` is one of a fixed set of keys, validated in
`backend/dao/tournament_dao.py` (`VALID_ROUNDS`) and mirrored in
`backend/mt_cli.py` and the `load-tournament-matches` skill. Labels live in
`utils/tournamentRounds.js`, which also exports the round sets every component
shares — do not redeclare them in a component.

| Set | Rounds | Used for |
|-----|--------|----------|
| `KNOCKOUT_ROUNDS` / `KNOCKOUT_ROUND_ORDER` | `round_of_32`, `round_of_16`, `quarterfinal`, `semifinal`, `third_place`, `final` | The Knockout section of the list, and its order |
| `BRACKET_ROUNDS` / `BRACKET_ROUND_ORDER` | the knockout rounds without `third_place` | Whether the Bracket view is offered, and its columns |
| `SHOOTOUT_ROUNDS` | the knockout rounds plus `consolation`, `placement_final` | Whether the inline score editor offers shootout inputs |

MLS NEXT Fest added three keys (SB-1752):

| Key | Short / long label | Knockout | Bracket | Shootout |
|-----|--------------------|----------|---------|----------|
| `showcase` | Showcase / Showcase | no | no | no |
| `consolation` | Consolation / Consolation | no | no | yes |
| `placement_final` | Placement / Placement Final | no | no | yes |

None of the three is a knockout or bracket round. A tournament whose only
"finals" are `placement_final` therefore does **not** switch on the Bracket
view — there is no elimination tree to draw.

Each of the three renders as **its own section** of the list (SB-1749), in any
tournament, large or small. The list's sections, in order:

| Section | Matches | Title |
|---------|---------|-------|
| Group Stage | `group_stage` | "Group Stage" |
| Showcase | `showcase` | the stage label |
| Knockout Rounds | `KNOCKOUT_ROUNDS` | "Knockout Rounds" |
| Placement Finals | `placement_final` | "Placement Finals — " + the stage label |
| Consolation | `consolation` | "Consolation — " + the stage label |
| Matches | no round, or a round with no section | "Matches" |

For these three rounds `tournament_group` holds a **stage label**, not a group
(`HD · Showcase`, `HD · Group Play`, `GA Cup Qualifier`), and one round can
hold several. So a section is one (round, stage label) pair — `HD · Showcase`
and `AD · Showcase` are two sections — titled by `stageSectionTitle` in
`utils/tournamentStages.js`: a label that already names the round stands alone
(`HD · Showcase`), otherwise the round leads (`Placement Finals — HD · Group
Play`), which keeps placement finals and consolation apart when they share a
label. Matches with no label get the round's own title. Empty sections drop
out, as before.

## Group format

`tournament_group` is one free-text field. Events that run several competitions
side by side reuse the same labels in each (both Fest divisions have a
"Group A"), so the stored value is namespaced by division:

| Stored value | Division | Label |
|--------------|----------|-------|
| `HD · A` | `HD` | `A` |
| `HD · Showcase` | `HD` | `Showcase` |
| `Bracket A` (legacy) | none | `Bracket A` — displayed unchanged |

The separator is exactly space, `·` (U+00B7 middle dot), space. Compose and
split with the helpers, never by hand: `compose_group` / `split_group` in
`backend/dao/tournament_groups.py`, mirrored by `composeGroup` / `splitGroup`
in `utils/tournamentGroups.js`. Both split on the first separator only, and a
value with no separator is a legacy group with a null division.

Two more rules are part of the format, because the Python and JavaScript
helpers must agree byte for byte on every input:

- **Trimming.** Each part is trimmed of an explicit character list
  (`GROUP_WHITESPACE`, the same literal in both files), not the language's own
  `strip()` / `trim()` — those disagree: JavaScript trims U+FEFF, Python trims
  U+001C–U+001F and U+0085. The list is the union: tab, LF, VT, FF, CR, space,
  U+001C–U+001F, U+0085, U+00A0, U+1680, U+2000–U+200A, U+2028, U+2029,
  U+202F, U+205F, U+3000, U+FEFF. Nothing else is trimmed (a zero-width space
  stays).
- **Compose rejects what would not split back.** `compose_group` raises
  `ValueError` (`composeGroup` throws `Error`, same message) for a division
  that contains the separator — or ends with ` ·`, which forms one with the
  separator that follows — and for a label that contains the separator when
  there is no division. A label containing the separator *with* a division is
  legal, since the split is on the first separator only. `split_group` /
  `splitGroup` never raise: a stored value always splits.

**The format is frozen.** Bracket follows store this string, so changing the
separator, the trimmed characters or the compose rule orphans every follow
already saved.

## Large tournaments

MLS NEXT Fest is about 2,400 matches. One API response is capped at 1,000 rows
(`supabase/config.toml`, `max_rows`), and `GET /api/tournaments/{id}` is one
unpaged query — so a tournament that size loses most of its matches silently.
The largest tournament before the Fest was 186.

### The scale switch

`GET /api/tournaments` returns an exact `match_count` per tournament. A
tournament with **more than 300 matches** (`LARGE_TOURNAMENT_MATCH_THRESHOLD`
in `useTournamentMatches.js` — the one place the number lives) is *large*.

| | Small (≤ 300) | Large (> 300) |
|---|---|---|
| Matches come from | one `GET /api/tournaments/{id}` | `GET /api/tournaments/{id}/matches`, 200 at a time (`TOURNAMENT_PAGE_SIZE`) |
| Age filter | "All Ages" + age chips, applied in the browser | **Age Group** select, applied by the server; one is always selected |
| Group filter | none | **Group** select, when the age group has groups |
| Team filter | past 8 matches | not offered — it would search only the loaded rows |
| Bracket / Standings tabs | by round shape | hidden; both need every match at once (scoped versions deferred) |
| Hero card stats | Played / Matches / Days / Your matches | **Matches** only, from `match_count` — the rest would be counts of a page |
| Hero card ribbon | status, stage in play, countdown to next kickoff | status from `start_date` / `end_date` alone ("Happening today", "Completed"); never "Live now", no stage, no countdown — each would describe one age group's page |
| "Your next match" | shown when the viewer's club has one | not shown — the next one may be on a page that is not loaded |
| More rows | — | **Load more**, with "Showing 200 of 412 matches" |

A small tournament behaves exactly as it did: one call, the same list, bracket
and standings. A large tournament never calls the detail endpoint and never
asks for more than one page per request.

A large tournament opens on the first age group with a match **today**, else
the first with any matches. Changing the age group clears the group.

**"Today" is the browser's calendar day, and that is a known limitation.**
Tournaments carry no timezone, so `on_date` is the viewer's local date. An
Arizona event opened from the US east coast just after midnight asks for a day
the event has not reached, finds nobody playing, and opens on the first age
group with matches instead of the one still on the field. The facets count one
day per request, so falling back to "the most recent match day" would need
either a change to `tournament_filter_facets` or a second request; neither is
done, and no timezone is guessed.

**Selecting a Group also selects the group-stage round.** A group is a
group-stage pool and its count in the control is a count of `group_stage`
matches, but `tournament_group` is also carried by other rounds. So the page
sends `round=group_stage` with every `group=` (`GROUP_FILTER_ROUND` in
`useTournamentMatches.js`) — the option says "(16)" and the list shows 16.
Clearing the group drops both. The API itself keeps `group` and `round`
independent.

A background refresh (the tab coming back) refetches what is on screen and
nothing else: it does not start while a tournament is still loading, and its
answer is dropped unless the tournament it fetched is still the selected one.

`viewedAgeGroupId` in `TournamentMatchCenter` is the age group on screen in
either mode (null in small mode means "All Ages"). Anything that needs to know
which age group the visitor is looking at reads that one computed.

### Endpoints

Both are public, and both hide test fixtures from anyone who is not an admin or
test user — the same rule as the detail endpoint. An unknown tournament is
`404`; a tournament with no matches is `200` with empty lists.

**`GET /api/tournaments/{id}/matches`** — one page, in day → kickoff → id
order, so pages neither overlap nor skip.

| Parameter | Meaning |
|-----------|---------|
| `age_group_id` | only this age group |
| `group` | only this stored `tournament_group`, e.g. `HD · A` — exact match |
| `round` | only this round key |
| `limit` | page size, default 200, capped at 500 |
| `offset` | rows to skip, default 0 |

```json
{ "matches": [ ... ], "total": 412, "limit": 200, "offset": 0 }
```

Each match has the same shape as in the detail endpoint's `matches`. `total`
is the exact number of matches the filters select, not the page length. An
offset past the end is an empty page with the real `total`.

Only **canonical** pages are cached: `limit` equal to the default (200 —
`DEFAULT_LIMIT` in `backend/dao/tournament_filters.py`, which
`TOURNAMENT_PAGE_SIZE` in the page must equal) and `offset` a multiple of it,
which is every request the page makes. They live for 60 seconds
(`TOURNAMENT_PAGE_CACHE_TTL`). Any other `limit` or `offset` is answered
straight from the database, so sweeping them creates no cache keys. Every
filter and the test partition are part of the key.

**A filter that cannot match returns nothing, never everything.** An
`age_group_id` that is not an id, or a `round` that is not a round key, is
`200` with no matches — the caller asked for something specific.

**`GET /api/tournaments/{id}/filters`** — what the matches can be filtered by.

| Parameter | Meaning |
|-----------|---------|
| `age_group_id` | list the groups of this age group (omit for every age group's) |
| `on_date` | `YYYY-MM-DD`; also count each age group's matches that day |

```json
{
  "facets_available": true,
  "age_groups": [
    { "id": 5, "name": "U13", "matches": 412, "matches_on_date": 36 }
  ],
  "groups": [
    { "key": "AD · A", "division": "AD", "label": "A", "matches": 6 },
    { "key": "HD · A", "division": "HD", "label": "A", "matches": 6 }
  ]
}
```

`groups` are the distinct `tournament_group` values of **`group_stage`**
matches, so a stage label on another round (`HD · Showcase`) is not a group.
`key` is the stored value and is what `group=` takes; `division` and `label`
are its two halves (see [Group format](#group-format)). The page shows the key
(`HD · A`), which is what keeps the two divisions' "Group A" apart.

Three states, and they are not interchangeable:

| `groups` | Means | The page |
|----------|-------|----------|
| a list | this age group has these groups | shows the Group control |
| `[]` | counted, and it has none (a showcase-only age group) | hides the control |
| `null` | not known | hides the control, and claims nothing |

The same goes for counts: `matches: null` is "not counted" and renders no
number — never `(0)`. `matches_on_date` is `null` whenever `on_date` was not
given. The response has room for more facets; `conferences` and a `teams`
block are SB-1753's.

The filters are decoration on the list. If that request fails, the matches
still load, the Age Group control is built from the tournament's own age
groups with no counts, and there is no Group control.

A failed or uncounted answer on a **refresh** keeps the groups already on
screen: a group may be selected, and removing the control would leave the list
narrowed with nothing to clear it. After an age-group change the old groups
are dropped — they belong to another age — and no group is selected.

### The migration, and the page without it

The counts come from one SQL function, `tournament_filter_facets`
(`supabase/migrations/20261123120000_tournament_filter_facets.sql`), because an
aggregate is the only way to count past the row cap. The same migration adds
the index `idx_matches_tournament_age_date` on
`matches (tournament_id, age_group_id, match_date)`. It creates no table, so
the backup and restore registries are untouched.

**Apply it with `./scripts/db_tools.sh migrate prod`.** The code deploys
separately, so until then:

- `/filters` answers `200` with `facets_available: false`, `groups: null`, and
  every `matches: null`; the age groups listed are the tournament's own.
- The page pages and filters by age group normally. The Age Group control
  shows no counts, there is no Group control, and it opens on the first age
  group rather than the one playing today.
- `/matches` does not depend on the function at all.

The "unavailable" answer is never cached, so the first request after the
migration is applied gets real counts.

**Only the missing function degrades.** PostgREST's `PGRST202` ("could not
find the function") is the one error answered with `facets_available: false`.
Anything else — a statement timeout, a revoked grant, a changed signature — is
a `500` with a generic message and the specifics in the server log, so a broken
function is seen rather than passing for "not migrated yet". The page treats
that `500` like any failed filters request: the list still renders.

### The admin panel

`AdminTournaments.vue` still loads a tournament through the detail endpoint,
so for a large tournament its match table is cut short. It no longer passes
the cut-off length off as the tournament's size: it asks
`/matches?limit=1` for the exact `total`, keeps that as the count, and shows
"Showing the first 1000 of 2400 matches." above the table. Moving the admin
panel to the paged endpoint is a separate piece of work.

## Matches ingested from the scraper

Tournament matches can arrive from match-scraper as well as from the admin
tools (SB-1747). A queue message carrying `tournament_id` is filed on the
tournament with a null division and the sender's `source` (`match-scraper` or
`match-scraper-agent`); the feed's raw
`competition` and `tournament_group` are composed into the stored
`tournament_group` with `compose_group`, never by hand, so `HD · A` and
`AD · A` stay two groups.

A scraped match is upserted on its source match id: a rescrape fills in the
score and shootout on the same row, an unchanged rescrape writes nothing, and
a hand-entered match on the same tournament is adopted rather than duplicated
— its typed group or round kept, its empty columns filled. A match is never
moved onto a tournament from a league or from another tournament, and a
rescrape missing part of the group never re-files a stored `HD · A`. Ingest only writes
`matches` — logged goals are never touched, and a scraped score that disagrees
with them stays the result while the goals stay the attribution.

Most scraped tournament teams have no manager, so no roster and no events:
that is the default the tab renders, and a match without a score is `null`,
not `0–0` (see [Absent is not zero](#absent-is-not-zero)).

**A scraped score can be stale on the Tournaments page.** Tournament reads
are cached for up to 24 hours. The ingest write clears that cache only when
the worker shares the API's cache (`CACHE_ENABLED=true` and the same
`REDIS_URL`), which the production worker currently does not — so a score the
worker files can take up to the cache lifetime to appear, unless an admin
write or a deploy clears the cache first.

The message fields, the stored-group rule and what drops a match are in
[match-scraper.md](../08-integrations/match-scraper.md#tournament-matches).

## Things that are deliberately not there

- **"Preview" as a row action.** The whole row is clickable. The old "Preview"
  link sat in the status column, so it read as a fourth match status.
- **The team filter on a short list.** It renders past 8 matches
  (`TEAM_FILTER_THRESHOLD`), or whenever a filter is already active. Below that
  the input was larger than the thing it filtered.
- **Weather.** Out of scope until SB-887 — `tournaments.location` is free text,
  so it needs geocoding first. When it lands, an absent forecast must render
  nothing rather than a placeholder temperature.

## Chips and dark mode

`TournamentChip` has three variants (`age`, `round`, `group`), each with a light
and a dark treatment. They replaced three unrelated hardcoded palettes
(`bg-indigo-100`, `bg-purple-100`, `bg-brand-100`) that had **no dark variant**
and rendered as pale blocks on a navy card.

Adding a chip? Add a variant there. Do not inline a colour.

## The match preview modal

A row click opens `MatchDetailView` inside `ui/ModalOverlay.vue`. (The Matches
tab renders the same view *inline* instead — hence `MatchDetailView`'s
`backLabel` prop, since "Back to Matches" is wrong when you arrived from
Tournaments.)

`ModalOverlay` exists because the previous inline wrapper could trap the user
(SB-890). Its close button was `absolute` on the card, so on a short window,
scrolling to read the content carried the only visible exit off the screen —
measured at `top: -70px`. Escape was unhandled and the page scrolled freely
behind it, so every way out failed at once.

The rule now: **three independent ways out**, so no single failure traps
anyone.

| Exit | How |
|------|-----|
| Close button | `fixed` to the **overlay**, not the card — reachable at any scroll offset |
| `Escape` | handled on the overlay |
| Backdrop | `@click.self` |

It sits at **z-index 1200**. `nav.auth-nav` is `position: relative; z-index:
1000` — page chrome in the same band the app uses for modals (`App.vue`,
`ConfirmModal`, every admin modal are all 1000, and only win by appearing later
in the DOM). At the original z-50 the nav painted over the top strip of the
viewport and swallowed clicks on the close button, so a user at the top of the
page could not close the modal at all (SB-896).

That bug hid from local verification because `auth-nav` scrolls with the page:
scrolled down, the nav is not in the top strip and the button works. It only
appears at `scrollTop = 0` — where a user opening the first match of a
tournament always is. **Verify modal changes at the top of the page.**

`App.vue`'s deep-link modal (the `?matchId=` push-notification path) uses the
same component, so both paths get the same behaviour.

It also teleports to `<body>`, so no ancestor `transform` / `filter` / `contain`
can ever turn `position: fixed` into a clipped box; locks body scroll with
`overflow: hidden` (which preserves scroll position, so closing does not jump
the reader to the top) plus scrollbar-width padding to stop the layout shifting
sideways; and carries `role="dialog"`, `aria-modal`, an accessible name,
focus-on-open, focus-restore-to-opener, and a Tab trap.

## The preview itself

`MatchPreview.vue` renders the scouting panel for an unplayed match: recent
form per team, common opponents, head-to-head.

**Form scorelines lead with the subject team's goals** and carry an `H`/`A`
marker (`teamScoreline` / `venueFor`). They used to print raw
`home_score–away_score` while the W/L letter beside them swapped on `isHome` —
so IFA's form read `W 1–3 FC Delco`, a win whose first number is lower, with
nothing on the row to say which number was IFA's. The opponent-name span
deliberately hides who was home, so there was no way to read it correctly.
Four call sites, all fixed; `teamScoreline` returns `null` for a missing score
so a `Not reported` match renders an em dash rather than a bare separator.

**A League or Flex match shows League and Flex form only** (SB-1346).
`MatchDetailView` passes the match's `match_type_id`; when that type is flagged
`counts_for_qualification`, `get_match_preview` narrows recent form to the
flagged types (`form_match_type_ids`). A tournament or friendly preview keeps
every competition. Each form row names its competition — League neutral,
anything else amber.

**Common opponents are League and Flex only, for every preview** (SB-1347,
`qualifying_match_type_ids`). A tournament or friendly result is not like-for-like
evidence, and a tournament draw must not surface as a "shared" opponent.
Head-to-head still spans every competition. If no type is flagged (failed
lookup), both fall back to every competition rather than blanking the panel.

**A tab with no rows does not render.** `Common Opponents` and `Head-to-Head`
used to show a literal `0` badge, so two of three tabs advertised their
emptiness and invited a click that led nowhere. If the active tab disappears on
a reload, the panel falls back to Recent Form.

**Each team gets its own empty state** — "No matches on record", with the
reason — sized to its column. Most clubs have no tracked results; that is the
default state, not an error.

In `MatchDetailView`, the **centre slot holds the score when there is one and
the kickoff when there is not**. It used to render `-` `-` `-` at 48px
unconditionally, which read as a broken component and occupied the position
where the answer belongs, while the kickoff sat in a six-cell grid with the
same weight as `Season`. `hasResult` requires a scorable status *and* non-null
scores, so stored zeros on a scheduled match (SB-886) cannot resurrect the
scoreboard. Date and Kickoff drop out of the grid whenever the hero is already
showing them.

## Tests

| File | Covers |
|------|--------|
| `__tests__/utils/tournamentStatus.spec.js` | Every status/date/grouping rule, clock pinned explicitly |
| `__tests__/utils/tournamentRounds.spec.js` | Round labels and the shared knockout / bracket / shootout sets |
| `__tests__/utils/tournamentGroups.spec.js` | Group format: namespaced, legacy, absent |
| `__tests__/components/ScorePill.spec.js` | The absent-is-not-zero guard, including the 42 real draws |
| `__tests__/components/TournamentMatchRow.spec.js` | Row states, club highlight, chips |
| `__tests__/components/TournamentHeroCard.spec.js` | Ribbon, schedule link, next-match strip, stats |
| `__tests__/components/TournamentMatchCenter.spec.js` | Wiring and filters |
| `__tests__/components/TournamentMatchCenterFestScale.spec.js` | Large tournaments: showcase-only and groups-plus-finals age groups, request parameters, degraded filters, small tournament unchanged |
| `__tests__/components/TournamentFilters.spec.js` | Age Group / Group controls; the three states of `groups` |
| `__tests__/components/AdminTournaments.truncation.spec.js` | Exact count and the truncation note in the admin panel |
| `__tests__/composables/useTournamentMatches.spec.js` | The scale switch, default age group, filter changes, paging, stale answers |
| `__tests__/utils/tournamentStages.spec.js` | Stage sections and their titles |
| `backend/tests/unit/test_tournament_filters.py` | Query parsing and facet shaping (pure) |
| `backend/tests/unit/test_tournament_matches_paging.py` | Paged DAO query, degraded facets, both endpoints' status codes |
| `backend/tests/integration/test_tournament_matches_paging.py` | 1,030 real matches: exact totals, pages that neither overlap nor skip, `HD · A` vs `AD · A`, the test partition. Facet tests skip until the migration is applied locally |

The default fixture is a **signed-out viewer looking at a scheduled fixture with
no user data**, per CLAUDE.md. The "my club" cases are the special case, because
they are the special case in production.
