# Tournaments Tab

**Status:** companion refactor shipped (SB-886), stale-status fix (SB-889), modal fix (SB-890), preview fixes (SB-892) | **Follow-ons:** weather (SB-887), tournament-level IG share (SB-888)

The Tournaments tab is a **companion**, not a schedule dump. It answers "what is
happening with my team this weekend" before it answers "what is in this
tournament".

Entry point: `TournamentMatchCenter.vue`, which owns data fetching, filters and
the three view modes (List / Bracket / Standings).

## Components

| Component | Job |
|-----------|-----|
| `TournamentMatchCenter.vue` | Fetches seasons + tournaments, owns filters and view mode |
| `TournamentHeroCard.vue` | Status ribbon, identity, "your next match", quick stats |
| `TournamentMatchRow.vue` | One match row — every list row on the page |
| `ui/ScorePill.vue` | The score, or `vs` when there isn't one |
| `ui/TournamentChip.vue` | Age / round / group chips |
| `ui/MatchStatusLabel.vue` | Scheduled / Live / Final / Cancelled |
| `TournamentBracket.vue` | Knockout bracket view |
| `TournamentStandings.vue` | Group-stage table view |
| `utils/tournamentStatus.js` | Pure date/status logic — all of it unit-tested |

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
| `__tests__/components/ScorePill.spec.js` | The absent-is-not-zero guard, including the 42 real draws |
| `__tests__/components/TournamentMatchRow.spec.js` | Row states, club highlight, chips |
| `__tests__/components/TournamentHeroCard.spec.js` | Ribbon, schedule link, next-match strip, stats |
| `__tests__/components/TournamentMatchCenter.spec.js` | Wiring and filters |

The default fixture is a **signed-out viewer looking at a scheduled fixture with
no user data**, per CLAUDE.md. The "my club" cases are the special case, because
they are the special case in production.
