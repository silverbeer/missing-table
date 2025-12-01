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
        <button type="button" class="edit-photo-btn" @click="showEditor = true">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fill-rule="evenodd"
              d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z"
              clip-rule="evenodd"
            />
          </svg>
          Customize Photo
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
      <div
        v-if="authStore.state.profile.team?.age_group?.name"
        class="info-group"
      >
        <label>Age Group:</label>
        <span class="age-group-badge">{{
          authStore.state.profile.team.age_group.name
        }}</span>
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
        <div v-if="parsedPositions.length > 0" class="positions-display">
          <span
            v-for="position in parsedPositions"
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

      <!-- Social Media Section -->
      <div v-if="hasSocialMedia" class="social-media-section">
        <label>Social Media:</label>
        <div class="social-links-display">
          <a
            v-if="authStore.state.profile.instagram_handle"
            :href="`https://instagram.com/${authStore.state.profile.instagram_handle}`"
            target="_blank"
            rel="noopener noreferrer"
            class="social-link-badge instagram"
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path
                d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"
              />
            </svg>
            <span>@{{ authStore.state.profile.instagram_handle }}</span>
          </a>
          <a
            v-if="authStore.state.profile.snapchat_handle"
            :href="`https://snapchat.com/add/${authStore.state.profile.snapchat_handle}`"
            target="_blank"
            rel="noopener noreferrer"
            class="social-link-badge snapchat"
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path
                d="M12.166 2c1.34.006 2.613.139 3.49.476.96.369 1.715.984 2.285 1.794.548.779.86 1.728.98 2.979.066.69.068 1.43.068 2.21v.242c.002.4.004.775.038 1.172.043.498.13.805.286 1.048.13.203.342.395.749.584.16.074.33.143.52.22l.18.073c.5.2.87.37 1.138.557.404.28.567.563.567.813s-.163.533-.567.813c-.268.187-.638.357-1.138.557l-.18.073c-.19.077-.36.146-.52.22-.407.189-.619.381-.749.584-.156.243-.243.55-.286 1.048-.034.397-.036.772-.038 1.172v.242c0 .78-.002 1.52-.068 2.21-.12 1.251-.432 2.2-.98 2.979-.57.81-1.325 1.425-2.285 1.794-.877.337-2.15.47-3.49.476h-.332c-1.34-.006-2.613-.139-3.49-.476-.96-.369-1.715-.984-2.285-1.794-.548-.779-.86-1.728-.98-2.979-.066-.69-.068-1.43-.068-2.21v-.242c-.002-.4-.004-.775-.038-1.172-.043-.498-.13-.805-.286-1.048-.13-.203-.342-.395-.749-.584-.16-.074-.33-.143-.52-.22l-.18-.073c-.5-.2-.87-.37-1.138-.557-.404-.28-.567-.563-.567-.813s.163-.533.567-.813c.268-.187.638-.357 1.138-.557l.18-.073c.19-.077.36-.146.52-.22.407-.189.619-.381.749-.584.156-.243.243-.55.286-1.048.034-.397.036-.772.038-1.172v-.242c0-.78.002-1.52.068-2.21.12-1.251.432-2.2.98-2.979.57-.81 1.325-1.425 2.285-1.794.877-.337 2.15-.47 3.49-.476z"
              />
            </svg>
            <span>@{{ authStore.state.profile.snapchat_handle }}</span>
          </a>
          <a
            v-if="authStore.state.profile.tiktok_handle"
            :href="`https://tiktok.com/@${authStore.state.profile.tiktok_handle}`"
            target="_blank"
            rel="noopener noreferrer"
            class="social-link-badge tiktok"
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path
                d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 5 20.1a6.34 6.34 0 0 0 10.86-4.43v-7a8.16 8.16 0 0 0 4.77 1.52v-3.4a4.85 4.85 0 0 1-1-.1z"
              />
            </svg>
            <span>@{{ authStore.state.profile.tiktok_handle }}</span>
          </a>
        </div>
      </div>
    </template>

    <template #profile-sections>
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
    const teamGames = ref([]);
    const teammates = ref([]);
    const activeTab = ref('upcoming');
    const loadingGames = ref(false);
    const loadingTeammates = ref(false);
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

    // Parse positions (may be JSON string or array)
    const parsedPositions = computed(() => {
      const positions = authStore.state.profile?.positions;
      if (!positions) return [];
      if (Array.isArray(positions)) return positions;
      if (typeof positions === 'string') {
        try {
          const parsed = JSON.parse(positions);
          return Array.isArray(parsed) ? parsed : [];
        } catch {
          return [];
        }
      }
      return [];
    });

    // Primary position for overlay display
    const primaryPosition = computed(() => {
      return parsedPositions.value.length > 0 ? parsedPositions.value[0] : null;
    });

    // Check if player has any social media handles
    const hasSocialMedia = computed(() => {
      const profile = authStore.state.profile;
      return (
        profile?.instagram_handle ||
        profile?.snapchat_handle ||
        profile?.tiktok_handle
      );
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

    const fetchTeamGames = async () => {
      const teamId = authStore.state.profile?.team?.id;
      if (!teamId) return;

      try {
        loadingGames.value = true;
        const games = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/matches/team/${teamId}`,
          { method: 'GET' }
        );
        teamGames.value = games;
      } catch (error) {
        console.error('Error fetching team games:', error);
      } finally {
        loadingGames.value = false;
      }
    };

    const fetchTeammates = async () => {
      const teamId = authStore.state.profile?.team?.id;
      if (!teamId) return;

      // Only admins and team managers can list all users
      const role = authStore.state.profile?.role;
      if (role !== 'admin' && role !== 'team-manager') {
        // Players can't view teammates list (would need a dedicated endpoint)
        return;
      }

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
      // Component initialization - team games loaded via watch
    });

    return {
      authStore,
      teamGames,
      teammates,
      activeTab,
      loadingGames,
      loadingTeammates,
      showEditor,
      profilePhotoUrl,
      primaryPosition,
      parsedPositions,
      hasSocialMedia,
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

.age-group-badge {
  background-color: #8b5cf6;
  color: white;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 14px;
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

.edit-photo-btn {
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

.edit-photo-btn:hover {
  background-color: #2563eb;
}

.edit-photo-btn svg {
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

/* Social Media Section */
.social-media-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.social-media-section label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.social-links-display {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.social-link-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 24px;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;
  min-height: 44px;
}

.social-link-badge:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.social-link-badge svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.social-link-badge.instagram {
  background: linear-gradient(
    45deg,
    #f09433,
    #e6683c,
    #dc2743,
    #cc2366,
    #bc1888
  );
  color: white;
}

.social-link-badge.snapchat {
  background: #fffc00;
  color: #000000;
}

.social-link-badge.tiktok {
  background: #000000;
  color: white;
}

@media (max-width: 480px) {
  .social-links-display {
    flex-direction: column;
  }

  .social-link-badge {
    justify-content: center;
  }
}
</style>
