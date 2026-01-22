<template>
  <!-- Profile Editor Modal -->
  <div v-if="showEditor" class="editor-modal" @click.self="showEditor = false">
    <div class="editor-modal-content">
      <PlayerProfileEditor
        @close="showEditor = false"
        @saved="showEditor = false"
      />
    </div>
  </div>

  <!-- Edit Info Modal -->
  <div
    v-if="showEditInfo"
    class="editor-modal"
    @click.self="showEditInfo = false"
  >
    <div class="edit-info-modal">
      <div class="modal-header">
        <h3>Edit Profile</h3>
        <button class="close-btn" @click="showEditInfo = false">&times;</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label>First Name</label>
          <input
            v-model="editableFirstName"
            type="text"
            placeholder="Your first name"
          />
        </div>
        <div class="form-group">
          <label>Last Name</label>
          <input
            v-model="editableLastName"
            type="text"
            placeholder="Your last name"
          />
        </div>
        <div class="form-group">
          <label>Hometown</label>
          <input
            v-model="editableHometown"
            type="text"
            placeholder="City, State"
          />
        </div>
        <div class="form-row">
          <div class="form-group half">
            <label>Jersey Number</label>
            <input
              v-model="editableNumber"
              type="number"
              min="1"
              max="99"
              placeholder="#"
            />
          </div>
          <div class="form-group half">
            <label>Position</label>
            <select v-model="editablePosition">
              <option value="">Select...</option>
              <option
                v-for="pos in availablePositions"
                :key="pos.abbreviation"
                :value="pos.abbreviation"
              >
                {{ pos.abbreviation }} - {{ pos.full_name }}
              </option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label
            >Display Name
            <span class="hint"
              >(Be creative! Add emojis, nicknames)</span
            ></label
          >
          <input
            v-model="editableDisplayName"
            type="text"
            placeholder="Your display name"
          />
        </div>
      </div>
      <div class="modal-footer">
        <span
          v-if="savingPersonalInfo || savingNumber || savingPosition"
          class="saving"
          >Saving...</span
        >
        <button class="done-btn" @click="saveAllAndClose">Done</button>
      </div>
    </div>
  </div>

  <div class="player-dashboard">
    <!-- Header -->
    <div class="dashboard-header">
      <h1>Player Dashboard</h1>
    </div>

    <!-- Hero Card -->
    <div class="hero-card" :style="heroCardStyle">
      <div class="hero-photo">
        <img
          v-if="profilePhotoUrl"
          :src="profilePhotoUrl"
          alt="Profile photo"
          class="hero-photo-img"
        />
        <div v-else class="hero-photo-placeholder">
          <span>{{
            (fullName || authStore.state.profile?.display_name || 'P')
              .charAt(0)
              .toUpperCase()
          }}</span>
        </div>
      </div>
      <div class="hero-info">
        <div class="player-name-row">
          <h2 class="player-name">
            {{ fullName || authStore.state.profile?.display_name || 'Player' }}
          </h2>
          <div class="player-badges">
            <span
              v-if="authStore.state.profile?.player_number"
              class="badge number-badge"
            >
              #{{ authStore.state.profile.player_number }}
            </span>
            <span v-if="primaryPosition" class="badge position-badge">
              {{ primaryPosition }}
            </span>
          </div>
        </div>

        <div v-if="authStore.state.profile?.team" class="team-line">
          <span class="team-name">{{ authStore.state.profile.team.name }}</span>
          <span v-if="currentAgeGroup?.name" class="separator">•</span>
          <span v-if="currentAgeGroup?.name" class="age-group">
            {{ currentAgeGroup.name }}
          </span>
          <span
            v-if="authStore.state.profile.team.league?.name"
            class="separator"
            >•</span
          >
          <span v-if="authStore.state.profile.team.league?.name" class="league">
            {{ authStore.state.profile.team.league.name }}
          </span>
          <span
            v-if="authStore.state.profile.team.division?.name"
            class="separator"
            >•</span
          >
          <span
            v-if="authStore.state.profile.team.division?.name"
            class="division"
          >
            {{ authStore.state.profile.team.division.name }}
          </span>
        </div>
        <div v-else class="no-team-line">Not assigned to a team</div>

        <div v-if="authStore.state.profile?.hometown" class="hometown-line">
          📍 {{ authStore.state.profile.hometown }}
        </div>

        <!-- Social Media -->
        <div v-if="hasSocialMedia" class="social-row">
          <a
            v-if="authStore.state.profile.instagram_handle"
            :href="`https://instagram.com/${authStore.state.profile.instagram_handle}`"
            target="_blank"
            rel="noopener noreferrer"
            class="social-icon instagram"
            title="Instagram"
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path
                d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"
              />
            </svg>
          </a>
          <a
            v-if="authStore.state.profile.snapchat_handle"
            :href="`https://snapchat.com/add/${authStore.state.profile.snapchat_handle}`"
            target="_blank"
            rel="noopener noreferrer"
            class="social-icon snapchat"
            title="Snapchat"
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path
                d="M12.166 2c1.34.006 2.613.139 3.49.476.96.369 1.715.984 2.285 1.794.548.779.86 1.728.98 2.979.066.69.068 1.43.068 2.21v.242c.002.4.004.775.038 1.172.043.498.13.805.286 1.048.13.203.342.395.749.584.16.074.33.143.52.22l.18.073c.5.2.87.37 1.138.557.404.28.567.563.567.813s-.163.533-.567.813c-.268.187-.638.357-1.138.557l-.18.073c-.19.077-.36.146-.52.22-.407.189-.619.381-.749.584-.156.243-.243.55-.286 1.048-.034.397-.036.772-.038 1.172v.242c0 .78-.002 1.52-.068 2.21-.12 1.251-.432 2.2-.98 2.979-.57.81-1.325 1.425-2.285 1.794-.877.337-2.15.47-3.49.476h-.332c-1.34-.006-2.613-.139-3.49-.476-.96-.369-1.715-.984-2.285-1.794-.548-.779-.86-1.728-.98-2.979-.066-.69-.068-1.43-.068-2.21v-.242c-.002-.4-.004-.775-.038-1.172-.043-.498-.13-.805-.286-1.048-.13-.203-.342-.395-.749-.584-.16-.074-.33-.143-.52-.22l-.18-.073c-.5-.2-.87-.37-1.138-.557-.404-.28-.567-.563-.567-.813s.163-.533.567-.813c.268-.187.638-.357 1.138-.557l.18-.073c.19-.077.36-.146.52-.22.407-.189.619-.381.749-.584.156-.243.243-.55.286-1.048.034-.397.036-.772.038-1.172v-.242c0-.78.002-1.52.068-2.21.12-1.251.432-2.2.98-2.979.57-.81 1.325-1.425 2.285-1.794.877-.337 2.15-.47 3.49-.476z"
              />
            </svg>
          </a>
          <a
            v-if="authStore.state.profile.tiktok_handle"
            :href="`https://tiktok.com/@${authStore.state.profile.tiktok_handle}`"
            target="_blank"
            rel="noopener noreferrer"
            class="social-icon tiktok"
            title="TikTok"
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path
                d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 5 20.1a6.34 6.34 0 0 0 10.86-4.43v-7a8.16 8.16 0 0 0 4.77 1.52v-3.4a4.85 4.85 0 0 1-1-.1z"
              />
            </svg>
          </a>
        </div>

        <div class="hero-actions">
          <button class="action-btn primary" @click="showEditor = true">
            Customize Photo
          </button>
          <button class="action-btn secondary" @click="showEditInfo = true">
            Edit Info
          </button>
        </div>
      </div>
    </div>

    <!-- Two Column: Photos & History -->
    <div v-if="authStore.state.profile?.team" class="two-column-section">
      <!-- Photo Carousel -->
      <div class="column-card photos-card">
        <h3>My Photos</h3>
        <div v-if="playerPhotos.length > 0" class="photo-carousel">
          <div class="carousel-container">
            <button
              v-if="playerPhotos.length > 1"
              class="carousel-btn prev"
              @click="prevPhoto"
            >
              ‹
            </button>
            <div class="carousel-image-wrapper">
              <img
                :src="playerPhotos[currentPhotoIndex]"
                alt="Player photo"
                class="carousel-image"
              />
            </div>
            <button
              v-if="playerPhotos.length > 1"
              class="carousel-btn next"
              @click="nextPhoto"
            >
              ›
            </button>
          </div>
          <div v-if="playerPhotos.length > 1" class="carousel-dots">
            <button
              v-for="(photo, index) in playerPhotos"
              :key="index"
              class="dot"
              :class="{ active: index === currentPhotoIndex }"
              @click="currentPhotoIndex = index"
            ></button>
          </div>
        </div>
        <div v-else class="no-photos">
          <div class="no-photos-icon">📷</div>
          <p>No photos yet</p>
          <button class="upload-btn" @click="showEditor = true">
            Add Photos
          </button>
        </div>
      </div>

      <!-- Team History -->
      <div class="column-card history-card">
        <h3>Team History</h3>
        <div v-if="loadingHistory" class="loading">Loading...</div>
        <div v-else-if="playerHistory.length === 0" class="no-history">
          No history recorded yet
        </div>
        <div v-else class="history-list">
          <div
            v-for="entry in playerHistory"
            :key="entry.id"
            class="history-item"
            :class="{ current: entry.is_current }"
          >
            <div class="history-season">
              {{ entry.season?.name }}
              <span v-if="entry.is_current" class="current-tag">Current</span>
            </div>
            <div class="history-team">{{ entry.team?.name }}</div>
            <div class="history-meta">
              <span v-if="entry.age_group?.name" class="meta-tag">{{
                entry.age_group.name
              }}</span>
              <span v-if="entry.jersey_number" class="meta-tag"
                >#{{ entry.jersey_number }}</span
              >
              <span v-if="entry.positions?.length" class="meta-tag">{{
                entry.positions.join(', ')
              }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Individual Player Stats -->
    <div
      v-if="authStore.state.profile?.team"
      class="stats-section individual-stats"
    >
      <h3>My Stats</h3>
      <div v-if="loadingStats" class="loading">Loading stats...</div>
      <div
        v-else-if="individualStats && individualStats.linked"
        class="stats-row four-col"
      >
        <div class="stat-item">
          <div class="stat-value">
            {{ individualStats.stats?.games_played || 0 }}
          </div>
          <div class="stat-label">Games Played</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">
            {{ individualStats.stats?.games_started || 0 }}
          </div>
          <div class="stat-label">Games Started</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">
            {{ individualStats.stats?.total_minutes || 0 }}
          </div>
          <div class="stat-label">Minutes</div>
        </div>
        <div class="stat-item highlight">
          <div class="stat-value">
            {{ individualStats.stats?.total_goals || 0 }}
          </div>
          <div class="stat-label">Goals</div>
        </div>
      </div>
      <div v-else class="no-stats">
        <p>No individual stats available yet.</p>
        <p class="hint">
          Stats are tracked when you're on the team roster and participate in
          matches.
        </p>
      </div>
    </div>

    <!-- Team Season Stats -->
    <div v-if="authStore.state.profile?.team" class="stats-section">
      <h3>Team Season Record</h3>
      <div class="stats-row">
        <div class="stat-item">
          <div class="stat-value">{{ totalGames }}</div>
          <div class="stat-label">Games</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ wins }}</div>
          <div class="stat-label">Wins</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ draws }}</div>
          <div class="stat-label">Draws</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ losses }}</div>
          <div class="stat-label">Losses</div>
        </div>
        <div class="stat-item highlight">
          <div class="stat-value">{{ winPercentage }}%</div>
          <div class="stat-label">Win Rate</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ goalsFor }}</div>
          <div class="stat-label">Goals For</div>
        </div>
      </div>
    </div>

    <!-- No Team State -->
    <div v-if="!authStore.state.profile?.team" class="no-team-card">
      <h3>Join a Team</h3>
      <p>Contact a team manager or administrator to get assigned to a team.</p>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import PlayerProfileEditor from './PlayerProfileEditor.vue';
import { getApiBaseUrl } from '../../config/api';
import { PLAYER_POSITIONS } from '@/constants/positions';

export default {
  name: 'PlayerProfile',
  components: {
    PlayerProfileEditor,
  },
  setup() {
    const authStore = useAuthStore();
    const teamGames = ref([]);
    const playerHistory = ref([]);
    const loadingHistory = ref(false);
    const showEditor = ref(false);
    const showEditInfo = ref(false);
    const availablePositions = ref(PLAYER_POSITIONS);
    const savingNumber = ref(false);
    const savingPosition = ref(false);
    const savingPersonalInfo = ref(false);
    const editableNumber = ref(null);
    const editablePosition = ref('');
    const editableFirstName = ref('');
    const editableLastName = ref('');
    const editableHometown = ref('');
    const editableDisplayName = ref('');
    const individualStats = ref(null);
    const loadingStats = ref(false);

    const profilePhotoUrl = computed(() => {
      const profile = authStore.state.profile;
      if (!profile) return null;
      const slot = profile.profile_photo_slot;
      if (slot && profile[`photo_${slot}_url`]) {
        return profile[`photo_${slot}_url`];
      }
      for (let i = 1; i <= 3; i++) {
        if (profile[`photo_${i}_url`]) {
          return profile[`photo_${i}_url`];
        }
      }
      return null;
    });

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

    const primaryPosition = computed(() => {
      return parsedPositions.value.length > 0 ? parsedPositions.value[0] : null;
    });

    const fullName = computed(() => {
      const first = authStore.state.profile?.first_name;
      const last = authStore.state.profile?.last_name;
      if (first && last) return `${first} ${last}`;
      if (first) return first;
      if (last) return last;
      return null;
    });

    // Photo carousel
    const currentPhotoIndex = ref(0);
    const playerPhotos = computed(() => {
      const profile = authStore.state.profile;
      if (!profile) return [];
      const photos = [];
      if (profile.photo_1_url) photos.push(profile.photo_1_url);
      if (profile.photo_2_url) photos.push(profile.photo_2_url);
      if (profile.photo_3_url) photos.push(profile.photo_3_url);
      return photos;
    });

    const nextPhoto = () => {
      if (playerPhotos.value.length > 0) {
        currentPhotoIndex.value =
          (currentPhotoIndex.value + 1) % playerPhotos.value.length;
      }
    };

    const prevPhoto = () => {
      if (playerPhotos.value.length > 0) {
        currentPhotoIndex.value =
          (currentPhotoIndex.value - 1 + playerPhotos.value.length) %
          playerPhotos.value.length;
      }
    };

    // Get current player history entry for age group info
    const currentHistoryEntry = computed(() => {
      return playerHistory.value.find(h => h.is_current) || null;
    });

    const currentAgeGroup = computed(() => {
      return currentHistoryEntry.value?.age_group || null;
    });

    const hasSocialMedia = computed(() => {
      const profile = authStore.state.profile;
      return (
        profile?.instagram_handle ||
        profile?.snapchat_handle ||
        profile?.tiktok_handle
      );
    });

    // Club colors for dynamic theming
    const clubColors = computed(() => {
      const club = authStore.state.profile?.team?.club;
      return {
        primary: club?.primary_color || '#1e3a8a',
        secondary: club?.secondary_color || '#3b82f6',
      };
    });

    const heroCardStyle = computed(() => {
      return {
        background: `linear-gradient(135deg, ${clubColors.value.primary} 0%, ${clubColors.value.secondary} 100%)`,
      };
    });

    const playedGames = computed(() => {
      return teamGames.value.filter(game => game.home_score !== null);
    });

    const totalGames = computed(() => playedGames.value.length);

    const wins = computed(() => {
      return playedGames.value.filter(game => {
        const teamId = authStore.state.profile?.team?.id;
        if (!teamId) return false;
        if (game.home_team_id === teamId)
          return game.home_score > game.away_score;
        return game.away_score > game.home_score;
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
        if (game.home_team_id === teamId)
          return game.home_score < game.away_score;
        return game.away_score < game.home_score;
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
        if (game.home_team_id === teamId) return total + game.home_score;
        return total + game.away_score;
      }, 0);
    });

    const initEditableFields = () => {
      editableNumber.value = authStore.state.profile?.player_number || null;
      const positions = parsedPositions.value;
      editablePosition.value = positions.length > 0 ? positions[0] : '';
      editableFirstName.value = authStore.state.profile?.first_name || '';
      editableLastName.value = authStore.state.profile?.last_name || '';
      editableHometown.value = authStore.state.profile?.hometown || '';
      editableDisplayName.value = authStore.state.profile?.display_name || '';
    };

    const savePlayerNumber = async () => {
      const currentNumber = authStore.state.profile?.player_number;
      if (editableNumber.value === currentNumber) return;
      try {
        savingNumber.value = true;
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/auth/profile/customization`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              player_number: editableNumber.value || null,
            }),
          }
        );
        await authStore.fetchProfile();
      } catch (error) {
        console.error('Error saving player number:', error);
        editableNumber.value = currentNumber;
      } finally {
        savingNumber.value = false;
      }
    };

    const savePosition = async () => {
      const currentPositions = parsedPositions.value;
      const currentPosition =
        currentPositions.length > 0 ? currentPositions[0] : '';
      if (editablePosition.value === currentPosition) return;
      try {
        savingPosition.value = true;
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/auth/profile/customization`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              positions: editablePosition.value ? [editablePosition.value] : [],
            }),
          }
        );
        await authStore.fetchProfile();
      } catch (error) {
        console.error('Error saving position:', error);
        editablePosition.value = currentPosition;
      } finally {
        savingPosition.value = false;
      }
    };

    const savePersonalInfo = async () => {
      const profile = authStore.state.profile;
      const currentFirstName = profile?.first_name || '';
      const currentLastName = profile?.last_name || '';
      const currentHometown = profile?.hometown || '';
      if (
        editableFirstName.value === currentFirstName &&
        editableLastName.value === currentLastName &&
        editableHometown.value === currentHometown
      )
        return;
      try {
        savingPersonalInfo.value = true;
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/auth/profile/customization`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              first_name: editableFirstName.value || null,
              last_name: editableLastName.value || null,
              hometown: editableHometown.value || null,
            }),
          }
        );
        await authStore.fetchProfile();
      } catch (error) {
        console.error('Error saving personal info:', error);
        editableFirstName.value = currentFirstName;
        editableLastName.value = currentLastName;
        editableHometown.value = currentHometown;
      } finally {
        savingPersonalInfo.value = false;
      }
    };

    const saveDisplayName = async () => {
      const currentDisplayName = authStore.state.profile?.display_name || '';
      if (editableDisplayName.value === currentDisplayName) return;
      try {
        await authStore.apiRequest(`${getApiBaseUrl()}/api/auth/profile`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            display_name: editableDisplayName.value || null,
          }),
        });
        await authStore.fetchProfile();
      } catch (error) {
        console.error('Error saving display name:', error);
        editableDisplayName.value = currentDisplayName;
      }
    };

    const saveAllAndClose = async () => {
      try {
        // Collect all changes into a single request
        const profile = authStore.state.profile;
        const updates = {};

        // Personal info changes
        if (editableFirstName.value !== (profile?.first_name || '')) {
          updates.first_name = editableFirstName.value || null;
        }
        if (editableLastName.value !== (profile?.last_name || '')) {
          updates.last_name = editableLastName.value || null;
        }
        if (editableHometown.value !== (profile?.hometown || '')) {
          updates.hometown = editableHometown.value || null;
        }
        if (editableNumber.value !== profile?.player_number) {
          updates.player_number = editableNumber.value || null;
        }
        const currentPositions = parsedPositions.value;
        const currentPosition =
          currentPositions.length > 0 ? currentPositions[0] : '';
        if (editablePosition.value !== currentPosition) {
          updates.positions = editablePosition.value
            ? [editablePosition.value]
            : [];
        }

        console.log('Saving updates:', updates);

        // Save customization if there are changes
        if (Object.keys(updates).length > 0) {
          savingPersonalInfo.value = true;
          const result = await authStore.apiRequest(
            `${getApiBaseUrl()}/api/auth/profile/customization`,
            {
              method: 'PUT',
              body: JSON.stringify(updates),
            }
          );
          console.log('Save result:', result);
        }

        // Save display name if changed
        const currentDisplayName = profile?.display_name || '';
        if (editableDisplayName.value !== currentDisplayName) {
          await authStore.apiRequest(`${getApiBaseUrl()}/api/auth/profile`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              display_name: editableDisplayName.value || null,
            }),
          });
        }

        // Refresh profile and close
        await authStore.fetchProfile();
        showEditInfo.value = false;
      } catch (error) {
        console.error('Error saving profile:', error);
      } finally {
        savingPersonalInfo.value = false;
      }
    };

    const fetchTeamGames = async () => {
      const teamId = authStore.state.profile?.team?.id;
      // Get age_group_id from current history entry (more reliable than team)
      const ageGroupId = currentHistoryEntry.value?.age_group_id;
      if (!teamId) return;
      try {
        // Build URL with age_group_id filter if available
        let url = `${getApiBaseUrl()}/api/matches/team/${teamId}`;
        if (ageGroupId) {
          url += `?age_group_id=${ageGroupId}`;
        }
        const games = await authStore.apiRequest(url, { method: 'GET' });
        teamGames.value = games;
      } catch (error) {
        console.error('Error fetching team games:', error);
      }
    };

    const fetchPlayerHistory = async () => {
      try {
        loadingHistory.value = true;
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/auth/profile/history`,
          { method: 'GET' }
        );
        if (response.success) {
          playerHistory.value = response.history || [];
        }
      } catch (error) {
        console.error('Error fetching player history:', error);
      } finally {
        loadingHistory.value = false;
      }
    };

    const fetchIndividualStats = async seasonId => {
      if (!seasonId) return;
      try {
        loadingStats.value = true;
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/me/player-stats?season_id=${seasonId}`,
          { method: 'GET' }
        );
        individualStats.value = response;
      } catch (error) {
        console.error('Error fetching individual stats:', error);
        individualStats.value = null;
      } finally {
        loadingStats.value = false;
      }
    };

    const isMyTeam = teamId => teamId === authStore.state.profile?.team?.id;

    const formatGameDate = dateString => {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
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

    watch(
      () => authStore.state.profile,
      () => initEditableFields(),
      { deep: true }
    );

    // Refetch games and individual stats when player history changes
    watch(
      () => currentHistoryEntry.value,
      async entry => {
        if (entry && authStore.state.profile?.team) {
          await fetchTeamGames();
          if (entry.season_id) {
            await fetchIndividualStats(entry.season_id);
          }
        }
      }
    );

    onMounted(async () => {
      initEditableFields();
      // Fetch history first, then games (so age group filter works)
      await fetchPlayerHistory();
      if (authStore.state.profile?.team) {
        await fetchTeamGames();
      }
    });

    return {
      authStore,
      playerHistory,
      loadingHistory,
      showEditor,
      showEditInfo,
      profilePhotoUrl,
      primaryPosition,
      fullName,
      currentAgeGroup,
      clubColors,
      heroCardStyle,
      hasSocialMedia,
      // Photo carousel
      playerPhotos,
      currentPhotoIndex,
      nextPhoto,
      prevPhoto,
      // Team Stats
      totalGames,
      wins,
      draws,
      losses,
      winPercentage,
      goalsFor,
      // Individual Stats
      individualStats,
      loadingStats,
      isMyTeam,
      formatGameDate,
      getGameResult,
      getResultClass,
      availablePositions,
      editableNumber,
      editablePosition,
      editableFirstName,
      editableLastName,
      editableHometown,
      editableDisplayName,
      savingNumber,
      savingPosition,
      savingPersonalInfo,
      savePlayerNumber,
      savePosition,
      savePersonalInfo,
      saveDisplayName,
      saveAllAndClose,
    };
  },
};
</script>

<style scoped>
.player-dashboard {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.dashboard-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
  margin: 0;
}

/* Hero Card */
.hero-card {
  display: flex;
  gap: 24px;
  /* background set dynamically via :style="heroCardStyle" using club colors */
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
  color: white;
}

.hero-photo {
  flex-shrink: 0;
}

.hero-photo-img {
  width: 160px;
  height: 160px;
  border-radius: 12px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  object-fit: cover;
}

.hero-photo-placeholder {
  width: 160px;
  height: 160px;
  border-radius: 12px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 64px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.8);
}

.hero-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.player-name-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.player-name {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
}

.player-badges {
  display: flex;
  gap: 8px;
}

.badge {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
}

.number-badge {
  background: rgba(255, 255, 255, 0.2);
}

.position-badge {
  background: #f59e0b;
  color: #1f2937;
}

.team-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  flex-wrap: wrap;
}

.team-name {
  font-weight: 600;
}

.separator {
  opacity: 0.5;
}

.age-group,
.league,
.division {
  opacity: 0.9;
}

.no-team-line {
  opacity: 0.7;
  font-style: italic;
}

.hometown-line {
  font-size: 14px;
  opacity: 0.9;
}

.social-row {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}

.social-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s;
}

.social-icon:hover {
  transform: scale(1.1);
}

.social-icon svg {
  width: 18px;
  height: 18px;
}

.social-icon.instagram {
  background: linear-gradient(45deg, #f09433, #dc2743, #bc1888);
  color: white;
}

.social-icon.snapchat {
  background: #fffc00;
  color: #000;
}

.social-icon.tiktok {
  background: #000;
  color: white;
}

.hero-actions {
  display: flex;
  gap: 12px;
  margin-top: auto;
  padding-top: 12px;
}

.action-btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.action-btn.primary {
  background: white;
  color: #1e3a8a;
}

.action-btn.primary:hover {
  background: #f0f9ff;
}

.action-btn.secondary {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.action-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* Two Column Section */
.two-column-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

.column-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.column-card h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 16px 0;
}

/* Photo Carousel */
.photos-card {
  display: flex;
  flex-direction: column;
}

.photo-carousel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.carousel-container {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.carousel-image-wrapper {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 250px;
}

.carousel-image {
  max-width: 100%;
  max-height: 300px;
  border-radius: 12px;
  object-fit: contain;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.carousel-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: #f3f4f6;
  color: #374151;
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}

.carousel-btn:hover {
  background: #e5e7eb;
}

.carousel-dots {
  display: flex;
  gap: 8px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: none;
  background: #d1d5db;
  cursor: pointer;
  padding: 0;
  transition: all 0.2s;
}

.dot.active {
  background: #3b82f6;
  transform: scale(1.2);
}

.no-photos {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
  color: #9ca3af;
}

.no-photos-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.no-photos p {
  margin: 0 0 16px 0;
}

.upload-btn {
  padding: 10px 20px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
}

.upload-btn:hover {
  background: #2563eb;
}

.no-games,
.no-history {
  text-align: center;
  color: #9ca3af;
  font-size: 14px;
  padding: 20px;
}

/* History Card */
.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-item {
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
  border-left: 3px solid #e5e7eb;
}

.history-item.current {
  border-left-color: #10b981;
  background: #f0fdf4;
}

.history-season {
  font-weight: 600;
  color: #1f2937;
  display: flex;
  align-items: center;
  gap: 8px;
}

.current-tag {
  font-size: 10px;
  background: #10b981;
  color: white;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
}

.history-team {
  font-size: 14px;
  color: #4b5563;
  margin-top: 4px;
}

.history-meta {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.meta-tag {
  font-size: 11px;
  padding: 2px 8px;
  background: #e5e7eb;
  border-radius: 4px;
  color: #4b5563;
}

/* Stats Section */
.stats-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  margin-bottom: 24px;
}

.stats-section h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 16px 0;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
}

.stat-item {
  text-align: center;
  padding: 16px;
  background: #f9fafb;
  border-radius: 8px;
}

.stat-item.highlight {
  background: #ecfdf5;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1f2937;
}

.stat-item.highlight .stat-value {
  color: #059669;
}

.stat-label {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
  text-transform: uppercase;
}

.stats-row.four-col {
  grid-template-columns: repeat(4, 1fr);
}

.individual-stats {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border: 1px solid #bae6fd;
}

.no-stats {
  text-align: center;
  color: #6b7280;
  padding: 20px;
}

.no-stats p {
  margin: 0;
}

.no-stats .hint {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 8px;
}

/* No Team Card */
.no-team-card {
  background: #fef2f2;
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  border: 1px solid #fecaca;
}

.no-team-card h3 {
  color: #dc2626;
  margin: 0 0 12px 0;
}

.no-team-card p {
  color: #6b7280;
  margin: 0;
}

/* Modal Styles */
.editor-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  z-index: 1000;
  overflow-y: auto;
  padding: 40px 20px;
}

.editor-modal-content {
  width: 100%;
  max-width: 1000px;
  background: white;
  border-radius: 16px;
}

.edit-info-modal {
  width: 100%;
  max-width: 480px;
  background: white;
  border-radius: 16px;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  color: #1f2937;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: #6b7280;
  cursor: pointer;
}

.modal-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 6px;
}

.form-group .hint {
  font-weight: 400;
  color: #9ca3af;
  font-size: 12px;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-group.half {
  flex: 1;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #e5e7eb;
}

.saving {
  font-size: 14px;
  color: #6b7280;
}

.done-btn {
  padding: 10px 24px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
}

.done-btn:hover {
  background: #2563eb;
}

.loading {
  text-align: center;
  color: #6b7280;
  padding: 20px;
}

/* Responsive */
@media (max-width: 768px) {
  .hero-card {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .player-name-row {
    justify-content: center;
  }

  .team-line {
    justify-content: center;
  }

  .social-row {
    justify-content: center;
  }

  .hero-actions {
    justify-content: center;
  }

  .two-column-section {
    grid-template-columns: 1fr;
  }

  .stats-row {
    grid-template-columns: repeat(3, 1fr);
  }

  .stats-row.four-col {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 480px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .stats-row.four-col {
    grid-template-columns: repeat(2, 1fr);
  }

  .hero-photo-img {
    width: 120px;
    height: 120px;
  }

  .player-name {
    font-size: 22px;
  }
}
</style>
