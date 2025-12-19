<template>
  <BaseProfile title="Fan Dashboard" @logout="$emit('logout')">
    <template #profile-fields>
      <!-- Club Assignment (for club fans) -->
      <div v-if="club" class="info-group">
        <label>Club:</label>
        <span class="club-name">{{ club.name }}</span>
      </div>
      <!-- Favorite Team -->
      <div v-if="authStore.state.profile.team" class="info-group">
        <label>Favorite Team:</label>
        <span class="team-name"
          >{{ authStore.state.profile.team.name }} ({{
            authStore.state.profile.team.city
          }})</span
        >
      </div>
      <div v-else class="info-group">
        <label>Favorite Team:</label>
        <span class="no-team">No team selected</span>
      </div>
      <div class="info-group">
        <label>Fan Status:</label>
        <span class="fan-status">{{
          club ? 'Club Fan' : 'Registered Fan'
        }}</span>
      </div>
    </template>

    <template #profile-sections>
      <!-- Team Selection -->
      <div v-if="isEditing" class="team-selection-section">
        <h3>Choose Your Favorite Team</h3>
        <div class="team-selector">
          <label for="teamSelect">Support a team:</label>
          <select
            id="teamSelect"
            v-model="editForm.team_id"
            class="team-select"
          >
            <option value="">No team preference</option>
            <option v-for="team in teams" :key="team.id" :value="team.id">
              {{ team.name }} ({{ team.city }})
            </option>
          </select>
          <p class="team-note">Follow your favorite team's games and results</p>
        </div>
      </div>

      <!-- Favorite Team Section -->
      <div v-if="authStore.state.profile.team" class="favorite-team">
        <h3>{{ authStore.state.profile.team.name }} Dashboard</h3>

        <!-- Team Quick Stats -->
        <div class="team-overview">
          <div class="team-header">
            <div class="team-info">
              <h4>{{ authStore.state.profile.team.name }}</h4>
              <p>{{ authStore.state.profile.team.city }}</p>
            </div>
            <div class="team-record">
              <div class="record-item">
                <span class="record-number">{{ wins }}</span>
                <span class="record-label">Wins</span>
              </div>
              <div class="record-item">
                <span class="record-number">{{ draws }}</span>
                <span class="record-label">Draws</span>
              </div>
              <div class="record-item">
                <span class="record-number">{{ losses }}</span>
                <span class="record-label">Losses</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Upcoming Games -->
        <div class="upcoming-games">
          <h4>Upcoming Games</h4>
          <div v-if="loadingGames" class="loading">Loading games...</div>
          <div v-else-if="upcomingGames.length === 0" class="no-games">
            No upcoming games scheduled
          </div>
          <div v-else class="games-list">
            <div
              v-for="game in upcomingGames.slice(0, 3)"
              :key="game.id"
              class="game-card"
            >
              <div class="game-date">
                {{ formatGameDate(game.game_date) }}
              </div>
              <div class="game-matchup">
                <span
                  class="team"
                  :class="{ 'my-team': isMyTeam(game.home_team_id) }"
                >
                  {{ game.home_team_name }}
                </span>
                <span class="vs">vs</span>
                <span
                  class="team"
                  :class="{ 'my-team': isMyTeam(game.away_team_id) }"
                >
                  {{ game.away_team_name }}
                </span>
              </div>
              <div class="game-type">{{ game.game_type_name }}</div>
            </div>
          </div>
          <div v-if="upcomingGames.length > 3" class="view-all">
            <button @click="showAllGames = !showAllGames" class="view-all-btn">
              {{
                showAllGames
                  ? 'Show Less'
                  : `View All ${upcomingGames.length} Games`
              }}
            </button>
          </div>
        </div>

        <!-- Recent Results -->
        <div class="recent-results">
          <h4>Recent Results</h4>
          <div v-if="recentGames.length === 0" class="no-games">
            No recent games
          </div>
          <div v-else class="results-list">
            <div
              v-for="game in recentGames.slice(0, 5)"
              :key="game.id"
              class="result-card"
            >
              <div class="result-date">
                {{ formatGameDate(game.game_date) }}
              </div>
              <div class="result-matchup">
                <div class="result-team">
                  <span :class="{ 'my-team': isMyTeam(game.home_team_id) }">
                    {{ game.home_team_name }}
                  </span>
                  <span class="score">{{ game.home_score }}</span>
                </div>
                <div class="result-separator">-</div>
                <div class="result-team">
                  <span class="score">{{ game.away_score }}</span>
                  <span :class="{ 'my-team': isMyTeam(game.away_team_id) }">
                    {{ game.away_team_name }}
                  </span>
                </div>
              </div>
              <div class="result-outcome">
                <span :class="getResultClass(game)">{{
                  getGameResult(game)
                }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- League Information -->
      <div class="league-info">
        <h3>League Information</h3>
        <div class="info-cards">
          <div class="info-card">
            <div class="card-icon">🏆</div>
            <h4>Current Season</h4>
            <p>2025-2026 Season</p>
            <small>Follow all teams and games</small>
          </div>

          <div class="info-card">
            <div class="card-icon">📊</div>
            <h4>League Standings</h4>
            <p>View Tables</p>
            <small>Check current league positions</small>
          </div>

          <div class="info-card">
            <div class="card-icon">📅</div>
            <h4>All Games</h4>
            <p>Full Schedule</p>
            <small>See all league fixtures</small>
          </div>

          <div class="info-card">
            <div class="card-icon">⚽</div>
            <h4>Teams</h4>
            <p>All Teams</p>
            <small>Explore team profiles</small>
          </div>
        </div>
      </div>

      <!-- Fan Features -->
      <div class="fan-features">
        <h3>Fan Features</h3>
        <div class="features-grid">
          <div class="feature-item">
            <div class="feature-icon">🔔</div>
            <div class="feature-text">
              <h4>Game Notifications</h4>
              <p>Get notified about your team's upcoming games</p>
            </div>
          </div>

          <div class="feature-item">
            <div class="feature-icon">📈</div>
            <div class="feature-text">
              <h4>Team Statistics</h4>
              <p>Track your favorite team's performance</p>
            </div>
          </div>

          <div class="feature-item">
            <div class="feature-icon">🎯</div>
            <div class="feature-text">
              <h4>Match Predictions</h4>
              <p>Make predictions for upcoming games</p>
            </div>
          </div>

          <div class="feature-item">
            <div class="feature-icon">👥</div>
            <div class="feature-text">
              <h4>Fan Community</h4>
              <p>Connect with other fans of your team</p>
            </div>
          </div>
        </div>
      </div>

      <!-- No Team Selected -->
      <div v-if="!authStore.state.profile.team" class="no-team-section">
        <div class="no-team-message">
          <h3>Welcome to the League!</h3>
          <p>
            Choose a favorite team to get personalized updates and follow their
            journey throughout the season.
          </p>
          <div class="fan-benefits">
            <h4>As a registered fan, you can:</h4>
            <ul>
              <li>Follow your favorite team's games and results</li>
              <li>View league standings and statistics</li>
              <li>Access the full game schedule</li>
              <li>Get updates on league news and events</li>
            </ul>
          </div>
        </div>
      </div>
    </template>
  </BaseProfile>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import BaseProfile from './BaseProfile.vue';
import { getApiBaseUrl } from '../../config/api';

export default {
  name: 'FanProfile',
  components: {
    BaseProfile,
  },
  emits: ['logout'],
  setup() {
    const authStore = useAuthStore();
    const teams = ref([]);
    const teamGames = ref([]);
    const showAllGames = ref(false);
    const loadingGames = ref(false);
    const isEditing = ref(false);
    const club = ref(null);

    const editForm = ref({
      team_id: null,
    });

    // Fetch club info if user has club_id
    const fetchClub = async () => {
      const clubId = authStore.state.profile?.club_id;
      if (!clubId) return;

      try {
        const response = await fetch(`${getApiBaseUrl()}/api/clubs/${clubId}`);
        if (response.ok) {
          club.value = await response.json();
        }
      } catch (error) {
        console.error('Error fetching club:', error);
      }
    };

    const upcomingGames = computed(() => {
      const now = new Date();
      const upcoming = teamGames.value.filter(
        game => new Date(game.game_date) > now || game.home_score === null
      );
      return showAllGames.value ? upcoming : upcoming.slice(0, 3);
    });

    const recentGames = computed(() => {
      return teamGames.value
        .filter(game => game.home_score !== null)
        .sort((a, b) => new Date(b.game_date) - new Date(a.game_date))
        .slice(0, 5);
    });

    const wins = computed(() => {
      return recentGames.value.filter(game => {
        const teamId = authStore.state.profile?.team?.id;
        if (!teamId) return false;

        if (game.home_team_id === teamId) {
          return game.home_score > game.away_score;
        } else {
          return game.away_score > game.home_score;
        }
      }).length;
    });

    const draws = computed(() => {
      return recentGames.value.filter(
        game => game.home_score === game.away_score
      ).length;
    });

    const losses = computed(() => {
      return recentGames.value.filter(game => {
        const teamId = authStore.state.profile?.team?.id;
        if (!teamId) return false;

        if (game.home_team_id === teamId) {
          return game.home_score < game.away_score;
        } else {
          return game.away_score < game.home_score;
        }
      }).length;
    });

    const fetchTeams = async () => {
      try {
        const response = await fetch(`${getApiBaseUrl()}/api/teams`);
        if (response.ok) {
          teams.value = await response.json();
        }
      } catch (error) {
        console.error('Error fetching teams:', error);
      }
    };

    const fetchTeamGames = async () => {
      const teamId = authStore.state.profile?.team?.id;
      if (!teamId) return;

      try {
        loadingGames.value = true;
        const response = await fetch(
          `${getApiBaseUrl()}/api/matches/team/${teamId}`
        );
        if (response.ok) {
          teamGames.value = await response.json();
        }
      } catch (error) {
        console.error('Error fetching team games:', error);
      } finally {
        loadingGames.value = false;
      }
    };

    const isMyTeam = teamId => {
      return teamId === authStore.state.profile?.team?.id;
    };

    const formatGameDate = dateString => {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
      });
    };

    const getGameResult = game => {
      const teamId = authStore.state.profile?.team?.id;
      if (!teamId) return '';

      let myScore, opponentScore;

      if (game.home_team_id === teamId) {
        myScore = game.home_score;
        opponentScore = game.away_score;
      } else {
        myScore = game.away_score;
        opponentScore = game.home_score;
      }

      if (myScore > opponentScore) return 'W';
      if (myScore < opponentScore) return 'L';
      return 'D';
    };

    const getResultClass = game => {
      const result = getGameResult(game);
      return {
        'result-win': result === 'W',
        'result-loss': result === 'L',
        'result-draw': result === 'D',
      };
    };

    // Watch for team changes
    watch(
      () => authStore.state.profile?.team,
      async newTeam => {
        if (newTeam) {
          await fetchTeamGames();
        }
      },
      { immediate: true }
    );

    onMounted(() => {
      fetchTeams();
      fetchClub();
    });

    return {
      authStore,
      teams,
      teamGames,
      showAllGames,
      loadingGames,
      isEditing,
      editForm,
      upcomingGames,
      recentGames,
      wins,
      draws,
      losses,
      isMyTeam,
      formatGameDate,
      getGameResult,
      getResultClass,
      club,
    };
  },
};
</script>

<style scoped>
.club-name {
  color: #7c3aed;
  font-weight: 600;
}

.team-name {
  color: #059669;
  font-weight: 600;
}

.no-team {
  color: #6b7280;
  font-style: italic;
}

.fan-status {
  color: #3b82f6;
  font-weight: 600;
}

.team-selection-section {
  background-color: #f0f9ff;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid #bae6fd;
}

.team-selector label {
  display: block;
  font-weight: 600;
  margin-bottom: 10px;
  color: #1e40af;
}

.team-select {
  width: 100%;
  padding: 10px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 14px;
  margin-bottom: 8px;
}

.team-note {
  color: #6b7280;
  font-size: 12px;
  margin: 0;
}

.favorite-team {
  background-color: #f8fafc;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.team-overview {
  background: white;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid #e5e7eb;
}

.team-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.team-info h4 {
  color: #1f2937;
  margin: 0 0 5px 0;
  font-size: 20px;
}

.team-info p {
  color: #6b7280;
  margin: 0;
}

.team-record {
  display: flex;
  gap: 20px;
}

.record-item {
  text-align: center;
}

.record-number {
  display: block;
  font-size: 24px;
  font-weight: bold;
  color: #059669;
}

.record-label {
  display: block;
  font-size: 12px;
  color: #6b7280;
  text-transform: uppercase;
}

.upcoming-games,
.recent-results {
  background: white;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid #e5e7eb;
}

.upcoming-games h4,
.recent-results h4 {
  color: #1f2937;
  margin-bottom: 15px;
}

.games-list,
.results-list {
  display: grid;
  gap: 12px;
}

.game-card,
.result-card {
  background-color: #f9fafb;
  padding: 15px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  display: grid;
  grid-template-columns: 120px 1fr 80px;
  gap: 15px;
  align-items: center;
}

.game-date,
.result-date {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}

.game-matchup,
.result-matchup {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.team {
  font-weight: 500;
}

.team.my-team {
  color: #059669;
  font-weight: 700;
}

.vs {
  color: #6b7280;
  font-size: 12px;
}

.game-type {
  text-align: center;
  font-size: 12px;
  color: #6b7280;
}

.result-team {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-separator {
  color: #6b7280;
  font-weight: bold;
}

.score {
  font-weight: bold;
  color: #1f2937;
}

.result-outcome {
  text-align: center;
}

.result-win {
  background-color: #d1fae5;
  color: #059669;
  padding: 4px 8px;
  border-radius: 12px;
  font-weight: bold;
  font-size: 12px;
}

.result-loss {
  background-color: #fee2e2;
  color: #dc2626;
  padding: 4px 8px;
  border-radius: 12px;
  font-weight: bold;
  font-size: 12px;
}

.result-draw {
  background-color: #fef3c7;
  color: #f59e0b;
  padding: 4px 8px;
  border-radius: 12px;
  font-weight: bold;
  font-size: 12px;
}

.view-all {
  text-align: center;
  margin-top: 15px;
}

.view-all-btn {
  background: none;
  border: 1px solid #d1d5db;
  color: #6b7280;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.view-all-btn:hover {
  background-color: #f9fafb;
  border-color: #9ca3af;
}

.no-games {
  text-align: center;
  color: #6b7280;
  padding: 20px;
  font-style: italic;
}

.league-info {
  background-color: #f0f9ff;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid #bae6fd;
}

.league-info h3 {
  color: #1e40af;
  margin-bottom: 20px;
}

.info-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
}

.info-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  border: 1px solid #e5e7eb;
  transition: all 0.2s ease;
  cursor: pointer;
}

.info-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.card-icon {
  font-size: 24px;
  margin-bottom: 10px;
}

.info-card h4 {
  color: #1f2937;
  margin: 10px 0 5px 0;
  font-size: 16px;
}

.info-card p {
  color: #3b82f6;
  font-weight: 600;
  margin: 0 0 5px 0;
}

.info-card small {
  color: #6b7280;
  font-size: 12px;
}

.fan-features {
  background-color: #ecfdf5;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid #a7f3d0;
}

.fan-features h3 {
  color: #047857;
  margin-bottom: 20px;
}

.features-grid {
  display: grid;
  gap: 15px;
}

.feature-item {
  display: flex;
  align-items: center;
  background: white;
  padding: 15px;
  border-radius: 8px;
  border: 1px solid #d1fae5;
}

.feature-icon {
  font-size: 24px;
  margin-right: 15px;
}

.feature-text h4 {
  color: #1f2937;
  margin: 0 0 5px 0;
  font-size: 16px;
}

.feature-text p {
  color: #6b7280;
  margin: 0;
  font-size: 14px;
}

.no-team-section {
  background-color: #f9fafb;
  padding: 30px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  text-align: center;
}

.no-team-message h3 {
  color: #1f2937;
  margin-bottom: 15px;
}

.no-team-message p {
  color: #6b7280;
  margin-bottom: 20px;
}

.fan-benefits {
  background: white;
  padding: 20px;
  border-radius: 6px;
  text-align: left;
}

.fan-benefits h4 {
  color: #374151;
  margin-bottom: 10px;
}

.fan-benefits ul {
  color: #374151;
  margin: 0 0 0 20px;
}

.fan-benefits li {
  margin-bottom: 5px;
}
</style>
