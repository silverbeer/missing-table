<template>
  <!-- Edit Profile Modal -->
  <div
    v-if="showEditProfile"
    class="modal-overlay"
    @click.self="showEditProfile = false"
  >
    <div class="edit-modal">
      <div class="modal-header">
        <h3>Edit Profile</h3>
        <button class="close-btn" @click="showEditProfile = false">
          &times;
        </button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label>Display Name</label>
          <input
            v-model="editForm.display_name"
            type="text"
            placeholder="Your display name"
          />
        </div>
        <div class="form-group">
          <label>Email</label>
          <input
            v-model="editForm.email"
            type="email"
            placeholder="your@email.com"
          />
        </div>
      </div>
      <div class="modal-footer">
        <button class="cancel-btn" @click="showEditProfile = false">
          Cancel
        </button>
        <button class="save-btn" @click="saveProfile" :disabled="saving">
          {{ saving ? 'Saving...' : 'Save Changes' }}
        </button>
      </div>
    </div>
  </div>

  <div class="fan-dashboard">
    <!-- Hero Card with Club/League Info -->
    <div class="hero-card" :style="heroCardStyle">
      <div class="hero-logo">
        <img
          v-if="club?.logo_url"
          :src="club.logo_url"
          :alt="club.name"
          class="club-logo-img"
        />
        <div v-else-if="club" class="club-logo-placeholder">
          <span>{{ (club?.name || 'C').charAt(0).toUpperCase() }}</span>
        </div>
        <div v-else class="league-logo-placeholder">
          <span>⚽</span>
        </div>
      </div>
      <div class="hero-info">
        <div class="club-name-row">
          <h2 class="club-name">{{ club?.name || 'League Fan' }}</h2>
          <span class="role-badge">{{ club ? 'Club Fan' : 'Fan' }}</span>
        </div>

        <div v-if="club?.city" class="location-line">{{ club.city }}</div>

        <div class="fan-info">
          <span class="fan-name">{{ displayName }}</span>
          <span class="separator">|</span>
          <span class="member-since">
            Member since {{ formatDate(authStore.state.profile?.created_at) }}
          </span>
        </div>

        <div class="hero-stats">
          <div class="hero-stat">
            <span class="stat-number">{{ clubTeams.length || '—' }}</span>
            <span class="stat-label">{{ club ? 'Club Teams' : 'Teams' }}</span>
          </div>
          <div class="hero-stat">
            <span class="stat-number">{{ upcomingMatchCount }}</span>
            <span class="stat-label">Upcoming</span>
          </div>
          <div class="hero-stat">
            <span class="stat-number">{{ followedTeam ? '1' : '0' }}</span>
            <span class="stat-label">Following</span>
          </div>
        </div>

        <div class="hero-actions">
          <button class="action-btn primary" @click="goToStandings">
            View Standings
          </button>
          <button class="action-btn secondary" @click="openEditProfile">
            Edit Profile
          </button>
          <button class="action-btn logout" @click="$emit('logout')">
            Logout
          </button>
        </div>
      </div>
    </div>

    <!-- Club Teams Section (for Club Fans) -->
    <div v-if="club && clubTeams.length > 0" class="club-teams-section">
      <h3>{{ club.name }} Teams</h3>
      <div class="teams-grid">
        <div
          v-for="team in clubTeams"
          :key="team.id"
          class="team-card"
          @click="goToTeam(team)"
        >
          <div class="team-icon">⚽</div>
          <div class="team-details">
            <h4>{{ team.name }}</h4>
            <p>{{ team.age_group_name || 'Youth' }}</p>
          </div>
          <div class="team-arrow">&rarr;</div>
        </div>
      </div>
    </div>

    <!-- Quick Access Section -->
    <div class="quick-access-section">
      <h3>Quick Access</h3>
      <div class="quick-cards">
        <div class="quick-card" @click="goToStandings">
          <div class="quick-icon">📊</div>
          <div class="quick-content">
            <h4>League Standings</h4>
            <p>Check current league positions</p>
          </div>
          <div class="quick-arrow">&rarr;</div>
        </div>

        <div class="quick-card" @click="goToSchedule">
          <div class="quick-icon">📅</div>
          <div class="quick-content">
            <h4>Match Schedule</h4>
            <p>See upcoming fixtures</p>
          </div>
          <div class="quick-arrow">&rarr;</div>
        </div>

        <div class="quick-card" @click="goToTeams">
          <div class="quick-icon">👥</div>
          <div class="quick-content">
            <h4>All Teams</h4>
            <p>Explore team profiles</p>
          </div>
          <div class="quick-arrow">&rarr;</div>
        </div>
      </div>
    </div>

    <!-- Upcoming Matches -->
    <div v-if="upcomingMatches.length > 0" class="upcoming-section">
      <h3>Upcoming Matches</h3>
      <div class="matches-list">
        <div
          v-for="match in upcomingMatches.slice(0, 5)"
          :key="match.id"
          class="match-card"
        >
          <div class="match-date">
            {{ formatMatchDate(match.game_date) }}
          </div>
          <div class="match-teams">
            <span class="home-team">{{ match.home_team_name }}</span>
            <span class="vs">vs</span>
            <span class="away-team">{{ match.away_team_name }}</span>
          </div>
          <div class="match-type">{{ match.match_type_name || 'League' }}</div>
        </div>
      </div>
    </div>

    <!-- Fan Features -->
    <div class="features-section">
      <h3>Fan Features</h3>
      <p class="section-description">
        As a {{ club ? club.name : 'league' }} fan, you have access to these
        features:
      </p>
      <div class="features-grid">
        <div class="feature-card">
          <div class="feature-icon">📊</div>
          <h4>Live Standings</h4>
          <p>Track league positions in real-time</p>
        </div>

        <div class="feature-card">
          <div class="feature-icon">📅</div>
          <h4>Full Schedule</h4>
          <p>Access all upcoming fixtures</p>
        </div>

        <div class="feature-card">
          <div class="feature-icon">⚽</div>
          <h4>Match Results</h4>
          <p>View scores and match details</p>
        </div>

        <div class="feature-card">
          <div class="feature-icon">👥</div>
          <h4>Team Profiles</h4>
          <p>Explore all teams in the league</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';

export default {
  name: 'FanProfile',
  emits: ['logout', 'navigate'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const club = ref(null);
    const clubTeams = ref([]);
    const upcomingMatches = ref([]);
    const showEditProfile = ref(false);
    const saving = ref(false);

    const editForm = reactive({
      display_name: '',
      email: '',
    });

    const displayName = computed(() => {
      return (
        authStore.state.profile?.display_name ||
        authStore.state.profile?.username ||
        'Fan'
      );
    });

    const followedTeam = computed(() => {
      return authStore.state.profile?.team || null;
    });

    const upcomingMatchCount = computed(() => {
      return upcomingMatches.value.length;
    });

    const clubColors = computed(() => {
      return {
        primary: club.value?.primary_color || '#1e3a8a',
        secondary: club.value?.secondary_color || '#3b82f6',
      };
    });

    const heroCardStyle = computed(() => {
      return {
        background: `linear-gradient(135deg, ${clubColors.value.primary} 0%, ${clubColors.value.secondary} 100%)`,
      };
    });

    const formatDate = dateString => {
      if (!dateString) return '';
      return new Date(dateString).toLocaleDateString('en-US', {
        month: 'short',
        year: 'numeric',
      });
    };

    const formatMatchDate = dateString => {
      if (!dateString) return '';
      return new Date(dateString).toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
      });
    };

    const fetchClub = async () => {
      const clubId = authStore.state.profile?.club_id;
      if (!clubId) return;

      try {
        const response = await fetch(`${getApiBaseUrl()}/api/clubs/${clubId}`);
        if (response.ok) {
          club.value = await response.json();
          // Fetch club teams after getting club
          await fetchClubTeams(clubId);
        }
      } catch (error) {
        console.error('Error fetching club:', error);
      }
    };

    const fetchClubTeams = async clubId => {
      try {
        const response = await fetch(
          `${getApiBaseUrl()}/api/clubs/${clubId}/teams`
        );
        if (response.ok) {
          clubTeams.value = await response.json();
        }
      } catch (error) {
        console.error('Error fetching club teams:', error);
      }
    };

    const fetchUpcomingMatches = async () => {
      try {
        const response = await fetch(`${getApiBaseUrl()}/api/matches/upcoming`);
        if (response.ok) {
          const matches = await response.json();
          // Filter to club teams if user is a club fan
          if (club.value && clubTeams.value.length > 0) {
            const teamIds = clubTeams.value.map(t => t.id);
            upcomingMatches.value = matches.filter(
              m =>
                teamIds.includes(m.home_team_id) ||
                teamIds.includes(m.away_team_id)
            );
          } else {
            upcomingMatches.value = matches.slice(0, 10);
          }
        }
      } catch (error) {
        console.error('Error fetching upcoming matches:', error);
      }
    };

    const initEditForm = () => {
      editForm.display_name = authStore.state.profile?.display_name || '';
      editForm.email = authStore.state.profile?.email || '';
    };

    const openEditProfile = () => {
      initEditForm();
      showEditProfile.value = true;
    };

    const saveProfile = async () => {
      saving.value = true;
      try {
        const result = await authStore.updateProfile({
          display_name: editForm.display_name,
          email: editForm.email,
        });
        if (result.success) {
          showEditProfile.value = false;
        }
      } catch (error) {
        console.error('Error saving profile:', error);
      } finally {
        saving.value = false;
      }
    };

    const goToStandings = () => {
      emit('navigate', 'table');
    };

    const goToSchedule = () => {
      emit('navigate', 'scores');
    };

    const goToTeams = () => {
      // Teams tab may not exist - navigate to standings as fallback
      emit('navigate', 'table');
    };

    const goToTeam = () => {
      // Team detail view - navigate to standings for now
      emit('navigate', 'table');
    };

    onMounted(async () => {
      await fetchClub();
      await fetchUpcomingMatches();
    });

    return {
      authStore,
      club,
      clubTeams,
      upcomingMatches,
      showEditProfile,
      saving,
      editForm,
      displayName,
      followedTeam,
      upcomingMatchCount,
      heroCardStyle,
      formatDate,
      formatMatchDate,
      openEditProfile,
      saveProfile,
      goToStandings,
      goToSchedule,
      goToTeams,
      goToTeam,
    };
  },
};
</script>

<style scoped>
.fan-dashboard {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
}

/* Hero Card */
.hero-card {
  display: flex;
  gap: 30px;
  padding: 30px;
  border-radius: 16px;
  color: white;
  margin-bottom: 30px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.hero-logo {
  flex-shrink: 0;
}

.club-logo-img {
  width: 120px;
  height: 120px;
  object-fit: contain;
  background: white;
  border-radius: 12px;
  padding: 10px;
}

.club-logo-placeholder,
.league-logo-placeholder {
  width: 120px;
  height: 120px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.club-logo-placeholder span {
  font-size: 48px;
  font-weight: bold;
  color: white;
}

.league-logo-placeholder span {
  font-size: 48px;
}

.hero-info {
  flex: 1;
}

.club-name-row {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 8px;
}

.club-name {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
}

.role-badge {
  background: rgba(255, 255, 255, 0.2);
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.location-line {
  font-size: 14px;
  opacity: 0.9;
  margin-bottom: 10px;
}

.fan-info {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  font-size: 14px;
  opacity: 0.9;
}

.separator {
  opacity: 0.5;
}

.hero-stats {
  display: flex;
  gap: 30px;
  margin-bottom: 20px;
}

.hero-stat {
  text-align: center;
}

.stat-number {
  display: block;
  font-size: 28px;
  font-weight: 700;
}

.stat-label {
  display: block;
  font-size: 12px;
  opacity: 0.8;
  text-transform: uppercase;
}

.hero-actions {
  display: flex;
  gap: 12px;
}

.action-btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  font-size: 14px;
}

.action-btn.primary {
  background: white;
  color: #1e3a8a;
}

.action-btn.primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.action-btn.secondary {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.action-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.3);
}

.action-btn.logout {
  background: rgba(220, 38, 38, 0.8);
  color: white;
}

.action-btn.logout:hover {
  background: rgba(220, 38, 38, 1);
}

/* Club Teams Section */
.club-teams-section {
  background: white;
  border-radius: 12px;
  padding: 25px;
  margin-bottom: 25px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.club-teams-section h3 {
  color: #1f2937;
  margin-bottom: 20px;
  font-size: 18px;
}

.teams-grid {
  display: grid;
  gap: 12px;
}

.team-card {
  display: flex;
  align-items: center;
  padding: 15px;
  background: #f8fafc;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #e5e7eb;
}

.team-card:hover {
  background: #f1f5f9;
  transform: translateX(4px);
}

.team-icon {
  font-size: 24px;
  margin-right: 15px;
}

.team-details {
  flex: 1;
}

.team-details h4 {
  margin: 0;
  color: #1f2937;
  font-size: 16px;
}

.team-details p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.team-arrow {
  color: #9ca3af;
  font-size: 18px;
}

/* Quick Access */
.quick-access-section {
  background: white;
  border-radius: 12px;
  padding: 25px;
  margin-bottom: 25px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.quick-access-section h3 {
  color: #1f2937;
  margin-bottom: 20px;
  font-size: 18px;
}

.quick-cards {
  display: grid;
  gap: 12px;
}

.quick-card {
  display: flex;
  align-items: center;
  padding: 18px;
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #bae6fd;
}

.quick-card:hover {
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}

.quick-icon {
  font-size: 28px;
  margin-right: 18px;
}

.quick-content {
  flex: 1;
}

.quick-content h4 {
  margin: 0;
  color: #1e40af;
  font-size: 16px;
}

.quick-content p {
  margin: 4px 0 0;
  color: #3b82f6;
  font-size: 13px;
}

.quick-arrow {
  color: #3b82f6;
  font-size: 20px;
  font-weight: bold;
}

/* Upcoming Matches */
.upcoming-section {
  background: white;
  border-radius: 12px;
  padding: 25px;
  margin-bottom: 25px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.upcoming-section h3 {
  color: #1f2937;
  margin-bottom: 20px;
  font-size: 18px;
}

.matches-list {
  display: grid;
  gap: 10px;
}

.match-card {
  display: grid;
  grid-template-columns: 100px 1fr 80px;
  align-items: center;
  padding: 15px;
  background: #f9fafb;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.match-date {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}

.match-teams {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.home-team,
.away-team {
  font-weight: 500;
  color: #1f2937;
}

.vs {
  color: #9ca3af;
  font-size: 12px;
}

.match-type {
  text-align: right;
  font-size: 11px;
  color: #6b7280;
  text-transform: uppercase;
}

/* Features Section */
.features-section {
  background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
  border-radius: 12px;
  padding: 25px;
  margin-bottom: 25px;
  border: 1px solid #a7f3d0;
}

.features-section h3 {
  color: #047857;
  margin-bottom: 10px;
  font-size: 18px;
}

.section-description {
  color: #065f46;
  margin-bottom: 20px;
  font-size: 14px;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 15px;
}

.feature-card {
  background: white;
  padding: 20px;
  border-radius: 10px;
  text-align: center;
  border: 1px solid #d1fae5;
  transition: all 0.2s;
}

.feature-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.15);
}

.feature-icon {
  font-size: 28px;
  margin-bottom: 10px;
}

.feature-card h4 {
  margin: 0 0 8px;
  color: #047857;
  font-size: 15px;
}

.feature-card p {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.edit-modal {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 450px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e5e7eb;
}

.modal-header h3 {
  margin: 0;
  color: #1f2937;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: #9ca3af;
  cursor: pointer;
}

.close-btn:hover {
  color: #4b5563;
}

.modal-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
  color: #374151;
}

.form-group input {
  width: 100%;
  padding: 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
}

.form-group input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px;
  border-top: 1px solid #e5e7eb;
}

.cancel-btn {
  padding: 10px 20px;
  background: #f3f4f6;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  color: #4b5563;
  cursor: pointer;
  font-weight: 500;
}

.cancel-btn:hover {
  background: #e5e7eb;
}

.save-btn {
  padding: 10px 20px;
  background: #3b82f6;
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font-weight: 500;
}

.save-btn:hover:not(:disabled) {
  background: #2563eb;
}

.save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Responsive */
@media (max-width: 768px) {
  .hero-card {
    flex-direction: column;
    text-align: center;
    padding: 25px;
  }

  .hero-logo {
    margin: 0 auto 20px;
  }

  .club-name-row {
    flex-direction: column;
    gap: 10px;
  }

  .fan-info {
    flex-direction: column;
    gap: 5px;
  }

  .separator {
    display: none;
  }

  .hero-stats {
    justify-content: center;
  }

  .hero-actions {
    flex-direction: column;
  }

  .match-card {
    grid-template-columns: 1fr;
    gap: 8px;
    text-align: center;
  }

  .match-type {
    text-align: center;
  }
}
</style>
