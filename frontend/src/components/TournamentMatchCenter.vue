<template>
  <div class="max-w-4xl mx-auto">
    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-12">
      <div
        class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"
      ></div>
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="bg-red-50 border border-red-200 rounded-md p-4"
    >
      <p class="text-red-800">{{ error }}</p>
    </div>

    <!-- No tournaments -->
    <div
      v-else-if="tournaments.length === 0"
      class="text-center py-16 text-gray-500"
    >
      <div class="text-5xl mb-4">🏆</div>
      <p class="text-lg font-medium text-gray-700">No active tournaments</p>
      <p class="text-sm mt-1">Check back soon for upcoming events.</p>
    </div>

    <template v-else>
      <!-- Tournament selector (only shown when multiple active) -->
      <div v-if="tournaments.length > 1" class="mb-6 flex flex-wrap gap-2">
        <button
          v-for="t in tournaments"
          :key="t.id"
          @click="selectTournament(t.id)"
          :class="[
            'px-4 py-2 rounded-full text-sm font-medium transition-colors',
            selectedId === t.id
              ? 'bg-blue-600 text-white'
              : 'bg-white border border-gray-300 text-gray-700 hover:border-blue-400',
          ]"
        >
          {{ t.name }}
        </button>
      </div>

      <!-- Tournament detail -->
      <div v-if="selected">
        <!-- Header card -->
        <div
          class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6"
        >
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 class="text-2xl font-bold text-gray-900">
                {{ selected.name }}
              </h2>
              <div
                class="flex flex-wrap items-center gap-3 mt-2 text-sm text-gray-500"
              >
                <span v-if="selected.start_date">
                  📅 {{ formatDate(selected.start_date) }}
                  <span v-if="selected.end_date">
                    – {{ formatDate(selected.end_date) }}</span
                  >
                </span>
                <span v-if="selected.location">📍 {{ selected.location }}</span>
                <span
                  v-for="ag in selected.age_groups || []"
                  :key="ag.id"
                  class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700"
                >
                  {{ ag.name }}
                </span>
              </div>
              <p v-if="selected.description" class="mt-3 text-sm text-gray-600">
                {{ selected.description }}
              </p>
            </div>
            <div class="text-right text-sm text-gray-500">
              <div class="text-2xl font-bold text-gray-800">
                {{ selected.matches?.length ?? 0 }}
              </div>
              <div>matches tracked</div>
            </div>
          </div>
        </div>

        <!-- Match loading -->
        <div v-if="matchesLoading" class="flex justify-center py-8">
          <div
            class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"
          ></div>
        </div>

        <template v-else-if="selected.matches">
          <!-- Age group filter -->
          <div
            v-if="availableAgeGroups.length > 1"
            class="mb-4 flex flex-wrap gap-2"
          >
            <button
              @click="ageGroupFilter = null"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                ageGroupFilter === null
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white border border-gray-300 text-gray-700 hover:border-indigo-400',
              ]"
            >
              All Ages
            </button>
            <button
              v-for="ag in availableAgeGroups"
              :key="ag.id"
              @click="ageGroupFilter = ag.id"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                ageGroupFilter === ag.id
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white border border-gray-300 text-gray-700 hover:border-indigo-400',
              ]"
            >
              {{ ag.name }}
            </button>
          </div>

          <!-- Team filter -->
          <div class="mb-4 flex items-center gap-3">
            <input
              v-model="teamFilter"
              type="text"
              placeholder="Filter by team…"
              class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-48"
            />
            <span class="text-sm text-gray-500"
              >{{ filteredMatches.length }} match{{
                filteredMatches.length !== 1 ? 'es' : ''
              }}</span
            >
            <button
              v-if="teamFilter || ageGroupFilter"
              @click="
                teamFilter = '';
                ageGroupFilter = null;
              "
              class="text-sm text-blue-600 hover:text-blue-800"
            >
              clear all
            </button>
          </div>

          <!-- No matches -->
          <div
            v-if="selected.matches.length === 0"
            class="text-center py-10 text-gray-500"
          >
            No matches entered yet.
          </div>

          <!-- Group stage section -->
          <div v-if="groupStageMatches.length > 0" class="mb-6">
            <h3
              class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3"
            >
              Group Stage
            </h3>
            <div class="space-y-2">
              <div
                v-for="match in groupStageMatches"
                :key="match.id"
                class="bg-white rounded-lg border border-gray-200 px-4 py-3 flex items-center gap-3 hover:border-gray-300 transition-colors"
              >
                <div class="w-24 shrink-0 text-xs text-gray-400">
                  {{ formatMatchDate(match.match_date) }}
                </div>
                <div class="flex gap-1 shrink-0">
                  <span
                    v-if="match.age_group"
                    class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-700"
                    >{{ match.age_group.name }}</span
                  >
                  <span
                    v-if="match.tournament_group"
                    class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600"
                    >{{ match.tournament_group }}</span
                  >
                </div>
                <div
                  class="flex-1 flex items-center justify-center gap-3 min-w-0"
                >
                  <span
                    class="text-sm font-medium text-gray-900 text-right truncate flex-1"
                    >{{ match.home_team?.name }}</span
                  >
                  <span
                    :class="[
                      'text-sm font-mono px-2 py-0.5 rounded shrink-0',
                      match.home_score != null
                        ? 'bg-gray-900 text-white font-bold'
                        : 'text-gray-400',
                    ]"
                  >
                    {{
                      match.home_score != null && match.away_score != null
                        ? match.home_penalty_score != null
                          ? `${match.home_score} – ${match.away_score} (${match.home_penalty_score}–${match.away_penalty_score} pens)`
                          : `${match.home_score} – ${match.away_score}`
                        : 'vs'
                    }}
                  </span>
                  <span
                    class="text-sm font-medium text-gray-900 text-left truncate flex-1"
                    >{{ match.away_team?.name }}</span
                  >
                </div>
                <div class="w-20 shrink-0 text-right">
                  <span
                    v-if="match.match_status === 'completed'"
                    class="text-xs text-green-600 font-medium"
                    >Final</span
                  >
                  <span
                    v-else-if="match.match_status === 'in_progress'"
                    class="text-xs text-blue-600 font-medium animate-pulse"
                    >Live</span
                  >
                  <span
                    v-else-if="match.match_status === 'cancelled'"
                    class="text-xs text-red-500"
                    >Cancelled</span
                  >
                  <span v-else class="text-xs text-gray-400">Scheduled</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Knockout section -->
          <div v-if="knockoutMatches.length > 0" class="mb-6">
            <h3
              class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3"
            >
              Knockout Rounds
            </h3>
            <div class="space-y-2">
              <div
                v-for="match in knockoutMatches"
                :key="match.id"
                class="bg-white rounded-lg border border-gray-200 px-4 py-3 flex items-center gap-3 hover:border-gray-300 transition-colors"
              >
                <div class="w-24 shrink-0 text-xs text-gray-400">
                  {{ formatMatchDate(match.match_date) }}
                </div>
                <div class="flex gap-1 shrink-0">
                  <span
                    v-if="match.age_group"
                    class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-700"
                    >{{ match.age_group.name }}</span
                  >
                  <span
                    v-if="roundLabel(match)"
                    class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700"
                    >{{ roundLabel(match) }}</span
                  >
                  <span
                    v-if="match.tournament_group"
                    class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600"
                    >{{ match.tournament_group }}</span
                  >
                </div>
                <div
                  class="flex-1 flex items-center justify-center gap-3 min-w-0"
                >
                  <span
                    class="text-sm font-medium text-gray-900 text-right truncate flex-1"
                    >{{ match.home_team?.name }}</span
                  >
                  <span
                    :class="[
                      'text-sm font-mono px-2 py-0.5 rounded shrink-0',
                      match.home_score != null
                        ? 'bg-gray-900 text-white font-bold'
                        : 'text-gray-400',
                    ]"
                  >
                    {{
                      match.home_score != null && match.away_score != null
                        ? match.home_penalty_score != null
                          ? `${match.home_score} – ${match.away_score} (${match.home_penalty_score}–${match.away_penalty_score} pens)`
                          : `${match.home_score} – ${match.away_score}`
                        : 'vs'
                    }}
                  </span>
                  <span
                    class="text-sm font-medium text-gray-900 text-left truncate flex-1"
                    >{{ match.away_team?.name }}</span
                  >
                </div>
                <div class="w-20 shrink-0 text-right">
                  <span
                    v-if="match.match_status === 'completed'"
                    class="text-xs text-green-600 font-medium"
                    >Final</span
                  >
                  <span
                    v-else-if="match.match_status === 'in_progress'"
                    class="text-xs text-blue-600 font-medium animate-pulse"
                    >Live</span
                  >
                  <span
                    v-else-if="match.match_status === 'cancelled'"
                    class="text-xs text-red-500"
                    >Cancelled</span
                  >
                  <span v-else class="text-xs text-gray-400">Scheduled</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Untagged matches (no round set) -->
          <div v-if="untaggedMatches.length > 0" class="mb-6">
            <h3
              class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3"
            >
              Matches
            </h3>
            <div class="space-y-2">
              <div
                v-for="match in untaggedMatches"
                :key="match.id"
                class="bg-white rounded-lg border border-gray-200 px-4 py-3 flex items-center gap-3 hover:border-gray-300 transition-colors"
              >
                <div class="w-24 shrink-0 text-xs text-gray-400">
                  {{ formatMatchDate(match.match_date) }}
                </div>
                <div class="flex gap-1 shrink-0">
                  <span
                    v-if="match.age_group"
                    class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-700"
                    >{{ match.age_group.name }}</span
                  >
                </div>
                <div
                  class="flex-1 flex items-center justify-center gap-3 min-w-0"
                >
                  <span
                    class="text-sm font-medium text-gray-900 text-right truncate flex-1"
                    >{{ match.home_team?.name }}</span
                  >
                  <span
                    :class="[
                      'text-sm font-mono px-2 py-0.5 rounded shrink-0',
                      match.home_score != null
                        ? 'bg-gray-900 text-white font-bold'
                        : 'text-gray-400',
                    ]"
                  >
                    {{
                      match.home_score != null && match.away_score != null
                        ? match.home_penalty_score != null
                          ? `${match.home_score} – ${match.away_score} (${match.home_penalty_score}–${match.away_penalty_score} pens)`
                          : `${match.home_score} – ${match.away_score}`
                        : 'vs'
                    }}
                  </span>
                  <span
                    class="text-sm font-medium text-gray-900 text-left truncate flex-1"
                    >{{ match.away_team?.name }}</span
                  >
                </div>
                <div class="w-20 shrink-0 text-right">
                  <span
                    v-if="match.match_status === 'completed'"
                    class="text-xs text-green-600 font-medium"
                    >Final</span
                  >
                  <span
                    v-else-if="match.match_status === 'in_progress'"
                    class="text-xs text-blue-600 font-medium animate-pulse"
                    >Live</span
                  >
                  <span
                    v-else-if="match.match_status === 'cancelled'"
                    class="text-xs text-red-500"
                    >Cancelled</span
                  >
                  <span v-else class="text-xs text-gray-400">Scheduled</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../config/api';

const KNOCKOUT_ROUNDS = new Set([
  'round_of_16',
  'quarterfinal',
  'semifinal',
  'third_place',
  'final',
]);

const ROUND_LABELS = {
  group_stage: 'Group Stage',
  round_of_16: 'R16',
  quarterfinal: 'QF',
  semifinal: 'SF',
  third_place: '3rd Place',
  final: 'Final',
};

export default {
  name: 'TournamentMatchCenter',
  setup() {
    const authStore = useAuthStore();

    const tournaments = ref([]);
    const loading = ref(true);
    const error = ref(null);

    const selectedId = ref(null);
    const selected = ref(null);
    const matchesLoading = ref(false);

    const teamFilter = ref('');
    const ageGroupFilter = ref(null);

    // ── helpers ──

    const formatDate = d =>
      d
        ? new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
          })
        : '';

    const formatMatchDate = d =>
      d
        ? new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
          })
        : '';

    const roundLabel = match => ROUND_LABELS[match.tournament_round] || null;

    // ── data ──

    const fetchTournaments = async () => {
      try {
        loading.value = true;
        error.value = null;
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/tournaments`,
          { method: 'GET' }
        );
        tournaments.value = data || [];
        if (tournaments.value.length > 0) {
          await selectTournament(tournaments.value[0].id);
        }
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const selectTournament = async id => {
      selectedId.value = id;
      matchesLoading.value = true;
      teamFilter.value = '';
      ageGroupFilter.value = null;
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/tournaments/${id}`,
          { method: 'GET' }
        );
        selected.value = data;
      } catch (err) {
        error.value = err.message;
      } finally {
        matchesLoading.value = false;
      }
    };

    // ── filtered + sectioned matches ──

    const availableAgeGroups = computed(() => {
      const matches = selected.value?.matches ?? [];
      const seen = new Map();
      for (const m of matches) {
        if (m.age_group && !seen.has(m.age_group.id)) {
          seen.set(m.age_group.id, m.age_group);
        }
      }
      return [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
    });

    const filteredMatches = computed(() => {
      let matches = selected.value?.matches ?? [];
      if (ageGroupFilter.value !== null) {
        matches = matches.filter(m => m.age_group?.id === ageGroupFilter.value);
      }
      if (!teamFilter.value) return matches;
      const q = teamFilter.value.toLowerCase();
      return matches.filter(
        m =>
          m.home_team?.name?.toLowerCase().includes(q) ||
          m.away_team?.name?.toLowerCase().includes(q)
      );
    });

    const groupStageMatches = computed(() =>
      filteredMatches.value.filter(m => m.tournament_round === 'group_stage')
    );

    const knockoutMatches = computed(() =>
      filteredMatches.value
        .filter(m => KNOCKOUT_ROUNDS.has(m.tournament_round))
        .sort((a, b) => {
          const order = [
            'round_of_16',
            'quarterfinal',
            'semifinal',
            'third_place',
            'final',
          ];
          return (
            order.indexOf(a.tournament_round) -
            order.indexOf(b.tournament_round)
          );
        })
    );

    const untaggedMatches = computed(() =>
      filteredMatches.value.filter(
        m =>
          !m.tournament_round ||
          (!KNOCKOUT_ROUNDS.has(m.tournament_round) &&
            m.tournament_round !== 'group_stage')
      )
    );

    onMounted(fetchTournaments);

    return {
      tournaments,
      loading,
      error,
      selectedId,
      selected,
      matchesLoading,
      teamFilter,
      ageGroupFilter,
      availableAgeGroups,
      filteredMatches,
      groupStageMatches,
      knockoutMatches,
      untaggedMatches,
      formatDate,
      formatMatchDate,
      roundLabel,
      selectTournament,
    };
  },
};
</script>
