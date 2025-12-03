<template>
  <div class="club-manager-dashboard">
    <!-- Header -->
    <div class="dashboard-header">
      <h1>Club Manager Dashboard</h1>
      <button @click="handleLogout" class="logout-btn">Logout</button>
    </div>

    <!-- Hero Card with Club Info -->
    <div class="hero-card" :style="heroCardStyle">
      <div class="hero-logo">
        <img
          v-if="club?.logo_url"
          :src="club.logo_url"
          :alt="club.name"
          class="club-logo-img"
        />
        <div v-else class="club-logo-placeholder">
          <span>{{ (club?.name || 'C').charAt(0).toUpperCase() }}</span>
        </div>
      </div>
      <div class="hero-info">
        <div class="club-name-row">
          <h2 class="club-name">{{ club?.name || 'Club' }}</h2>
          <span class="role-badge">Club Manager</span>
        </div>

        <div v-if="club?.city" class="location-line">
          {{ club.city }}
        </div>

        <div class="manager-info">
          <span class="manager-name">{{ displayName }}</span>
          <span class="separator">|</span>
          <span class="member-since">
            Member since {{ formatDate(authStore.state.profile?.created_at) }}
          </span>
        </div>

        <div class="hero-stats">
          <div class="hero-stat">
            <span class="stat-number">{{ clubTeams.length }}</span>
            <span class="stat-label">Teams</span>
          </div>
          <div class="hero-stat">
            <span class="stat-number">{{ totalMatches }}</span>
            <span class="stat-label">Matches</span>
          </div>
          <div class="hero-stat">
            <span class="stat-number">{{ totalPlayers }}</span>
            <span class="stat-label">Players</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="quick-actions">
      <h3>Quick Actions</h3>
      <div class="actions-grid">
        <router-link to="/admin?tab=teams" class="action-card">
          <div class="action-icon">&#9917;</div>
          <div class="action-content">
            <h4>Manage Teams</h4>
            <p>Add, edit, and organize your club's teams</p>
          </div>
          <div class="action-arrow">&rarr;</div>
        </router-link>

        <router-link to="/admin?tab=matches" class="action-card">
          <div class="action-icon">&#128197;</div>
          <div class="action-content">
            <h4>Manage Matches</h4>
            <p>View and edit match schedules and results</p>
          </div>
          <div class="action-arrow">&rarr;</div>
        </router-link>

        <router-link to="/admin?tab=players" class="action-card">
          <div class="action-icon">&#128101;</div>
          <div class="action-content">
            <h4>Manage Players</h4>
            <p>View and assign players to teams</p>
          </div>
          <div class="action-arrow">&rarr;</div>
        </router-link>
      </div>
    </div>

    <!-- Club Teams -->
    <div class="teams-section">
      <h3>Your Teams</h3>
      <div v-if="loadingTeams" class="loading">Loading teams...</div>
      <div v-else-if="clubTeams.length === 0" class="no-teams">
        <p>No teams found for this club.</p>
        <router-link to="/admin?tab=teams" class="add-team-btn">
          Add First Team
        </router-link>
      </div>
      <div v-else class="teams-grid">
        <div v-for="team in clubTeams" :key="team.id" class="team-card">
          <div class="team-header">
            <h4>{{ team.name }}</h4>
            <span v-if="team.age_group_name" class="age-badge">{{
              team.age_group_name
            }}</span>
          </div>
          <div class="team-details">
            <div v-if="team.division_name" class="team-meta">
              <span class="meta-label">Division:</span>
              <span>{{ team.division_name }}</span>
            </div>
            <div v-if="team.league_name" class="team-meta">
              <span class="meta-label">League:</span>
              <span>{{ team.league_name }}</span>
            </div>
          </div>
          <div class="team-stats">
            <div class="team-stat">
              <span class="stat-value">{{ team.player_count || 0 }}</span>
              <span class="stat-name">Players</span>
            </div>
            <div class="team-stat">
              <span class="stat-value">{{ team.match_count || 0 }}</span>
              <span class="stat-name">Matches</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- No Club Assigned -->
    <div v-if="!club" class="no-club-card">
      <h3>No Club Assigned</h3>
      <p>
        You haven't been assigned to manage a club yet. Contact an administrator
        to get assigned.
      </p>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';

export default {
  name: 'ClubManagerProfile',
  emits: ['logout'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const clubTeams = ref([]);
    const loadingTeams = ref(false);

    const club = computed(() => authStore.state.profile?.club || null);

    const displayName = computed(() => {
      return (
        authStore.state.profile?.display_name ||
        authStore.state.profile?.username ||
        'Manager'
      );
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

    const totalMatches = computed(() => {
      return clubTeams.value.reduce(
        (sum, team) => sum + (team.match_count || 0),
        0
      );
    });

    const totalPlayers = computed(() => {
      return clubTeams.value.reduce(
        (sum, team) => sum + (team.player_count || 0),
        0
      );
    });

    const formatDate = dateString => {
      if (!dateString) return '';
      return new Date(dateString).toLocaleDateString('en-US', {
        month: 'short',
        year: 'numeric',
      });
    };

    const fetchClubTeams = async () => {
      const clubId = authStore.state.profile?.club_id;
      if (!clubId) return;

      try {
        loadingTeams.value = true;
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/clubs/${clubId}/teams`
        );
        clubTeams.value = response || [];
      } catch (error) {
        console.error('Error fetching club teams:', error);
      } finally {
        loadingTeams.value = false;
      }
    };

    const handleLogout = async () => {
      if (confirm('Are you sure you want to log out?')) {
        await authStore.logout();
        emit('logout');
      }
    };

    onMounted(() => {
      fetchClubTeams();
    });

    return {
      authStore,
      club,
      clubTeams,
      loadingTeams,
      displayName,
      clubColors,
      heroCardStyle,
      totalMatches,
      totalPlayers,
      formatDate,
      handleLogout,
    };
  },
};
</script>

<style scoped>
.club-manager-dashboard {
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

.logout-btn {
  background-color: #dc2626;
  color: white;
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s;
}

.logout-btn:hover {
  background-color: #b91c1c;
}

/* Hero Card */
.hero-card {
  display: flex;
  gap: 24px;
  border-radius: 16px;
  padding: 28px;
  margin-bottom: 24px;
  color: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.hero-logo {
  flex-shrink: 0;
}

.club-logo-img {
  width: 140px;
  height: 140px;
  border-radius: 12px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  object-fit: contain;
  background: rgba(255, 255, 255, 0.95);
  padding: 8px;
}

.club-logo-placeholder {
  width: 140px;
  height: 140px;
  border-radius: 12px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 56px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.8);
}

.hero-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.club-name-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.club-name {
  font-size: 32px;
  font-weight: 700;
  margin: 0;
}

.role-badge {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.2);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.location-line {
  font-size: 16px;
  opacity: 0.9;
}

.manager-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  opacity: 0.85;
  margin-top: 4px;
}

.separator {
  opacity: 0.5;
}

.hero-stats {
  display: flex;
  gap: 32px;
  margin-top: auto;
  padding-top: 16px;
}

.hero-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.hero-stat .stat-number {
  font-size: 28px;
  font-weight: 700;
}

.hero-stat .stat-label {
  font-size: 12px;
  text-transform: uppercase;
  opacity: 0.8;
}

/* Quick Actions */
.quick-actions {
  margin-bottom: 24px;
}

.quick-actions h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 16px 0;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.action-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: white;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  text-decoration: none;
  color: inherit;
  transition: all 0.2s;
}

.action-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
  transform: translateY(-2px);
}

.action-icon {
  font-size: 28px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f9ff;
  border-radius: 10px;
}

.action-content {
  flex: 1;
}

.action-content h4 {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.action-content p {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
}

.action-arrow {
  font-size: 20px;
  color: #9ca3af;
  transition: transform 0.2s;
}

.action-card:hover .action-arrow {
  transform: translateX(4px);
  color: #3b82f6;
}

/* Teams Section */
.teams-section {
  margin-bottom: 24px;
}

.teams-section h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 16px 0;
}

.teams-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.team-card {
  background: white;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  padding: 20px;
  transition: all 0.2s;
}

.team-card:hover {
  border-color: #d1d5db;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.team-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.team-header h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.age-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: #dbeafe;
  color: #1e40af;
}

.team-details {
  margin-bottom: 16px;
}

.team-meta {
  display: flex;
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 4px;
}

.meta-label {
  color: #9ca3af;
  margin-right: 6px;
}

.team-stats {
  display: flex;
  gap: 24px;
  padding-top: 12px;
  border-top: 1px solid #f3f4f6;
}

.team-stat {
  display: flex;
  flex-direction: column;
}

.team-stat .stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
}

.team-stat .stat-name {
  font-size: 12px;
  color: #6b7280;
}

.no-teams {
  background: #f9fafb;
  border-radius: 12px;
  padding: 40px;
  text-align: center;
}

.no-teams p {
  color: #6b7280;
  margin: 0 0 16px 0;
}

.add-team-btn {
  display: inline-block;
  padding: 10px 20px;
  background: #3b82f6;
  color: white;
  text-decoration: none;
  border-radius: 8px;
  font-weight: 500;
  transition: background 0.2s;
}

.add-team-btn:hover {
  background: #2563eb;
}

/* No Club */
.no-club-card {
  background: #fef2f2;
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  border: 1px solid #fecaca;
}

.no-club-card h3 {
  color: #dc2626;
  margin: 0 0 12px 0;
}

.no-club-card p {
  color: #6b7280;
  margin: 0;
}

.loading {
  text-align: center;
  color: #6b7280;
  padding: 40px;
}

/* Responsive */
@media (max-width: 768px) {
  .hero-card {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .club-name-row {
    justify-content: center;
  }

  .manager-info {
    justify-content: center;
    flex-wrap: wrap;
  }

  .hero-stats {
    justify-content: center;
  }

  .actions-grid {
    grid-template-columns: 1fr;
  }

  .teams-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 480px) {
  .club-logo-img,
  .club-logo-placeholder {
    width: 100px;
    height: 100px;
  }

  .club-name {
    font-size: 24px;
  }

  .hero-stats {
    gap: 20px;
  }

  .hero-stat .stat-number {
    font-size: 22px;
  }
}
</style>
