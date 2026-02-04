<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Playoffs Management</h3>
      <div class="flex space-x-3">
        <!-- League selector -->
        <select
          v-model="selectedLeague"
          @change="onLeagueChange"
          class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select League</option>
          <option v-for="league in leagues" :key="league.id" :value="league.id">
            {{ league.name }}
          </option>
        </select>

        <!-- Season selector -->
        <select
          v-model="selectedSeason"
          @change="fetchBracket"
          class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select Season</option>
          <option v-for="season in seasons" :key="season.id" :value="season.id">
            {{ season.name }}
          </option>
        </select>

        <!-- Age Group selector -->
        <select
          v-model="selectedAgeGroup"
          @change="fetchBracket"
          class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select Age Group</option>
          <option v-for="ag in ageGroups" :key="ag.id" :value="ag.id">
            {{ ag.name }}
          </option>
        </select>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-8">
      <div
        class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"
      ></div>
    </div>

    <!-- Error -->
    <div
      v-if="error"
      class="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-sm"
    >
      {{ error }}
    </div>

    <!-- Success message -->
    <div
      v-if="successMessage"
      class="mb-4 p-3 bg-green-50 border border-green-200 text-green-700 rounded-md text-sm"
    >
      {{ successMessage }}
    </div>

    <!-- No selections yet -->
    <div
      v-if="
        !loading && (!selectedLeague || !selectedSeason || !selectedAgeGroup)
      "
      class="text-center py-12 text-gray-500"
    >
      Select a league, season, and age group to manage playoffs.
    </div>

    <!-- Bracket content -->
    <div
      v-if="!loading && selectedLeague && selectedSeason && selectedAgeGroup"
    >
      <!-- No bracket exists -->
      <div v-if="bracket.length === 0" class="text-center py-12">
        <p class="text-gray-500 mb-4">
          No playoff bracket exists for this selection.
        </p>
        <div v-if="divisions.length >= 2" class="space-y-4">
          <div class="flex justify-center space-x-4 text-sm text-gray-600">
            <span>
              Division A:
              <strong>{{ getDivisionName(divisions[0].id) }}</strong>
            </span>
            <span>
              Division B:
              <strong>{{ getDivisionName(divisions[1].id) }}</strong>
            </span>
          </div>
          <button
            @click="generateBracket"
            :disabled="actionLoading"
            class="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 font-medium"
          >
            {{ actionLoading ? 'Generating...' : 'Generate Playoff Bracket' }}
          </button>
        </div>
        <div v-else class="text-sm text-red-600 mt-2">
          This league needs at least 2 divisions to generate a playoff bracket.
        </div>
      </div>

      <!-- Bracket exists -->
      <div v-if="bracket.length > 0">
        <!-- Action bar -->
        <div class="flex justify-end mb-4">
          <button
            @click="resetBracket"
            :disabled="actionLoading"
            class="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 text-sm"
          >
            {{ actionLoading ? 'Deleting...' : 'Reset Bracket' }}
          </button>
        </div>

        <!-- Bracket grid -->
        <div class="bracket-grid">
          <!-- Quarterfinals -->
          <div class="bracket-round">
            <h4
              class="text-sm font-semibold text-gray-500 uppercase mb-3 text-center"
            >
              Quarterfinals
            </h4>
            <div class="space-y-4">
              <BracketSlotCard
                v-for="s in qfSlots"
                :key="s.id"
                :bracketSlot="s"
                @advance="advanceWinner"
                :actionLoading="actionLoading"
              />
            </div>
          </div>

          <!-- Semifinals -->
          <div class="bracket-round">
            <h4
              class="text-sm font-semibold text-gray-500 uppercase mb-3 text-center"
            >
              Semifinals
            </h4>
            <div class="space-y-4 mt-12">
              <BracketSlotCard
                v-for="s in sfSlots"
                :key="s.id"
                :bracketSlot="s"
                @advance="advanceWinner"
                :actionLoading="actionLoading"
              />
            </div>
          </div>

          <!-- Final -->
          <div class="bracket-round">
            <h4
              class="text-sm font-semibold text-gray-500 uppercase mb-3 text-center"
            >
              Final
            </h4>
            <div class="mt-32">
              <BracketSlotCard
                v-for="s in finalSlots"
                :key="s.id"
                :bracketSlot="s"
                @advance="advanceWinner"
                :actionLoading="actionLoading"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';
import BracketSlotCard from './BracketSlotCard.vue';

export default {
  name: 'AdminPlayoffs',
  components: { BracketSlotCard },
  setup() {
    const authStore = useAuthStore();

    // Reference data
    const leagues = ref([]);
    const seasons = ref([]);
    const ageGroups = ref([]);
    const divisions = ref([]);

    // Selections
    const selectedLeague = ref('');
    const selectedSeason = ref('');
    const selectedAgeGroup = ref('');

    // State
    const bracket = ref([]);
    const loading = ref(false);
    const actionLoading = ref(false);
    const error = ref(null);
    const successMessage = ref(null);

    // Computed: slots by round
    const qfSlots = computed(() =>
      bracket.value
        .filter(s => s.round === 'quarterfinal')
        .sort((a, b) => a.bracket_position - b.bracket_position)
    );
    const sfSlots = computed(() =>
      bracket.value
        .filter(s => s.round === 'semifinal')
        .sort((a, b) => a.bracket_position - b.bracket_position)
    );
    const finalSlots = computed(() =>
      bracket.value.filter(s => s.round === 'final')
    );

    const getDivisionName = divId => {
      const div = divisions.value.find(d => d.id === divId);
      return div ? div.name : `Division ${divId}`;
    };

    const fetchReferenceData = async () => {
      try {
        const [seasonsData, ageGroupsData, leaguesData] = await Promise.all([
          authStore.apiRequest(`${getApiBaseUrl()}/api/seasons`, {
            method: 'GET',
          }),
          authStore.apiRequest(`${getApiBaseUrl()}/api/age-groups`, {
            method: 'GET',
          }),
          authStore.apiRequest(`${getApiBaseUrl()}/api/leagues`, {
            method: 'GET',
          }),
        ]);

        seasons.value = seasonsData || [];
        ageGroups.value = ageGroupsData || [];
        leagues.value = leaguesData || [];
      } catch (err) {
        console.error('Error fetching reference data:', err);
      }
    };

    const onLeagueChange = async () => {
      // Fetch divisions for the selected league
      divisions.value = [];
      bracket.value = [];
      if (!selectedLeague.value) return;

      try {
        const allDivisions = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/divisions`,
          { method: 'GET' }
        );
        divisions.value = allDivisions.filter(
          d => d.league_id === parseInt(selectedLeague.value)
        );
      } catch (err) {
        console.error('Error fetching divisions:', err);
      }

      await fetchBracket();
    };

    const fetchBracket = async () => {
      error.value = null;
      successMessage.value = null;
      if (
        !selectedLeague.value ||
        !selectedSeason.value ||
        !selectedAgeGroup.value
      ) {
        bracket.value = [];
        return;
      }

      try {
        loading.value = true;
        const params = new URLSearchParams({
          league_id: selectedLeague.value,
          season_id: selectedSeason.value,
          age_group_id: selectedAgeGroup.value,
        });
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/playoffs/bracket?${params}`,
          { method: 'GET' }
        );
        bracket.value = data || [];
      } catch (err) {
        error.value = err.message || 'Failed to fetch bracket';
      } finally {
        loading.value = false;
      }
    };

    const generateBracket = async () => {
      if (divisions.value.length < 2) return;
      if (
        !confirm(
          'Generate playoff bracket from current standings? This will create QF matches.'
        )
      )
        return;

      try {
        actionLoading.value = true;
        error.value = null;
        successMessage.value = null;

        const body = {
          league_id: parseInt(selectedLeague.value),
          season_id: parseInt(selectedSeason.value),
          age_group_id: parseInt(selectedAgeGroup.value),
          division_a_id: divisions.value[0].id,
          division_b_id: divisions.value[1].id,
        };

        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/playoffs/generate`,
          {
            method: 'POST',
            body: JSON.stringify(body),
          }
        );

        bracket.value = data || [];
        successMessage.value = 'Playoff bracket generated successfully!';
      } catch (err) {
        error.value = err.message || 'Failed to generate bracket';
      } finally {
        actionLoading.value = false;
      }
    };

    const advanceWinner = async slotId => {
      try {
        actionLoading.value = true;
        error.value = null;
        successMessage.value = null;

        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/playoffs/advance`,
          {
            method: 'POST',
            body: JSON.stringify({ slot_id: slotId }),
          }
        );

        successMessage.value = 'Winner advanced successfully!';
        await fetchBracket();
      } catch (err) {
        error.value = err.message || 'Failed to advance winner';
      } finally {
        actionLoading.value = false;
      }
    };

    const resetBracket = async () => {
      if (
        !confirm(
          'Delete the entire bracket and all playoff matches? This cannot be undone.'
        )
      )
        return;

      try {
        actionLoading.value = true;
        error.value = null;
        successMessage.value = null;

        const params = new URLSearchParams({
          league_id: selectedLeague.value,
          season_id: selectedSeason.value,
          age_group_id: selectedAgeGroup.value,
        });

        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/playoffs/bracket?${params}`,
          { method: 'DELETE' }
        );

        bracket.value = [];
        successMessage.value = 'Bracket deleted successfully.';
      } catch (err) {
        error.value = err.message || 'Failed to delete bracket';
      } finally {
        actionLoading.value = false;
      }
    };

    onMounted(async () => {
      await fetchReferenceData();
    });

    return {
      leagues,
      seasons,
      ageGroups,
      divisions,
      selectedLeague,
      selectedSeason,
      selectedAgeGroup,
      bracket,
      loading,
      actionLoading,
      error,
      successMessage,
      qfSlots,
      sfSlots,
      finalSlots,
      getDivisionName,
      onLeagueChange,
      fetchBracket,
      generateBracket,
      advanceWinner,
      resetBracket,
    };
  },
};
</script>

<style scoped>
.bracket-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 2rem;
  min-height: 400px;
}

@media (max-width: 768px) {
  .bracket-grid {
    grid-template-columns: 1fr;
  }
}
</style>
