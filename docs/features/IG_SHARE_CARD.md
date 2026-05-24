# Instagram Match Share Card

**Status:** v1 shipped (SB-32) · goal scorers (SB-33) | **Parent:** SB-19 | **Backend:** SB-31

A "Share to Instagram" flow on the match detail page that generates a
**1080×1080 PNG** suitable for an Instagram square post.

## What it does

From the match detail page, authorized users (admin, club manager, team
manager of either team) see an **Instagram** button next to the existing
"Copy Scoreboard" share. Clicking it opens a modal where they:

1. Pick a template (see below).
2. Optionally upload a JPEG/PNG photo (≤ 5 MB).
3. See a live preview of the 1080×1080 card.
4. **Download PNG** or **Copy to clipboard**.

The card is rendered client-side via `html2canvas`. The source photo is
uploaded to Cloudflare R2 (`POST /api/matches/{id}/photo`) so it's
persisted on the match for future reuse (e.g. SB-33 goal-scorers overlay).

### Templates

| Template | When to use | Default? |
|----------|-------------|----------|
| **Photo Overlay** | Hero action shots, photo-first storytelling | Default when no tournament round |
| **Brand Split** | Strong missingtable.com branding (panel + photo) | — |
| **Tournament Round** | Quarterfinal / Semifinal / Final matches — round name is the hero | Default when `match.tournament_round` is set |
| **Stadium** | No good photo available — full scoreboard-style card | — |

The Tournament Round option is only surfaced in the picker when the match has `tournament_round` populated (e.g. `"round_of_8"`, `"quarterfinal"`, `"final"`).

### Modes

- **Preview** — scheduled matches. Big "VS" + kickoff time.
- **Result** — completed matches. Final score, "FINAL" / "FULL TIME" badge. Modal
  defaults to this mode for completed matches; user can toggle.

Modes are independent of templates — every template supports both.

### Goal scorers (SB-33)

When a completed match was **live-scored** (it has goal events), the
**Result** card lists the scorers under the scoreboard — two columns
(home right-aligned, away left-aligned), **one line per goal in
chronological order**, mirroring the in-app match scoreboard. Each line
shows the scorer (player name or jersey number) and the minute
(`56'`, or `90+5'` for stoppage time).

Multi-goal games are highlighted:

- **Brace (2 goals):** the scorer's lines render in accent **gold**.
- **Hat-trick (3+ goals):** adds a gold **"⚽⚽⚽ HAT-TRICK · {name}"**
  banner above the columns (shows the tally, e.g. "4 GOALS", beyond 3).

Scorers appear on **all four templates** in Result mode only — never in
Preview, and never when the match has no goal events (e.g. a result
entered directly without live scoring). A scorer's goals are tallied by
`player_id` when present, otherwise by name **scoped to their team** (so
each side's `#9` stays distinct).

Events are fetched once by `MatchDetailView`
(`GET /api/matches/{id}/live/events`) and passed into the modal → card →
templates; the derivation lives in `useIgShareData`.

### Graceful degradation

If R2 is unavailable (503: not configured, or a transient error), the
card still downloads — only the persistence step fails. The UI surfaces
a clear message ("Card will download but the photo will not be saved").

## Files

- `frontend/src/components/IgShareCard.vue` — thin dispatcher; picks the
  right template component based on a `template` prop and re-exposes the
  inner `root` ref for html2canvas.
- `frontend/src/components/ig/IgOverlay.vue` — Photo Overlay template.
- `frontend/src/components/ig/IgSplit.vue` — Brand Split template.
- `frontend/src/components/ig/IgTournamentRound.vue` — Tournament Round template.
- `frontend/src/components/ig/IgStadium.vue` — Stadium Scoreboard template.
- `frontend/src/components/ig/IgScorers.vue` — presentational goal-scorers
  block (two columns + hat-trick banner). Shared by all four templates;
  `size` prop ('lg' | 'sm') scales it for the roomy vs. tighter cards.
- `frontend/src/composables/useIgShareData.js` — shared computed props
  (team data, score, dateLabel, tournament-name preference, "Unknown"
  filtering, round-name normalization) **plus scorer derivation**
  (`homeScorers`, `awayScorers`, `hasScorers`, `hatTricks`). Single
  source of truth across all four templates.
- `frontend/src/components/IgShareModal.vue` — file pick, template
  picker, upload, capture, download/clipboard flow.
- `frontend/src/components/MatchDetailView.vue` — entry-point button +
  permission gate (`canShareMatchPhoto`).

## Permission

Same as `auth_manager.can_edit_match`:

- `admin` → any match
- `club_manager` → matches involving any team in their club
- `team-manager` → matches involving their team

Reason: uncapped uploads = uncapped storage cost. Tighter than the
original "any logged-in user" scope from SB-19.

## Related

- [SB-19 — IG match share image umbrella](https://linear.app) (Linear)
- [SB-31 — R2 photo upload backend](https://github.com/silverbeer/missing-table/pull/360)
- SB-33 — goal scorers overlay (shipped: scorer list + brace/hat-trick highlight on result cards)
