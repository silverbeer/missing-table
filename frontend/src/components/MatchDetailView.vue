<template>
  <div class="match-detail-view p-3 lg:p-4">
    <!-- Back button -->
    <button
      @click="$emit('back')"
      data-testid="back-button"
      class="flex items-center gap-1.5 px-2 py-1 text-gray-600 hover:text-gray-900 font-medium text-xs mb-2 rounded hover:bg-gray-100 transition-colors"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        class="w-4 h-4"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M15 19l-7-7 7-7"
        />
      </svg>
      <span>Back to Matches</span>
    </button>

    <!-- Loading state -->
    <div
      v-if="loading"
      class="flex flex-col items-center justify-center py-12"
      data-testid="loading-state"
    >
      <div
        class="w-8 h-8 border-3 border-gray-300 border-t-blue-500 rounded-full animate-spin mb-3"
      ></div>
      <p class="text-gray-500 text-sm">Loading match details...</p>
    </div>

    <!-- Error state -->
    <div
      v-else-if="error"
      class="flex flex-col items-center justify-center py-12 text-center"
      data-testid="error-state"
    >
      <div
        class="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center text-red-500 text-xl font-bold mb-3"
      >
        !
      </div>
      <p class="text-gray-500 mb-3 text-sm" data-testid="error-message">
        {{ error }}
      </p>
      <button
        @click="fetchMatch"
        data-testid="retry-button"
        class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium text-sm transition-colors"
      >
        Try Again
      </button>
    </div>

    <!-- Match content -->
    <div v-else-if="match" class="max-w-sm mx-auto" data-testid="match-content">
      <!-- Capture container for share -->
      <div
        ref="scoreboardRef"
        class="bg-slate-800 rounded-lg p-2"
        data-testid="scoreboard"
      >
        <!-- Stadium Scoreboard -->
        <div
          class="scoreboard bg-gradient-to-r from-slate-800 via-slate-700 to-slate-800 rounded-lg p-3 mb-2"
        >
          <!-- LIVE indicator -->
          <div
            v-if="match.match_status === 'live'"
            class="flex justify-center mb-3"
          >
            <div
              class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-red-600 text-white font-bold uppercase tracking-wider text-xs animate-pulse shadow-[0_0_15px_rgba(220,38,38,0.7)]"
              data-testid="status-badge"
            >
              <span
                class="w-1.5 h-1.5 rounded-full bg-white animate-ping"
              ></span>
              LIVE
            </div>
          </div>

          <!-- Status badge for non-live matches -->
          <div v-else class="flex justify-center mb-3">
            <div
              class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider"
              :class="statusBadgeClass"
              data-testid="status-badge"
            >
              {{ match.match_status || 'scheduled' }}
            </div>
          </div>

          <!-- Teams and Score -->
          <div class="flex flex-row items-start justify-center gap-4 lg:gap-8">
            <!-- Home Team -->
            <div class="flex flex-col items-center text-center flex-1 min-w-0">
              <!-- Club Logo -->
              <div
                class="w-14 h-14 lg:w-16 lg:h-16 rounded-full flex items-center justify-center bg-white/10 backdrop-blur-sm overflow-hidden mb-2 border border-slate-500 flex-shrink-0"
                :style="{ boxShadow: `0 0 20px ${homeTeamColor}40` }"
              >
                <img
                  v-if="match.home_team_club?.logo_url"
                  :src="match.home_team_club.logo_url"
                  :alt="`${match.home_team_name} logo`"
                  class="w-12 h-12 lg:w-14 lg:h-14 object-contain"
                />
                <div v-else class="text-lg lg:text-xl font-bold text-slate-400">
                  {{ getTeamInitials(match.home_team_name) }}
                </div>
              </div>
              <h2 class="text-sm lg:text-base font-bold text-white mb-0.5">
                {{ match.home_team_name }}
              </h2>
              <span class="text-[10px] text-slate-400 uppercase tracking-wider"
                >Home</span
              >
            </div>

            <!-- Score Display -->
            <div class="flex items-center gap-2 lg:gap-3 pt-4 lg:pt-5">
              <span
                class="score-number text-3xl lg:text-5xl font-bold text-white"
                data-testid="home-score"
              >
                {{ match.home_score ?? '-' }}
              </span>
              <span class="text-xl lg:text-2xl font-light text-slate-500"
                >-</span
              >
              <span
                class="score-number text-3xl lg:text-5xl font-bold text-white"
                data-testid="away-score"
              >
                {{ match.away_score ?? '-' }}
              </span>
            </div>

            <!-- Away Team -->
            <div class="flex flex-col items-center text-center flex-1 min-w-0">
              <!-- Club Logo -->
              <div
                class="w-14 h-14 lg:w-16 lg:h-16 rounded-full flex items-center justify-center bg-white/10 backdrop-blur-sm overflow-hidden mb-2 border border-slate-500 flex-shrink-0"
                :style="{ boxShadow: `0 0 20px ${awayTeamColor}40` }"
              >
                <img
                  v-if="match.away_team_club?.logo_url"
                  :src="match.away_team_club.logo_url"
                  :alt="`${match.away_team_name} logo`"
                  class="w-12 h-12 lg:w-14 lg:h-14 object-contain"
                />
                <div v-else class="text-lg lg:text-xl font-bold text-slate-400">
                  {{ getTeamInitials(match.away_team_name) }}
                </div>
              </div>
              <h2 class="text-sm lg:text-base font-bold text-white mb-0.5">
                {{ match.away_team_name }}
              </h2>
              <span class="text-[10px] text-slate-400 uppercase tracking-wider"
                >Away</span
              >
            </div>
          </div>

          <!-- Goal Scorers -->
          <div
            v-if="homeGoals.length || awayGoals.length"
            class="flex justify-center gap-4 mt-3 pt-3 border-t border-slate-600"
          >
            <div class="flex-1 text-right max-w-[140px]">
              <div
                v-for="goal in homeGoals"
                :key="goal.id"
                class="text-xs text-slate-300 mb-1"
              >
                {{ goal.player_name }} {{ formatMinute(goal) }}
              </div>
            </div>
            <div class="w-px bg-slate-600 flex-shrink-0"></div>
            <div class="flex-1 text-left max-w-[140px]">
              <div
                v-for="goal in awayGoals"
                :key="goal.id"
                class="text-xs text-slate-300 mb-1"
              >
                {{ goal.player_name }} {{ formatMinute(goal) }}
              </div>
            </div>
          </div>
        </div>

        <!-- Match Details Card -->
        <div class="bg-slate-700/50 rounded-lg p-3">
          <h3 class="text-sm font-semibold text-white mb-3">Match Details</h3>
          <div class="grid grid-cols-2 lg:grid-cols-3 gap-2">
            <div class="detail-item">
              <span class="text-[10px] text-slate-500 uppercase tracking-wider"
                >Date</span
              >
              <span class="text-xs font-medium text-white">{{
                formatDate(match.match_date)
              }}</span>
            </div>
            <div
              v-if="formatLocalTime(match.scheduled_kickoff)"
              class="detail-item"
            >
              <span class="text-[10px] text-slate-500 uppercase tracking-wider"
                >Kickoff</span
              >
              <span class="text-xs font-medium text-white">{{
                formatLocalTime(match.scheduled_kickoff)
              }}</span>
            </div>
            <div class="detail-item">
              <span class="text-[10px] text-slate-500 uppercase tracking-wider"
                >Type</span
              >
              <span class="text-xs font-medium text-white">{{
                match.match_type_name || 'League'
              }}</span>
            </div>
            <div class="detail-item">
              <span class="text-[10px] text-slate-500 uppercase tracking-wider"
                >Season</span
              >
              <span class="text-xs font-medium text-white">{{
                match.season_name
              }}</span>
            </div>
            <div class="detail-item">
              <span class="text-[10px] text-slate-500 uppercase tracking-wider"
                >Age Group</span
              >
              <span class="text-xs font-medium text-white">{{
                match.age_group_name
              }}</span>
            </div>
            <div
              v-if="match.division_name && match.match_type_name !== 'Friendly'"
              class="detail-item"
            >
              <span class="text-[10px] text-slate-500 uppercase tracking-wider"
                >Division</span
              >
              <span class="text-xs font-medium text-white">{{
                match.division_name
              }}</span>
            </div>
            <div v-if="leagueName" class="detail-item">
              <span class="text-[10px] text-slate-500 uppercase tracking-wider"
                >League</span
              >
              <span class="text-xs font-medium text-white">{{
                leagueName
              }}</span>
            </div>
          </div>
        </div>
      </div>
      <!-- End capture container -->

      <!-- Share Button (at bottom, not captured in image) -->
      <div class="flex justify-center mt-3">
        <button
          @click="shareScoreboard"
          :disabled="shareStatus === 'copying'"
          data-testid="share-button"
          class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors"
          :class="{
            'bg-green-600 text-white': shareStatus === 'success',
            'bg-red-600 text-white': shareStatus === 'error',
            'bg-gray-200 text-gray-700 hover:bg-gray-300':
              !shareStatus || shareStatus === 'copying',
          }"
        >
          <!-- Copy icon -->
          <svg
            v-if="!shareStatus"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            class="w-3.5 h-3.5"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
            />
          </svg>
          <!-- Loading spinner -->
          <svg
            v-else-if="shareStatus === 'copying'"
            class="w-3.5 h-3.5 animate-spin"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              class="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              stroke-width="4"
            ></circle>
            <path
              class="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            ></path>
          </svg>
          <!-- Check icon -->
          <svg
            v-else-if="shareStatus === 'success'"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            class="w-3.5 h-3.5"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M5 13l4 4L19 7"
            />
          </svg>
          <!-- Error icon -->
          <svg
            v-else-if="shareStatus === 'error'"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            class="w-3.5 h-3.5"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
          <span v-if="!shareStatus">Copy to Clipboard</span>
          <span v-else-if="shareStatus === 'copying'">Copying...</span>
          <span v-else-if="shareStatus === 'success'">Copied!</span>
          <span v-else-if="shareStatus === 'error'">Failed</span>
        </button>
      </div>

      <!-- Pre-match Lineup Section (scheduled matches, authorized users only) -->
      <div
        v-if="canManageLineup && match.match_status === 'scheduled'"
        class="mt-3"
        data-testid="lineup-section"
      >
        <button
          @click="toggleLineupSection"
          data-testid="lineup-toggle"
          class="w-full flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm font-semibold rounded-lg transition-colors"
          :class="{ 'bg-slate-600': showLineupSection }"
        >
          <span class="text-base font-bold w-5 text-center">{{
            showLineupSection ? '-' : '+'
          }}</span>
          Starting Lineup
        </button>

        <div v-if="showLineupSection" class="mt-2 bg-slate-800 rounded-lg p-3">
          <!-- No roster for either team -->
          <div
            v-if="rostersLoaded && !homeRoster.length && !awayRoster.length"
            class="text-slate-400 text-sm text-center py-4"
            data-testid="no-roster-message"
          >
            No roster available for either team. Add players to a team roster
            before setting lineups.
          </div>

          <!-- Loading state -->
          <div
            v-else-if="lineupDataLoading"
            class="text-slate-400 text-sm text-center py-4"
          >
            Loading lineups...
          </div>

          <!-- Team tabs + LineupManager -->
          <template v-else-if="rostersLoaded">
            <div class="flex gap-2 mb-3">
              <button
                @click="activeLineupTab = 'home'"
                data-testid="lineup-tab-home"
                class="flex-1 py-2 px-3 text-sm font-medium rounded-lg border-2 transition-colors truncate"
                :class="
                  activeLineupTab === 'home'
                    ? 'border-blue-500 bg-blue-500/20 text-white'
                    : 'border-slate-600 text-slate-400 hover:border-slate-500'
                "
              >
                {{ match.home_team_name }}
              </button>
              <button
                @click="activeLineupTab = 'away'"
                data-testid="lineup-tab-away"
                class="flex-1 py-2 px-3 text-sm font-medium rounded-lg border-2 transition-colors truncate"
                :class="
                  activeLineupTab === 'away'
                    ? 'border-blue-500 bg-blue-500/20 text-white'
                    : 'border-slate-600 text-slate-400 hover:border-slate-500'
                "
              >
                {{ match.away_team_name }}
              </button>
            </div>

            <!-- Home team tab -->
            <div v-if="activeLineupTab === 'home'">
              <div
                v-if="!homeRoster.length"
                class="text-slate-400 text-sm text-center py-4"
                data-testid="no-roster-home"
              >
                No roster available for {{ match.home_team_name }}.
              </div>
              <LineupManager
                v-else
                :team-id="match.home_team_id"
                :team-name="match.home_team_name"
                :roster="homeRoster"
                :initial-lineup="homeLineup"
                :saving="savingLineup"
                :sport-type="sportType"
                @save="handleSaveLineup(match.home_team_id, $event)"
              />
            </div>

            <!-- Away team tab -->
            <div v-if="activeLineupTab === 'away'">
              <div
                v-if="!awayRoster.length"
                class="text-slate-400 text-sm text-center py-4"
                data-testid="no-roster-away"
              >
                No roster available for {{ match.away_team_name }}.
              </div>
              <LineupManager
                v-else
                :team-id="match.away_team_id"
                :team-name="match.away_team_name"
                :roster="awayRoster"
                :initial-lineup="awayLineup"
                :saving="savingLineup"
                :sport-type="sportType"
                @save="handleSaveLineup(match.away_team_id, $event)"
              />
            </div>
          </template>
        </div>
      </div>

      <!-- Screen reader description -->
      <span class="sr-only">
        {{ match.home_team_name }} {{ match.home_score ?? 'no score' }} versus
        {{ match.away_team_name }} {{ match.away_score ?? 'no score' }}. Match
        status: {{ match.match_status || 'scheduled' }}.
        {{ match.match_type_name }} match on {{ formatDate(match.match_date) }}.
      </span>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../config/api';
import html2canvas from 'html2canvas';
import { useMatchLineup } from '../composables/useMatchLineup';
import LineupManager from './live/LineupManager.vue';

export default {
  name: 'MatchDetailView',
  components: {
    LineupManager,
  },
  props: {
    matchId: {
      type: [Number, String],
      required: true,
    },
  },
  emits: ['back'],
  setup(props) {
    const authStore = useAuthStore();
    const loading = ref(true);
    const error = ref(null);
    const match = ref(null);
    const events = ref([]);
    const scoreboardRef = ref(null);
    const shareStatus = ref(null); // 'copying', 'success', 'error'

    // Get home team primary color for glow effect
    const homeTeamColor = computed(() => {
      return match.value?.home_team_club?.primary_color || '#3B82F6';
    });

    // Get away team primary color for glow effect
    const awayTeamColor = computed(() => {
      return match.value?.away_team_club?.primary_color || '#EF4444';
    });

    // Get league name from division object
    const leagueName = computed(() => {
      return match.value?.division?.leagues?.name || null;
    });

    // Determine sport type from match data
    const sportType = computed(() => {
      return (
        match.value?.sport_type ||
        match.value?.division?.leagues?.sport_type ||
        'soccer'
      );
    });

    // Filter goals by team
    const homeGoals = computed(() => {
      return events.value
        .filter(
          e =>
            e.event_type === 'goal' && e.team_id === match.value?.home_team_id
        )
        .sort((a, b) => (a.match_minute || 0) - (b.match_minute || 0));
    });

    const awayGoals = computed(() => {
      return events.value
        .filter(
          e =>
            e.event_type === 'goal' && e.team_id === match.value?.away_team_id
        )
        .sort((a, b) => (a.match_minute || 0) - (b.match_minute || 0));
    });

    // Format minute display (e.g., "22'" or "90+5'")
    const formatMinute = goal => {
      if (!goal.match_minute) return '';
      if (goal.extra_time) {
        return `${goal.match_minute}+${goal.extra_time}'`;
      }
      return `${goal.match_minute}'`;
    };

    // Status badge class based on match status
    const statusBadgeClass = computed(() => {
      const status = match.value?.match_status || 'scheduled';
      const classes = {
        completed: 'bg-green-900/50 text-green-400 border border-green-700',
        scheduled: 'bg-blue-900/50 text-blue-400 border border-blue-700',
        postponed: 'bg-yellow-900/50 text-yellow-400 border border-yellow-700',
        cancelled: 'bg-red-900/50 text-red-400 border border-red-700',
      };
      return classes[status] || classes.scheduled;
    });

    // Get team initials for fallback logo
    const getTeamInitials = teamName => {
      if (!teamName) return '?';
      return teamName
        .split(' ')
        .map(word => word[0])
        .join('')
        .substring(0, 3)
        .toUpperCase();
    };

    // Format date for display
    const formatDate = dateString => {
      if (!dateString) return '';
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    };

    // Format UTC datetime to local time display
    const formatLocalTime = isoString => {
      if (!isoString) return null;
      const date = new Date(isoString);
      return date.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      });
    };

    // Fetch match events (goals, etc.)
    const fetchEvents = async () => {
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/matches/${props.matchId}/live/events`
        );
        events.value = data || [];
      } catch (err) {
        // Events might not exist for older matches, that's ok
        console.log('No events found for match:', err.message);
        events.value = [];
      }
    };

    // Fetch match details
    const fetchMatch = async () => {
      loading.value = true;
      error.value = null;

      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/matches/${props.matchId}`
        );
        match.value = data;
        // Also fetch events for completed/live matches
        if (data.match_status === 'completed' || data.match_status === 'live') {
          await fetchEvents();
        }
      } catch (err) {
        console.error('Error fetching match:', err);
        if (err.message?.includes('401') || err.message?.includes('403')) {
          error.value = 'You must be logged in to view match details';
        } else if (err.message?.includes('404')) {
          error.value = 'Match not found';
        } else {
          error.value = 'Failed to load match details';
        }
      } finally {
        loading.value = false;
      }
    };

    // Watch for matchId changes
    watch(
      () => props.matchId,
      () => {
        fetchMatch();
      }
    );

    onMounted(() => {
      fetchMatch();
    });

    // Share scoreboard as image to clipboard
    const shareScoreboard = async () => {
      if (!scoreboardRef.value) return;

      shareStatus.value = 'copying';

      try {
        const canvas = await html2canvas(scoreboardRef.value, {
          backgroundColor: '#1e293b', // slate-800
          scale: 2, // Higher resolution
          logging: false,
          useCORS: true, // Enable CORS for cross-origin images (logos)
          allowTaint: false, // Don't taint canvas (safer)
        });

        canvas.toBlob(async blob => {
          try {
            await navigator.clipboard.write([
              new ClipboardItem({ 'image/png': blob }),
            ]);
            shareStatus.value = 'success';
            setTimeout(() => {
              shareStatus.value = null;
            }, 2000);
          } catch (err) {
            console.error('Failed to copy to clipboard:', err);
            shareStatus.value = 'error';
            setTimeout(() => {
              shareStatus.value = null;
            }, 2000);
          }
        }, 'image/png');
      } catch (err) {
        console.error('Failed to capture scoreboard:', err);
        shareStatus.value = 'error';
        setTimeout(() => {
          shareStatus.value = null;
        }, 2000);
      }
    };

    // --- Pre-match lineup management ---
    const {
      homeRoster,
      awayRoster,
      homeLineup,
      awayLineup,
      fetchTeamRosters,
      fetchLineups,
      saveLineup,
    } = useMatchLineup(props.matchId, match);

    // Permission: can the current user manage lineups for this match?
    const canManageLineup = computed(() => {
      if (!match.value) return false;
      if (!authStore.isAuthenticated.value) return false;
      if (authStore.isAdmin.value) return true;
      if (authStore.isClubManager.value) return true;
      if (authStore.isTeamManager.value) {
        const userTeamId = authStore.userTeamId.value;
        return (
          userTeamId === match.value.home_team_id ||
          userTeamId === match.value.away_team_id
        );
      }
      return false;
    });

    // Lineup UI state
    const showLineupSection = ref(false);
    const activeLineupTab = ref('home');
    const rostersLoaded = ref(false);
    const lineupDataLoading = ref(false);
    const savingLineup = ref(false);

    // Toggle lineup section and lazy-load rosters/lineups
    const toggleLineupSection = async () => {
      showLineupSection.value = !showLineupSection.value;

      if (showLineupSection.value && !rostersLoaded.value) {
        lineupDataLoading.value = true;
        try {
          await Promise.all([fetchTeamRosters(), fetchLineups()]);
          rostersLoaded.value = true;
        } catch (err) {
          console.error('Failed to load lineups and rosters:', err);
        } finally {
          lineupDataLoading.value = false;
        }
      }
    };

    // Handle lineup save from LineupManager component
    const handleSaveLineup = async (teamId, lineupData) => {
      savingLineup.value = true;
      try {
        const result = await saveLineup(
          teamId,
          lineupData.formation_name,
          lineupData.positions
        );
        if (!result.success) {
          console.error('Failed to save lineup:', result.error);
        }
      } catch (err) {
        console.error('Error saving lineup:', err);
      } finally {
        savingLineup.value = false;
      }
    };

    return {
      loading,
      error,
      match,
      events,
      homeGoals,
      awayGoals,
      homeTeamColor,
      awayTeamColor,
      leagueName,
      sportType,
      statusBadgeClass,
      getTeamInitials,
      formatDate,
      formatLocalTime,
      formatMinute,
      fetchMatch,
      scoreboardRef,
      shareStatus,
      shareScoreboard,
      // Lineup
      canManageLineup,
      showLineupSection,
      activeLineupTab,
      homeRoster,
      awayRoster,
      homeLineup,
      awayLineup,
      rostersLoaded,
      lineupDataLoading,
      savingLineup,
      toggleLineupSection,
      handleSaveLineup,
    };
  },
};
</script>

<style scoped>
/* Glowing score numbers */
.score-number {
  text-shadow:
    0 0 20px rgba(255, 255, 255, 0.4),
    0 0 40px rgba(255, 255, 255, 0.2),
    0 0 60px rgba(255, 255, 255, 0.1);
}

/* Detail item styling */
.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* Scoreboard subtle animation for live matches */
@keyframes pulse-glow {
  0%,
  100% {
    box-shadow: 0 0 20px rgba(239, 68, 68, 0.3);
  }
  50% {
    box-shadow: 0 0 40px rgba(239, 68, 68, 0.5);
  }
}

.scoreboard:has(.animate-pulse) {
  animation: pulse-glow 2s ease-in-out infinite;
}
</style>
