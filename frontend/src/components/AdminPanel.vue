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
      <div class="mb-6 sm:mb-8" data-testid="admin-nav">
        <!-- Mobile: native select grouped by category -->
        <label for="admin-section-select" class="sr-only">Admin section</label>
        <select
          id="admin-section-select"
          v-model="currentSection"
          data-testid="admin-section-select"
          class="sm:hidden block w-full px-3 py-2.5 text-base font-medium bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
        >
          <optgroup
            v-for="category in adminCategories"
            :key="category.id"
            :label="category.name"
          >
            <option
              v-for="section in category.sections"
              :key="section.id"
              :value="section.id"
            >
              {{ section.name }}
            </option>
          </optgroup>
        </select>

        <!-- Desktop: two-level tab bar (categories + sub-tabs) -->
        <div class="hidden sm:block space-y-2" aria-label="Admin sections">
          <nav
            class="flex flex-wrap gap-1 bg-gray-100 p-1 rounded-lg"
            aria-label="Admin categories"
          >
            <button
              v-for="category in adminCategories"
              :key="category.id"
              @click="selectCategory(category.id)"
              :data-testid="`admin-category-${category.id}`"
              :class="[
                currentCategory === category.id
                  ? 'bg-white text-gray-900 shadow'
                  : 'text-gray-600 hover:text-gray-900',
                'px-4 py-2 text-sm font-medium rounded-md transition-colors whitespace-nowrap',
              ]"
            >
              {{ category.name }}
            </button>
          </nav>
          <nav
            v-if="currentCategorySections.length > 1"
            class="flex flex-wrap gap-1 px-1"
            aria-label="Admin sub-sections"
          >
            <button
              v-for="section in currentCategorySections"
              :key="section.id"
              @click="currentSection = section.id"
              :data-testid="`admin-tab-${section.id}`"
              :class="[
                currentSection === section.id
                  ? 'text-brand-700 border-brand-500'
                  : 'text-gray-500 hover:text-gray-800 border-transparent hover:border-gray-300',
                'px-3 py-1.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
              ]"
            >
              {{ section.name }}
            </button>
          </nav>
        </div>
      </div>

      <!-- Section Content -->
      <div
        class="bg-white rounded-lg shadow-sm border border-gray-200"
        data-testid="admin-content"
      >
        <!-- Invite Requests Management -->
        <div
          v-if="currentSection === 'invite-requests'"
          class="p-3 sm:p-6"
          data-testid="admin-section-invite-requests"
        >
          <AdminInviteRequests />
        </div>

        <!-- Channel Access Requests -->
        <div
          v-if="currentSection === 'channel-requests'"
          class="p-3 sm:p-6"
          data-testid="admin-section-channel-requests"
        >
          <AdminChannelRequests />
        </div>

        <!-- Live Match Notifications (per-club Telegram/Discord) -->
        <div
          v-if="currentSection === 'club-notifications'"
          class="p-3 sm:p-6"
          data-testid="admin-section-club-notifications"
        >
          <AdminClubNotifications />
        </div>

        <!-- Age Groups Management -->
        <div
          v-if="currentSection === 'age-groups'"
          class="p-3 sm:p-6"
          data-testid="admin-section-age-groups"
        >
          <AdminAgeGroups />
        </div>

        <!-- Seasons Management -->
        <div
          v-if="currentSection === 'seasons'"
          class="p-3 sm:p-6"
          data-testid="admin-section-seasons"
        >
          <AdminSeasons />
        </div>

        <!-- Leagues Management -->
        <div
          v-if="currentSection === 'leagues'"
          class="p-3 sm:p-6"
          data-testid="admin-section-leagues"
        >
          <AdminLeagues />
        </div>

        <!-- Divisions Management -->
        <div
          v-if="currentSection === 'divisions'"
          class="p-3 sm:p-6"
          data-testid="admin-section-divisions"
        >
          <AdminDivisions />
        </div>

        <!-- Clubs Management -->
        <div
          v-if="currentSection === 'clubs'"
          class="p-3 sm:p-6"
          data-testid="admin-section-clubs"
        >
          <AdminClubs />
        </div>

        <!-- Teams Management -->
        <div
          v-if="currentSection === 'teams'"
          class="p-3 sm:p-6"
          data-testid="admin-section-teams"
        >
          <AdminTeams />
        </div>

        <!-- Players Management -->
        <div
          v-if="currentSection === 'players'"
          class="p-3 sm:p-6"
          data-testid="admin-section-players"
        >
          <AdminPlayers />
        </div>

        <!-- Matches Management -->
        <div
          v-if="currentSection === 'matches'"
          class="p-3 sm:p-6"
          data-testid="admin-section-matches"
        >
          <AdminMatches />
        </div>

        <!-- Goals Management -->
        <div
          v-if="currentSection === 'goals'"
          class="p-3 sm:p-6"
          data-testid="admin-section-goals"
        >
          <AdminGoals />
        </div>

        <!-- Playoffs Management -->
        <div
          v-if="currentSection === 'playoffs'"
          class="p-3 sm:p-6"
          data-testid="admin-section-playoffs"
        >
          <AdminPlayoffs />
        </div>

        <!-- Invites Management -->
        <div
          v-if="currentSection === 'invites'"
          class="p-3 sm:p-6"
          data-testid="admin-section-invites"
        >
          <AdminInvites />
        </div>

        <!-- Tournaments Management -->
        <div
          v-if="currentSection === 'tournaments'"
          class="p-3 sm:p-6"
          data-testid="admin-section-tournaments"
        >
          <AdminTournaments />
        </div>

        <!-- Cache Management -->
        <div
          v-if="currentSection === 'cache'"
          class="p-3 sm:p-6"
          data-testid="admin-section-cache"
        >
          <AdminCache />
        </div>

        <!-- Users / Login Activity -->
        <div
          v-if="currentSection === 'users'"
          class="p-3 sm:p-6"
          data-testid="admin-section-users"
        >
          <AdminUsers />
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
import AdminChannelRequests from './admin/AdminChannelRequests.vue';
import AdminClubNotifications from './admin/AdminClubNotifications.vue';
import AdminInviteRequests from './admin/AdminInviteRequests.vue';
import AdminPlayoffs from './admin/AdminPlayoffs.vue';
import AdminCache from './admin/AdminCache.vue';
import AdminUsers from './admin/AdminUsers.vue';
import AdminTournaments from './admin/AdminTournaments.vue';

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
    AdminChannelRequests,
    AdminClubNotifications,
    AdminInviteRequests,
    AdminPlayoffs,
    AdminCache,
    AdminUsers,
    AdminTournaments,
  },
  setup() {
    const authStore = useAuthStore();

    // Define all sections with role requirements + category assignment.
    // Categories drive the two-level desktop tab bar (SB-7). Mobile still
    // renders a single flat <select> grouped by <optgroup>.
    const allAdminSections = [
      {
        id: 'invite-requests',
        name: 'Requests',
        adminOnly: true,
        category: 'access',
      },
      {
        id: 'channel-requests',
        name: 'Channel Requests',
        adminOnly: false,
        category: 'access',
      },
      {
        id: 'club-notifications',
        name: 'Live Match Notifications',
        adminOnly: false,
        category: 'access',
      },
      { id: 'invites', name: 'Invites', adminOnly: false, category: 'access' },
      {
        id: 'age-groups',
        name: 'Age Groups',
        adminOnly: true,
        category: 'league-setup',
      },
      {
        id: 'seasons',
        name: 'Seasons',
        adminOnly: true,
        category: 'league-setup',
      },
      {
        id: 'leagues',
        name: 'Leagues',
        adminOnly: true,
        category: 'league-setup',
      },
      {
        id: 'divisions',
        name: 'Divisions',
        adminOnly: true,
        category: 'league-setup',
      },
      {
        id: 'clubs',
        name: 'Clubs',
        adminOnly: true,
        category: 'teams-players',
      },
      {
        id: 'teams',
        name: 'Teams',
        adminOnly: false,
        category: 'teams-players',
      },
      {
        id: 'players',
        name: 'Players',
        adminOnly: false,
        category: 'teams-players',
      },
      { id: 'matches', name: 'Matches', adminOnly: false, category: 'matches' },
      { id: 'goals', name: 'Goals', adminOnly: false, category: 'matches' },
      {
        id: 'playoffs',
        name: 'Playoffs',
        adminOnly: true,
        category: 'matches',
      },
      {
        id: 'tournaments',
        name: 'Tournaments',
        adminOnly: true,
        category: 'matches',
      },
      { id: 'cache', name: 'Cache', adminOnly: true, category: 'system' },
      { id: 'users', name: 'Users', adminOnly: true, category: 'system' },
    ];

    const categoryDefs = [
      { id: 'access', name: 'Access' },
      { id: 'league-setup', name: 'League Setup' },
      { id: 'teams-players', name: 'Teams & Players' },
      { id: 'matches', name: 'Matches' },
      { id: 'system', name: 'System' },
    ];

    // Sections visible to the current user (role filter).
    const adminSections = computed(() => {
      if (authStore.isAdmin.value) {
        return allAdminSections;
      }
      // Club managers only see non-adminOnly sections.
      return allAdminSections.filter(section => !section.adminOnly);
    });

    // Categories that have at least one visible section for this role.
    // Each carries its filtered sections list for the second-row sub-tabs.
    const adminCategories = computed(() => {
      const visible = adminSections.value;
      return categoryDefs
        .map(cat => ({
          ...cat,
          sections: visible.filter(s => s.category === cat.id),
        }))
        .filter(cat => cat.sections.length > 0);
    });

    // Default to the first section the user can actually see.
    const initialSection = adminSections.value[0]?.id || 'teams';
    const currentSection = ref(initialSection);

    const currentCategory = computed(() => {
      const section = allAdminSections.find(s => s.id === currentSection.value);
      return section?.category || adminCategories.value[0]?.id;
    });

    const currentCategorySections = computed(() => {
      const cat = adminCategories.value.find(
        c => c.id === currentCategory.value
      );
      return cat?.sections || [];
    });

    const selectCategory = catId => {
      const cat = adminCategories.value.find(c => c.id === catId);
      if (cat && cat.sections.length > 0) {
        currentSection.value = cat.sections[0].id;
      }
    };

    return {
      authStore,
      currentSection,
      currentCategory,
      adminSections,
      adminCategories,
      currentCategorySections,
      selectCategory,
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
