<template>
  <BaseProfile title="Team Manager Dashboard" @logout="$emit('logout')">
    <template #profile-fields>
      <div v-if="authStore.state.profile.team" class="info-group">
        <label>Managing Team:</label>
        <span class="team-name"
          >{{ authStore.state.profile.team.name }} ({{
            authStore.state.profile.team.city
          }})</span
        >
      </div>
      <div v-else class="info-group">
        <label>Team Assignment:</label>
        <span class="no-team">No team assigned</span>
      </div>
    </template>

    <template #profile-sections>
      <!-- Team Selection -->
      <div v-if="isEditing" class="team-selection-section">
        <h3>Team Assignment</h3>
        <div class="team-selector">
          <label for="teamSelect">Select Team to Manage:</label>
          <select
            id="teamSelect"
            v-model="editForm.team_id"
            class="team-select"
          >
            <option value="">No team</option>
            <option v-for="team in teams" :key="team.id" :value="team.id">
              {{ team.name }} ({{ team.city }})
            </option>
          </select>
        </div>
      </div>

      <!-- Team Management Section -->
      <div v-if="authStore.state.profile.team" class="team-management">
        <h3>Team Management</h3>
        <div class="management-grid">
          <div class="management-card" @click="showPlayers = !showPlayers">
            <div class="card-icon">👥</div>
            <h4>Team Roster</h4>
            <p>Manage team players and lineup</p>
            <div class="card-stat">{{ playerCount }} players</div>
          </div>

          <div class="management-card" @click="showGames = !showGames">
            <div class="card-icon">⚽</div>
            <h4>Games & Schedule</h4>
            <p>View and manage team games</p>
            <div class="card-stat">{{ gameCount }} games</div>
          </div>

          <div class="management-card">
            <div class="card-icon">📊</div>
            <h4>Team Statistics</h4>
            <p>View team performance data</p>
            <div class="card-stat">Season stats</div>
          </div>

          <div class="management-card">
            <div class="card-icon">📅</div>
            <h4>Practice Schedule</h4>
            <p>Manage practice sessions</p>
            <div class="card-stat">Schedule training</div>
          </div>
        </div>
      </div>

      <!-- Players Section -->
      <div
        v-if="showPlayers && authStore.state.profile.team"
        class="players-section"
      >
        <div class="section-header">
          <h3>Team Roster</h3>
          <button @click="showPlayers = false" class="close-btn">×</button>
        </div>

        <div v-if="loadingPlayers" class="loading">Loading players...</div>
        <div v-else class="players-grid">
          <div
            v-for="player in teamPlayers"
            :key="player.id"
            class="player-card"
          >
            <div class="player-avatar">
              {{ getInitials(player.display_name || player.email) }}
            </div>
            <div class="player-details">
              <h4>{{ player.display_name || 'No name' }}</h4>
              <p class="player-email">{{ player.email }}</p>
              <span class="player-status active">Active Player</span>
            </div>
            <div class="player-actions">
              <button class="action-btn">Contact</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Games Section -->
      <div
        v-if="showGames && authStore.state.profile.team"
        class="games-section"
      >
        <div class="section-header">
          <h3>Team Games</h3>
          <button @click="showGames = false" class="close-btn">×</button>
        </div>

        <div v-if="loadingGames" class="loading">Loading games...</div>
        <div v-else class="games-list">
          <div v-for="game in teamGames" :key="game.id" class="game-card">
            <div class="game-date">
              {{ formatGameDate(game.game_date) }}
            </div>
            <div class="game-teams">
              <span class="team-name">{{ game.home_team_name }}</span>
              <span class="vs">vs</span>
              <span class="team-name">{{ game.away_team_name }}</span>
            </div>
            <div class="game-score">
              <span v-if="game.home_score !== null">
                {{ game.home_score }} - {{ game.away_score }}
              </span>
              <span v-else class="scheduled">Scheduled</span>
            </div>
            <div class="game-type">
              {{ game.game_type_name }}
            </div>
          </div>
        </div>
      </div>

      <!-- Team Quick Stats -->
      <div v-if="authStore.state.profile.team" class="team-stats">
        <h3>Quick Team Overview</h3>
        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-number">{{ teamGames.length }}</div>
            <div class="stat-label">Total Games</div>
          </div>
          <div class="stat-item">
            <div class="stat-number">{{ wins }}</div>
            <div class="stat-label">Wins</div>
          </div>
          <div class="stat-item">
            <div class="stat-number">{{ draws }}</div>
            <div class="stat-label">Draws</div>
          </div>
          <div class="stat-item">
            <div class="stat-number">{{ losses }}</div>
            <div class="stat-label">Losses</div>
          </div>
        </div>
      </div>

      <!-- No Team Assigned Message -->
      <div v-if="!authStore.state.profile.team" class="no-team-section">
        <div class="no-team-message">
          <h3>No Team Assigned</h3>
          <p>
            You haven't been assigned to manage a team yet. Contact an
            administrator to get assigned to a team.
          </p>
          <div class="contact-admin">
            <p>Once assigned, you'll be able to:</p>
            <ul>
              <li>Manage team roster and player information</li>
              <li>View and manage game schedules</li>
              <li>Access team statistics and performance data</li>
              <li>Coordinate practice sessions</li>
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

export default {
  name: 'TeamManagerProfile',
  components: {
    BaseProfile,
  },
  emits: ['logout'],
  setup() {
    const authStore = useAuthStore();
    const teams = ref([]);
    const teamPlayers = ref([]);
    const teamGames = ref([]);
    const showPlayers = ref(false);
    const showGames = ref(false);
    const loadingPlayers = ref(false);
    const loadingGames = ref(false);
    const isEditing = ref(false);

    const editForm = ref({
      team_id: null,
    });

    const playerCount = computed(() => teamPlayers.value.length);
    const gameCount = computed(() => teamGames.value.length);

    const wins = computed(() => {
      return teamGames.value.filter(game => {
        const teamId = authStore.state.profile?.team?.id;
        if (!teamId || game.home_score === null) return false;

        if (game.home_team_id === teamId) {
          return game.home_score > game.away_score;
        } else {
          return game.away_score > game.home_score;
        }
      }).length;
    });

    const draws = computed(() => {
      return teamGames.value.filter(game => {
        return game.home_score !== null && game.home_score === game.away_score;
      }).length;
    });

    const losses = computed(() => {
      return teamGames.value.filter(game => {
        const teamId = authStore.state.profile?.team?.id;
        if (!teamId || game.home_score === null) return false;

        if (game.home_team_id === teamId) {
          return game.home_score < game.away_score;
        } else {
          return game.away_score < game.home_score;
        }
      }).length;
    });

    const fetchTeams = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/teams');
        if (response.ok) {
          teams.value = await response.json();
        }
      } catch (error) {
        console.error('Error fetching teams:', error);
      }
    };

    const fetchTeamPlayers = async () => {
      const teamId = authStore.state.profile?.team?.id;
      if (!teamId) return;

      try {
        loadingPlayers.value = true;
        const response = await authStore.apiRequest(
          'http://localhost:8000/api/auth/users'
        );
        teamPlayers.value = response.filter(
          user => user.team_id === teamId && user.role === 'team-player'
        );
      } catch (error) {
        console.error('Error fetching team players:', error);
      } finally {
        loadingPlayers.value = false;
      }
    };

    const fetchTeamGames = async () => {
      const teamId = authStore.state.profile?.team?.id;
      if (!teamId) return;

      try {
        loadingGames.value = true;
        const response = await fetch(
          `http://localhost:8000/api/games/team/${teamId}`
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

    const formatGameDate = dateString => {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
      });
    };

    const getInitials = name => {
      if (!name) return '?';
      return name
        .split(' ')
        .map(n => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
    };

    // Watch for team changes
    watch(
      () => authStore.state.profile?.team,
      async newTeam => {
        if (newTeam) {
          await Promise.all([fetchTeamPlayers(), fetchTeamGames()]);
        }
      },
      { immediate: true }
    );

    onMounted(() => {
      fetchTeams();
    });

    return {
      authStore,
      teams,
      teamPlayers,
      teamGames,
      showPlayers,
      showGames,
      loadingPlayers,
      loadingGames,
      isEditing,
      editForm,
      playerCount,
      gameCount,
      wins,
      draws,
      losses,
      fetchTeamPlayers,
      fetchTeamGames,
      formatGameDate,
      getInitials,
    };
  },
};
</script>

<style scoped>
.team-name {
  color: #059669;
  font-weight: 600;
}

.no-team {
  color: #dc2626;
  font-style: italic;
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
}

.team-management {
  background-color: #f8fafc;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.management-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
}

.management-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: center;
}

.management-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border-color: #059669;
}

.card-icon {
  font-size: 24px;
  margin-bottom: 10px;
}

.management-card h4 {
  color: #1f2937;
  margin: 10px 0 5px 0;
  font-size: 16px;
}

.management-card p {
  color: #6b7280;
  font-size: 14px;
  margin: 0 0 10px 0;
}

.card-stat {
  color: #059669;
  font-weight: 600;
  font-size: 12px;
}

.players-section,
.games-section {
  background-color: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e5e7eb;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: #6b7280;
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  color: #dc2626;
}

.players-grid {
  padding: 20px;
  display: grid;
  gap: 15px;
}

.player-card {
  display: flex;
  align-items: center;
  padding: 15px;
  background-color: #f9fafb;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.player-avatar {
  width: 45px;
  height: 45px;
  background-color: #059669;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  margin-right: 15px;
}

.player-details {
  flex: 1;
}

.player-details h4 {
  margin: 0 0 5px 0;
  color: #1f2937;
}

.player-email {
  color: #6b7280;
  font-size: 14px;
  margin: 0 0 5px 0;
}

.player-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
  background-color: #d1fae5;
  color: #059669;
}

.action-btn {
  background-color: #059669;
  color: white;
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.games-list {
  padding: 20px;
}

.game-card {
  display: grid;
  grid-template-columns: 120px 1fr 120px 100px;
  gap: 15px;
  align-items: center;
  padding: 15px;
  background-color: #f9fafb;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  margin-bottom: 10px;
}

.game-date {
  font-weight: 600;
  color: #374151;
  font-size: 14px;
}

.game-teams {
  display: flex;
  align-items: center;
  gap: 10px;
}

.vs {
  color: #6b7280;
  font-size: 12px;
}

.game-score {
  text-align: center;
  font-weight: 600;
}

.scheduled {
  color: #f59e0b;
  font-size: 12px;
}

.game-type {
  text-align: center;
  font-size: 12px;
  color: #6b7280;
}

.team-stats {
  background-color: #ecfdf5;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #a7f3d0;
}

.team-stats h3 {
  color: #047857;
  margin-bottom: 15px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 15px;
}

.stat-item {
  text-align: center;
  background: white;
  padding: 15px;
  border-radius: 6px;
}

.stat-number {
  font-size: 24px;
  font-weight: bold;
  color: #047857;
  margin-bottom: 5px;
}

.stat-label {
  color: #6b7280;
  font-size: 12px;
  text-transform: uppercase;
}

.no-team-section {
  background-color: #fef2f2;
  padding: 30px;
  border-radius: 8px;
  border: 1px solid #fecaca;
  text-align: center;
}

.no-team-message h3 {
  color: #dc2626;
  margin-bottom: 15px;
}

.no-team-message p {
  color: #6b7280;
  margin-bottom: 20px;
}

.contact-admin {
  background: white;
  padding: 20px;
  border-radius: 6px;
  text-align: left;
}

.contact-admin ul {
  color: #374151;
  margin: 10px 0 0 20px;
}

.contact-admin li {
  margin-bottom: 5px;
}
</style>
