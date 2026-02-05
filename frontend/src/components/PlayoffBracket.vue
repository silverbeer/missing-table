<template>
  <div class="playoff-bracket">
    <!-- Loading -->
    <div v-if="loading" class="text-center py-8 text-gray-500">
      Loading bracket...
    </div>

    <!-- Error -->
    <div v-else-if="error" class="text-center py-4 text-red-600 text-sm">
      {{ error }}
    </div>

    <!-- No bracket -->
    <div
      v-else-if="bracket.length === 0"
      class="text-center py-8 text-gray-400 text-sm"
    >
      No playoff bracket available.
    </div>

    <!-- Bracket display -->
    <div v-else>
      <div v-for="tier in bracketTiers" :key="tier.key" class="tier-section">
        <h3 class="tier-header">{{ tier.label }}</h3>
        <div class="bracket-layout">
          <!-- Quarterfinals column -->
          <div class="bracket-column">
            <h4 class="round-header">Quarterfinals</h4>
            <div class="matchups matchups-qf">
              <div
                v-for="s in getSlotsByRound(tier.key, 'quarterfinal')"
                :key="s.id"
                class="matchup-card"
                :class="{ completed: s.match_status === 'completed' }"
              >
                <div class="team-row" :class="{ winner: isWinner(s, 'home') }">
                  <span class="seed" v-if="s.home_seed">{{ s.home_seed }}</span>
                  <span class="team-name">{{ s.home_team_name || 'TBD' }}</span>
                  <span class="score">{{ s.home_score ?? '' }}</span>
                </div>
                <div class="team-row" :class="{ winner: isWinner(s, 'away') }">
                  <span class="seed" v-if="s.away_seed">{{ s.away_seed }}</span>
                  <span class="team-name">{{ s.away_team_name || 'TBD' }}</span>
                  <span class="score">{{ s.away_score ?? '' }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Connector QF→SF -->
          <div class="connector-column connector-qf-sf">
            <div class="connector-pair">
              <div class="connector-line top"></div>
              <div class="connector-line bottom"></div>
              <div class="connector-merge"></div>
            </div>
            <div class="connector-pair">
              <div class="connector-line top"></div>
              <div class="connector-line bottom"></div>
              <div class="connector-merge"></div>
            </div>
          </div>

          <!-- Semifinals column -->
          <div class="bracket-column">
            <h4 class="round-header">Semifinals</h4>
            <div class="matchups matchups-sf">
              <div
                v-for="s in getSlotsByRound(tier.key, 'semifinal')"
                :key="s.id"
                class="matchup-card"
                :class="{ completed: s.match_status === 'completed' }"
              >
                <div class="team-row" :class="{ winner: isWinner(s, 'home') }">
                  <span class="seed" v-if="s.home_seed">{{ s.home_seed }}</span>
                  <span class="team-name">{{ s.home_team_name || 'TBD' }}</span>
                  <span class="score">{{ s.home_score ?? '' }}</span>
                </div>
                <div class="team-row" :class="{ winner: isWinner(s, 'away') }">
                  <span class="seed" v-if="s.away_seed">{{ s.away_seed }}</span>
                  <span class="team-name">{{ s.away_team_name || 'TBD' }}</span>
                  <span class="score">{{ s.away_score ?? '' }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Connector SF→Final -->
          <div class="connector-column connector-sf-final">
            <div class="connector-pair">
              <div class="connector-line top"></div>
              <div class="connector-line bottom"></div>
              <div class="connector-merge"></div>
            </div>
          </div>

          <!-- Final column -->
          <div class="bracket-column">
            <h4 class="round-header">Final</h4>
            <div class="matchups matchups-final">
              <div
                v-for="s in getSlotsByRound(tier.key, 'final')"
                :key="s.id"
                class="matchup-card final-card"
                :class="{ completed: s.match_status === 'completed' }"
              >
                <div class="team-row" :class="{ winner: isWinner(s, 'home') }">
                  <span class="team-name">{{ s.home_team_name || 'TBD' }}</span>
                  <span class="score">{{ s.home_score ?? '' }}</span>
                </div>
                <div class="team-row" :class="{ winner: isWinner(s, 'away') }">
                  <span class="team-name">{{ s.away_team_name || 'TBD' }}</span>
                  <span class="score">{{ s.away_score ?? '' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../config/api';

export default {
  name: 'PlayoffBracket',
  props: {
    leagueId: { type: Number, required: true },
    seasonId: { type: Number, required: true },
    ageGroupId: { type: Number, required: true },
  },
  setup(props) {
    const authStore = useAuthStore();
    const bracket = ref([]);
    const loading = ref(false);
    const error = ref(null);

    // Derive bracket tiers dynamically from bracket data
    const bracketTiers = computed(() => {
      const tierNames = [...new Set(bracket.value.map(s => s.bracket_tier))];
      // Sort alphabetically for consistent display
      tierNames.sort();
      return tierNames.map(name => ({
        key: name,
        label: name,
      }));
    });

    const getSlotsByRound = (tier, round) =>
      bracket.value
        .filter(s => s.bracket_tier === tier && s.round === round)
        .sort((a, b) => a.bracket_position - b.bracket_position);

    const isWinner = (s, side) => {
      if (s.match_status !== 'completed') return false;
      if (s.home_score == null || s.away_score == null) return false;
      if (side === 'home') return s.home_score > s.away_score;
      return s.away_score > s.home_score;
    };

    const fetchBracket = async () => {
      if (!props.leagueId || !props.seasonId || !props.ageGroupId) return;
      try {
        loading.value = true;
        error.value = null;
        const params = new URLSearchParams({
          league_id: props.leagueId,
          season_id: props.seasonId,
          age_group_id: props.ageGroupId,
        });
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/playoffs/bracket?${params}`,
          { method: 'GET' }
        );
        bracket.value = data || [];
      } catch (err) {
        error.value = err.message || 'Failed to load bracket';
      } finally {
        loading.value = false;
      }
    };

    onMounted(fetchBracket);

    watch(
      () => [props.leagueId, props.seasonId, props.ageGroupId],
      fetchBracket
    );

    return {
      bracket,
      loading,
      error,
      bracketTiers,
      getSlotsByRound,
      isWinner,
    };
  },
};
</script>

<style scoped>
.playoff-bracket {
  overflow-x: auto;
}

.tier-section {
  margin-bottom: 2.5rem;
}

.tier-header {
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
  margin-bottom: 0.75rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid #e5e7eb;
}

/* Bracket layout — 5 columns: QF | connectors | SF | connectors | Final */
.bracket-layout {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) 32px minmax(140px, 1fr) 32px minmax(
      140px,
      1fr
    );
  gap: 0;
  align-items: start;
  min-width: 560px;
}

.round-header {
  font-size: 0.75rem;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  text-align: center;
  margin-bottom: 0.75rem;
}

/* Matchup cards */
.matchup-card {
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  overflow: hidden;
  background: #fff;
  font-size: 0.8125rem;
}

.matchup-card.completed {
  border-color: #86efac;
}

.final-card {
  border-width: 2px;
  border-color: #fbbf24;
}

.final-card.completed {
  border-color: #22c55e;
}

.team-row {
  display: flex;
  align-items: center;
  padding: 0.375rem 0.5rem;
}

.team-row + .team-row {
  border-top: 1px solid #f3f4f6;
}

.team-row.winner {
  font-weight: 700;
  color: #15803d;
  background: #f0fdf4;
}

.seed {
  width: 1rem;
  text-align: right;
  color: #9ca3af;
  font-size: 0.6875rem;
  margin-right: 0.375rem;
  flex-shrink: 0;
}

.team-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.score {
  min-width: 1.25rem;
  text-align: right;
  font-family: ui-monospace, monospace;
  font-weight: 600;
  margin-left: 0.5rem;
}

/* Spacing between matchup cards per round */
.matchups-qf {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.matchups-sf {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  /* Vertically center between QF pairs */
  margin-top: 1.75rem;
}

.matchups-final {
  /* Vertically center between SF pair */
  margin-top: 4.25rem;
}

/* Connector lines */
.connector-column {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  padding-top: 1.75rem; /* align with round header */
}

.connector-pair {
  position: relative;
  flex: 1;
}

.connector-qf-sf .connector-pair {
  height: 5.5rem;
  margin-bottom: 0.5rem;
}

.connector-sf-final .connector-pair {
  height: 8.5rem;
  margin-top: 1.75rem;
}

.connector-line {
  position: absolute;
  right: 0;
  width: 50%;
  border-top: 2px solid #d1d5db;
}

.connector-line.top {
  top: 25%;
}

.connector-line.bottom {
  top: 75%;
}

.connector-merge {
  position: absolute;
  right: 0;
  top: 25%;
  height: 50%;
  border-right: 2px solid #d1d5db;
}

/* Mobile: stack vertically */
@media (max-width: 640px) {
  .bracket-layout {
    grid-template-columns: 1fr;
    min-width: unset;
    gap: 1rem;
  }

  .connector-column {
    display: none;
  }

  .matchups-sf,
  .matchups-final {
    margin-top: 0;
  }
}
</style>
