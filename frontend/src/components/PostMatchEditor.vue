<template>
  <div class="mt-3" data-testid="post-match-section">
    <!-- Toggle button -->
    <button
      @click="toggleSection"
      data-testid="post-match-toggle"
      class="w-full flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm font-semibold rounded-lg transition-colors"
      :class="{ 'bg-slate-600': showSection }"
    >
      <span class="text-base font-bold w-5 text-center">{{
        showSection ? '-' : '+'
      }}</span>
      Match Stats
    </button>

    <div v-if="showSection" class="mt-2 bg-slate-800 rounded-lg p-3">
      <!-- Loading state -->
      <div v-if="dataLoading" class="text-slate-400 text-sm text-center py-4">
        Loading match stats...
      </div>

      <!-- No roster message -->
      <div
        v-else-if="dataLoaded && !homeRoster.length && !awayRoster.length"
        class="text-slate-400 text-sm text-center py-4"
      >
        No roster available for either team.
      </div>

      <!-- Content -->
      <template v-else-if="dataLoaded">
        <!-- Team tabs -->
        <div class="flex gap-2 mb-3">
          <button
            @click="activeTab = 'home'"
            data-testid="post-match-tab-home"
            class="flex-1 py-2 px-3 text-sm font-medium rounded-lg border-2 transition-colors truncate"
            :class="
              activeTab === 'home'
                ? 'border-blue-500 bg-blue-500/20 text-white'
                : 'border-slate-600 text-slate-400 hover:border-slate-500'
            "
          >
            {{ match.home_team_name }}
          </button>
          <button
            @click="activeTab = 'away'"
            data-testid="post-match-tab-away"
            class="flex-1 py-2 px-3 text-sm font-medium rounded-lg border-2 transition-colors truncate"
            :class="
              activeTab === 'away'
                ? 'border-blue-500 bg-blue-500/20 text-white'
                : 'border-slate-600 text-slate-400 hover:border-slate-500'
            "
          >
            {{ match.away_team_name }}
          </button>
        </div>

        <!-- Home team panel -->
        <div v-if="activeTab === 'home'">
          <TeamStatsPanel
            :team-id="match.home_team_id"
            :team-name="match.home_team_name"
            :roster="homeRoster"
            :events="teamEvents(match.home_team_id)"
            :player-stats="homeStats"
            :can-edit="canEditTeam(match.home_team_id)"
            :saving="saving"
            :error="error"
            @add-goal="handleAddGoal"
            @remove-goal="handleRemoveGoal"
            @add-substitution="handleAddSubstitution"
            @remove-substitution="handleRemoveSubstitution"
            @save-stats="handleSaveStats"
          />
        </div>

        <!-- Away team panel -->
        <div v-if="activeTab === 'away'">
          <TeamStatsPanel
            :team-id="match.away_team_id"
            :team-name="match.away_team_name"
            :roster="awayRoster"
            :events="teamEvents(match.away_team_id)"
            :player-stats="awayStats"
            :can-edit="canEditTeam(match.away_team_id)"
            :saving="saving"
            :error="error"
            @add-goal="handleAddGoal"
            @remove-goal="handleRemoveGoal"
            @add-substitution="handleAddSubstitution"
            @remove-substitution="handleRemoveSubstitution"
            @save-stats="handleSaveStats"
          />
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue';
import { usePostMatchStats } from '../composables/usePostMatchStats';
import { useMatchLineup } from '../composables/useMatchLineup';
import TeamStatsPanel from './post-match/TeamStatsPanel.vue';

export default {
  name: 'PostMatchEditor',
  components: {
    TeamStatsPanel,
  },
  props: {
    matchId: { type: [Number, String], required: true },
    match: { type: Object, required: true },
    events: { type: Array, default: () => [] },
  },
  emits: ['events-changed'],
  setup(props, { emit }) {
    const showSection = ref(false);
    const activeTab = ref('home');
    const dataLoaded = ref(false);
    const dataLoading = ref(false);

    // Use lineup composable to get rosters
    const { homeRoster, awayRoster, fetchTeamRosters } = useMatchLineup(
      props.matchId,
      computed(() => props.match)
    );

    // Use post-match stats composable
    const {
      homeStats,
      awayStats,
      saving,
      error,
      canEditTeam,
      fetchAllStats,
      addGoal,
      removeGoal,
      addSubstitution,
      removeSubstitution,
      savePlayerStats,
    } = usePostMatchStats(
      props.matchId,
      computed(() => props.match)
    );

    // Filter events by team
    function teamEvents(teamId) {
      return props.events.filter(
        e =>
          e.team_id === teamId &&
          !e.is_deleted &&
          (e.event_type === 'goal' || e.event_type === 'substitution')
      );
    }

    // Toggle section and lazy-load data
    async function toggleSection() {
      showSection.value = !showSection.value;

      if (showSection.value && !dataLoaded.value) {
        dataLoading.value = true;
        try {
          await Promise.all([fetchTeamRosters(), fetchAllStats()]);
          dataLoaded.value = true;
        } catch (err) {
          console.error('Failed to load post-match data:', err);
        } finally {
          dataLoading.value = false;
        }
      }
    }

    // Event handlers
    async function handleAddGoal(goalData) {
      const result = await addGoal(goalData);
      if (result.success) {
        emit('events-changed');
        await fetchAllStats();
      }
    }

    async function handleRemoveGoal(eventId) {
      const result = await removeGoal(eventId);
      if (result.success) {
        emit('events-changed');
        await fetchAllStats();
      }
    }

    async function handleAddSubstitution(subData) {
      const result = await addSubstitution(subData);
      if (result.success) {
        emit('events-changed');
      }
    }

    async function handleRemoveSubstitution(eventId) {
      const result = await removeSubstitution(eventId);
      if (result.success) {
        emit('events-changed');
      }
    }

    async function handleSaveStats(teamId, entries) {
      await savePlayerStats(teamId, entries);
    }

    return {
      showSection,
      activeTab,
      dataLoaded,
      dataLoading,
      homeRoster,
      awayRoster,
      homeStats,
      awayStats,
      saving,
      error,
      canEditTeam,
      teamEvents,
      toggleSection,
      handleAddGoal,
      handleRemoveGoal,
      handleAddSubstitution,
      handleRemoveSubstitution,
      handleSaveStats,
    };
  },
};
</script>
