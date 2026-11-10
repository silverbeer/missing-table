<template>
  <div data-testid="admin-club-notifications">
    <div class="flex justify-between items-center gap-3 flex-wrap mb-6">
      <h2 class="text-xl font-bold text-fg">Live Match Notifications</h2>
      <div
        v-if="isAdmin"
        class="flex gap-1 text-sm"
        role="tablist"
        data-testid="admin-notifications-scope"
      >
        <button
          v-for="tab in scopeTabs"
          :key="tab.id"
          role="tab"
          :aria-selected="scope === tab.id"
          :class="[
            'px-3 py-1.5 rounded-md border',
            scope === tab.id
              ? 'bg-brand-600 text-white border-brand-600'
              : 'bg-card text-fg border-line',
          ]"
          :data-testid="`scope-${tab.id}`"
          @click="scope = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <ChannelManager
      v-if="isAdmin && scope === 'global'"
      scope-type="global"
      heading="Every match"
    />

    <template v-else>
      <!-- Admins pick a club; club_managers are auto-scoped to their own -->
      <div v-if="isAdmin" class="flex items-center gap-3 mb-4">
        <label class="text-sm text-fg-muted" for="club-picker">Club:</label>
        <select
          id="club-picker"
          v-model.number="selectedClubId"
          data-testid="admin-notifications-club-picker"
          class="px-3 py-2 bg-card text-fg border border-line rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option :value="null" disabled>Select a club…</option>
          <option v-for="c in clubs" :key="c.id" :value="c.id">
            {{ c.name }}
          </option>
        </select>
      </div>

      <div v-if="loadingClubs" class="text-sm text-fg-muted">
        Loading clubs…
      </div>

      <div
        v-else-if="!isAdmin && !selectedClubId"
        class="bg-yellow-50 border border-yellow-200 rounded-md p-4 text-sm text-yellow-800 dark:bg-yellow-500/10 dark:border-yellow-500/30 dark:text-yellow-200"
        data-testid="no-club-assigned"
      >
        No club is assigned to your account. Contact an administrator to have
        one assigned before configuring notifications.
      </div>

      <div v-else-if="selectedClubId">
        <ChannelManager scope-type="club" :club-id="selectedClubId" />
        <p class="text-sm text-fg-muted mt-4">
          Squad channels (one age group) are set up from that team's page.
        </p>
      </div>

      <div v-else class="text-sm text-fg-muted" data-testid="no-club-selected">
        Select a club to configure its notification channels.
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import ChannelManager from '@/components/notifications/ChannelManager.vue';

const authStore = useAuthStore();

const isAdmin = computed(() => authStore.isAdmin.value);
const ownClubId = computed(() => authStore.state.profile?.club_id ?? null);

const clubs = ref([]);
const loadingClubs = ref(false);
const selectedClubId = ref(null);

const scopeTabs = [
  { id: 'club', label: 'One club' },
  { id: 'global', label: 'Every match' },
];
const scope = ref('club');

const fetchClubs = async () => {
  loadingClubs.value = true;
  try {
    const resp = await fetch(`${getApiBaseUrl()}/api/clubs`, {
      headers: authStore.getAuthHeaders(),
    });
    if (resp.ok) {
      clubs.value = await resp.json();
    }
  } finally {
    loadingClubs.value = false;
  }
};

onMounted(async () => {
  if (isAdmin.value) {
    await fetchClubs();
  } else {
    selectedClubId.value = ownClubId.value;
  }
});
</script>
