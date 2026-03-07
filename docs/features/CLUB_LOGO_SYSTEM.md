# Club Logo System Improvements

## Problem

The `enrich` command successfully finds club websites, but the logos it captures (og:image, favicons, banners) are often wrong — they're marketing banners, tiny favicons, or unrelated images rather than actual club crests. Additionally, logos only appear in 4 of 9 possible places in the UI.

## Goals

1. Create a local `club-logos/` staging folder with a naming convention for curating logos
2. Integrate logo upload into `manage_clubs.py sync` so local logos get pushed to Supabase Storage
3. Add the `enrich` command ability to download candidate logos to this folder
4. Add club logos to all remaining UI locations (matches list, league table, profiles)

## Image Standard

- **Format**: PNG with transparent background, square aspect ratio
- **Source resolution**: 512x512px (or at least 256x256)
- **One source file per club** — CSS handles all display sizes:
  - `xs` = 24px (inline in tables/standings)
  - `sm` = 32px (match cards, profile inline)
  - `md` = 40px (admin grid, match list cards)
  - `lg` = 56px (match detail badges)
  - `xl` = 140px (profile hero sections)
- **Naming**: `{slug}.png` where slug = lowercase, hyphens for spaces, accents stripped
  - `inter-miami-cf.png`, `orlando-city-sc.png`, `dc-united.png`, `cf-montreal.png`

---

## Logo Onboarding Workflow

When onboarding new divisions/clubs, follow this repeatable process to add logos:

### Directory Structure

```
club-logos/
  raw/        ← Drop source images here (any format/size), named as {slug}.ext
  ready/      ← Processed 512x512 PNGs (output of prep-logo.py --batch)
```

### Step-by-Step

```bash
# 1. See what clubs need logos and what filenames to use
cd backend && uv run python manage_clubs.py logo-status

# 2. Drop raw images into staging folder, named by slug from step 1
cp ~/Downloads/logo.png club-logos/raw/bayside-fc.png

# 3. Batch prep all raw images (bg removal, resize to 512x512)
cd backend && uv run python ../scripts/prep-logo.py --batch

# 4. Upload all prepared logos to the database
cd backend && uv run python manage_clubs.py upload-logos
```

### Command Reference

| Command | Description |
|---------|-------------|
| `manage_clubs.py logo-status` | Show all DB clubs with slug filename and logo status |
| `prep-logo.py --batch` | Process all `club-logos/raw/*` images to `club-logos/ready/` |
| `prep-logo.py --batch --no-remove-bg` | Batch prep without background removal |
| `prep-logo.py input.png --club "Name"` | Process a single file by club name |
| `manage_clubs.py upload-logos` | Upload all `club-logos/ready/*.png` to DB |
| `manage_clubs.py upload-logos --dry-run` | Preview what would be uploaded |
| `manage_clubs.py upload-logos --overwrite` | Re-upload even if club already has a logo |
| `manage_clubs.py upload-logos --extract-colors` | Also extract primary/secondary brand colors from logos |

### Notes

- `logo-status` shows the expected slug filename for every club in the DB
- `upload-logos` matches files to ALL DB clubs (not just clubs.json)
- Batch prep skips files where output is already newer than input (re-run safe)
- SVG and other unsupported formats are skipped with a warning
- The `club-logos` Supabase storage bucket is auto-created on `supabase db reset` via `config.toml`

---

## Phase 1: Backend Data Plumbing

Prerequisite for frontend work — makes club/logo data available in match list and standings queries.

### 1.1 `backend/dao/match_dao.py` — Add club joins to match queries

`get_all_matches()` (line ~376) and `get_matches_by_team()` (line ~462) currently select teams without club data. `get_match_by_id()` (line ~696) already joins clubs — copy that pattern.

Change the team selects from:
```
home_team:teams!matches_home_team_id_fkey(id, name)
```
to:
```
home_team:teams!matches_home_team_id_fkey(id, name, club:clubs(id, name, logo_url))
```

Add to the flatten blocks (after `away_team_name`):
```python
"home_team_club": match["home_team"].get("club") if match.get("home_team") else None,
"away_team_club": match["away_team"].get("club") if match.get("away_team") else None,
```

Same for `_fetch_matches_for_standings()` (line ~862) — add `club:clubs(id, name, logo_url)` to both team selects.

### 1.2 `backend/dao/standings.py` — Propagate logo_url through standings

In `calculate_standings()` (line ~82), add `logo_url` to the defaultdict:
```python
standings = defaultdict(lambda: {
    "played": 0, "wins": 0, "draws": 0, "losses": 0,
    "goals_for": 0, "goals_against": 0, "goal_difference": 0, "points": 0,
    "logo_url": None,
})
```

After line ~134, capture club data:
```python
home_club = match["home_team"].get("club") or {}
away_club = match["away_team"].get("club") or {}
if not standings[home_team]["logo_url"]:
    standings[home_team]["logo_url"] = home_club.get("logo_url")
if not standings[away_team]["logo_url"]:
    standings[away_team]["logo_url"] = away_club.get("logo_url")
```

---

## Phase 2: Local Logo Folder & Upload Integration

### 2.1 `.gitignore` — Add `club-logos/`

Add `club-logos/` to the root `.gitignore` (binary assets don't belong in git).

### 2.2 `backend/models/clubs.py` — Add `club_name_to_slug()` utility

```python
import re
import unicodedata

def club_name_to_slug(name: str) -> str:
    """Convert club name to filename slug: 'Inter Miami CF' -> 'inter-miami-cf'"""
    # Normalize unicode (strip accents)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    # Lowercase, replace non-alphanumeric with hyphens, collapse
    name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return name
```

### 2.3 `backend/manage_clubs.py` — Logo upload during sync

After a club is created or updated, check for a local logo file:
```python
slug = club_name_to_slug(club.club_name)
logo_path = LOGO_DIR / f"{slug}.png"
if logo_path.exists():
    upload_club_logo(token, club_id, logo_path)
```

Add `upload_club_logo()` helper that POSTs to the existing `/api/clubs/{club_id}/logo` endpoint. Add `logos_uploaded` counter to the sync summary.

---

## Phase 3: Frontend Components

### 3.1 NEW `frontend/src/components/shared/ClubLogo.vue`

Reusable logo component. Props: `logoUrl`, `name`, `size` (xs/sm/md/lg/xl).

**Critical: No-logo fallback must look clean.** Most clubs will NOT have logos — this is the common case:
- `logoUrl` present: show logo image in a subtle circular container
- `logoUrl` absent at xs/sm sizes (lists/tables): show **nothing** — no initials, no placeholder icon
- `logoUrl` absent at lg/xl sizes (hero/profile): show styled initial letter in colored circle
- Layout must not shift: use fixed-width containers so spacing is consistent

### 3.2 `frontend/src/components/MatchesView.vue` — Add logos to match display

Both desktop table and mobile card views use `v-html="getTeamDisplay(match)"`. After Phase 1, match objects include `home_team_club` and `away_team_club`.

Add `<ClubLogo>` components alongside team names. For "My Club" tab, show opponent's logo; for "All Matches" tab, show both. When no logo exists, nothing extra renders.

~8 template locations need the logo (4 desktop variants x 2 for mobile).

### 3.3 `frontend/src/components/LeagueTable.vue` — Add logos to standings

Standings rows will include `logo_url` after Phase 1. Add `<ClubLogo size="xs">` before team name. Hide on smallest screens (`hidden sm:flex`).

### 3.4 `frontend/src/components/profiles/TeamManagerProfile.vue` — Add club logo

Data available at `authStore.state.profile.club` (club managers) and `authStore.state.profile.team.club` (team managers). Add `<ClubLogo size="sm">` before club/team name.

### 3.5 `frontend/src/components/profiles/PlayerProfile.vue` — Add club logo

Already uses `authStore.state.profile.team.club` for colors. Add `<ClubLogo size="xs">` in team-line section.

### 3.6 `frontend/src/components/profiles/PlayerCard.vue` — Add club badge (optional/lower priority)

Would need `clubLogoUrl` prop passed from `TeamRosterPage.vue`.

---

## Phase 4: Match-Scraper Enrichment

### 4.1 `match-scraper/src/models/discovery.py` — Add `club_name_to_slug()`

Same function as backend (duplicated since separate repos).

### 4.2 `match-scraper/src/scraper/club_enrichment.py` — Add logo download

New method `_download_logo()` that saves the discovered logo image to a local folder as `{slug}.png`. Add `--logo-dir` CLI option to the `enrich` command.

---

## Current Logo Display Summary

| Component | Has Logo? | Size | Data Source |
|-----------|-----------|------|-------------|
| AdminClubs grid | Yes | 40px (md) | API |
| MatchDetailView | Yes | 56-64px (lg) | `match.home_team_club` |
| ClubManagerProfile | Yes | 140px (xl) | `authStore.state.profile.club` |
| FanProfile | Yes | 140px (xl) | `authStore.state.profile.club` |
| MatchesView (My Club) | **No** | needs 24px (xs) | needs `home_team_club`/`away_team_club` |
| LeagueTable | **No** | needs 24px (xs) | needs `logo_url` in standings |
| TeamManagerProfile | **No** | needs 32px (sm) | `authStore.state.profile.club` available |
| PlayerProfile | **No** | needs 24px (xs) | `authStore.state.profile.team.club` available |
| PlayerCard | **No** | needs 16px | needs prop from parent |

## Verification Checklist

1. Place a test logo at `club-logos/bayside-fc.png` (512x512 PNG)
2. Run `manage_clubs.py sync` — verify logo uploads and URL updates in DB
3. Open MatchesView — verify logos appear next to team names in both desktop/mobile views
4. Open LeagueTable — verify logos appear in standings rows
5. Open TeamManagerProfile — verify club logo appears
6. Open PlayerProfile — verify club logo appears in team line
7. Run `mls-scraper enrich --input florida-clubs.json --logo-dir ./club-logos/` — verify candidate logos downloaded
8. Check MatchDetailView still works (regression check)

## Key Files Reference

### Backend (missing-table repo)
- `backend/dao/match_dao.py` — match queries with team/club joins
- `backend/dao/standings.py` — standings calculation
- `backend/models/clubs.py` — club data models
- `backend/manage_clubs.py` — club sync CLI tool

### Frontend (missing-table repo)
- `frontend/src/components/shared/ClubLogo.vue` — NEW reusable component
- `frontend/src/components/MatchesView.vue` — match list views
- `frontend/src/components/LeagueTable.vue` — standings table
- `frontend/src/components/profiles/TeamManagerProfile.vue`
- `frontend/src/components/profiles/PlayerProfile.vue`
- `frontend/src/components/profiles/PlayerCard.vue`

### Existing logo patterns to consolidate into ClubLogo.vue
- `frontend/src/components/admin/AdminClubs.vue` — 40px circular logo
- `frontend/src/components/MatchDetailView.vue` — 56-64px with glow effect
- `frontend/src/components/profiles/ClubManagerProfile.vue` — 140px hero
- `frontend/src/components/profiles/FanProfile.vue` — 140px hero

### Match-Scraper (separate repo)
- `match-scraper/src/models/discovery.py` — club discovery models
- `match-scraper/src/scraper/club_enrichment.py` — enrichment pipeline
