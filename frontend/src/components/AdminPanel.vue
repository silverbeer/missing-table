<template>
  <div class="admin-panel">
    <!-- Admin Access Check -->
    <div v-if="!authStore.isAdmin.value" class="text-center py-12">
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
      <div class="mb-8">
        <nav
          class="flex space-x-1 bg-gray-100 p-1 rounded-lg"
          aria-label="Admin sections"
        >
          <button
            v-for="section in adminSections"
            :key="section.id"
            @click="currentSection = section.id"
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
      <div class="bg-white rounded-lg shadow-sm border border-gray-200">
        <!-- Invite Requests Management -->
        <div v-if="currentSection === 'invite-requests'" class="p-6">
          <AdminInviteRequests />
        </div>

        <!-- Age Groups Management -->
        <div v-if="currentSection === 'age-groups'" class="p-6">
          <AdminAgeGroups />
        </div>

        <!-- Seasons Management -->
        <div v-if="currentSection === 'seasons'" class="p-6">
          <AdminSeasons />
        </div>

        <!-- Leagues Management -->
        <div v-if="currentSection === 'leagues'" class="p-6">
          <AdminLeagues />
        </div>

        <!-- Divisions Management -->
        <div v-if="currentSection === 'divisions'" class="p-6">
          <AdminDivisions />
        </div>

        <!-- Clubs Management -->
        <div v-if="currentSection === 'clubs'" class="p-6">
          <AdminClubs />
        </div>

        <!-- Teams Management -->
        <div v-if="currentSection === 'teams'" class="p-6">
          <AdminTeams />
        </div>

        <!-- Matches Management -->
        <div v-if="currentSection === 'matches'" class="p-6">
          <AdminMatches />
        </div>

        <!-- Invites Management -->
        <div v-if="currentSection === 'invites'" class="p-6">
          <AdminInvites />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue';
import { useAuthStore } from '@/stores/auth';
import AdminAgeGroups from './admin/AdminAgeGroups.vue';
import AdminSeasons from './admin/AdminSeasons.vue';
import AdminLeagues from './admin/AdminLeagues.vue';
import AdminDivisions from './admin/AdminDivisions.vue';
import AdminClubs from './admin/AdminClubs.vue';
import AdminTeams from './admin/AdminTeams.vue';
import AdminMatches from './admin/AdminMatches.vue';
import AdminInvites from './admin/AdminInvites.vue';
import AdminInviteRequests from './admin/AdminInviteRequests.vue';

export default {
  name: 'AdminPanel',
  components: {
    AdminAgeGroups,
    AdminSeasons,
    AdminLeagues,
    AdminDivisions,
    AdminClubs,
    AdminTeams,
    AdminMatches,
    AdminInvites,
    AdminInviteRequests,
  },
  setup() {
    const authStore = useAuthStore();
    const currentSection = ref('invite-requests');

    const adminSections = [
      { id: 'invite-requests', name: 'Requests' },
      { id: 'age-groups', name: 'Age Groups' },
      { id: 'seasons', name: 'Seasons' },
      { id: 'leagues', name: 'Leagues' },
      { id: 'divisions', name: 'Divisions' },
      { id: 'clubs', name: 'Clubs' },
      { id: 'teams', name: 'Teams' },
      { id: 'matches', name: 'Matches' },
      { id: 'invites', name: 'Invites' },
    ];

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
