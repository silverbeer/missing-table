<template>
  <div class="admin-panel" data-testid="admin-panel">
    <!-- Admin Access Check -->
    <div
      v-if="!authStore.isAdmin.value && !authStore.isClubManager.value"
      class="text-center py-12"
      data-testid="admin-access-denied"
    >
      <div class="max-w-md mx-auto">
        <div class="text-red-600 text-6xl mb-4">🚫</div>
        <h2 class="text-2xl font-bold text-gray-900 mb-2">Access Denied</h2>
        <p class="text-gray-600">
          You need administrator privileges to access this page.
        </p>
      </div>
    </div>

    <!-- Admin Content (only for admins) -->
    <div v-else>
      <!-- Admin Description -->
      <div class="mb-6">
        <p class="text-gray-600">Manage league data and configurations</p>
      </div>

      <!-- Admin Navigation -->
      <div class="mb-8" data-testid="admin-nav">
        <nav
          class="flex space-x-1 bg-gray-100 p-1 rounded-lg"
          aria-label="Admin sections"
        >
          <button
            v-for="section in adminSections"
            :key="section.id"
            @click="currentSection = section.id"
            :data-testid="`admin-tab-${section.id}`"
            :class="[
              currentSection === section.id
                ? 'bg-white text-gray-900 shadow'
                : 'text-gray-600 hover:text-gray-900',
              'px-4 py-2 text-sm font-medium rounded-md transition-colors',
            ]"
          >
            {{ section.name }}
          </button>
        </nav>
      </div>

      <!-- Section Content -->
      <div
        class="bg-white rounded-lg shadow-sm border border-gray-200"
        data-testid="admin-content"
      >
        <!-- Invite Requests Management -->
        <div
          v-if="currentSection === 'invite-requests'"
          class="p-6"
          data-testid="admin-section-invite-requests"
        >
          <AdminInviteRequests />
        </div>

        <!-- Age Groups Management -->
        <div
          v-if="currentSection === 'age-groups'"
          class="p-6"
          data-testid="admin-section-age-groups"
        >
          <AdminAgeGroups />
        </div>

        <!-- Seasons Management -->
        <div
          v-if="currentSection === 'seasons'"
          class="p-6"
          data-testid="admin-section-seasons"
        >
          <AdminSeasons />
        </div>

        <!-- Leagues Management -->
        <div
          v-if="currentSection === 'leagues'"
          class="p-6"
          data-testid="admin-section-leagues"
        >
          <AdminLeagues />
        </div>

        <!-- Divisions Management -->
        <div
          v-if="currentSection === 'divisions'"
          class="p-6"
          data-testid="admin-section-divisions"
        >
          <AdminDivisions />
        </div>

        <!-- Clubs Management -->
        <div
          v-if="currentSection === 'clubs'"
          class="p-6"
          data-testid="admin-section-clubs"
        >
          <AdminClubs />
        </div>

        <!-- Teams Management -->
        <div
          v-if="currentSection === 'teams'"
          class="p-6"
          data-testid="admin-section-teams"
        >
          <AdminTeams />
        </div>

        <!-- Players Management -->
        <div
          v-if="currentSection === 'players'"
          class="p-6"
          data-testid="admin-section-players"
        >
          <AdminPlayers />
        </div>

        <!-- Matches Management -->
        <div
          v-if="currentSection === 'matches'"
          class="p-6"
          data-testid="admin-section-matches"
        >
          <AdminMatches />
        </div>

        <!-- Goals Management -->
        <div
          v-if="currentSection === 'goals'"
          class="p-6"
          data-testid="admin-section-goals"
        >
          <AdminGoals />
        </div>

        <!-- Playoffs Management -->
        <div
          v-if="currentSection === 'playoffs'"
          class="p-6"
          data-testid="admin-section-playoffs"
        >
          <AdminPlayoffs />
        </div>

        <!-- Invites Management -->
        <div
          v-if="currentSection === 'invites'"
          class="p-6"
          data-testid="admin-section-invites"
        >
          <AdminInvites />
        </div>

        <!-- Cache Management -->
        <div
          v-if="currentSection === 'cache'"
          class="p-6"
          data-testid="admin-section-cache"
        >
          <AdminCache />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue';
import { useAuthStore } from '@/stores/auth';
import AdminAgeGroups from './admin/AdminAgeGroups.vue';
import AdminSeasons from './admin/AdminSeasons.vue';
import AdminLeagues from './admin/AdminLeagues.vue';
import AdminDivisions from './admin/AdminDivisions.vue';
import AdminClubs from './admin/AdminClubs.vue';
import AdminTeams from './admin/AdminTeams.vue';
import AdminPlayers from './admin/AdminPlayers.vue';
import AdminMatches from './admin/AdminMatches.vue';
import AdminGoals from './admin/AdminGoals.vue';
import AdminInvites from './admin/AdminInvites.vue';
import AdminInviteRequests from './admin/AdminInviteRequests.vue';
import AdminPlayoffs from './admin/AdminPlayoffs.vue';
import AdminCache from './admin/AdminCache.vue';

export default {
  name: 'AdminPanel',
  components: {
    AdminAgeGroups,
    AdminSeasons,
    AdminLeagues,
    AdminDivisions,
    AdminClubs,
    AdminTeams,
    AdminPlayers,
    AdminMatches,
    AdminGoals,
    AdminInvites,
    AdminInviteRequests,
    AdminPlayoffs,
    AdminCache,
  },
  setup() {
    const authStore = useAuthStore();
    const currentSection = ref('invite-requests');

    // Define all sections with role requirements
    const allAdminSections = [
      { id: 'invite-requests', name: 'Requests', adminOnly: true },
      { id: 'age-groups', name: 'Age Groups', adminOnly: true },
      { id: 'seasons', name: 'Seasons', adminOnly: true },
      { id: 'leagues', name: 'Leagues', adminOnly: true },
      { id: 'divisions', name: 'Divisions', adminOnly: true },
      { id: 'clubs', name: 'Clubs', adminOnly: true },
      { id: 'teams', name: 'Teams', adminOnly: false },
      { id: 'players', name: 'Players', adminOnly: false },
      { id: 'matches', name: 'Matches', adminOnly: false },
      { id: 'goals', name: 'Goals', adminOnly: false },
      { id: 'playoffs', name: 'Playoffs', adminOnly: true },
      { id: 'invites', name: 'Invites', adminOnly: false },
      { id: 'cache', name: 'Cache', adminOnly: true },
    ];

    // Filter sections based on user role
    const adminSections = computed(() => {
      if (authStore.isAdmin.value) {
        return allAdminSections;
      }
      // Club managers only see Teams, Matches, Invites
      return allAdminSections.filter(section => !section.adminOnly);
    });

    // Update current section when role changes
    if (
      !authStore.isAdmin.value &&
      currentSection.value === 'invite-requests'
    ) {
      currentSection.value = 'teams';
    }

    return {
      authStore,
      currentSection,
      adminSections,
    };
  },
};
</script>

<style scoped>
.admin-panel {
  max-width: 1200px;
  margin: 0 auto;
}
</style>
