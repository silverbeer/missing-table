<template>
  <div>
    <!-- Header -->
    <div class="mb-6">
      <h2 class="text-lg font-semibold text-gray-800">
        Quality of Play Rankings
      </h2>
      <p class="text-sm text-gray-500 mt-1">
        Homegrown · Updated weekly by MLS Next
      </p>
    </div>

    <!-- Filters -->
    <div class="mb-6 space-y-3">
      <!-- Division -->
      <div>
        <h3 class="text-sm font-medium text-gray-700 mb-2">Division</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="div in homegrownDivisions"
            :key="div.id"
            @click="selectedDivisionId = div.id"
            :class="[
              'px-4 py-2 text-sm rounded-lg font-medium transition-colors',
              selectedDivisionId === div.id
                ? 'bg-brand-500 text-white shadow-sm'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
            ]"
          >
            {{ div.name }}
          </button>
        </div>
      </div>

      <!-- Age Group -->
      <div>
        <h3 class="text-sm font-medium text-gray-700 mb-2">Age Group</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="ag in qopAgeGroups"
            :key="ag.id"
            @click="selectedAgeGroupId = ag.id"
            :class="[
              'px-4 py-2 text-sm rounded-lg font-medium transition-colors',
              selectedAgeGroupId === ag.id
                ? 'bg-brand-500 text-white shadow-sm'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
            ]"
          >
            {{ ag.name }}
          </button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-8 text-gray-500">
      Loading QoP rankings...
    </div>

    <!-- Error -->
    <div v-else-if="error" class="text-center py-8 text-red-600">
      {{ error }}
    </div>

    <!-- No data -->
    <div v-else-if="!rankings.length" class="text-center py-8 text-gray-500">
      No QoP rankings available yet for this age group.
    </div>

    <!-- Rankings Table -->
    <div v-else class="overflow-x-auto">
      <div
        v-if="weekOf"
        class="flex items-center gap-2 text-xs text-gray-400 mb-2"
      >
        <button
          v-if="prevSnapshotId != null"
          type="button"
          @click="goToSnapshot(prevSnapshotId)"
          :disabled="loading"
          class="px-2 py-0.5 rounded hover:bg-slate-100 text-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
          :title="`Previous week${priorWeekOf ? ' (' + priorWeekOf + ')' : ''}`"
          aria-label="Previous snapshot"
        >
          ◀
        </button>
        <span>
          Week of {{ weekOf
          }}<span v-if="priorWeekOf">
            &nbsp;·&nbsp; Prior week: {{ priorWeekOf }}</span
          >
        </span>
        <button
          v-if="nextSnapshotId != null"
          type="button"
          @click="goToSnapshot(nextSnapshotId)"
          :disabled="loading"
          class="px-2 py-0.5 rounded hover:bg-slate-100 text-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
          title="Next week"
          aria-label="Next snapshot"
        >
          ▶
        </button>
      </div>

      <table class="min-w-full divide-y divide-slate-200">
        <thead class="bg-brand-500">
          <tr>
            <th
              class="px-3 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Rank"
            >
              #
            </th>
            <th
              class="px-3 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Rank change from prior week"
            >
              +/-
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider"
            >
              Team
            </th>
            <th
              class="px-4 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Matches Played"
            >
              MP
            </th>
            <th
              class="hidden sm:table-cell px-4 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Attacking Score"
            >
              ATT
            </th>
            <th
              class="hidden sm:table-cell px-4 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Defensive Score"
            >
              DEF
            </th>
            <th
              class="px-4 py-3 text-center text-xs font-semibold text-brand-200 uppercase tracking-wider"
              title="Quality of Play Score"
            >
              QoP
            </th>
          </tr>
        </thead>
        <tbody class="bg-white">
          <!-- Championship Qualification label before first row -->
          <tr v-if="rankings.length" class="border-0">
            <td colspan="7" class="px-0 py-0">
              <div class="flex items-center gap-2 pb-1 pt-1 px-3 bg-blue-50">
                <span
                  class="text-xs font-semibold text-blue-700 uppercase tracking-wide whitespace-nowrap"
                  >Championship Qualification</span
                >
              </div>
            </td>
          </tr>
          <template v-for="entry in rankings" :key="entry.rank">
            <tr
              class="hover:bg-slate-50 transition-colors border-b border-slate-100"
            >
              <td class="px-3 py-3 text-sm text-gray-500">
                {{ entry.rank }}
              </td>
              <td class="px-3 py-3 text-xs text-center">
                <span
                  v-if="entry.rank_change > 0"
                  class="text-green-600 font-medium"
                  :title="`Up ${entry.rank_change}`"
                >
                  ▲{{ entry.rank_change }}
                </span>
                <span
                  v-else-if="entry.rank_change < 0"
                  class="text-red-600 font-medium"
                  :title="`Down ${Math.abs(entry.rank_change)}`"
                >
                  ▼{{ Math.abs(entry.rank_change) }}
                </span>
                <span v-else class="text-gray-400">—</span>
              </td>
              <td class="px-4 py-3 text-sm font-medium text-gray-900">
                {{ entry.team_name }}
              </td>
              <td class="px-4 py-3 text-sm text-center text-gray-500">
                {{ entry.matches_played ?? '—' }}
              </td>
              <td
                class="hidden sm:table-cell px-4 py-3 text-sm text-center text-gray-500"
              >
                {{ entry.att_score != null ? entry.att_score.toFixed(1) : '—' }}
                <span
                  v-if="entry.att_change != null && entry.att_change > 0"
                  class="ml-1 text-xs font-normal text-green-600"
                  :title="`ATT up ${entry.att_change} from prior week`"
                  >+{{ entry.att_change.toFixed(1) }}</span
                >
                <span
                  v-else-if="entry.att_change != null && entry.att_change < 0"
                  class="ml-1 text-xs font-normal text-red-500"
                  :title="`ATT down ${Math.abs(entry.att_change)} from prior week`"
                  >{{ entry.att_change.toFixed(1) }}</span
                >
              </td>
              <td
                class="hidden sm:table-cell px-4 py-3 text-sm text-center text-gray-500"
              >
                {{ entry.def_score != null ? entry.def_score.toFixed(1) : '—' }}
                <span
                  v-if="entry.def_change != null && entry.def_change > 0"
                  class="ml-1 text-xs font-normal text-green-600"
                  :title="`DEF up ${entry.def_change} from prior week`"
                  >+{{ entry.def_change.toFixed(1) }}</span
                >
                <span
                  v-else-if="entry.def_change != null && entry.def_change < 0"
                  class="ml-1 text-xs font-normal text-red-500"
                  :title="`DEF down ${Math.abs(entry.def_change)} from prior week`"
                  >{{ entry.def_change.toFixed(1) }}</span
                >
              </td>
              <td
                class="px-4 py-3 text-sm text-center font-bold text-brand-600"
              >
                {{ entry.qop_score != null ? entry.qop_score.toFixed(1) : '—' }}
                <span
                  v-if="entry.qop_change != null && entry.qop_change > 0"
                  class="ml-1 text-xs font-normal text-green-600"
                  :title="`QoP up ${entry.qop_change} from prior week`"
                  >+{{ entry.qop_change.toFixed(1) }}</span
                >
                <span
                  v-else-if="entry.qop_change != null && entry.qop_change < 0"
                  class="ml-1 text-xs font-normal text-red-500"
                  :title="`QoP down ${Math.abs(entry.qop_change)} from prior week`"
                  >{{ entry.qop_change.toFixed(1) }}</span
                >
              </td>
            </tr>
            <!-- Championship Qualification cutoff: after rank 5 -->
            <tr v-if="entry.rank === 5" class="border-0">
              <td colspan="7" class="px-0 py-0">
                <div
                  class="flex items-center gap-2 border-t-2 border-blue-500 pt-1 pb-1 px-3"
                >
                  <span
                    class="text-xs font-semibold text-blue-600 uppercase tracking-wide whitespace-nowrap"
                    >Premier Qualification</span
                  >
                </div>
              </td>
            </tr>
            <!-- Tournament cutoff: after rank 10 -->
            <tr v-if="entry.rank === 10" class="border-0">
              <td colspan="7" class="px-0 py-0">
                <div
                  class="flex items-center gap-2 border-t-2 border-red-400 pt-1 pb-1 px-3"
                >
                  <span
                    class="text-xs font-semibold text-red-500 uppercase tracking-wide whitespace-nowrap"
                    >Not Invited — MLS NEXT Cup Tournament · Salt Lake City,
                    UT</span
                  >
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';

export default {
  name: 'QoPStandings',
  setup() {
    const authStore = useAuthStore();

    const homegrownDivisions = ref([]);
    const selectedDivisionId = ref(null);
    const qopAgeGroups = ref([]);
    const selectedAgeGroupId = ref(null);

    const rankings = ref([]);
    const weekOf = ref(null);
    const priorWeekOf = ref(null);
    const currentSnapshotId = ref(null);
    const prevSnapshotId = ref(null);
    const nextSnapshotId = ref(null);
    const loading = ref(false);
    const error = ref(null);

    const resolveIds = async () => {
      const [ageGroupsData, divisionsData, leaguesData] = await Promise.all([
        authStore.apiRequest(`${getApiBaseUrl()}/api/age-groups`),
        authStore.apiRequest(`${getApiBaseUrl()}/api/divisions`),
        authStore.apiRequest(`${getApiBaseUrl()}/api/leagues`),
      ]);

      const homegrown = leaguesData.find(l => l.name === 'Homegrown');
      if (!homegrown) {
        error.value = 'Homegrown league not found.';
        return false;
      }

      const divs = divisionsData
        .filter(d => Number(d.league_id) === Number(homegrown.id))
        .sort((a, b) => a.name.localeCompare(b.name));
      if (!divs.length) {
        error.value = 'No divisions found for Homegrown league.';
        return false;
      }
      homegrownDivisions.value = divs;

      const northeast = divs.find(d => d.name === 'Northeast');
      selectedDivisionId.value = northeast ? northeast.id : divs[0].id;

      const relevant = ageGroupsData
        .filter(ag => ag.name === 'U13' || ag.name === 'U14')
        .sort((a, b) => a.name.localeCompare(b.name));
      qopAgeGroups.value = relevant;

      const u14 = relevant.find(ag => ag.name === 'U14');
      selectedAgeGroupId.value = u14 ? u14.id : (relevant[0]?.id ?? null);

      return true;
    };

    const fetchRankings = async () => {
      if (!selectedAgeGroupId.value || !selectedDivisionId.value) return;

      loading.value = true;
      error.value = null;

      try {
        const params = new URLSearchParams({
          division_id: selectedDivisionId.value,
          age_group_id: selectedAgeGroupId.value,
        });
        if (currentSnapshotId.value != null) {
          params.set('snapshot_id', currentSnapshotId.value);
        }
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/qop-rankings?${params}`
        );
        rankings.value = data.rankings ?? [];
        weekOf.value = data.week_of ?? null;
        priorWeekOf.value = data.prior_week_of ?? null;
        currentSnapshotId.value = data.snapshot_id ?? null;
        prevSnapshotId.value = data.prev_snapshot_id ?? null;
        nextSnapshotId.value = data.next_snapshot_id ?? null;
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const goToSnapshot = id => {
      currentSnapshotId.value = id;
      fetchRankings();
    };

    // Changing filters should always return to the newest snapshot for the
    // new (division, age_group) pair — otherwise a stale snapshot_id from the
    // prior selection would 404 and render empty.
    watch([selectedAgeGroupId, selectedDivisionId], () => {
      currentSnapshotId.value = null;
      fetchRankings();
    });

    onMounted(async () => {
      const ok = await resolveIds();
      if (ok) await fetchRankings();
    });

    return {
      homegrownDivisions,
      selectedDivisionId,
      qopAgeGroups,
      selectedAgeGroupId,
      rankings,
      weekOf,
      priorWeekOf,
      prevSnapshotId,
      nextSnapshotId,
      loading,
      error,
      goToSnapshot,
    };
  },
};
</script>
