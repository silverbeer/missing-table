<template>
  <div data-testid="leaderboards-panel">
    <FilterPanel view="ranking" :summary="summaryText" class="mb-6">
      <div data-testid="age-group-filter">
        <h3 class="text-sm font-medium text-fg mb-3">Age Groups</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="age in AGE_GROUPS"
            :key="age"
            type="button"
            @click="selectedAgeGroup = age"
            :class="pillClass(selectedAgeGroup === age)"
            :data-testid="`age-group-${age}`"
          >
            {{ age }}
          </button>
        </div>
      </div>
      <div data-testid="league-filter">
        <h3 class="text-sm font-medium text-fg mb-3">Division</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="league in LEAGUES"
            :key="league"
            type="button"
            @click="selectedLeague = league"
            :class="pillClass(selectedLeague === league)"
            :data-testid="`league-${league}`"
          >
            {{ league }}
          </button>
        </div>
      </div>
    </FilterPanel>

    <div
      v-if="loading"
      class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 animate-pulse"
      data-testid="leaderboards-skeleton"
      aria-busy="true"
    >
      <div
        v-for="n in 3"
        :key="n"
        class="rounded-lg border border-line bg-card p-4 space-y-3"
      >
        <div class="h-4 w-1/2 rounded bg-surface-alt"></div>
        <div class="h-3 w-3/4 rounded bg-surface-alt"></div>
        <div v-for="r in 5" :key="r" class="h-6 rounded bg-surface-alt"></div>
      </div>
    </div>

    <div
      v-else-if="error"
      class="rounded-lg border border-line bg-card p-6 text-center"
      data-testid="leaderboards-error"
    >
      <p class="text-sm text-fg mb-3">{{ error }}</p>
      <button
        type="button"
        class="px-4 py-2 text-sm rounded-lg font-medium bg-brand-500 text-white"
        data-testid="leaderboards-retry"
        @click="retry"
      >
        Retry
      </button>
    </div>

    <div
      v-else-if="isEmpty"
      class="rounded-lg border border-line bg-card p-6 text-center"
      data-testid="leaderboards-empty"
    >
      <p class="text-base font-semibold text-fg">No results yet</p>
      <p
        v-if="result?.reason"
        class="mt-1 text-sm text-fg-muted"
        data-testid="leaderboards-empty-reason"
      >
        {{ result.reason }}
      </p>
    </div>

    <template v-else-if="result">
      <!-- Below sm one board at a time: six stacked cards is a long scroll. -->
      <div class="sm:hidden mb-4">
        <label class="sr-only" for="board-picker">Board</label>
        <select
          id="board-picker"
          v-model="selectedBoardKey"
          class="block w-full px-3 py-2 border border-line bg-card text-fg rounded-md text-sm"
          data-testid="board-picker"
        >
          <option v-for="board in boards" :key="board.key" :value="board.key">
            {{ board.title }}
          </option>
        </select>
      </div>
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <LeaderboardCard
          v-for="board in boards"
          :key="board.key"
          :class="board.key === selectedBoardKey ? '' : 'hidden sm:flex'"
          :board="board"
          :coverage="result.coverage"
          :age-group="result.age_group?.name || selectedAgeGroup"
          :league="result.league || selectedLeague"
          @select-team="navigateToTeam"
        />
      </div>
      <UnrankedList
        v-if="result.unranked_count > 0"
        class="mt-6"
        :rows="result.unranked || []"
        :count="result.unranked_count"
        :min-gp="result.coverage?.min_gp ?? 6"
      />
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import { filterSummary } from '@/utils/filterSummary';
import FilterPanel from '../ui/FilterPanel.vue';
import LeaderboardCard from './LeaderboardCard.vue';
import UnrankedList from './UnrankedList.vue';

// Leaderboards cover a top-level league's conferences (SB-1781); Flex is a
// child league and has none of its own, so it is not offered.
const AGE_GROUPS = ['U15', 'U16', 'U17', 'U19'];
const LEAGUES = ['Homegrown'];
// The per-match boards and the two records. Totals are left to the CLI: next
// to per-match values they mostly restate matches played.
const BOARD_ORDER = ['ppg', 'gf_pg', 'ga_pg', 'gd_pg', 'unbeaten', 'pro_wins'];
const LIMIT = 20;

const emit = defineEmits(['navigate-to-team']);
const authStore = useAuthStore();

const selectedAgeGroup = ref('U15');
const selectedLeague = ref('Homegrown');
const selectedBoardKey = ref(BOARD_ORDER[0]);

const result = ref(null);
const loading = ref(false);
const error = ref('');

// For the league id in a team click. Optional: a failed read leaves the
// navigation with one filter fewer. Logos come on each row (club_logo_url).
const leagues = ref([]);

const pillClass = active => [
  'px-4 py-2 text-sm rounded-lg font-medium transition-colors',
  active
    ? 'bg-brand-500 text-white shadow-sm'
    : 'bg-surface-alt text-fg-muted hover:bg-line',
];

const summaryText = computed(() =>
  filterSummary([selectedAgeGroup.value, selectedLeague.value])
);

const boards = computed(() => {
  const byKey = Object.fromEntries(
    (result.value?.boards || []).map(b => [b.key, b])
  );
  return BOARD_ORDER.map(k => byKey[k]).filter(Boolean);
});

const isEmpty = computed(() => {
  const r = result.value;
  if (!r) return false;
  if (r.reason) return true;
  const anyRows = boards.value.some(b => b.rows && b.rows.length > 0);
  return !anyRows && !(r.unranked && r.unranked.length > 0);
});

// A filter change mid-flight must not let the older answer land last.
let requestId = 0;

const fetchBoards = async () => {
  const id = ++requestId;
  loading.value = true;
  error.value = '';
  const params = new URLSearchParams({
    league: selectedLeague.value,
    age_group: selectedAgeGroup.value,
    limit: String(LIMIT),
  });
  try {
    const data = await authStore.apiRequest(
      `${getApiBaseUrl()}/api/leaderboards?${params}`
    );
    if (id !== requestId) return;
    result.value = data;
    if (!boards.value.some(b => b.key === selectedBoardKey.value)) {
      selectedBoardKey.value = boards.value[0]?.key ?? BOARD_ORDER[0];
    }
  } catch (err) {
    if (id !== requestId) return;
    result.value = null;
    error.value = err?.message || 'Leaderboards are unavailable right now.';
  } finally {
    if (id === requestId) loading.value = false;
  }
};

const fetchLeagues = async () => {
  try {
    const data = await authStore.apiRequest(`${getApiBaseUrl()}/api/leagues`);
    if (Array.isArray(data)) leagues.value = data;
  } catch (err) {
    console.error('Error fetching leagues:', err);
  }
};

// Retry the boards, and the league list too if it never arrived.
const retry = () => {
  fetchBoards();
  if (leagues.value.length === 0) fetchLeagues();
};

// The payload shape LeagueTable emits, so Matches opens on this team at the
// age group, league and season the boards counted. No conference: with a team
// selected, Matches ignores it (SB-1116).
const navigateToTeam = row => {
  const ageGroupId = result.value?.age_group?.id ?? null;
  const leagueId =
    leagues.value.find(
      l => l.name === (result.value?.league || selectedLeague.value)
    )?.id ?? null;
  emit('navigate-to-team', {
    teamId: row.team.id,
    clubId: row.club_id ?? null,
    ageGroupId,
    leagueId,
    divisionId: null,
    seasonId: result.value?.season?.id ?? null,
  });
};

watch([selectedAgeGroup, selectedLeague], fetchBoards);

onMounted(() => {
  fetchBoards();
  fetchLeagues();
});
</script>
