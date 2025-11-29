<template>
  <!-- Profile Editor Modal -->
  <div v-if="showEditor" class="editor-modal">
    <div class="editor-modal-content">
      <PlayerProfileEditor
        @close="showEditor = false"
        @saved="showEditor = false"
      />
    </div>
  </div>

  <BaseProfile title="Player Dashboard" @logout="$emit('logout')">
    <template #profile-fields>
      <!-- Profile Photo Preview -->
      <div class="profile-photo-section">
        <PlayerPhotoOverlay
          :photo-url="profilePhotoUrl"
          :number="authStore.state.profile.player_number"
          :position="primaryPosition"
          :overlay-style="authStore.state.profile.overlay_style || 'badge'"
          :primary-color="authStore.state.profile.primary_color || '#3B82F6'"
          :text-color="authStore.state.profile.text_color || '#FFFFFF'"
          :accent-color="authStore.state.profile.accent_color || '#1D4ED8'"
          class="profile-photo-preview"
        />
        <button
          type="button"
          class="edit-profile-btn"
          @click="showEditor = true"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"
            />
          </svg>
          Edit Profile
        </button>
      </div>

      <div v-if="authStore.state.profile.team" class="info-group">
        <label>Team:</label>
        <span class="team-name"
          >{{ authStore.state.profile.team.name }} ({{
            authStore.state.profile.team.city
          }})</span
        >
      </div>
      <div v-else class="info-group">
        <label>Team Assignment:</label>
        <span class="no-team">Not assigned to a team</span>
      </div>
      <div class="info-group">
        <label>Player Number:</label>
        <span
          v-if="authStore.state.profile.player_number"
          class="player-number"
        >
          #{{ authStore.state.profile.player_number }}
        </span>
        <span v-else class="no-number">Not assigned</span>
      </div>
      <div class="info-group">
        <label>Positions:</label>
        <div
          v-if="
            authStore.state.profile.positions &&
            authStore.state.profile.positions.length > 0
          "
          class="positions-display"
        >
          <span
            v-for="position in authStore.state.profile.positions"
            :key="position"
            class="position-badge"
          >
            {{ position }}
          </span>
        </div>
        <span v-else class="no-positions">No positions set</span>
      </div>
      <div class="info-group">
        <label>Player Status:</label>
        <span class="player-status active">Active Player</span>
      </div>
    </template>

    <template #profile-sections="{ isEditing, editForm }">
      <!-- Player Information Editing -->
      <div v-if="isEditing" class="player-edit-section">
        <h3>Player Information</h3>

        <!-- Team Selection -->
        <div class="form-group">
          <label for="teamSelect">Team Assignment:</label>
          <select
            id="teamSelect"
            v-model="editForm.team_id"
            class="form-select"
          >
            <option value="">No team</option>
            <option v-for="team in teams" :key="team.id" :value="team.id">
              {{ team.name }} ({{ team.city }})
            </option>
          </select>
          <p class="form-note">Team assignment requires manager approval</p>
        </div>

        <!-- Player Number -->
        <div class="form-group">
          <label for="playerNumber">Player Number:</label>
          <input
            id="playerNumber"
            v-model.number="editForm.player_number"
            type="number"
            min="1"
            max="99"
            class="form-input"
            placeholder="Enter jersey number"
          />
          <p class="form-note">Choose a unique number for your team</p>
        </div>

        <!-- Positions -->
        <div class="form-group">
          <label>Playing Positions:</label>
          <div v-if="loadingPositions" class="loading">
            Loading positions...
          </div>
          <div v-else class="positions-selector">
            <div class="positions-grid">
              <label
                v-for="position in availablePositions"
                :key="position.abbreviation"
                class="position-option"
              >
                <input
                  type="checkbox"
                  :value="position.abbreviation"
                  v-model="editForm.positions"
                  class="position-checkbox"
                />
                <span class="position-label">
                  <strong>{{ position.abbreviation }}</strong>
                  <small>{{ position.full_name }}</small>
                </span>
              </label>
            </div>
          </div>
          <p class="form-note">Select all positions you can play</p>
        </div>
      </div>

      <!-- My Games Section -->
      <div v-if="authStore.state.profile.team" class="my-games">
        <h3>My Games</h3>
        <div class="games-tabs">
          <button
            @click="activeTab = 'upcoming'"
            :class="{ active: activeTab === 'upcoming' }"
            class="tab-btn"
          >
            Upcoming Games ({{ upcomingGames.length }})
          </button>
          <button
            @click="activeTab = 'played'"
            :class="{ active: activeTab === 'played' }"
            class="tab-btn"
          >
            Played Games ({{ playedGames.length }})
          </button>
        </div>

        <div v-if="loadingGames" class="loading">Loading games...</div>

        <div v-else-if="activeTab === 'upcoming'" class="games-section">
          <div v-if="upcomingGames.length === 0" class="no-games">
            No upcoming games scheduled
          </div>
          <div v-else class="games-list">
            <div
              v-for="game in upcomingGames"
              :key="game.id"
              class="game-card upcoming"
            >
              <div class="game-header">
                <div class="game-date">
                  {{ formatGameDate(game.game_date) }}
                </div>
                <div class="game-type">{{ game.game_type_name }}</div>
              </div>
              <div class="game-matchup">
                <div class="team-info">
                  <span
                    class="team-name"
                    :class="{ 'my-team': isMyTeam(game.home_team_id) }"
                  >
                    {{ game.home_team_name }}
                  </span>
                  <span
                    class="home-indicator"
                    v-if="isMyTeam(game.home_team_id)"
                    >HOME</span
                  >
                </div>
                <div class="vs">VS</div>
                <div class="team-info">
                  <span
                    class="team-name"
                    :class="{ 'my-team': isMyTeam(game.away_team_id) }"
                  >
                    {{ game.away_team_name }}
                  </span>
                  <span
                    class="away-indicator"
                    v-if="isMyTeam(game.away_team_id)"
                    >AWAY</span
                  >
                </div>
              </div>
              <div class="game-status">
                <span class="scheduled">⏰ Scheduled</span>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'played'" class="games-section">
          <div v-if="playedGames.length === 0" class="no-games">
            No games played yet
          </div>
          <div v-else class="games-list">
            <div
              v-for="game in playedGames"
              :key="game.id"
              class="game-card played"
            >
              <div class="game-header">
                <div class="game-date">
                  {{ formatGameDate(game.game_date) }}
                </div>
                <div class="game-type">{{ game.game_type_name }}</div>
              </div>
              <div class="game-matchup">
                <div class="team-score">
                  <span
                    class="team-name"
                    :class="{ 'my-team': isMyTeam(game.home_team_id) }"
                  >
                    {{ game.home_team_name }}
                  </span>
                  <span class="score">{{ game.home_score }}</span>
                </div>
                <div class="vs">-</div>
                <div class="team-score">
                  <span class="score">{{ game.away_score }}</span>
                  <span
                    class="team-name"
                    :class="{ 'my-team': isMyTeam(game.away_team_id) }"
                  >
                    {{ game.away_team_name }}
                  </span>
                </div>
              </div>
              <div class="game-result">
                <span :class="getResultClass(game)">{{
                  getGameResult(game)
                }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Player Statistics -->
      <div v-if="authStore.state.profile.team" class="player-stats">
        <h3>Season Statistics</h3>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-number">{{ totalGames }}</div>
            <div class="stat-label">Games Played</div>
          </div>
          <div class="stat-card">
            <div class="stat-number">{{ wins }}</div>
            <div class="stat-label">Wins</div>
          </div>
          <div class="stat-card">
            <div class="stat-number">{{ draws }}</div>
            <div class="stat-label">Draws</div>
          </div>
          <div class="stat-card">
            <div class="stat-number">{{ losses }}</div>
            <div class="stat-label">Losses</div>
          </div>
          <div class="stat-card">
            <div class="stat-number">{{ winPercentage }}%</div>
            <div class="stat-label">Win Rate</div>
          </div>
          <div class="stat-card">
            <div class="stat-number">{{ goalsFor }}</div>
            <div class="stat-label">Goals For</div>
          </div>
        </div>
      </div>

      <!-- Teammates Section -->
      <div v-if="authStore.state.profile.team" class="teammates">
        <h3>My Teammates</h3>
        <div v-if="loadingTeammates" class="loading">Loading teammates...</div>
        <div v-else class="teammates-grid">
          <div
            v-for="teammate in teammates"
            :key="teammate.id"
            class="teammate-card"
          >
            <div class="teammate-avatar">
              {{ getInitials(teammate.display_name || teammate.email) }}
            </div>
            <div class="teammate-info">
              <h4>{{ teammate.display_name || 'No name' }}</h4>
              <p class="teammate-role">{{ formatRole(teammate.role) }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- No Team Section -->
      <div v-if="!authStore.state.profile.team" class="no-team-section">
        <div class="no-team-message">
          <h3>Join a Team</h3>
          <p>
            You're not currently assigned to a team. Contact a team manager or
            administrator to join a team and start playing!
          </p>
          <div class="join-benefits">
            <h4>Benefits of joining a team:</h4>
            <ul>
              <li>View your game schedule and results</li>
              <li>Track your playing statistics</li>
              <li>Connect with teammates</li>
              <li>Receive team updates and announcements</li>
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
import PlayerPhotoOverlay from './PlayerPhotoOverlay.vue';
import PlayerProfileEditor from './PlayerProfileEditor.vue';
import { getApiBaseUrl } from '../../config/api';

export default {
  name: 'PlayerProfile',
  components: {
    BaseProfile,
    PlayerPhotoOverlay,
    PlayerProfileEditor,
  },
  emits: ['logout'],
  setup() {
    const authStore = useAuthStore();
    const teams = ref([]);
    const teamGames = ref([]);
    const teammates = ref([]);
    const availablePositions = ref([]);
    const activeTab = ref('upcoming');
    const loadingGames = ref(false);
    const loadingTeammates = ref(false);
    const loadingPositions = ref(false);
    const showEditor = ref(false);

    // Profile photo URL - use profile photo slot or first available
    const profilePhotoUrl = computed(() => {
      const profile = authStore.state.profile;
      if (!profile) return null;
      const slot = profile.profile_photo_slot;
      if (slot && profile[`photo_${slot}_url`]) {
        return profile[`photo_${slot}_url`];
      }
      // Fall back to first available photo
      for (let i = 1; i <= 3; i++) {
        if (profile[`photo_${i}_url`]) {
          return profile[`photo_${i}_url`];
        }
      }
      return null;
    });

    // Primary position for overlay display
    const primaryPosition = computed(() => {
      const positions = authStore.state.profile?.positions;
      return positions && positions.length > 0 ? positions[0] : null;
    });

    const upcomingGames = computed(() => {
      const now = new Date();
      return teamGames.value.filter(
        game => new Date(game.game_date) > now || game.home_score === null
      );
    });

    const playedGames = computed(() => {
      return teamGames.value.filter(game => game.home_score !== null);
    });

    const totalGames = computed(() => playedGames.value.length);

    const wins = computed(() => {
      return playedGames.value.filter(game => {
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
      return playedGames.value.filter(
        game => game.home_score === game.away_score
      ).length;
    });

    const losses = computed(() => {
      return playedGames.value.filter(game => {
        const teamId = authStore.state.profile?.team?.id;
        if (!teamId) return false;

        if (game.home_team_id === teamId) {
          return game.home_score < game.away_score;
        } else {
          return game.away_score < game.home_score;
        }
      }).length;
    });

    const winPercentage = computed(() => {
      if (totalGames.value === 0) return 0;
      return Math.round((wins.value / totalGames.value) * 100);
    });

    const goalsFor = computed(() => {
      const teamId = authStore.state.profile?.team?.id;
      if (!teamId) return 0;

      return playedGames.value.reduce((total, game) => {
        if (game.home_team_id === teamId) {
          return total + game.home_score;
        } else {
          return total + game.away_score;
        }
      }, 0);
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

    const fetchPositions = async () => {
      try {
        loadingPositions.value = true;
        const response = await fetch(`${getApiBaseUrl()}/api/positions`);
        if (response.ok) {
          availablePositions.value = await response.json();
        }
      } catch (error) {
        console.error('Error fetching positions:', error);
      } finally {
        loadingPositions.value = false;
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

    const fetchTeammates = async () => {
      const teamId = authStore.state.profile?.team?.id;
      if (!teamId) return;

      try {
        loadingTeammates.value = true;
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/auth/users`
        );
        teammates.value = response.filter(
          user =>
            user.team_id === teamId &&
            user.id !== authStore.state.user?.id &&
            (user.role === 'team-player' || user.role === 'team-manager')
        );
      } catch (error) {
        console.error('Error fetching teammates:', error);
      } finally {
        loadingTeammates.value = false;
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
        hour: '2-digit',
        minute: '2-digit',
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

      if (myScore > opponentScore) return 'WIN';
      if (myScore < opponentScore) return 'LOSS';
      return 'DRAW';
    };

    const getResultClass = game => {
      const result = getGameResult(game);
      return {
        'result-win': result === 'WIN',
        'result-loss': result === 'LOSS',
        'result-draw': result === 'DRAW',
      };
    };

    const formatRole = role => {
      const roleMap = {
        'team-manager': 'Team Manager',
        'team-player': 'Player',
      };
      return roleMap[role] || role;
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
          await Promise.all([fetchTeamGames(), fetchTeammates()]);
        }
      },
      { immediate: true }
    );

    onMounted(() => {
      fetchTeams();
      fetchPositions();
    });

    return {
      authStore,
      teams,
      teamGames,
      teammates,
      availablePositions,
      activeTab,
      loadingGames,
      loadingTeammates,
      loadingPositions,
      showEditor,
      profilePhotoUrl,
      primaryPosition,
      upcomingGames,
      playedGames,
      totalGames,
      wins,
      draws,
      losses,
      winPercentage,
      goalsFor,
      isMyTeam,
      formatGameDate,
      getGameResult,
      getResultClass,
      formatRole,
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

.player-status.active {
  color: #059669;
  font-weight: 600;
}

.player-number {
  color: #3b82f6;
  font-weight: 700;
  font-size: 18px;
}

.no-number,
.no-positions {
  color: #6b7280;
  font-style: italic;
}

.positions-display {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.position-badge {
  background-color: #3b82f6;
  color: white;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
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

.my-games {
  background-color: #f8fafc;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.games-tabs {
  display: flex;
  margin-bottom: 20px;
  border-bottom: 1px solid #e5e7eb;
}

.tab-btn {
  background: none;
  border: none;
  padding: 12px 20px;
  cursor: pointer;
  font-size: 14px;
  color: #6b7280;
  border-bottom: 2px solid transparent;
  transition: all 0.2s ease;
}

.tab-btn.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
  font-weight: 600;
}

.tab-btn:hover {
  color: #3b82f6;
}

.games-list {
  display: grid;
  gap: 15px;
}

.game-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.game-card.upcoming {
  border-left: 4px solid #f59e0b;
}

.game-card.played {
  border-left: 4px solid #059669;
}

.game-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.game-date {
  font-weight: 600;
  color: #374151;
}

.game-type {
  background-color: #e5e7eb;
  color: #6b7280;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
}

.game-matchup {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 15px;
}

.team-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.team-score {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.team-name {
  font-weight: 500;
  color: #374151;
}

.team-name.my-team {
  color: #059669;
  font-weight: 700;
}

.home-indicator,
.away-indicator {
  font-size: 10px;
  background-color: #059669;
  color: white;
  padding: 2px 6px;
  border-radius: 10px;
  margin-top: 4px;
}

.vs {
  color: #6b7280;
  font-weight: 600;
  margin: 0 20px;
}

.score {
  font-size: 20px;
  font-weight: bold;
  color: #1f2937;
}

.game-status {
  text-align: center;
}

.scheduled {
  color: #f59e0b;
  font-size: 14px;
  font-weight: 500;
}

.game-result {
  text-align: center;
}

.result-win {
  color: #059669;
  font-weight: bold;
  background-color: #d1fae5;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
}

.result-loss {
  color: #dc2626;
  font-weight: bold;
  background-color: #fee2e2;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
}

.result-draw {
  color: #f59e0b;
  font-weight: bold;
  background-color: #fef3c7;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
}

.no-games {
  text-align: center;
  color: #6b7280;
  padding: 40px;
  font-style: italic;
}

.player-stats {
  background-color: #ecfdf5;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid #a7f3d0;
}

.player-stats h3 {
  color: #047857;
  margin-bottom: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 15px;
}

.stat-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  border: 1px solid #d1fae5;
}

.stat-number {
  font-size: 28px;
  font-weight: bold;
  color: #047857;
  margin-bottom: 8px;
}

.stat-label {
  color: #6b7280;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.teammates {
  background-color: #f0f9ff;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid #bae6fd;
}

.teammates h3 {
  color: #1e40af;
  margin-bottom: 20px;
}

.teammates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
}

.teammate-card {
  background: white;
  padding: 15px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
}

.teammate-avatar {
  width: 40px;
  height: 40px;
  background-color: #3b82f6;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  margin-right: 12px;
  font-size: 14px;
}

.teammate-info h4 {
  margin: 0 0 4px 0;
  color: #1f2937;
  font-size: 14px;
}

.teammate-role {
  color: #6b7280;
  font-size: 12px;
  margin: 0;
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

.join-benefits {
  background: white;
  padding: 20px;
  border-radius: 6px;
  text-align: left;
}

.join-benefits h4 {
  color: #374151;
  margin-bottom: 10px;
}

.join-benefits ul {
  color: #374151;
  margin: 0 0 0 20px;
}

.join-benefits li {
  margin-bottom: 5px;
}

/* Player Edit Form Styles */
.player-edit-section {
  background-color: #f0f9ff;
  padding: 25px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid #bae6fd;
}

.player-edit-section h3 {
  color: #1e40af;
  margin-bottom: 20px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  font-weight: 600;
  margin-bottom: 8px;
  color: #1e40af;
}

.form-select,
.form-input {
  width: 100%;
  padding: 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  background-color: white;
}

.form-select:focus,
.form-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-note {
  color: #6b7280;
  font-size: 12px;
  margin: 5px 0 0 0;
}

.positions-selector {
  margin-top: 10px;
}

.positions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
  max-height: 300px;
  overflow-y: auto;
  padding: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background-color: white;
}

.position-option {
  display: flex;
  align-items: center;
  padding: 8px;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.2s ease;
}

.position-option:hover {
  background-color: #f3f4f6;
}

.position-checkbox {
  margin-right: 10px;
  width: 16px;
  height: 16px;
}

.position-label {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.position-label strong {
  color: #1f2937;
  font-size: 14px;
}

.position-label small {
  color: #6b7280;
  font-size: 11px;
}

/* Profile Photo Section */
.profile-photo-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #e5e7eb;
}

.profile-photo-preview {
  width: 150px;
  height: 150px;
}

.edit-profile-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background-color: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.edit-profile-btn:hover {
  background-color: #2563eb;
}

.edit-profile-btn svg {
  width: 16px;
  height: 16px;
}

/* Editor Modal */
.editor-modal {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  z-index: 1000;
  overflow-y: auto;
  padding: 20px;
}

.editor-modal-content {
  width: 100%;
  max-width: 1000px;
  background-color: white;
  border-radius: 16px;
  margin: 40px 0;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    transform: translateY(-20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}
</style>
