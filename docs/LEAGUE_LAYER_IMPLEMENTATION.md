# League Layer Implementation Plan

## Overview
Add a "League" organizational layer to Missing Table, creating a hierarchy: **League → Division → Teams**

## Design Decisions

### Confirmed Requirements
- ✅ **Default League Name**: "Homegrown"
- ✅ **Division Name Uniqueness**: Unique per league (can have "Northeast" in multiple leagues)
- ✅ **League Required**: Every division MUST belong to a league (NOT NULL)
- ✅ **UI Filter Order**: Age Group → Season → League → Division
- ✅ **Data Migration**: All existing divisions assigned to "Homegrown" league

### Current Structure
```
Season + Age Group + Division → Teams → Matches
```

### Proposed Structure
```
League → Division → Teams
Season + Age Group + League + Division → Matches
```

---

## Phase 1: Database Schema & Migration

### Step 1.1: Create Leagues Table Migration

**File**: `supabase-local/migrations/YYYYMMDDHHMMSS_add_league_layer.sql`

```sql
-- ============================================================================
-- ADD LEAGUE LAYER
-- ============================================================================
-- Purpose: Add League organizational layer above Divisions
-- Impact: Creates leagues table, adds league_id to divisions, migrates data

-- ============================================================================
-- CREATE LEAGUES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS leagues (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create default "Homegrown" league
INSERT INTO leagues (name, description, is_active)
VALUES ('Homegrown', 'Default league for all existing divisions and teams', true);

-- ============================================================================
-- ADD LEAGUE_ID TO DIVISIONS
-- ============================================================================

-- Add league_id column (nullable initially for data migration)
ALTER TABLE divisions
ADD COLUMN IF NOT EXISTS league_id INTEGER REFERENCES leagues(id) ON DELETE RESTRICT;

-- Migrate all existing divisions to "Homegrown" league
UPDATE divisions
SET league_id = (SELECT id FROM leagues WHERE name = 'Homegrown')
WHERE league_id IS NULL;

-- Make league_id required after migration
ALTER TABLE divisions
ALTER COLUMN league_id SET NOT NULL;

-- ============================================================================
-- UPDATE UNIQUE CONSTRAINTS
-- ============================================================================

-- Drop old global unique constraint on division name
ALTER TABLE divisions DROP CONSTRAINT IF EXISTS divisions_name_key;

-- Add new unique constraint: division name unique within league
ALTER TABLE divisions
ADD CONSTRAINT divisions_name_league_id_key UNIQUE (name, league_id);

-- ============================================================================
-- ADD INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_divisions_league_id ON divisions(league_id);

-- ============================================================================
-- ENABLE RLS
-- ============================================================================

ALTER TABLE leagues ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- RLS POLICIES FOR LEAGUES
-- ============================================================================

-- Everyone can view leagues
DROP POLICY IF EXISTS leagues_select_all ON leagues;
CREATE POLICY leagues_select_all ON leagues FOR SELECT USING (true);

-- Only admins can modify leagues
DROP POLICY IF EXISTS leagues_admin_all ON leagues;
CREATE POLICY leagues_admin_all ON leagues FOR ALL USING (is_admin());

-- ============================================================================
-- UPDATE SCHEMA VERSION
-- ============================================================================

SELECT add_schema_version(
    '1.1.0',
    'YYYYMMDDHHMMSS_add_league_layer',
    'Add league organizational layer above divisions'
);
```

**Checklist**:
- [ ] Create migration file with timestamp
- [ ] Run migration on local database: `npx supabase db reset`
- [ ] Verify leagues table created
- [ ] Verify all divisions have league_id set to "Homegrown"
- [ ] Verify unique constraint updated (test creating duplicate division names in different leagues)

---

### Step 1.2: Backup Database Before Migration

```bash
# Backup current state before schema changes
cd /Users/silverbeer/gitrepos/missing-table
export APP_ENV=local
./scripts/db_tools.sh backup
```

**Checklist**:
- [ ] Create backup of current local database
- [ ] Verify backup file created in backups/ directory
- [ ] Note backup filename for rollback if needed

---

## Phase 2: Backend API Implementation

### Step 2.1: Update Pydantic Models

**File**: `backend/app.py` (Pydantic models section)

```python
# Add League models
class League(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class LeagueCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class LeagueUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

# Update Division model to include league_id
class Division(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    league_id: int  # ADD THIS
    league: Optional[League] = None  # ADD THIS for nested data
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class DivisionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    league_id: int  # ADD THIS

class DivisionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    league_id: Optional[int] = None  # ADD THIS
```

**Checklist**:
- [ ] Add League, LeagueCreate, LeagueUpdate models
- [ ] Update Division models to include league_id
- [ ] Add optional league nested field to Division model

---

### Step 2.2: Add League DAO Methods

**File**: `backend/dao/enhanced_data_access_fixed.py`

```python
# Add to SportsDataAccess class

def get_all_leagues(self) -> list[dict]:
    """Get all leagues ordered by name."""
    try:
        response = self.supabase_client.table('leagues')\
            .select('*')\
            .order('name')\
            .execute()
        return response.data
    except Exception as e:
        logger.error(f"Error fetching leagues: {e}")
        raise

def get_league_by_id(self, league_id: int) -> dict | None:
    """Get league by ID."""
    try:
        response = self.supabase_client.table('leagues')\
            .select('*')\
            .eq('id', league_id)\
            .execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error fetching league {league_id}: {e}")
        raise

def create_league(self, league_data: dict) -> dict:
    """Create new league."""
    try:
        response = self.supabase_client.table('leagues')\
            .insert(league_data)\
            .execute()
        return response.data[0]
    except Exception as e:
        logger.error(f"Error creating league: {e}")
        raise

def update_league(self, league_id: int, league_data: dict) -> dict:
    """Update league."""
    try:
        response = self.supabase_client.table('leagues')\
            .update(league_data)\
            .eq('id', league_id)\
            .execute()
        return response.data[0]
    except Exception as e:
        logger.error(f"Error updating league {league_id}: {e}")
        raise

def delete_league(self, league_id: int) -> bool:
    """Delete league (if no divisions exist)."""
    try:
        self.supabase_client.table('leagues')\
            .delete()\
            .eq('id', league_id)\
            .execute()
        return True
    except Exception as e:
        logger.error(f"Error deleting league {league_id}: {e}")
        raise

# Update existing get_all_divisions to include league data
def get_all_divisions(self) -> list[dict]:
    """Get all divisions with league info."""
    try:
        response = self.supabase_client.table('divisions')\
            .select('*, leagues!divisions_league_id_fkey(id, name, description, is_active)')\
            .order('name')\
            .execute()
        return response.data
    except Exception as e:
        logger.error(f"Error fetching divisions: {e}")
        raise

def get_divisions_by_league(self, league_id: int) -> list[dict]:
    """Get divisions filtered by league."""
    try:
        response = self.supabase_client.table('divisions')\
            .select('*, leagues!divisions_league_id_fkey(id, name, description)')\
            .eq('league_id', league_id)\
            .order('name')\
            .execute()
        return response.data
    except Exception as e:
        logger.error(f"Error fetching divisions for league {league_id}: {e}")
        raise
```

**Checklist**:
- [ ] Add league CRUD methods to DAO
- [ ] Update get_all_divisions to include league data
- [ ] Add get_divisions_by_league filter method
- [ ] Test DAO methods with local database

---

### Step 2.3: Add League API Endpoints

**File**: `backend/app.py` (API endpoints section)

```python
# ============================================================================
# LEAGUE ENDPOINTS
# ============================================================================

@app.get("/api/leagues")
async def get_leagues(current_user: dict[str, Any] = Depends(get_current_user_required)):
    """Get all leagues."""
    try:
        leagues = sports_dao.get_all_leagues()
        return leagues
    except Exception as e:
        logger.error(f"Error retrieving leagues: {e!s}")
        raise HTTPException(
            status_code=503, detail="Failed to fetch leagues"
        )

@app.post("/api/leagues")
async def create_league(
    league: LeagueCreate,
    current_user: dict[str, Any] = Depends(require_admin)
):
    """Create new league (admin only)."""
    try:
        league_data = league.dict()
        new_league = sports_dao.create_league(league_data)
        return new_league
    except Exception as e:
        logger.error(f"Error creating league: {e!s}")
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/leagues/{league_id}")
async def update_league(
    league_id: int,
    league: LeagueUpdate,
    current_user: dict[str, Any] = Depends(require_admin)
):
    """Update league (admin only)."""
    try:
        league_data = {k: v for k, v in league.dict().items() if v is not None}
        updated_league = sports_dao.update_league(league_id, league_data)
        return updated_league
    except Exception as e:
        logger.error(f"Error updating league {league_id}: {e!s}")
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/leagues/{league_id}")
async def delete_league(
    league_id: int,
    current_user: dict[str, Any] = Depends(require_admin)
):
    """Delete league (admin only, fails if divisions exist)."""
    try:
        sports_dao.delete_league(league_id)
        return {"message": f"League {league_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting league {league_id}: {e!s}")
        raise HTTPException(
            status_code=400,
            detail="Cannot delete league with existing divisions"
        )

# Update divisions endpoint to support league filtering
@app.get("/api/divisions")
async def get_divisions(
    current_user: dict[str, Any] = Depends(get_current_user_required),
    league_id: Optional[int] = Query(None, description="Filter by league ID")
):
    """Get all divisions, optionally filtered by league."""
    try:
        if league_id:
            divisions = sports_dao.get_divisions_by_league(league_id)
        else:
            divisions = sports_dao.get_all_divisions()
        return divisions
    except Exception as e:
        logger.error(f"Error retrieving divisions: {e!s}")
        raise HTTPException(status_code=503, detail="Failed to fetch divisions")
```

**Checklist**:
- [ ] Add GET /api/leagues endpoint
- [ ] Add POST /api/leagues endpoint (admin only)
- [ ] Add PUT /api/leagues/{id} endpoint (admin only)
- [ ] Add DELETE /api/leagues/{id} endpoint (admin only)
- [ ] Update GET /api/divisions to support league_id filter
- [ ] Test all endpoints with curl or Postman

---

## Phase 3: Frontend - Admin Panel

### Step 3.1: Create AdminLeagues Component

**File**: `frontend/src/components/admin/AdminLeagues.vue`

**Note**: Copy structure from `AdminDivisions.vue` and adapt for leagues

```vue
<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Leagues Management</h3>
      <button
        @click="showAddModal = true"
        class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium"
      >
        Add League
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>

    <!-- Error State -->
    <div v-if="error" class="bg-red-50 border border-red-200 rounded-md p-4 mb-4">
      <div class="text-red-800">{{ error }}</div>
    </div>

    <!-- Leagues Table -->
    <div v-else class="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
      <table class="min-w-full divide-y divide-gray-300">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Name
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Description
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Divisions
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Status
            </th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="league in leagues" :key="league.id">
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
              {{ league.name }}
            </td>
            <td class="px-6 py-4 text-sm text-gray-500">
              {{ league.description || 'No description' }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ getDivisionCount(league.id) }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
              <span
                :class="league.is_active ? 'text-green-600' : 'text-gray-400'"
              >
                {{ league.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
              <button
                @click="editLeague(league)"
                class="text-blue-600 hover:text-blue-900 mr-3"
              >
                Edit
              </button>
              <button
                @click="deleteLeague(league)"
                class="text-red-600 hover:text-red-900"
                :disabled="getDivisionCount(league.id) > 0"
                :class="{
                  'opacity-50 cursor-not-allowed': getDivisionCount(league.id) > 0,
                }"
              >
                Delete
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Add/Edit Modal (implement similar to other admin components) -->
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';

export default {
  name: 'AdminLeagues',
  setup() {
    const authStore = useAuthStore();
    const leagues = ref([]);
    const divisions = ref([]);
    const loading = ref(true);
    const formLoading = ref(false);
    const error = ref(null);
    const showAddModal = ref(false);
    const showEditModal = ref(false);
    const editingLeague = ref(null);

    const formData = ref({
      name: '',
      description: '',
      is_active: true,
    });

    const fetchLeagues = async () => {
      try {
        loading.value = true;
        const response = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/leagues`,
          { method: 'GET' }
        );
        leagues.value = response;
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchDivisions = async () => {
      try {
        const response = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/divisions`,
          { method: 'GET' }
        );
        divisions.value = response;
      } catch (err) {
        console.error('Error fetching divisions:', err);
      }
    };

    const getDivisionCount = leagueId => {
      return divisions.value.filter(d => d.league_id === leagueId).length;
    };

    const createLeague = async () => {
      try {
        formLoading.value = true;
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/leagues`,
          {
            method: 'POST',
            body: JSON.stringify(formData.value),
          }
        );
        await fetchLeagues();
        closeModals();
        resetForm();
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    const editLeague = league => {
      editingLeague.value = league;
      formData.value = { ...league };
      showEditModal.value = true;
    };

    const updateLeague = async () => {
      try {
        formLoading.value = true;
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/leagues/${editingLeague.value.id}`,
          {
            method: 'PUT',
            body: JSON.stringify(formData.value),
          }
        );
        await fetchLeagues();
        closeModals();
        resetForm();
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    const deleteLeague = async league => {
      if (getDivisionCount(league.id) > 0) {
        error.value = 'Cannot delete league with existing divisions';
        return;
      }

      if (!confirm(`Delete league "${league.name}"?`)) return;

      try {
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/leagues/${league.id}`,
          { method: 'DELETE' }
        );
        await fetchLeagues();
      } catch (err) {
        error.value = err.message;
      }
    };

    const closeModals = () => {
      showAddModal.value = false;
      showEditModal.value = false;
      editingLeague.value = null;
    };

    const resetForm = () => {
      formData.value = {
        name: '',
        description: '',
        is_active: true,
      };
    };

    onMounted(async () => {
      await Promise.all([fetchLeagues(), fetchDivisions()]);
    });

    return {
      leagues,
      loading,
      formLoading,
      error,
      showAddModal,
      showEditModal,
      formData,
      createLeague,
      editLeague,
      updateLeague,
      deleteLeague,
      getDivisionCount,
      closeModals,
    };
  },
};
</script>
```

**Checklist**:
- [ ] Create AdminLeagues.vue component
- [ ] Implement CRUD operations (Create, Read, Update, Delete)
- [ ] Add validation (prevent deleting leagues with divisions)
- [ ] Test all operations in local environment

---

### Step 3.2: Update AdminPanel to Include Leagues Tab

**File**: `frontend/src/components/AdminPanel.vue`

```vue
<!-- Add to tabs -->
<button
  @click="currentTab = 'leagues'"
  :class="tabClass('leagues')"
>
  Leagues
</button>

<!-- Add to component rendering -->
<AdminLeagues v-if="currentTab === 'leagues'" />

<!-- Add to imports -->
<script>
import AdminLeagues from './admin/AdminLeagues.vue';

export default {
  components: {
    // ... existing components
    AdminLeagues,
  },
  // ...
};
</script>
```

**Checklist**:
- [ ] Add "Leagues" tab to AdminPanel
- [ ] Import AdminLeagues component
- [ ] Test navigation between tabs

---

### Step 3.3: Update AdminDivisions to Include League Selector

**File**: `frontend/src/components/admin/AdminDivisions.vue`

```vue
<!-- Add to the form modal -->
<div class="mb-4">
  <label class="block text-sm font-medium text-gray-700 mb-2">
    League
  </label>
  <select
    v-model="formData.league_id"
    required
    class="w-full px-3 py-2 border border-gray-300 rounded-md"
  >
    <option value="">Select League</option>
    <option v-for="league in leagues" :key="league.id" :value="league.id">
      {{ league.name }}
    </option>
  </select>
</div>

<!-- Update script section -->
<script>
// Add leagues ref
const leagues = ref([]);

// Add fetchLeagues function
const fetchLeagues = async () => {
  try {
    const response = await authStore.apiRequest(
      `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/leagues`,
      { method: 'GET' }
    );
    leagues.value = response;
  } catch (err) {
    console.error('Error fetching leagues:', err);
  }
};

// Update formData to include league_id
const formData = ref({
  name: '',
  description: '',
  league_id: '', // ADD THIS
});

// Update onMounted
onMounted(async () => {
  await Promise.all([fetchDivisions(), fetchTeams(), fetchLeagues()]);
});

// Add to return
return {
  // ... existing
  leagues,
};
</script>
```

**Checklist**:
- [ ] Add league dropdown to division form
- [ ] Fetch leagues on component mount
- [ ] Update formData to include league_id
- [ ] Test creating/editing divisions with league selection

---

## Phase 4: Frontend - Public UI

### Step 4.1: Update LeagueTable Component

**File**: `frontend/src/components/LeagueTable.vue`

```vue
<template>
  <div class="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Filter Controls -->
    <div class="bg-white shadow-sm rounded-lg p-6 mb-6">
      <!-- Age Group Row -->
      <div class="mb-4">
        <h3 class="text-sm font-medium text-gray-700 mb-3">Age Group</h3>
        <!-- existing age group dropdown -->
      </div>

      <!-- Season and League Row -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-4">
        <!-- Season Dropdown -->
        <div>
          <h3 class="text-sm font-medium text-gray-700 mb-3">Season</h3>
          <!-- existing season dropdown -->
        </div>

        <!-- League Dropdown (NEW) -->
        <div>
          <h3 class="text-sm font-medium text-gray-700 mb-3">League</h3>
          <select
            v-model="selectedLeagueId"
            @change="loadStandings"
            class="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option
              v-for="league in leagues"
              :key="league.id"
              :value="league.id"
            >
              {{ league.name }}
            </option>
          </select>
        </div>
      </div>

      <!-- Division Row -->
      <div>
        <h3 class="text-sm font-medium text-gray-700 mb-3">Division</h3>
        <select
          v-model="selectedDivisionId"
          @change="loadStandings"
          class="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
        >
          <option
            v-for="division in filteredDivisions"
            :key="division.id"
            :value="division.id"
          >
            {{ division.name }}
          </option>
        </select>
      </div>
    </div>

    <!-- Rest of component... -->
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';

export default {
  name: 'LeagueTable',
  setup() {
    const authStore = useAuthStore();
    const ageGroups = ref([]);
    const seasons = ref([]);
    const leagues = ref([]);
    const divisions = ref([]);
    const standings = ref([]);
    const loading = ref(false);
    const error = ref(null);

    const selectedAgeGroupId = ref(null);
    const selectedSeasonId = ref(null);
    const selectedLeagueId = ref(null);
    const selectedDivisionId = ref(null);

    // Filter divisions by selected league
    const filteredDivisions = computed(() => {
      if (!selectedLeagueId.value) return divisions.value;
      return divisions.value.filter(d => d.league_id === selectedLeagueId.value);
    });

    const fetchLeagues = async () => {
      try {
        const data = await authStore.apiCall(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/leagues`
        );
        leagues.value = data.sort((a, b) => a.name.localeCompare(b.name));

        // Set default to "Homegrown" league
        const homegrown = leagues.value.find(l => l.name === 'Homegrown');
        if (homegrown) {
          selectedLeagueId.value = homegrown.id;
        }
      } catch (err) {
        console.error('Error fetching leagues:', err);
      }
    };

    const fetchDivisions = async () => {
      try {
        const data = await authStore.apiCall(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/divisions`
        );
        divisions.value = data.sort((a, b) => a.name.localeCompare(b.name));
      } catch (err) {
        console.error('Error fetching divisions:', err);
      }
    };

    // Watch for league change and reset division selection
    watch(selectedLeagueId, () => {
      // Reset division to first in filtered list
      if (filteredDivisions.value.length > 0) {
        selectedDivisionId.value = filteredDivisions.value[0].id;
      } else {
        selectedDivisionId.value = null;
      }
    });

    // Update loadStandings to include league_id if needed
    const loadStandings = async () => {
      if (!selectedSeasonId.value || !selectedAgeGroupId.value || !selectedDivisionId.value) {
        return;
      }

      try {
        loading.value = true;
        error.value = null;

        const params = {
          seasonId: selectedSeasonId.value,
          ageGroupId: selectedAgeGroupId.value,
          divisionId: selectedDivisionId.value,
        };

        const url = `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/table?season_id=${params.seasonId}&age_group_id=${params.ageGroupId}&division_id=${params.divisionId}`;

        standings.value = await authStore.apiCall(url);
      } catch (err) {
        error.value = 'Failed to load standings. Please try again.';
        console.error('Error loading standings:', err);
      } finally {
        loading.value = false;
      }
    };

    // Watch all filters
    watch([selectedSeasonId, selectedAgeGroupId, selectedLeagueId, selectedDivisionId], () => {
      loadStandings();
    });

    onMounted(async () => {
      await Promise.all([
        fetchAgeGroups(),
        fetchSeasons(),
        fetchLeagues(),
        fetchDivisions(),
      ]);
    });

    return {
      ageGroups,
      seasons,
      leagues,
      divisions,
      filteredDivisions,
      standings,
      loading,
      error,
      selectedAgeGroupId,
      selectedSeasonId,
      selectedLeagueId,
      selectedDivisionId,
      loadStandings,
    };
  },
};
</script>
```

**Checklist**:
- [ ] Add leagues ref and selectedLeagueId
- [ ] Add fetchLeagues function
- [ ] Add league dropdown in UI (between season and division)
- [ ] Implement filteredDivisions computed property
- [ ] Add watcher to reset division when league changes
- [ ] Set default to "Homegrown" league on mount
- [ ] Test filtering by league

---

### Step 4.2: Update ScoresSchedule Component

**File**: `frontend/src/components/ScoresSchedule.vue`

Similar changes to LeagueTable.vue:
- Add league selector dropdown
- Filter divisions by league
- Default to "Homegrown" league

**Checklist**:
- [ ] Add league dropdown to filters
- [ ] Implement division filtering by league
- [ ] Set default league to "Homegrown"
- [ ] Test match filtering with league selection

---

## Phase 5: Testing & Validation

### Step 5.1: Database Testing

**Checklist**:
- [ ] Verify "Homegrown" league created
- [ ] Verify all existing divisions have league_id
- [ ] Test creating division with duplicate name in same league (should fail)
- [ ] Test creating division with duplicate name in different league (should succeed)
- [ ] Test deleting league with divisions (should fail)
- [ ] Test deleting league without divisions (should succeed)

---

### Step 5.2: Backend API Testing

```bash
# Test league endpoints
curl -X GET http://localhost:8000/api/leagues \
  -H "Authorization: Bearer YOUR_TOKEN"

curl -X POST http://localhost:8000/api/leagues \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "ECNL", "description": "Elite Clubs National League"}'

# Test divisions filtered by league
curl -X GET "http://localhost:8000/api/divisions?league_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Checklist**:
- [ ] Test GET /api/leagues (returns all leagues)
- [ ] Test POST /api/leagues with admin token (creates league)
- [ ] Test POST /api/leagues without admin token (returns 403)
- [ ] Test PUT /api/leagues/{id} (updates league)
- [ ] Test DELETE /api/leagues/{id} with divisions (fails)
- [ ] Test DELETE /api/leagues/{id} without divisions (succeeds)
- [ ] Test GET /api/divisions?league_id=X (filters by league)

---

### Step 5.3: Frontend Testing

**Admin Panel Testing**:
- [ ] Navigate to Leagues tab
- [ ] Create new league
- [ ] Edit league
- [ ] Try to delete league with divisions (should show error)
- [ ] Create division and assign to new league
- [ ] Verify division shows up under correct league

**Public UI Testing**:
- [ ] Load LeagueTable.vue
- [ ] Verify "Homegrown" league selected by default
- [ ] Change league selection
- [ ] Verify divisions filter correctly
- [ ] Load standings for different league/division combinations
- [ ] Test ScoresSchedule.vue with league filtering

---

## Phase 6: Documentation & Deployment

### Step 6.1: Update Documentation

**Files to Update**:
- [ ] `docs/03-architecture/database-schema.md` - Add leagues table diagram
- [ ] `docs/02-development/daily-workflow.md` - Update with league management
- [ ] `README.md` - Update overview with league concept
- [ ] `CLAUDE.md` - Update project overview

**Checklist**:
- [ ] Document leagues table schema
- [ ] Document league-division relationship
- [ ] Update architecture diagrams
- [ ] Add league management to admin workflow docs

---

### Step 6.2: Create Migration Script for Cloud Environments

**File**: `scripts/migrate_to_leagues.py`

```python
#!/usr/bin/env python3
"""
Migrate dev/prod environments to league layer.
Run after deploying new schema.
"""
import os
from supabase import create_client
from dotenv import load_dotenv

def migrate_environment(env_name: str):
    """Migrate environment to league layer."""
    print(f"🔧 Migrating {env_name} environment to league layer...")

    # Load environment
    env_file = f'.env.{env_name}'
    load_dotenv(env_file)

    # Create Supabase client
    supabase_url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')

    if not supabase_url or not service_key:
        print(f"❌ Missing credentials for {env_name}")
        return False

    supabase = create_client(supabase_url, service_key)

    # Check if migration already done
    leagues = supabase.table('leagues').select('*').execute()
    if leagues.data:
        print(f"✅ {env_name} already has leagues - migration complete")
        return True

    # Run migration (schema should already be applied via Supabase migration)
    # Just verify data integrity
    divisions = supabase.table('divisions').select('*').execute()
    divisions_without_league = [d for d in divisions.data if not d.get('league_id')]

    if divisions_without_league:
        print(f"⚠️  Found {len(divisions_without_league)} divisions without league_id")
        print(f"   Run the SQL migration first!")
        return False

    print(f"✅ {env_name} migration validated - all divisions have league_id")
    return True

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python migrate_to_leagues.py <env>")
        print("  env: local, dev, or prod")
        sys.exit(1)

    env = sys.argv[1]
    success = migrate_environment(env)
    sys.exit(0 if success else 1)
```

**Checklist**:
- [ ] Create migration validation script
- [ ] Test on local environment
- [ ] Run on dev environment after deploying schema
- [ ] Run on prod environment after deploying schema

---

### Step 6.3: Deploy to Dev Environment

**Deployment Steps**:
```bash
# 1. Commit all changes
git add .
git commit -m "feat: Add league organizational layer

- Add leagues table and migration
- Add league CRUD API endpoints
- Add AdminLeagues component
- Update divisions to belong to leagues
- Update LeagueTable and ScoresSchedule with league filtering
- Create 'Homegrown' default league for existing data"

# 2. Push to GitHub
git push origin feature/add-league-layer

# 3. Create PR and merge to main

# 4. Deployment will auto-trigger via GitHub Actions

# 5. After deployment, verify migration ran successfully
# 6. Test in dev environment (https://dev.missingtable.com)
```

**Checklist**:
- [ ] Commit all changes to feature branch
- [ ] Create PR with detailed description
- [ ] Review PR changes
- [ ] Merge PR to main
- [ ] Verify GitHub Actions deployment succeeds
- [ ] Test dev environment thoroughly
- [ ] Run migration validation script on dev

---

### Step 6.4: Deploy to Production

**Checklist**:
- [ ] Verify dev environment works correctly for 24-48 hours
- [ ] Create production deployment PR
- [ ] Get stakeholder approval
- [ ] Backup production database before deployment
- [ ] Deploy to production
- [ ] Verify migration ran successfully
- [ ] Test production environment
- [ ] Monitor for issues
- [ ] Update VERSION file if needed

---

## Rollback Plan

If issues occur, rollback steps:

### Database Rollback
```sql
-- Remove league_id from divisions
ALTER TABLE divisions DROP COLUMN IF EXISTS league_id;

-- Restore original unique constraint
ALTER TABLE divisions
ADD CONSTRAINT divisions_name_key UNIQUE (name);

-- Drop leagues table
DROP TABLE IF EXISTS leagues CASCADE;
```

### Code Rollback
```bash
# Revert to previous version
git revert <commit-hash>
git push origin main
```

**Checklist**:
- [ ] Document rollback procedure
- [ ] Test rollback on local environment
- [ ] Keep backup of pre-migration database state

---

## Success Criteria

**Phase 1 Complete**:
- [ ] Leagues table created
- [ ] All divisions have league_id
- [ ] "Homegrown" league exists with all divisions

**Phase 2 Complete**:
- [ ] All league API endpoints working
- [ ] Divisions can be filtered by league
- [ ] Admin operations secured

**Phase 3 Complete**:
- [ ] AdminLeagues component functional
- [ ] AdminDivisions includes league selector
- [ ] All CRUD operations work

**Phase 4 Complete**:
- [ ] LeagueTable shows league filter
- [ ] ScoresSchedule shows league filter
- [ ] Divisions filter by league correctly

**Phase 5 Complete**:
- [ ] All tests pass
- [ ] No regression in existing functionality
- [ ] Performance acceptable

**Phase 6 Complete**:
- [ ] Documentation updated
- [ ] Deployed to dev successfully
- [ ] Deployed to production successfully

---

## Estimated Timeline

| Phase | Time Estimate | Status |
|-------|--------------|--------|
| Phase 1: Database | 2-3 hours | ⬜ Not Started |
| Phase 2: Backend API | 4-6 hours | ⬜ Not Started |
| Phase 3: Admin Panel | 4-6 hours | ⬜ Not Started |
| Phase 4: Public UI | 4-6 hours | ⬜ Not Started |
| Phase 5: Testing | 2-3 hours | ⬜ Not Started |
| Phase 6: Docs & Deploy | 2-3 hours | ⬜ Not Started |
| **Total** | **18-27 hours** | **0% Complete** |

---

## Notes & Decisions Log

### 2025-10-29
- ✅ Confirmed default league name: "Homegrown"
- ✅ Confirmed division names unique per league
- ✅ Confirmed league required for all divisions
- ✅ Confirmed UI filter order: Age Group → Season → League → Division
- ✅ Created feature branch: `feature/add-league-layer`
- ✅ Created implementation document

---

**Last Updated**: 2025-10-29
**Document Version**: 1.0
**Author**: Claude Code
**Status**: Ready for Implementation
