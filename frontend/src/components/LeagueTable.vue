<template>
  <div>
    <!-- Filters Section -->
    <div class="mb-6 space-y-4">
      <!-- Age Group Links -->
      <div>
        <h3 class="text-sm font-medium text-gray-700 mb-3">Age Groups</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="ageGroup in ageGroups"
            :key="ageGroup.id"
            @click="selectedAgeGroupId = ageGroup.id"
            :class="[
              'px-4 py-2 text-sm rounded-md font-medium transition-colors',
              selectedAgeGroupId === ageGroup.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
            ]"
          >
            {{ ageGroup.name }}
          </button>
        </div>
      </div>

      <!-- Season and Division Row -->
      <div
        class="flex flex-col sm:flex-row sm:space-x-6 space-y-4 sm:space-y-0"
      >
        <!-- Season Dropdown -->
        <div class="flex-1">
          <h3 class="text-sm font-medium text-gray-700 mb-3">Season</h3>
          <select
            v-model="selectedSeasonId"
            class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          >
            <option
              v-for="season in seasons"
              :key="season.id"
              :value="season.id"
            >
              {{ season.name }} ({{ formatSeasonDates(season) }})
            </option>
          </select>
        </div>

        <!-- Division Dropdown -->
        <div class="flex-1">
          <h3 class="text-sm font-medium text-gray-700 mb-3">Division</h3>
          <select
            v-model="selectedDivisionId"
            class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          >
            <option
              v-for="division in divisions"
              :key="division.id"
              :value="division.id"
            >
              {{ division.name }}
            </option>
          </select>
        </div>
      </div>
    </div>

    <div class="overflow-x-auto">
      <!-- Loading State -->
      <div v-if="loading" class="text-center py-4">Loading table data...</div>

      <!-- Error State -->
      <div v-else-if="error" class="text-center py-4 text-red-600">
        Error: {{ error }}
      </div>

      <!-- Table -->
      <table v-else class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Pos
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Team
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              GP
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              W
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              D
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              L
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              GF
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              GA
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              GD
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Pts
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="(team, index) in tableData" :key="team.team">
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ index + 1 }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900"
            >
              {{ team.team }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.played }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.wins }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.draws }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.losses }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.goals_for }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.goals_against }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.goal_difference }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.points }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch } from 'vue';
import { useAuthStore } from '../stores/auth';

export default {
  name: 'LeagueTable',
  setup() {
    const authStore = useAuthStore();
    const tableData = ref([]);
    const ageGroups = ref([]);
    const divisions = ref([]);
    const seasons = ref([]);
    const selectedAgeGroupId = ref(2); // Default to U14
    const selectedDivisionId = ref(1); // Default to Northeast
    const selectedSeasonId = ref(2); // Default to 2024-2025
    const error = ref(null);
    const loading = ref(true);

    const fetchAgeGroups = async () => {
      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/age-groups`
        );
        ageGroups.value = data.sort((a, b) => a.name.localeCompare(b.name));

        // Set U14 as default if available
        const u14 = data.find(ag => ag.name === 'U14');
        if (u14) {
          selectedAgeGroupId.value = u14.id;
        }
      } catch (err) {
        console.error('Error fetching age groups:', err);
      }
    };

    const fetchDivisions = async () => {
      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/divisions`
        );
        divisions.value = data.sort((a, b) => a.name.localeCompare(b.name));

        // Set Northeast as default if available
        const northeast = data.find(d => d.name === 'Northeast');
        if (northeast) {
          selectedDivisionId.value = northeast.id;
        }
      } catch (err) {
        console.error('Error fetching divisions:', err);
      }
    };

    const fetchSeasons = async () => {
      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/seasons`
        );
        // Sort seasons by start date (most recent first)
        seasons.value = data.sort(
          (a, b) => new Date(b.start_date) - new Date(a.start_date)
        );

        // Set 2025-2026 as default if available
        const currentSeason = data.find(s => s.name === '2025-2026');
        if (currentSeason) {
          selectedSeasonId.value = currentSeason.id;
        }
      } catch (err) {
        console.error('Error fetching seasons:', err);
      }
    };

    const formatSeasonDates = season => {
      const startYear = new Date(season.start_date).getFullYear();
      const endYear = new Date(season.end_date).getFullYear();
      return `${startYear}-${endYear}`;
    };

    const fetchTableData = async () => {
      loading.value = true;
      console.log('Fetching table data...', {
        seasonId: selectedSeasonId.value,
        ageGroupId: selectedAgeGroupId.value,
        divisionId: selectedDivisionId.value,
      });
      try {
        const url = `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/table?season_id=${selectedSeasonId.value}&age_group_id=${selectedAgeGroupId.value}&division_id=${selectedDivisionId.value}`;
        const data = await authStore.apiRequest(url);
        console.log('Table data received:', data);

        tableData.value = data;
        console.log('Table data set:', tableData.value);
      } catch (err) {
        console.error('Error fetching table data:', err);
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    // Watch for changes in filters and refetch data
    watch([selectedSeasonId, selectedAgeGroupId, selectedDivisionId], () => {
      fetchTableData();
    });

    onMounted(async () => {
      console.log('LeagueTable component mounted');
      await Promise.all([fetchAgeGroups(), fetchDivisions(), fetchSeasons()]);
      fetchTableData();
    });

    return {
      tableData,
      ageGroups,
      divisions,
      seasons,
      selectedAgeGroupId,
      selectedDivisionId,
      selectedSeasonId,
      formatSeasonDates,
      error,
      loading,
    };
  },
};
</script>
