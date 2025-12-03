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
          <span v-if="emailError" class="field-error">{{ emailError }}</span>
        </div>
      </div>
      <div class="modal-footer">
        <button class="cancel-btn" @click="showEditProfile = false">
          Cancel
        </button>
        <button
          class="save-btn"
          @click="saveProfile"
          :disabled="saving || emailError"
        >
          {{ saving ? 'Saving...' : 'Save Changes' }}
        </button>
      </div>
    </div>
  </div>

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

        <div v-if="club?.city" class="location-line">{{ club.city }}</div>

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

        <div class="hero-actions">
          <button class="action-btn primary" @click="goToManageClub">
            Manage Club
          </button>
          <button class="action-btn secondary" @click="openEditProfile">
            Edit Profile
          </button>
        </div>
      </div>
    </div>

    <!-- What You Can Do Section -->
    <div class="capabilities-section">
      <h3>What You Can Do</h3>
      <p class="section-description">
        As a club manager, you have full control over your club's teams,
        matches, and members. Click below or use the
        <strong>Manage Club</strong> tab above to access these features.
      </p>
      <div class="capabilities-grid">
        <div class="capability-card" @click="goToManageClub">
          <div class="capability-icon">&#128236;</div>
          <div class="capability-content">
            <h4>Invite Members</h4>
            <p>
              Invite team managers, players, and parents to join your club on
              Missing Table.
            </p>
          </div>
          <div class="capability-arrow">&rarr;</div>
        </div>

        <div class="capability-card" @click="goToManageClub">
          <div class="capability-icon">&#9917;</div>
          <div class="capability-content">
            <h4>Manage Teams</h4>
            <p>
              Add new teams, edit team details, and assign teams to leagues and
              divisions.
            </p>
          </div>
          <div class="capability-arrow">&rarr;</div>
        </div>

        <div class="capability-card" @click="goToManageClub">
          <div class="capability-icon">&#128197;</div>
          <div class="capability-content">
            <h4>Manage Matches</h4>
            <p>
              Add match results, update scores, and manage your teams' game
              schedules.
            </p>
          </div>
          <div class="capability-arrow">&rarr;</div>
        </div>

        <div class="capability-card" @click="goToManageClub">
          <div class="capability-icon">&#128101;</div>
          <div class="capability-content">
            <h4>Manage Players</h4>
            <p>
              View player rosters, assign players to teams, and manage player
              information.
            </p>
          </div>
          <div class="capability-arrow">&rarr;</div>
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
import { ref, reactive, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';

export default {
  name: 'ClubManagerProfile',
  emits: ['logout', 'switch-tab'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const clubTeams = ref([]);
    const showEditProfile = ref(false);
    const saving = ref(false);
    const emailError = ref('');

    const goToManageClub = () => {
      emit('switch-tab', 'admin');
    };

    const editForm = reactive({
      display_name: '',
      email: '',
    });

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

    const initEditForm = () => {
      editForm.display_name = authStore.state.profile?.display_name || '';
      editForm.email = authStore.state.profile?.email || '';
      emailError.value = '';
    };

    const openEditProfile = () => {
      initEditForm();
      showEditProfile.value = true;
    };

    const validateEmail = () => {
      emailError.value = '';
      if (!editForm.email || editForm.email.trim() === '') {
        return true; // Empty email is OK
      }
      const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
      if (!emailPattern.test(editForm.email)) {
        emailError.value = 'Please enter a valid email address';
        return false;
      }
      return true;
    };

    const saveProfile = async () => {
      if (!validateEmail()) return;

      try {
        saving.value = true;
        await authStore.apiRequest(`${getApiBaseUrl()}/api/auth/profile`, {
          method: 'PUT',
          body: JSON.stringify({
            display_name: editForm.display_name || null,
            email: editForm.email || null,
          }),
        });
        await authStore.fetchProfile();
        showEditProfile.value = false;
      } catch (error) {
        console.error('Error saving profile:', error);
      } finally {
        saving.value = false;
      }
    };

    const fetchClubTeams = async () => {
      const clubId = authStore.state.profile?.club_id;
      if (!clubId) return;

      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/clubs/${clubId}/teams`
        );
        clubTeams.value = response || [];
      } catch (error) {
        console.error('Error fetching club teams:', error);
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
      initEditForm();
    });

    return {
      authStore,
      club,
      clubTeams,
      displayName,
      clubColors,
      heroCardStyle,
      totalMatches,
      totalPlayers,
      formatDate,
      handleLogout,
      goToManageClub,
      showEditProfile,
      openEditProfile,
      editForm,
      emailError,
      saving,
      saveProfile,
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
  background-color: #6b7280;
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
  background-color: #4b5563;
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
  object-fit: contain;
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
  margin-top: 12px;
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

.hero-actions {
  margin-top: auto;
  padding-top: 12px;
  display: flex;
  gap: 12px;
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

/* Capabilities Section */
.capabilities-section {
  margin-bottom: 24px;
}

.capabilities-section h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.section-description {
  color: #6b7280;
  font-size: 14px;
  margin: 0 0 16px 0;
  line-height: 1.5;
}

.capabilities-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.capability-card {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px;
  background: white;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  text-decoration: none;
  color: inherit;
  transition: all 0.2s;
  cursor: pointer;
}

.capability-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
  transform: translateY(-2px);
}

.capability-icon {
  font-size: 28px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f9ff;
  border-radius: 10px;
  flex-shrink: 0;
}

.capability-content {
  flex: 1;
}

.capability-content h4 {
  margin: 0 0 6px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.capability-content p {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.4;
}

.capability-arrow {
  font-size: 20px;
  color: #9ca3af;
  transition: transform 0.2s;
  align-self: center;
}

.capability-card:hover .capability-arrow {
  transform: translateX(4px);
  color: #3b82f6;
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

/* Modal Styles */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  z-index: 1000;
  overflow-y: auto;
  padding: 60px 20px;
}

.edit-modal {
  width: 100%;
  max-width: 440px;
  background: white;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
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
  padding: 0;
  line-height: 1;
}

.close-btn:hover {
  color: #1f2937;
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

.form-group input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
}

.form-group input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.field-error {
  display: block;
  font-size: 12px;
  color: #dc2626;
  margin-top: 4px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #e5e7eb;
  background: #f9fafb;
}

.cancel-btn {
  padding: 10px 20px;
  background: white;
  color: #374151;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-weight: 500;
  font-size: 14px;
  cursor: pointer;
  white-space: nowrap;
}

.cancel-btn:hover {
  background: #f3f4f6;
}

.save-btn {
  padding: 10px 20px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  font-size: 14px;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background-color 0.2s ease,
    opacity 0.2s ease;
}

.save-btn:hover:not(:disabled) {
  background: #2563eb;
}

.save-btn:disabled {
  background: #9ca3af;
  cursor: not-allowed;
  opacity: 0.7;
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

  .hero-actions {
    display: flex;
    justify-content: center;
  }

  .capabilities-grid {
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
