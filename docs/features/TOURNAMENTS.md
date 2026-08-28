# Tournaments Tab

**Status:** companion refactor shipped (SB-886) | **Follow-ons:** weather (SB-887), tournament-level IG share (SB-888)

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
