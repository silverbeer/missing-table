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
      <!-- No bracket exists - show configuration form -->
      <div v-if="bracket.length === 0" class="py-8">
        <p class="text-gray-500 mb-6 text-center">
          No playoff bracket exists for this selection.
        </p>

        <div v-if="divisions.length >= 2" class="max-w-lg mx-auto space-y-5">
          <h4 class="text-sm font-semibold text-gray-700 mb-3">
            Bracket Configuration
          </h4>

          <!-- Bracket Type Selection -->
          <div>
            <label class="block text-sm text-gray-600 mb-1">Bracket Type</label>
            <select
              v-model="configBracketType"
              class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option v-for="bt in bracketTypes" :key="bt.key" :value="bt.key">
                {{ bt.name }}
              </option>
            </select>
            <p class="mt-1 text-xs text-gray-500">
              {{ selectedBracketType?.description }}
            </p>
          </div>

          <!-- Division Selection -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm text-gray-600 mb-1">Division A</label>
              <select
                v-model="configDivisionA"
                class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select...</option>
                <option
                  v-for="d in divisions"
                  :key="d.id"
                  :value="d.id"
                  :disabled="d.id === configDivisionB"
                >
                  {{ d.name }}
                </option>
              </select>
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-1">Division B</label>
              <select
                v-model="configDivisionB"
                class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select...</option>
                <option
                  v-for="d in divisions"
                  :key="d.id"
                  :value="d.id"
                  :disabled="d.id === configDivisionA"
                >
                  {{ d.name }}
                </option>
              </select>
            </div>
          </div>

          <!-- Start Date -->
          <div>
            <label class="block text-sm text-gray-600 mb-1"
              >First Round Date (Quarterfinals)</label
            >
            <input
              type="date"
              v-model="configStartDate"
              class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <!-- Tier Names -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm text-gray-600 mb-1"
                >Upper Bracket Name (Positions 1-4)</label
              >
              <input
                type="text"
                v-model="configTier1Name"
                placeholder="Gold Cup"
                class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-1"
                >Lower Bracket Name (Positions 5-8)</label
              >
              <input
                type="text"
                v-model="configTier2Name"
                placeholder="Silver Cup"
                class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div class="pt-2">
            <button
              @click="showGenerateConfirm"
              :disabled="actionLoading || !canGenerate"
              class="w-full px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 font-medium"
            >
              {{ actionLoading ? 'Generating...' : 'Generate Playoff Bracket' }}
            </button>
          </div>
        </div>

        <div v-else class="text-sm text-red-600 mt-2 text-center">
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

        <!-- Bracket tiers -->
        <div v-for="tier in bracketTiers" :key="tier.key" class="mb-8">
          <h4 class="text-md font-semibold text-gray-700 mb-3 border-b pb-1">
            {{ tier.label }}
          </h4>
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
                  v-for="s in getSlotsByRound(tier.key, 'quarterfinal')"
                  :key="s.id"
                  :bracketSlot="s"
                  @advance="advanceWinner"
                  @updated="fetchBracket"
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
                  v-for="s in getSlotsByRound(tier.key, 'semifinal')"
                  :key="s.id"
                  :bracketSlot="s"
                  @advance="advanceWinner"
                  @updated="fetchBracket"
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
                  v-for="s in getSlotsByRound(tier.key, 'final')"
                  :key="s.id"
                  :bracketSlot="s"
                  @advance="advanceWinner"
                  @updated="fetchBracket"
                  :actionLoading="actionLoading"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Generate Bracket Confirmation Modal -->
    <ConfirmModal
      :show="showConfirmModal"
      title="Generate Playoff Bracket"
      confirmText="Generate Bracket"
      :loading="actionLoading"
      loadingText="Generating..."
      variant="info"
      @confirm="generateBracket"
      @cancel="showConfirmModal = false"
    >
      <!-- Bracket Type Header -->
      <div
        class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md text-center"
      >
        <div class="text-lg font-semibold text-blue-900">
          {{ selectedBracketType?.name }}
        </div>
        <div class="text-xs text-blue-700 mt-1">
          {{ selectedBracketType?.description }}
        </div>
      </div>

      <!-- Configuration Details -->
      <div class="bg-gray-50 rounded-md p-4 text-sm space-y-2">
        <div class="grid grid-cols-2 gap-x-4">
          <div class="text-gray-500">Division A:</div>
          <div class="font-medium">{{ getDivisionName(configDivisionA) }}</div>
        </div>
        <div class="grid grid-cols-2 gap-x-4">
          <div class="text-gray-500">Division B:</div>
          <div class="font-medium">{{ getDivisionName(configDivisionB) }}</div>
        </div>
        <div class="grid grid-cols-2 gap-x-4">
          <div class="text-gray-500">First Round Date:</div>
          <div class="font-medium">{{ configStartDate }}</div>
        </div>
        <div class="border-t border-gray-200 my-2"></div>
        <div class="grid grid-cols-2 gap-x-4">
          <div class="text-gray-500">Upper Bracket (1-4):</div>
          <div class="font-medium">{{ configTier1Name || 'Gold Cup' }}</div>
        </div>
        <div class="grid grid-cols-2 gap-x-4">
          <div class="text-gray-500">Lower Bracket (5-8):</div>
          <div class="font-medium">{{ configTier2Name || 'Silver Cup' }}</div>
        </div>
      </div>
    </ConfirmModal>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';
import BracketSlotCard from './BracketSlotCard.vue';
import ConfirmModal from '../ConfirmModal.vue';

export default {
  name: 'AdminPlayoffs',
  components: { BracketSlotCard, ConfirmModal },
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

    // Bracket types (expandable in the future)
    const bracketTypes = [
      {
        key: 'dual_tier_16',
        name: '16-Team Dual Bracket',
        description:
          'All 16 teams compete in two parallel single-elimination brackets: positions 1-4 in upper bracket, positions 5-8 in lower bracket.',
        tiers: [
          { start: 1, end: 4 },
          { start: 5, end: 8 },
        ],
      },
      // Future bracket types can be added here:
      // { key: 'single_8', name: '8-Team Single Elimination', ... },
      // { key: 'double_elim', name: 'Double Elimination', ... },
    ];

    // Bracket generation config
    const configBracketType = ref('dual_tier_16');
    const configDivisionA = ref('');
    const configDivisionB = ref('');
    const configStartDate = ref('');
    const configTier1Name = ref('Gold Cup');
    const configTier2Name = ref('Silver Cup');

    // Confirm modal state
    const showConfirmModal = ref(false);

    // Get selected bracket type details
    const selectedBracketType = computed(() =>
      bracketTypes.find(bt => bt.key === configBracketType.value)
    );

    // Computed: can generate bracket?
    const canGenerate = computed(
      () =>
        configDivisionA.value &&
        configDivisionB.value &&
        configStartDate.value &&
        configDivisionA.value !== configDivisionB.value
    );

    // Computed: derive bracket tiers from bracket data (or show nothing if empty)
    const bracketTiers = computed(() => {
      const tierNames = [...new Set(bracket.value.map(s => s.bracket_tier))];
      // Sort alphabetically for consistent display
      tierNames.sort();
      return tierNames.map(name => ({
        key: name,
        label: name,
      }));
    });

    // Get slots filtered by tier and round
    const getSlotsByRound = (tier, round) =>
      bracket.value
        .filter(s => s.bracket_tier === tier && s.round === round)
        .sort((a, b) => a.bracket_position - b.bracket_position);

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
      configDivisionA.value = '';
      configDivisionB.value = '';
      if (!selectedLeague.value) return;

      try {
        const allDivisions = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/divisions`,
          { method: 'GET' }
        );
        divisions.value = allDivisions.filter(
          d => d.league_id === parseInt(selectedLeague.value)
        );
        // Default to first two divisions if available
        if (divisions.value.length >= 2) {
          configDivisionA.value = divisions.value[0].id;
          configDivisionB.value = divisions.value[1].id;
        }
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

    const showGenerateConfirm = () => {
      if (!canGenerate.value) return;
      showConfirmModal.value = true;
    };

    const generateBracket = async () => {
      showConfirmModal.value = false;

      try {
        actionLoading.value = true;
        error.value = null;
        successMessage.value = null;

        const body = {
          league_id: parseInt(selectedLeague.value),
          season_id: parseInt(selectedSeason.value),
          age_group_id: parseInt(selectedAgeGroup.value),
          division_a_id: parseInt(configDivisionA.value),
          division_b_id: parseInt(configDivisionB.value),
          start_date: configStartDate.value,
          tiers: [
            {
              name: configTier1Name.value || 'Gold Cup',
              start_position: 1,
              end_position: 4,
            },
            {
              name: configTier2Name.value || 'Silver Cup',
              start_position: 5,
              end_position: 8,
            },
          ],
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
      // Default start date to 7 days from now
      const defaultDate = new Date();
      defaultDate.setDate(defaultDate.getDate() + 7);
      configStartDate.value = defaultDate.toISOString().split('T')[0];
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
      bracketTiers,
      bracketTypes,
      configBracketType,
      selectedBracketType,
      configDivisionA,
      configDivisionB,
      configStartDate,
      configTier1Name,
      configTier2Name,
      canGenerate,
      showConfirmModal,
      getSlotsByRound,
      getDivisionName,
      onLeagueChange,
      fetchBracket,
      showGenerateConfirm,
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
