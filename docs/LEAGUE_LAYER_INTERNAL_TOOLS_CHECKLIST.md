# League Layer Internal Tools Checklist

Detailed checklist for updating internal tools to support the League layer.

**Related Document**: [LEAGUE_LAYER_IMPLEMENTATION.md](./LEAGUE_LAYER_IMPLEMENTATION.md)

---

## Table of Contents

1. [P0 - Critical Tools](#p0---critical-tools)
2. [P1 - High Priority Tools](#p1---high-priority-tools)
3. [P2 - Medium Priority Tools](#p2---medium-priority-tools)
4. [P3 - Low Priority Tools](#p3---low-priority-tools)
5. [P4 - Testing Only](#p4---testing-only)
6. [Match-Scraper Integration](#match-scraper-integration)

---

## P0 - Critical Tools

**Must complete before deploying to ANY environment**

### ✅ Tool 1: API Client Models (`backend/api_client/models.py`)

**Impact**: 🔴 CRITICAL - Used by match-scraper and other API consumers

**File Location**: `backend/api_client/models.py`

**Current Code** (Lines 27-34):
```python
class DivisionCreate(BaseModel):
    name: str = Field(..., title='Name')
    description: Optional[str] = Field(None, title='Description')

class DivisionUpdate(BaseModel):
    name: str = Field(..., title='Name')
    description: Optional[str] = Field(None, title='Description')
```

**Updated Code**:
```python
class DivisionCreate(BaseModel):
    name: str = Field(..., title='Name')
    description: Optional[str] = Field(None, title='Description')
    league_id: int = Field(..., title='League Id')  # ← NEW REQUIRED FIELD

class DivisionUpdate(BaseModel):
    name: Optional[str] = Field(None, title='Name')
    description: Optional[str] = Field(None, title='Description')
    league_id: Optional[int] = Field(None, title='League Id')  # ← NEW OPTIONAL FIELD
```

**Implementation Steps**:
- [ ] 1. Open `backend/api_client/models.py`
- [ ] 2. Add `league_id: int = Field(..., title='League Id')` to `DivisionCreate`
- [ ] 3. Add `league_id: Optional[int] = Field(None, title='League Id')` to `DivisionUpdate`
- [ ] 4. Check if models are auto-generated from OpenAPI schema
- [ ] 5. If auto-generated, update `backend/app.py` Division models first, then regenerate:
  ```bash
  cd backend
  uv run python scripts/generate_api_models.py
  ```
- [ ] 6. If manually maintained, make changes directly

**Testing**:
- [ ] Run: `cd backend && uv run python -c "from api_client.models import DivisionCreate; print(DivisionCreate.model_fields)"`
- [ ] Verify `league_id` appears in output
- [ ] Test importing: `from api_client.models import DivisionCreate, DivisionUpdate`

**Validation**:
```bash
# Test model instantiation
cd backend
uv run python -c "
from api_client.models import DivisionCreate
div = DivisionCreate(name='Test', description='Test div', league_id=1)
print(f'✅ DivisionCreate works: {div.model_dump()}')
"
```

**Why Critical**: Match-scraper uses these models. Without this change, match-scraper cannot create divisions after schema migration, breaking the entire integration.

---

## P1 - High Priority Tools

**Complete before frontend work begins**

### ✅ Tool 2: API Client (`backend/api_client/client.py`)

**Impact**: 🟡 MEDIUM - API client methods need updates

**File Location**: `backend/api_client/client.py`

**Check Required Methods**:
1. `create_division()` - Should accept `league_id`
2. `update_division()` - Should accept `league_id`
3. `get_divisions()` - Should support `?league_id=X` filtering

**Implementation Steps**:
- [ ] 1. Search for division-related methods in `client.py`
- [ ] 2. Review method signatures
- [ ] 3. Update to include league_id parameter where needed
- [ ] 4. Update docstrings to document league_id parameter

**Testing**:
```bash
cd backend
# Review the client methods
grep -n "def.*division" api_client/client.py
```

---

### ✅ Tool 3: Database Inspector (`backend/inspect_db.py`)

**Impact**: 🟡 MEDIUM - Developer troubleshooting tool

**File Location**: `backend/inspect_db.py`

#### Task 3.1: Add `leagues` Command

**Add new command** (insert after `divisions` command, around line 157):

```python
@app.command()
def leagues(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    show_sql: bool = typer.Option(False, "--show-sql", help="Show SQL query")
):
    """List all leagues"""
    load_environment()
    supabase = get_supabase_client()

    response = supabase.table("leagues").select("*").order("name").execute()

    table = Table(title="Leagues", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", width=5)
    table.add_column("Name", style="green", width=20)
    table.add_column("Active", style="yellow", width=8)
    if verbose:
        table.add_column("Description", style="dim", width=30)
        table.add_column("Created", style="dim", width=10)

    for league in response.data:
        row = [
            str(league["id"]),
            league["name"],
            "✓" if league.get("is_active") else "✗"
        ]
        if verbose:
            row.append(league.get("description", "N/A") or "N/A")
            if league.get("created_at"):
                row.append(league["created_at"][:10])
        table.add_row(*row)

    console.print(table)
    console.print(f"\n[green]Total:[/green] {len(response.data)} leagues")

    if show_sql:
        sql_query = "SELECT * FROM leagues ORDER BY name ASC;"
        console.print(f"\n[cyan]SQL Query (copy to Supabase SQL Editor):[/cyan]")
        console.print(f"[white]{sql_query}[/white]")
```

**Implementation Steps**:
- [ ] 1. Open `backend/inspect_db.py`
- [ ] 2. Add new `leagues()` command after `divisions()` command
- [ ] 3. Test: `cd backend && uv run python inspect_db.py leagues`
- [ ] 4. Test verbose mode: `cd backend && uv run python inspect_db.py leagues -v`
- [ ] 5. Test SQL display: `cd backend && uv run python inspect_db.py leagues --show-sql`

#### Task 3.2: Update `divisions` Command

**Current Code** (Lines 128-156):
```python
@app.command()
def divisions(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """List all divisions"""
    load_environment()
    supabase = get_supabase_client()

    response = supabase.table("divisions").select("*").order("name").execute()

    table = Table(title="Divisions", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    if verbose:
        table.add_column("Created", style="dim")

    for div in response.data:
        row = [str(div["id"]), div["name"]]
        if verbose and div.get("created_at"):
            row.append(div["created_at"])
        table.add_row(*row)

    console.print(table)
    console.print(f"\n[green]Total:[/green] {len(response.data)} divisions")
```

**Updated Code**:
```python
@app.command()
def divisions(
    league: Optional[str] = typer.Option(None, "--league", "-l", help="Filter by league name"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """List all divisions"""
    load_environment()
    supabase = get_supabase_client()

    # Updated query to include league info
    response = supabase.table("divisions").select(
        "*, leagues!divisions_league_id_fkey(id, name)"
    ).order("name").execute()

    divisions_data = response.data

    # Filter by league if specified
    if league:
        divisions_data = [
            d for d in divisions_data
            if d.get("leagues") and league.lower() in d["leagues"]["name"].lower()
        ]

    table = Table(
        title=f"Divisions ({len(divisions_data)})",
        show_header=True,
        header_style="bold magenta"
    )
    table.add_column("ID", style="cyan", width=5)
    table.add_column("Name", style="green", width=25)
    table.add_column("League", style="yellow", width=20)  # ← NEW COLUMN
    if verbose:
        table.add_column("Created", style="dim", width=10)

    for div in divisions_data:
        league_name = "Unknown"
        if div.get("leagues"):
            league_name = div["leagues"].get("name", "Unknown")

        row = [str(div["id"]), div["name"], league_name]
        if verbose and div.get("created_at"):
            row.append(div["created_at"][:10])
        table.add_row(*row)

    console.print(table)
    console.print(f"\n[green]Total:[/green] {len(divisions_data)} divisions")

    # Show filter info if applied
    if league:
        console.print(f"[dim]Filtered by league: {league}[/dim]")
```

**Implementation Steps**:
- [ ] 1. Locate `divisions()` command in `backend/inspect_db.py` (around line 128)
- [ ] 2. Add `league` parameter to function signature
- [ ] 3. Update Supabase query to include league join
- [ ] 4. Add league filtering logic
- [ ] 5. Add "League" column to table
- [ ] 6. Update row construction to include league name

**Testing**:
- [ ] Test basic: `cd backend && uv run python inspect_db.py divisions`
- [ ] Test league filter: `cd backend && uv run python inspect_db.py divisions --league Homegrown`
- [ ] Test verbose: `cd backend && uv run python inspect_db.py divisions -v`
- [ ] Test both: `cd backend && uv run python inspect_db.py divisions -l Homegrown -v`

**Validation**:
```bash
# After migration, verify divisions show league info
cd backend
APP_ENV=local uv run python inspect_db.py divisions

# Should show output like:
# ID | Name       | League
# 1  | Northeast  | Homegrown
# 2  | Southeast  | Homegrown
```

---

## P2 - Medium Priority Tools

**Complete before dev deployment**

### ✅ Tool 4: Team Population Script (`backend/populate_teams_supabase.py`)

**Impact**: 🟡 MEDIUM - Data seeding script

**File Location**: `backend/populate_teams_supabase.py`

**Issue**: Line 79-86 hardcodes `division_id = 1` without league context.

**Current Code** (Lines 79-86):
```python
# Add team mapping for U14 age group (id=2) with default division (id=1)
team_mappings.append(
    {
        "team_id": team_id,
        "age_group_id": 2,  # U14
        "division_id": 1,  # Default division
    }
)
```

**Updated Code**:
```python
# Get Homegrown league
homegrown_league = supabase.table("leagues").select("id").eq("name", "Homegrown").execute()
if not homegrown_league.data:
    print("❌ Error: Homegrown league not found")
    return

league_id = homegrown_league.data[0]["id"]

# Get or create default division for Homegrown league
divisions = supabase.table("divisions").select("id").eq("name", "Default").eq("league_id", league_id).execute()
if divisions.data:
    division_id = divisions.data[0]["id"]
    print(f"✅ Using existing division (ID: {division_id})")
else:
    # Create default division if it doesn't exist
    print("Creating default division for Homegrown league...")
    new_div = supabase.table("divisions").insert({
        "name": "Default",
        "description": "Default division for Homegrown league",
        "league_id": league_id
    }).execute()
    division_id = new_div.data[0]["id"]
    print(f"✅ Created division (ID: {division_id})")

# Add team mapping for U14 age group with proper division
team_mappings.append(
    {
        "team_id": team_id,
        "age_group_id": 2,  # U14
        "division_id": division_id,  # ← Now uses league-aware division
    }
)
```

**Implementation Steps**:
- [ ] 1. Open `backend/populate_teams_supabase.py`
- [ ] 2. Locate the team_mappings section (around line 73)
- [ ] 3. Add league lookup logic before the loop
- [ ] 4. Add division lookup/create logic
- [ ] 5. Update team_mappings to use the league-aware division_id
- [ ] 6. Add error handling if Homegrown league not found

**Testing**:
```bash
cd backend
# Run the script to test (use with caution - creates data!)
uv run python populate_teams_supabase.py

# Verify team mappings have correct division
uv run python inspect_db.py stats
```

---

### ✅ Tool 5: Team Population Script (Legacy) (`backend/populate_teams.py`)

**Impact**: 🟡 MEDIUM - Legacy data seeding script

**File Location**: `backend/populate_teams.py`

**Implementation Steps**:
- [ ] 1. Check if this script is still used: `git log --follow backend/populate_teams.py`
- [ ] 2. If used recently, apply similar updates as `populate_teams_supabase.py`
- [ ] 3. If not used, add deprecation notice at top of file
- [ ] 4. Consider moving to `.archive/` directory

**Deprecation Notice** (if not used):
```python
"""
DEPRECATED: This script is deprecated in favor of populate_teams_supabase.py
Last used: [DATE]
Kept for historical reference only.
"""
```

---

## P3 - Low Priority Tools

**Nice to have, can be done later**

### ✅ Tool 6: CLI Tool (`backend/cli.py`)

**Impact**: 🟢 LOW - Optional enhancement

**File Location**: `backend/cli.py`

**Current State**: CLI doesn't create divisions, so it works without changes.

**Optional Enhancement**: Add league management commands

**Implementation Steps** (Optional):
- [ ] 1. Add `leagues` command to list all leagues
- [ ] 2. Add `divisions` command with league filter
- [ ] 3. Update help text to mention league filtering

**Optional Code** (add after `table()` command):

```python
@app.command()
def leagues():
    """List all leagues."""
    try:
        response = httpx.get(f"{API_BASE_URL}/api/leagues")
        response.raise_for_status()
        leagues = response.json()

        table = Table(title="Leagues")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Active", style="yellow")

        for league in sorted(leagues, key=lambda x: x["name"]):
            active = "✓" if league.get("is_active", True) else "✗"
            table.add_row(str(league["id"]), league["name"], active)

        console.print(table)
        console.print(f"\n[dim]Total leagues: {len(leagues)}[/dim]")

    except httpx.RequestError as e:
        console.print(f"[red]Error connecting to API: {e}[/red]")
    except httpx.HTTPStatusError as e:
        console.print(f"[red]API error: {e}[/red]")


@app.command()
def divisions(
    league: str | None = typer.Option(None, "--league", "-l", help="Filter by league")
):
    """List all divisions with optional league filter."""
    try:
        url = f"{API_BASE_URL}/api/divisions"

        if league:
            # Get league ID first
            leagues_response = httpx.get(f"{API_BASE_URL}/api/leagues")
            leagues_response.raise_for_status()
            leagues = leagues_response.json()

            matching_league = next(
                (l for l in leagues if l['name'].lower() == league.lower()),
                None
            )

            if matching_league:
                url += f"?league_id={matching_league['id']}"
            else:
                console.print(f"[red]League '{league}' not found[/red]")
                return

        response = httpx.get(url)
        response.raise_for_status()
        divisions = response.json()

        table = Table(title="Divisions")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("League", style="yellow")

        for div in sorted(divisions, key=lambda x: x['name']):
            league_name = "Unknown"
            if isinstance(div.get('league'), dict):
                league_name = div['league'].get('name', 'Unknown')

            table.add_row(str(div['id']), div['name'], league_name)

        console.print(table)
        console.print(f"\n[dim]Total divisions: {len(divisions)}[/dim]")

    except httpx.RequestError as e:
        console.print(f"[red]Error connecting to API: {e}[/red]")
    except httpx.HTTPStatusError as e:
        console.print(f"[red]API error: {e}[/red]")
```

**Testing** (if implemented):
- [ ] `cd backend && uv run python cli.py leagues`
- [ ] `cd backend && uv run python cli.py divisions`
- [ ] `cd backend && uv run python cli.py divisions --league Homegrown`

---

## P4 - Testing Only

**Only testing required, likely no code changes**

### ✅ Tool 7: E2E Seeding Script (`scripts/e2e-seed-fixed.py`)

**Impact**: 🟢 LOW - Testing infrastructure

**File Location**: `scripts/e2e-seed-fixed.py`

**Analysis**: Script doesn't create divisions, only teams and games. Should work without changes.

**Testing Steps**:
- [ ] 1. Ensure local Supabase running: `cd supabase-local && npx supabase start`
- [ ] 2. Apply league migration: `npx supabase db reset`
- [ ] 3. Run E2E seed: `cd backend && uv run python ../scripts/e2e-seed-fixed.py`
- [ ] 4. Check output for errors
- [ ] 5. Verify test teams created: `uv run python inspect_db.py teams --search Test`
- [ ] 6. If failures occur, check if script references divisions

**Expected Output**:
```
🌱 Fixed E2E Test Database Seeding
========================================
🏆 Seeding test teams...
✅ Team: Test FC Alpha
✅ Team: Test FC Beta
✅ Team: Test FC Gamma
🔗 Creating team mappings...
✅ Mapping: Test FC Alpha -> U13
✅ Mapping: Test FC Beta -> U13
✅ Mapping: Test FC Gamma -> U13
⚽ Seeding test games...
✅ Game 1: Test FC Alpha vs Test FC Beta
✅ Game 2: Test FC Beta vs Test FC Alpha
✅ Game 3: Test FC Alpha vs Test FC Gamma

✅ E2E database seeding completed successfully!
```

---

### ✅ Tool 8: Database Backup/Restore (`scripts/db_tools.sh`)

**Impact**: 🟢 LOW - Should work automatically

**File Location**: `scripts/db_tools.sh`

**Analysis**: Script uses JSON export/import which should automatically include leagues table.

**Testing Steps**:
- [ ] 1. Run backup before migration: `./scripts/db_tools.sh backup`
- [ ] 2. Note backup filename
- [ ] 3. Apply league migration
- [ ] 4. Run backup after migration: `./scripts/db_tools.sh backup`
- [ ] 5. Verify leagues table in backup:
  ```bash
  # Check if leagues table exists in backup JSON
  cat backups/[latest-backup].json | grep -o '"leagues"' | head -1
  ```
- [ ] 6. Test restore: `./scripts/db_tools.sh restore [backup-file]`
- [ ] 7. Verify divisions have league_id: `cd backend && uv run python inspect_db.py divisions`

**Expected Behavior**:
- Backup should include `leagues` table data
- Restore should recreate `leagues` table
- All divisions should have `league_id` after restore

---

### ✅ Tool 9: Duplicate Match Cleanup (`backend/cleanup_duplicate_matches.py`)

**Impact**: 🟢 NONE - No changes needed

**File Location**: `backend/cleanup_duplicate_matches.py`

**Analysis**: Script works with matches table, not divisions or leagues. No changes needed.

**Testing Steps**:
- [ ] 1. Run scan after migration: `cd backend && uv run python cleanup_duplicate_matches.py scan`
- [ ] 2. Verify script runs without errors
- [ ] 3. If errors occur, check if script has any division references (unlikely)

---

## P5 - Review Required

**Audit for potential division references**

### ✅ Tool 10: MLS Next Data Migration (`backend/migrate_mlsnext_data.py`)

**Impact**: 🟡 UNKNOWN - Needs audit

**File Location**: `backend/migrate_mlsnext_data.py`

**Audit Steps**:
- [ ] 1. Open file and search for "division": `grep -n "division" backend/migrate_mlsnext_data.py`
- [ ] 2. Check if script creates divisions
- [ ] 3. Check if script updates divisions
- [ ] 4. If yes to either, add league_id handling
- [ ] 5. Add comment at top of file: "Assumes Homegrown league (ID: 1)"

**Code Pattern to Look For**:
```python
# BAD - Missing league_id
supabase.table("divisions").insert({"name": "Northeast"})

# GOOD - Includes league_id
homegrown_id = 1  # Homegrown league
supabase.table("divisions").insert({"name": "Northeast", "league_id": homegrown_id})
```

---

### ✅ Tool 11: U13 Games Import (`backend/import_u13_games_update.py`)

**Impact**: 🟡 UNKNOWN - Needs audit

**File Location**: `backend/import_u13_games_update.py`

**Audit Steps**:
- [ ] 1. Open file and search for "division": `grep -n "division" backend/import_u13_games_update.py`
- [ ] 2. Check if script creates divisions
- [ ] 3. Check if script looks up divisions
- [ ] 4. If creates, add league_id handling
- [ ] 5. If looks up, ensure lookup includes league context

---

## Match-Scraper Integration

### Coordination Checklist

**File Location**: `backend/api_client/models.py` (affects match-scraper)

**Before Deploying to Dev**:
- [ ] 1. Complete P0 Task: Update `api_client/models.py`
- [ ] 2. Document Homegrown league ID from dev environment
- [ ] 3. Create GitHub issue in match-scraper repo: "Add league support for missing-table integration"
- [ ] 4. Update match-scraper README with migration notes

**Match-Scraper Code Changes Required**:

```python
# In match-scraper repository

# 1. Add to config or constants
HOMEGROWN_LEAGUE_ID = 1  # Get from missing-table after migration

# 2. Update division creation logic
def create_or_get_division(name: str, description: str = None) -> int:
    """Create division or get existing one."""
    # Check if division exists in Homegrown league
    response = api_client.get(
        f"/api/divisions",
        params={"league_id": HOMEGROWN_LEAGUE_ID}
    )
    existing = next((d for d in response if d['name'] == name), None)

    if existing:
        return existing['id']

    # Create new division with league_id
    division_data = {
        "name": name,
        "description": description,
        "league_id": HOMEGROWN_LEAGUE_ID  # ← REQUIRED FIELD
    }

    response = api_client.post("/api/divisions", json=division_data)
    return response['id']
```

**Testing Match-Scraper Integration**:
- [ ] 1. Deploy updated missing-table to dev
- [ ] 2. Get Homegrown league ID from dev: `cd backend && APP_ENV=dev uv run python -c "from dao.enhanced_data_access_fixed import SportsDataAccess; dao = SportsDataAccess(); leagues = dao.get_all_leagues(); print([l for l in leagues if l['name']=='Homegrown'])"`
- [ ] 3. Update match-scraper config with league ID
- [ ] 4. Update match-scraper division creation code
- [ ] 5. Test scraper against dev environment
- [ ] 6. Verify divisions created with correct league_id

---

## Quick Reference Commands

### Inspection Commands

```bash
# List all leagues
cd backend && uv run python inspect_db.py leagues

# List divisions with league info
cd backend && uv run python inspect_db.py divisions

# Filter divisions by league
cd backend && uv run python inspect_db.py divisions --league Homegrown

# Show database stats (includes league count)
cd backend && uv run python inspect_db.py stats
```

### Testing Commands

```bash
# Test API client models
cd backend
uv run python -c "from api_client.models import DivisionCreate; print(DivisionCreate.model_fields)"

# Test backup/restore
./scripts/db_tools.sh backup
./scripts/db_tools.sh restore [backup-file]

# Test E2E seeding
cd backend && uv run python ../scripts/e2e-seed-fixed.py
```

### Verification Commands

```bash
# After migration, verify leagues table exists
cd backend
APP_ENV=local uv run python -c "
from dao.enhanced_data_access_fixed import SportsDataAccess
dao = SportsDataAccess()
leagues = dao.get_all_leagues()
print(f'✅ Found {len(leagues)} leagues')
for l in leagues:
    print(f'  - {l[\"name\"]} (ID: {l[\"id\"]})')
"

# Verify all divisions have league_id
APP_ENV=local uv run python -c "
from dao.enhanced_data_access_fixed import SportsDataAccess
dao = SportsDataAccess()
divisions = dao.get_all_divisions()
missing_league = [d for d in divisions if not d.get('league_id')]
if missing_league:
    print(f'❌ Found {len(missing_league)} divisions without league_id')
else:
    print(f'✅ All {len(divisions)} divisions have league_id')
"
```

---

## Completion Checklist

**Phase 1.5 Complete When**:
- [ ] All P0 tasks completed and tested
- [ ] All P1 tasks completed and tested
- [ ] All P2 tasks completed and tested
- [ ] P4 testing completed successfully
- [ ] P5 audit completed with any necessary updates
- [ ] Match-scraper integration plan documented
- [ ] All tools tested in local environment
- [ ] No errors when running inspection commands
- [ ] Backup/restore tested and working
- [ ] E2E tests passing

**Ready to Proceed to Phase 2** when all above items are checked.

---

**Last Updated**: 2025-10-29
**Document Version**: 1.0
**Author**: Claude Code
**Related**: [LEAGUE_LAYER_IMPLEMENTATION.md](./LEAGUE_LAYER_IMPLEMENTATION.md)
