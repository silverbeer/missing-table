<template>
  <div class="team-roster-router">
    <!-- Loading state -->
    <div v-if="authStore.state.loading" class="loading-state">
      <div class="loading-spinner"></div>
      <p>Loading...</p>
    </div>

    <!-- Not authenticated -->
    <div v-else-if="!authStore.isAuthenticated" class="not-authenticated">
      <h3>Authentication Required</h3>
      <p>Please log in to view your team.</p>
    </div>

    <!-- No stake in any squad -->
    <div v-else-if="!canSeeTeamPage" class="not-player">
      <div class="info-icon">
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
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </div>
      <h3>No Squad Access</h3>
      <p>
        The team page is available to players, team and club managers, and fans
        of a club.
      </p>
    </div>

    <!-- No team assigned -->
    <div v-else-if="!hasTeam" class="no-team">
      <div class="info-icon">
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
            d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
          />
        </svg>
      </div>
      <h3>No Team Assigned</h3>
      <p>You need to be assigned to a team to view the roster.</p>
      <p class="sub-text">
        Contact your team manager or administrator to get assigned.
      </p>
    </div>

    <!-- Router content -->
    <div v-else class="router-content">
      <!-- Player Detail View -->
      <PlayerDetailView
        v-if="selectedPlayerId"
        :playerId="selectedPlayerId"
        @back="selectedPlayerId = null"
      />

      <!-- Team Roster Page -->
      <TeamRosterPage v-else @viewPlayer="handleViewPlayer" />
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { hasAnyRole, TEAM_PAGE_ROLES } from '@/utils/roles';
import TeamRosterPage from './TeamRosterPage.vue';
import PlayerDetailView from './PlayerDetailView.vue';

export default {
  name: 'TeamRosterRouter',
  components: {
    TeamRosterPage,
    PlayerDetailView,
  },
  setup() {
    const authStore = useAuthStore();
    const selectedPlayerId = ref(null);

    // Get user role from profile
    const userRole = computed(() => {
      return authStore.state.profile?.role || 'team-fan';
    });

    // The same list App.vue gates the tab on. Kept in one place because these
    // two checks drifted apart once already: the tab appeared and the page
    // behind it said "Players Only" (SB-668).
    const canSeeTeamPage = computed(() =>
      hasAnyRole(TEAM_PAGE_ROLES, userRole.value)
    );

    // Admins belong to no squad and no club by design, not by omission, so
    // every affiliation check below is false for them. Without this they get
    // "No Team Assigned" and no way forward — the one role meant to see
    // everything ends up with less access than a fan (SB-792). They pick a
    // team on the page instead.
    const canBrowseAnyTeam = computed(() =>
      hasAnyRole(['admin'], userRole.value)
    );

    // A squad to show. A club manager or club fan has no team_id and no player
    // history, but belongs to a club — TeamRosterPage resolves a team from it,
    // so requiring a team here would lock them out of a page built for them.
    const hasTeam = computed(() => {
      if (canBrowseAnyTeam.value) return true;
      const profile = authStore.state.profile;
      return (
        !!profile?.team_id ||
        profile?.current_teams?.length > 0 ||
        !!profile?.club_id
      );
    });

    // Handle clicking on a player card
    const handleViewPlayer = player => {
      selectedPlayerId.value = player.id;
    };

    return {
      authStore,
      selectedPlayerId,
      userRole,
      canSeeTeamPage,
      canBrowseAnyTeam,
      hasTeam,
      handleViewPlayer,
    };
  },
};
</script>

<style scoped>
.team-roster-router {
  min-height: 100vh;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #e5e7eb;
  border-top: 4px solid #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

.loading-state p {
  color: rgb(var(--color-fg-muted));
  font-size: 16px;
  margin: 0;
}

.not-authenticated,
.not-player,
.no-team {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  background-color: rgb(var(--color-surface-alt));
  border-radius: 12px;
  margin: 20px;
}

.info-icon {
  width: 64px;
  height: 64px;
  background-color: #dbeafe;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.info-icon svg {
  width: 32px;
  height: 32px;
  color: #3b82f6;
}

.not-authenticated h3,
.not-player h3,
.no-team h3 {
  color: rgb(var(--color-fg));
  margin: 0 0 12px 0;
  font-size: 20px;
  font-weight: 600;
}

.not-authenticated p,
.not-player p,
.no-team p {
  color: rgb(var(--color-fg-muted));
  margin: 0;
  font-size: 15px;
}

.sub-text {
  margin-top: 8px !important;
  font-size: 14px !important;
  color: rgb(var(--color-fg-muted)) !important;
}

.router-content {
  min-height: 100vh;
}

/* Responsive */
@media (max-width: 480px) {
  .not-authenticated,
  .not-player,
  .no-team {
    padding: 40px 16px;
    margin: 12px;
  }

  .info-icon {
    width: 56px;
    height: 56px;
  }

  .info-icon svg {
    width: 28px;
    height: 28px;
  }

  .not-authenticated h3,
  .not-player h3,
  .no-team h3 {
    font-size: 18px;
  }

  .not-authenticated p,
  .not-player p,
  .no-team p {
    font-size: 14px;
  }
}
</style>
