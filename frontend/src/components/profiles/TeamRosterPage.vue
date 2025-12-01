<template>
  <div class="team-roster-page">
    <!-- Loading state -->
    <div v-if="loading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>Loading team roster...</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="error-container">
      <div class="error-icon">!</div>
      <p>{{ error }}</p>
      <button @click="fetchTeamPlayers" class="retry-button">Try Again</button>
    </div>

    <!-- Content -->
    <template v-else>
      <!-- Team header card -->
      <div class="team-header-card" :style="teamHeaderStyle">
        <div class="team-header-content">
          <!-- Club logo or placeholder -->
          <div class="club-logo-container">
            <img
              v-if="team?.club?.logo_url"
              :src="team.club.logo_url"
              :alt="team.club.name"
              class="club-logo"
            />
            <div
              v-else
              class="club-logo-placeholder"
              :style="logoPlaceholderStyle"
            >
              <span>{{ clubInitials }}</span>
            </div>
          </div>

          <!-- Team info -->
          <div class="team-info-container">
            <h1 class="team-name">{{ teamName }}</h1>
            <p class="club-name" v-if="team?.club?.name">
              {{ team.club.name }}
            </p>
            <p class="team-location" v-if="team?.city">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                class="location-icon"
              >
                <path
                  fill-rule="evenodd"
                  d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z"
                  clip-rule="evenodd"
                />
              </svg>
              {{ team.city }}
            </p>
          </div>
        </div>

        <!-- Team badges -->
        <div class="team-badges">
          <!-- Age Group badge -->
          <span v-if="team?.age_group?.name" class="badge age-group-badge">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              class="badge-icon"
            >
              <path
                d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z"
              />
            </svg>
            {{ team.age_group.name }}
          </span>
          <!-- Academy badge -->
          <span v-if="team?.academy_team" class="badge academy-badge">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              class="badge-icon"
            >
              <path
                d="M10.394 2.08a1 1 0 00-.788 0l-7 3a1 1 0 000 1.84L5.25 8.051a.999.999 0 01.356-.257l4-1.714a1 1 0 11.788 1.838L7.667 9.088l1.94.831a1 1 0 00.787 0l7-3a1 1 0 000-1.838l-7-3zM3.31 9.397L5 10.12v4.102a8.969 8.969 0 00-1.05-.174 1 1 0 01-.89-.89 11.115 11.115 0 01.25-3.762zM9.3 16.573A9.026 9.026 0 007 14.935v-3.957l1.818.78a3 3 0 002.364 0l5.508-2.361a11.026 11.026 0 01.25 3.762 1 1 0 01-.89.89 8.968 8.968 0 00-5.35 2.524 1 1 0 01-1.4 0zM6 18a1 1 0 001-1v-2.065a8.935 8.935 0 00-2-.712V17a1 1 0 001 1z"
              />
            </svg>
            Academy
          </span>
          <!-- Division badge -->
          <span v-if="team?.division?.name" class="badge division-badge">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              class="badge-icon"
            >
              <path
                fill-rule="evenodd"
                d="M3 6a3 3 0 013-3h10a1 1 0 01.8 1.6L14.25 8l2.55 3.4A1 1 0 0116 13H6a1 1 0 00-1 1v3a1 1 0 11-2 0V6z"
                clip-rule="evenodd"
              />
            </svg>
            {{ team.division.name }}
          </span>
        </div>

        <!-- Player count -->
        <div class="roster-count">
          <span class="count-number">{{ playerCount }}</span>
          <span class="count-label"
            >Player{{ playerCount !== 1 ? 's' : '' }}</span
          >
        </div>
      </div>

      <!-- Empty state -->
      <div v-if="players.length === 0" class="empty-state">
        <div class="empty-icon">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.5"
              d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
            />
          </svg>
        </div>
        <p>No teammates yet</p>
        <p class="empty-subtext">
          Players will appear here when they join your team
        </p>
      </div>

      <!-- Player grid -->
      <div v-else class="player-grid">
        <PlayerCard
          v-for="player in players"
          :key="player.id"
          :player="player"
          :clubColor="team?.club?.primary_color"
          :overlayPrimaryColor="team?.club?.primary_color"
          :overlayTextColor="'#FFFFFF'"
          :overlayAccentColor="team?.club?.secondary_color"
          :overlayStyleOverride="'badge'"
          @click="handlePlayerClick"
        />
      </div>
    </template>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import PlayerCard from './PlayerCard.vue';

export default {
  name: 'TeamRosterPage',
  components: {
    PlayerCard,
  },
  emits: ['viewPlayer'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const loading = ref(true);
    const error = ref(null);
    const team = ref(null);
    const players = ref([]);

    // Get team name
    const teamName = computed(() => {
      if (team.value?.name) {
        return team.value.name;
      }
      // Fallback to user's team from auth store
      return authStore.state.profile?.team?.name || 'My Team';
    });

    // Player count
    const playerCount = computed(() => players.value.length);

    // Club initials for placeholder logo
    const clubInitials = computed(() => {
      const clubName = team.value?.club?.name || team.value?.name || '';
      return clubName
        .split(' ')
        .map(word => word[0])
        .join('')
        .substring(0, 2)
        .toUpperCase();
    });

    // Dynamic header style using club colors
    const teamHeaderStyle = computed(() => {
      const primaryColor = team.value?.club?.primary_color || '#1E3A8A';
      const secondaryColor = team.value?.club?.secondary_color || '#3B82F6';
      return {
        background: `linear-gradient(135deg, ${primaryColor} 0%, ${secondaryColor} 100%)`,
      };
    });

    // Logo placeholder style
    const logoPlaceholderStyle = computed(() => {
      const primaryColor = team.value?.club?.primary_color || '#1E3A8A';
      return {
        backgroundColor: '#ffffff',
        color: primaryColor,
      };
    });

    // Fetch team players from API
    const fetchTeamPlayers = async () => {
      loading.value = true;
      error.value = null;

      try {
        // Get user's team_id from auth store
        const teamId = authStore.state.profile?.team_id;
        if (!teamId) {
          error.value = 'You are not assigned to a team';
          loading.value = false;
          return;
        }

        const token = localStorage.getItem('auth_token');
        const response = await fetch(
          `${getApiBaseUrl()}/api/teams/${teamId}/players`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          }
        );

        if (!response.ok) {
          if (response.status === 403) {
            error.value = 'You can only view your own team roster';
          } else if (response.status === 404) {
            error.value = 'Team not found';
          } else {
            error.value = 'Failed to load team roster';
          }
          loading.value = false;
          return;
        }

        const data = await response.json();
        if (data.success) {
          team.value = data.team;
          players.value = data.players || [];
        } else {
          error.value = 'Failed to load team roster';
        }
      } catch (err) {
        console.error('Error fetching team players:', err);
        error.value = 'Unable to connect to server';
      } finally {
        loading.value = false;
      }
    };

    // Handle player card click
    const handlePlayerClick = player => {
      emit('viewPlayer', player);
    };

    onMounted(() => {
      fetchTeamPlayers();
    });

    return {
      loading,
      error,
      team,
      players,
      teamName,
      playerCount,
      clubInitials,
      teamHeaderStyle,
      logoPlaceholderStyle,
      fetchTeamPlayers,
      handlePlayerClick,
    };
  },
};
</script>

<style scoped>
.team-roster-page {
  padding: 16px;
  max-width: 1200px;
  margin: 0 auto;
}

/* Loading state */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 16px;
  color: #6b7280;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Error state */
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 16px;
  text-align: center;
}

.error-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background-color: #fee2e2;
  color: #ef4444;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 16px;
}

.error-container p {
  color: #6b7280;
  margin-bottom: 16px;
}

.retry-button {
  padding: 10px 20px;
  background-color: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  min-height: 44px;
  transition: background-color 0.15s ease;
}

.retry-button:hover {
  background-color: #2563eb;
}

/* Team header card */
.team-header-card {
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
  color: white;
  position: relative;
  overflow: hidden;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
}

.team-header-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
  pointer-events: none;
}

.team-header-content {
  display: flex;
  align-items: center;
  gap: 20px;
  position: relative;
  z-index: 1;
}

.club-logo-container {
  flex-shrink: 0;
}

.club-logo {
  width: 100px;
  height: 100px;
  border-radius: 16px;
  object-fit: cover;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.club-logo-placeholder {
  width: 100px;
  height: 100px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 800;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.team-info-container {
  flex: 1;
  min-width: 0;
}

.team-name {
  font-size: 28px;
  font-weight: 800;
  margin: 0 0 4px 0;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  line-height: 1.2;
}

.club-name {
  font-size: 16px;
  font-weight: 500;
  margin: 0 0 8px 0;
  opacity: 0.9;
}

.team-location {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  margin: 0;
  opacity: 0.85;
}

.location-icon {
  width: 16px;
  height: 16px;
}

/* Badges */
.team-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
  position: relative;
  z-index: 1;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(4px);
}

.badge-icon {
  width: 14px;
  height: 14px;
}

/* Player count */
.roster-count {
  position: absolute;
  top: 20px;
  right: 20px;
  text-align: center;
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(4px);
  padding: 12px 16px;
  border-radius: 12px;
}

.count-number {
  display: block;
  font-size: 32px;
  font-weight: 800;
  line-height: 1;
}

.count-label {
  display: block;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  opacity: 0.9;
  margin-top: 4px;
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 16px;
  text-align: center;
  color: #6b7280;
}

.empty-icon {
  width: 64px;
  height: 64px;
  background-color: #f3f4f6;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.empty-icon svg {
  width: 32px;
  height: 32px;
  color: #9ca3af;
}

.empty-state p {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: #4b5563;
}

.empty-subtext {
  font-size: 14px !important;
  font-weight: 400 !important;
  color: #9ca3af !important;
  margin-top: 8px !important;
}

/* Player grid - responsive */
.player-grid {
  display: grid;
  gap: 16px;
  /* Mobile-first: 2 columns */
  grid-template-columns: repeat(2, 1fr);
}

/* Tablet: 3 columns */
@media (min-width: 640px) {
  .player-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
  }
}

/* Desktop: 4 columns */
@media (min-width: 1024px) {
  .player-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: 24px;
  }

  .team-roster-page {
    padding: 24px;
  }
}

/* Large desktop: 5 columns */
@media (min-width: 1280px) {
  .player-grid {
    grid-template-columns: repeat(5, 1fr);
  }
}

/* Mobile adjustments */
@media (max-width: 480px) {
  .team-roster-page {
    padding: 12px;
  }

  .team-header-card {
    padding: 16px;
    border-radius: 12px;
  }

  .team-header-content {
    gap: 12px;
  }

  .club-logo,
  .club-logo-placeholder {
    width: 70px;
    height: 70px;
    font-size: 24px;
  }

  .team-name {
    font-size: 20px;
  }

  .club-name {
    font-size: 14px;
  }

  .team-location {
    font-size: 12px;
  }

  .roster-count {
    top: 12px;
    right: 12px;
    padding: 8px 12px;
  }

  .count-number {
    font-size: 24px;
  }

  .count-label {
    font-size: 10px;
  }

  .badge {
    padding: 4px 10px;
    font-size: 11px;
  }

  .player-grid {
    gap: 12px;
  }
}
</style>
