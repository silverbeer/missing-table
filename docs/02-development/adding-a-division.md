# Adding a New Division to MT

> **Audience**: Developers expanding MT to cover new MLS Next divisions
> **Prerequisites**: Access to match-scraper, missing-table, and match-scraper-agent repos
> **Time**: ~1 hour (plus discovery scraping time)

This guide walks through the full process of adding a new MLS Next division to Missing Table, using **Florida (Homegrown)** as a concrete example.

---

## Overview

Adding a division touches three repositories:

| Repo | What Changes |
|------|-------------|
| **match-scraper** | Add division to valid list, run discovery to find clubs/teams |
| **missing-table** | Add division to DB seed data, import clubs and teams |
| **match-scraper-agent** | Add scraping targets so the CronJob picks up the new division |

---

## Step 1: Discover Clubs (match-scraper)

The `discover` command scrapes MLS Next across all age groups for a division and outputs a clubs JSON file listing every team found.

### 1a. Add Division to VALID_DIVISIONS

Edit `src/cli/main.py` in the match-scraper repo and add the division name:

```python
VALID_DIVISIONS = [
    "Northeast",
    "Southeast",
    "Central",
    # ... existing divisions ...
    "Florida",      # <-- add here
]
```

### 1b. Run Discovery

```bash
cd ~/gitrepos/match-scraper
uv run mls-scraper discover --division Florida
```

This will:
- Scrape all age groups (U13, U14, U15, U16, U17, U19) for the division
- Extract every unique team name from home and away fields
- Output `florida-clubs.json` with clubs and their age group coverage

**Options:**
```bash
# Custom output filename
uv run mls-scraper discover --division Florida --output florida-clubs.json

# Limit to specific age groups (faster for testing)
uv run mls-scraper discover --division Florida --age-groups U14,U15

# Show browser (useful for debugging)
uv run mls-scraper discover --division Florida --no-headless
```

### 1c. Review the Output

The output file follows the `clubs.json` format:

```json
[
  {
    "club_name": "Inter Miami CF",
    "location": "",
    "website": "",
    "teams": [
      {
        "team_name": "Inter Miami CF",
        "league": "Homegrown",
        "division": "Florida",
        "age_groups": ["U13", "U14", "U17"]
      }
    ]
  }
]
```

Review the file and note:
- **Club count** — does it look reasonable for the division?
- **Age group coverage** — some clubs won't have teams in every age group (normal)
- **Team names** — these come directly from MLS Next and must match exactly for scraping to work

### 1d. Commit to match-scraper

```bash
git checkout -b feature/add-florida-division
git add src/cli/main.py src/models/discovery.py src/scraper/division_discovery.py
git commit -m "feat: Add Florida to VALID_DIVISIONS and discover command"
git push origin feature/add-florida-division
# Create PR and merge
```

---

## Step 2: Add Division to MT Database (missing-table)

### 2a. Update Seed Data

Edit `supabase-local/seed.sql` and add the division to the divisions INSERT:

```sql
-- Divisions (depend on leagues)
INSERT INTO public.divisions (id, name, description, league_id) VALUES
  (1, 'Northeast', 'Northeast Division', 1),
  (2, 'Florida', 'Florida Division', 1),        -- league_id=1 is Homegrown
  (7, 'New England', 'New England Division', 2)  -- league_id=2 is Academy
ON CONFLICT (id) DO NOTHING;
```

**Notes:**
- Use the next available `id` (check existing values)
- `league_id` = 1 for Homegrown, 2 for Academy
- Academy divisions are called "conferences" on MLS Next but stored in the same `divisions` table

### 2b. Update Setup Script

Edit `backend/scripts/setup/setup_leagues_divisions.py` and add the division:

```python
divisions_to_create = [
    {
        "name": "Northeast",
        "league_id": homegrown_league_id,
        "description": "Northeast Division (Homegrown)",
    },
    {
        "name": "Florida",
        "league_id": homegrown_league_id,
        "description": "Florida Division (Homegrown)",
    },
    # ... other divisions ...
]
```

### 2c. Apply to Local Database

**Option A** — Reset DB (wipes match data, applies seed):
```bash
cd supabase-local && npx supabase db reset
```

**Option B** — Run setup script (keeps existing data):
```bash
cd backend && uv run python scripts/setup/setup_leagues_divisions.py
```

### 2d. Verify

```sql
SELECT d.name, l.name as league
FROM divisions d
JOIN leagues l ON d.league_id = l.id
WHERE d.name = 'Florida';
```

---

## Step 3: Import Clubs and Teams (missing-table)

### 3a. Add Discovered Clubs to clubs.json

Merge the entries from the discovered file (e.g., `florida-clubs.json`) into the main `clubs.json` at the project root. Each club entry includes:
- `club_name`, `location`, `website`
- `teams[]` with `team_name`, `league`, `division`, and `age_groups`

You can optionally fill in `location` and `website` fields for clubs you know.

### 3b. Sync Clubs to Database

Start the backend first, then run the sync:

```bash
# Start MT backend
./missing-table.sh dev

# Sync clubs.json to database (creates clubs and teams)
cd backend && uv run python manage_clubs.py sync

# Dry run first to preview changes
cd backend && uv run python manage_clubs.py sync --dry-run
```

### 3c. Verify

```bash
cd backend && uv run python manage_clubs.py list
```

Check that the new division's clubs and teams appear in the output.

---

## Step 4: Enable Automated Scraping (match-scraper-agent)

### 4a. Update Agent System Prompt

Edit `agent.md` to add the new scraping targets:

```markdown
## What to Scrape

You MUST scrape all five of these targets, in priority order:

1. **U14 HG Northeast** (top priority)
2. **U13 HG Northeast**
3. **U14 HG Florida** (division="Florida")      <-- add
4. **U13 HG Florida** (division="Florida")      <-- add
5. **U14 Academy New England** (conference="New England")
```

### 4b. Add CLI Target Mappings

Edit `src/cli/main.py` and add entries to both `_TARGET_SCRAPER_CONFIG` and `_TARGET_PROMPTS`:

```python
_TARGET_SCRAPER_CONFIG: dict[str, dict[str, str]] = {
    # ... existing targets ...
    "u14-hg-florida": {
        "age_group": "U14",
        "league": "Homegrown",
        "division": "Florida",
    },
    "u13-hg-florida": {
        "age_group": "U13",
        "league": "Homegrown",
        "division": "Florida",
    },
}

_TARGET_PROMPTS: dict[str, str] = {
    # ... existing targets ...
    "u14-hg-florida": (
        "Only scrape U14 Homegrown Florida (division='Florida') today. "
        "Do not scrape other targets."
    ),
    "u13-hg-florida": (
        "Only scrape U13 Homegrown Florida (division='Florida') today. "
        "Do not scrape other targets."
    ),
}
```

**Note:** Homegrown divisions use the `division` parameter. Academy conferences use the `conference` parameter.

### 4c. Test Locally

```bash
cd ~/gitrepos/match-scraper-agent

# Test scraping without the LLM agent (direct scraper test)
uv run match-scraper-agent scrape --target u14-hg-florida

# Test with the full agent (dry run, no RabbitMQ submission)
uv run match-scraper-agent run --target u14-hg-florida --dry-run
```

### 4d. Commit to match-scraper-agent

```bash
git checkout -b feature/florida-targets
git add agent.md src/cli/main.py
git commit -m "feat: Add Florida scraping targets"
git push origin feature/florida-targets
# Create PR and merge
```

---

## Step 5: Deploy

1. **Merge PRs** in all three repos
2. **missing-table**: CI builds images, ArgoCD deploys. Apply seed changes to prod DB if needed:
   ```bash
   cd supabase-local && npx supabase db push --linked
   ```
3. **match-scraper-agent**: After merge, rebuild the K3s CronJob image. The next scheduled run (4x/day) will automatically scrape the new division.

---

## Checklist

- [ ] **match-scraper**: Division added to `VALID_DIVISIONS`
- [ ] **match-scraper**: `discover` command run, clubs JSON reviewed
- [ ] **missing-table**: Division added to `supabase-local/seed.sql`
- [ ] **missing-table**: Division added to `backend/scripts/setup/setup_leagues_divisions.py`
- [ ] **missing-table**: Local DB updated (reset or setup script)
- [ ] **missing-table**: Discovered clubs merged into `clubs.json`
- [ ] **missing-table**: `manage_clubs.py sync` run successfully
- [ ] **match-scraper-agent**: Targets added to `agent.md`
- [ ] **match-scraper-agent**: Targets added to `_TARGET_SCRAPER_CONFIG` and `_TARGET_PROMPTS`
- [ ] **match-scraper-agent**: Local scrape test passes
- [ ] All PRs merged and deployed

---

## Reference: Key Files

| File | Repo | Purpose |
|------|------|---------|
| `src/cli/main.py` (VALID_DIVISIONS) | match-scraper | List of scrapeable divisions |
| `src/scraper/division_discovery.py` | match-scraper | Discovery engine |
| `supabase-local/seed.sql` | missing-table | Division seed data |
| `backend/scripts/setup/setup_leagues_divisions.py` | missing-table | Division setup via API |
| `clubs.json` | missing-table | Club/team definitions |
| `backend/manage_clubs.py` | missing-table | Club/team sync tool |
| `agent.md` | match-scraper-agent | Agent system prompt (what to scrape) |
| `src/cli/main.py` (_TARGET_*) | match-scraper-agent | CLI target mappings |

---

<div align="center">

[Back to Development Guide](README.md) | [Back to Documentation Hub](../README.md)

</div>
