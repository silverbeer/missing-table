<template>
  <div class="player-detail-view">
    <!-- Back button -->
    <button @click="$emit('back')" class="back-button">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M15 19l-7-7 7-7"
        />
      </svg>
      <span>Back to Team</span>
    </button>

    <!-- Loading state -->
    <div v-if="loading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>Loading player profile...</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="error-container">
      <div class="error-icon">!</div>
      <p>{{ error }}</p>
      <button @click="fetchPlayerProfile" class="retry-button">
        Try Again
      </button>
    </div>

    <!-- Player profile content -->
    <div v-else-if="player" class="profile-content">
      <!-- Profile card -->
      <div class="profile-card">
        <!-- Photo section -->
        <div class="photo-section">
          <PlayerPhotoOverlay
            :photoUrl="profilePhotoUrl"
            :number="player.player_number"
            :position="primaryPosition"
            :overlayStyle="player.overlay_style || 'badge'"
            :primaryColor="player.primary_color || '#3B82F6'"
            :textColor="player.text_color || '#FFFFFF'"
            :accentColor="player.accent_color || '#1D4ED8'"
            :altText="`${player.display_name} profile photo`"
          />
        </div>

        <!-- Info section -->
        <div class="info-section">
          <h1 class="player-name">{{ player.display_name || 'Player' }}</h1>

          <div class="player-details">
            <div v-if="player.player_number" class="detail-item">
              <span class="detail-label">Number</span>
              <span class="detail-value">#{{ player.player_number }}</span>
            </div>
            <div v-if="positions" class="detail-item">
              <span class="detail-label"
                >Position{{ player.positions?.length > 1 ? 's' : '' }}</span
              >
              <span class="detail-value">{{ positions }}</span>
            </div>
            <div v-if="player.team?.name" class="detail-item">
              <span class="detail-label">Team</span>
              <span class="detail-value">{{ player.team.name }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Social media section -->
      <div v-if="hasSocialMedia" class="social-section">
        <h2 class="section-title">Social Media</h2>
        <div class="social-links">
          <a
            v-if="player.instagram_handle"
            :href="`https://instagram.com/${player.instagram_handle}`"
            target="_blank"
            rel="noopener noreferrer"
            class="social-link instagram"
          >
            <div class="social-icon">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path
                  d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"
                />
              </svg>
            </div>
            <div class="social-info">
              <span class="platform">Instagram</span>
              <span class="handle">@{{ player.instagram_handle }}</span>
            </div>
            <svg
              class="link-arrow"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5l7 7-7 7"
              />
            </svg>
          </a>

          <a
            v-if="player.snapchat_handle"
            :href="`https://snapchat.com/add/${player.snapchat_handle}`"
            target="_blank"
            rel="noopener noreferrer"
            class="social-link snapchat"
          >
            <div class="social-icon">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path
                  d="M12.166 2c1.34.006 2.613.139 3.49.476.96.369 1.715.984 2.285 1.794.548.779.86 1.728.98 2.979.066.69.068 1.43.068 2.21v.242c.002.4.004.775.038 1.172.043.498.13.805.286 1.048.13.203.342.395.749.584.16.074.33.143.52.22l.18.073c.5.2.87.37 1.138.557.404.28.567.563.567.813s-.163.533-.567.813c-.268.187-.638.357-1.138.557l-.18.073c-.19.077-.36.146-.52.22-.407.189-.619.381-.749.584-.156.243-.243.55-.286 1.048-.034.397-.036.772-.038 1.172v.242c0 .78-.002 1.52-.068 2.21-.12 1.251-.432 2.2-.98 2.979-.57.81-1.325 1.425-2.285 1.794-.877.337-2.15.47-3.49.476h-.332c-1.34-.006-2.613-.139-3.49-.476-.96-.369-1.715-.984-2.285-1.794-.548-.779-.86-1.728-.98-2.979-.066-.69-.068-1.43-.068-2.21v-.242c-.002-.4-.004-.775-.038-1.172-.043-.498-.13-.805-.286-1.048-.13-.203-.342-.395-.749-.584-.16-.074-.33-.143-.52-.22l-.18-.073c-.5-.2-.87-.37-1.138-.557-.404-.28-.567-.563-.567-.813s.163-.533.567-.813c.268-.187.638-.357 1.138-.557l.18-.073c.19-.077.36-.146.52-.22.407-.189.619-.381.749-.584.156-.243.243-.55.286-1.048.034-.397.036-.772.038-1.172v-.242c0-.78.002-1.52.068-2.21.12-1.251.432-2.2.98-2.979.57-.81 1.325-1.425 2.285-1.794.877-.337 2.15-.47 3.49-.476z"
                />
              </svg>
            </div>
            <div class="social-info">
              <span class="platform">Snapchat</span>
              <span class="handle">@{{ player.snapchat_handle }}</span>
            </div>
            <svg
              class="link-arrow"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5l7 7-7 7"
              />
            </svg>
          </a>

          <a
            v-if="player.tiktok_handle"
            :href="`https://tiktok.com/@${player.tiktok_handle}`"
            target="_blank"
            rel="noopener noreferrer"
            class="social-link tiktok"
          >
            <div class="social-icon">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path
                  d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 5 20.1a6.34 6.34 0 0 0 10.86-4.43v-7a8.16 8.16 0 0 0 4.77 1.52v-3.4a4.85 4.85 0 0 1-1-.1z"
                />
              </svg>
            </div>
            <div class="social-info">
              <span class="platform">TikTok</span>
              <span class="handle">@{{ player.tiktok_handle }}</span>
            </div>
            <svg
              class="link-arrow"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5l7 7-7 7"
              />
            </svg>
          </a>
        </div>
      </div>

      <!-- Recent games section -->
      <div v-if="recentGames && recentGames.length > 0" class="games-section">
        <h2 class="section-title">Recent Games</h2>
        <div class="games-list">
          <div v-for="game in recentGames" :key="game.id" class="game-item">
            <div class="game-date">{{ formatDate(game.match_date) }}</div>
            <div class="game-teams">
              <span class="team-name">{{
                game.home_team?.name || game.home_team_name || 'TBD'
              }}</span>
              <span
                class="game-score"
                :class="{ 'has-score': game.home_score !== null }"
              >
                {{ game.home_score ?? '-' }} - {{ game.away_score ?? '-' }}
              </span>
              <span class="team-name">{{
                game.away_team?.name || game.away_team_name || 'TBD'
              }}</span>
            </div>
            <div
              v-if="game.status"
              class="game-status"
              :class="game.status.toLowerCase()"
            >
              {{ game.status }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import PlayerPhotoOverlay from './PlayerPhotoOverlay.vue';

export default {
  name: 'PlayerDetailView',
  components: {
    PlayerPhotoOverlay,
  },
  props: {
    playerId: {
      type: String,
      required: true,
    },
  },
  emits: ['back'],
  setup(props) {
    const authStore = useAuthStore();
    const loading = ref(true);
    const error = ref(null);
    const player = ref(null);
    const recentGames = ref([]);

    // Get profile photo URL based on profile_photo_slot
    const profilePhotoUrl = computed(() => {
      if (!player.value) return null;
      const slot = player.value.profile_photo_slot || 1;
      return player.value[`photo_${slot}_url`] || null;
    });

    // Get primary position
    const primaryPosition = computed(() => {
      if (!player.value?.positions?.length) return null;
      return player.value.positions[0];
    });

    // Get formatted positions
    const positions = computed(() => {
      if (!player.value?.positions?.length) return null;
      return player.value.positions.join(', ');
    });

    // Check for social media
    const hasSocialMedia = computed(() => {
      return (
        player.value?.instagram_handle ||
        player.value?.snapchat_handle ||
        player.value?.tiktok_handle
      );
    });

    // Format date for display
    const formatDate = dateString => {
      if (!dateString) return '';
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    };

    // Fetch player profile
    const fetchPlayerProfile = async () => {
      loading.value = true;
      error.value = null;

      try {
        const response = await fetch(`/api/players/${props.playerId}/profile`, {
          headers: {
            Authorization: `Bearer ${authStore.accessToken}`,
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          if (response.status === 403) {
            error.value = 'You can only view profiles of your teammates';
          } else if (response.status === 404) {
            error.value = 'Player not found';
          } else {
            error.value = 'Failed to load player profile';
          }
          loading.value = false;
          return;
        }

        const data = await response.json();
        if (data.success) {
          player.value = data.player;
          recentGames.value = data.recent_games || [];
        } else {
          error.value = 'Failed to load player profile';
        }
      } catch (err) {
        console.error('Error fetching player profile:', err);
        error.value = 'Unable to connect to server';
      } finally {
        loading.value = false;
      }
    };

    // Watch for playerId changes
    watch(
      () => props.playerId,
      () => {
        fetchPlayerProfile();
      }
    );

    onMounted(() => {
      fetchPlayerProfile();
    });

    return {
      loading,
      error,
      player,
      recentGames,
      profilePhotoUrl,
      primaryPosition,
      positions,
      hasSocialMedia,
      formatDate,
      fetchPlayerProfile,
    };
  },
};
</script>

<style scoped>
.player-detail-view {
  padding: 16px;
  max-width: 600px;
  margin: 0 auto;
}

/* Back button */
.back-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: none;
  border: none;
  color: #3b82f6;
  font-weight: 500;
  font-size: 15px;
  cursor: pointer;
  margin-bottom: 16px;
  min-height: 44px;
  border-radius: 8px;
  transition: background-color 0.15s ease;
}

.back-button:hover {
  background-color: #eff6ff;
}

.back-button svg {
  width: 20px;
  height: 20px;
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

/* Profile card */
.profile-card {
  background: white;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;
}

.photo-section {
  width: 100%;
  max-width: 300px;
  margin: 0 auto;
  padding: 20px 20px 0;
}

.info-section {
  padding: 20px;
  text-align: center;
}

.player-name {
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 16px 0;
}

.player-details {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 16px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 20px;
  background-color: #f9fafb;
  border-radius: 12px;
  min-width: 100px;
}

.detail-label {
  font-size: 12px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.detail-value {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

/* Section titles */
.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 12px 0;
  padding: 0 4px;
}

/* Social media section */
.social-section {
  margin-bottom: 20px;
}

.social-links {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.social-link {
  display: flex;
  align-items: center;
  padding: 14px 16px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  text-decoration: none;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;
  min-height: 56px;
}

.social-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.social-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
}

.social-icon svg {
  width: 24px;
  height: 24px;
}

.social-link.instagram .social-icon {
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

.social-link.snapchat .social-icon {
  background: #fffc00;
  color: #000000;
}

.social-link.tiktok .social-icon {
  background: #000000;
  color: white;
}

.social-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.platform {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.handle {
  font-size: 13px;
  color: #6b7280;
}

.link-arrow {
  width: 20px;
  height: 20px;
  color: #9ca3af;
}

/* Games section */
.games-section {
  margin-bottom: 20px;
}

.games-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.game-item {
  background: white;
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.game-date {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}

.game-teams {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.game-teams .team-name {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
}

.game-teams .team-name:last-child {
  text-align: right;
}

.game-score {
  font-size: 16px;
  font-weight: 700;
  color: #9ca3af;
  white-space: nowrap;
}

.game-score.has-score {
  color: #1f2937;
}

.game-status {
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  display: inline-block;
}

.game-status.scheduled {
  background-color: #dbeafe;
  color: #1d4ed8;
}

.game-status.completed,
.game-status.final {
  background-color: #dcfce7;
  color: #15803d;
}

.game-status.cancelled {
  background-color: #fee2e2;
  color: #b91c1c;
}

/* Mobile adjustments */
@media (max-width: 480px) {
  .player-detail-view {
    padding: 12px;
  }

  .photo-section {
    max-width: 250px;
    padding: 16px 16px 0;
  }

  .info-section {
    padding: 16px;
  }

  .player-name {
    font-size: 20px;
  }

  .detail-item {
    padding: 10px 16px;
    min-width: 80px;
  }

  .detail-value {
    font-size: 14px;
  }

  .section-title {
    font-size: 16px;
  }

  .social-link {
    padding: 12px 14px;
    min-height: 52px;
  }

  .social-icon {
    width: 36px;
    height: 36px;
  }

  .social-icon svg {
    width: 20px;
    height: 20px;
  }
}
</style>
