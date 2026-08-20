<template>
  <div class="admin-users">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-xl font-semibold text-fg">User Login Activity</h2>
      <button
        @click="activeTab === 'users' ? fetchUsers() : fetchLoginEvents()"
        :disabled="loading"
        class="px-3 py-1.5 text-sm bg-surface-alt text-fg-muted rounded hover:bg-line disabled:opacity-50"
      >
        {{ loading ? 'Loading...' : 'Refresh' }}
      </button>
    </div>

    <!-- Error -->
    <div
      v-if="error"
      class="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm"
    >
      {{ error }}
    </div>

    <!-- Tabs -->
    <div class="mb-4 border-b border-line">
      <nav class="flex space-x-4">
        <button
          @click="
            activeTab = 'users';
            fetchUsers();
          "
          :class="[
            activeTab === 'users'
              ? 'border-b-2 border-brand-600 text-brand-600 dark:border-brand-300 dark:text-brand-300'
              : 'text-fg-muted hover:text-fg',
            'pb-2 text-sm font-medium',
          ]"
        >
          Users ({{ userTotal }})
        </button>
        <button
          @click="
            activeTab = 'events';
            fetchLoginEvents();
          "
          :class="[
            activeTab === 'events'
              ? 'border-b-2 border-brand-600 text-brand-600 dark:border-brand-300 dark:text-brand-300'
              : 'text-fg-muted hover:text-fg',
            'pb-2 text-sm font-medium',
          ]"
        >
          Login History ({{ eventTotal }})
        </button>
      </nav>
    </div>

    <!-- Users Tab -->
    <div v-if="activeTab === 'users'">
      <div v-if="loading" class="text-center py-8 text-fg-muted">
        Loading users...
      </div>
      <div
        v-else-if="users.length === 0"
        class="text-center py-8 text-fg-muted"
      >
        No users found.
      </div>
      <div v-else class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead>
            <tr class="text-left text-fg-muted border-b border-line">
              <th class="pb-2 pr-4 font-medium">Username</th>
              <th class="pb-2 pr-4 font-medium">Display Name</th>
              <th class="pb-2 pr-4 font-medium">Role</th>
              <th class="pb-2 pr-4 font-medium">Team</th>
              <th class="pb-2 pr-4 font-medium">Club</th>
              <th class="pb-2 pr-4 font-medium">Last Login</th>
              <th class="pb-2 pr-4 font-medium">Joined</th>
              <th class="pb-2 font-medium">
                <span class="sr-only">Edit</span>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-line">
            <tr
              v-for="user in users"
              :key="user.id"
              class="hover:bg-surface-alt"
            >
              <td class="py-2 pr-4 font-mono text-fg">
                {{ user.username }}
              </td>
              <td class="py-2 pr-4 text-fg-muted">
                {{ user.display_name || '—' }}
              </td>
              <td class="py-2 pr-4">
                <span :class="roleBadgeClass(user.role)">{{
                  user.role || 'user'
                }}</span>
              </td>
              <!-- SB-803: affiliation was in the payload all along but never
                   shown, so an account named for a club and attached to
                   nothing looked identical to a correct one. -->
              <td class="py-2 pr-4" :class="affiliationClass(user, 'team')">
                {{
                  user.team_name || (user.team_id ? `#${user.team_id}` : '—')
                }}
              </td>
              <td class="py-2 pr-4" :class="affiliationClass(user, 'club')">
                {{
                  user.club_name || (user.club_id ? `#${user.club_id}` : '—')
                }}
              </td>
              <td class="py-2 pr-4 text-fg-muted">
                <span v-if="user.last_login_at">
                  <span
                    :class="
                      user.last_login_success
                        ? 'text-green-600'
                        : 'text-red-500'
                    "
                    class="mr-1"
                    >{{ user.last_login_success ? '✓' : '✗' }}</span
                  >
                  {{ formatDate(user.last_login_at) }}
                </span>
                <span v-else class="text-fg-muted italic">Never</span>
              </td>
              <td class="py-2 pr-4 text-fg-muted">
                {{ formatDate(user.created_at) }}
              </td>
              <td class="py-2">
                <button
                  type="button"
                  class="px-2.5 py-1 text-xs font-medium rounded border border-line hover:bg-surface-alt"
                  :data-testid="`edit-user-${user.username}`"
                  @click="openEditor(user)"
                >
                  Edit
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- SB-803: edit sheet. Full-screen on small viewports on purpose —
             this gets used one-handed at a match, where an inline row edit is
             unusable. -->
        <div
          v-if="editing"
          class="fixed inset-0 z-50 flex sm:items-center sm:justify-center bg-black/50"
          data-testid="user-editor"
          @click.self="closeEditor"
        >
          <div
            class="bg-card w-full h-full sm:h-auto sm:max-w-md sm:rounded-xl p-5 overflow-y-auto flex flex-col gap-4"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <h3 class="text-lg font-semibold text-fg">
                  {{ editing.username }}
                </h3>
                <p class="text-xs text-fg-muted">
                  {{ editing.display_name || 'No display name' }}
                </p>
              </div>
              <button
                type="button"
                class="text-fg-muted hover:text-fg text-xl leading-none px-2"
                data-testid="user-editor-close"
                aria-label="Close"
                @click="closeEditor"
              >
                &times;
              </button>
            </div>

            <label class="flex flex-col gap-1">
              <span
                class="text-xs font-medium text-fg-muted uppercase tracking-wide"
                >Role</span
              >
              <select
                v-model="form.role"
                data-testid="edit-role"
                class="px-3 py-2.5 rounded-lg border border-line bg-surface text-fg"
              >
                <option v-for="r in ROLE_OPTIONS" :key="r" :value="r">
                  {{ r }}
                </option>
              </select>
            </label>

            <label class="flex flex-col gap-1">
              <span
                class="text-xs font-medium text-fg-muted uppercase tracking-wide"
                >Team</span
              >
              <input
                v-model="teamSearch"
                type="search"
                placeholder="Search teams…"
                data-testid="team-search"
                class="px-3 py-2.5 rounded-lg border border-line bg-surface text-fg"
              />
              <select
                v-model="form.team_id"
                size="5"
                data-testid="edit-team"
                class="px-3 py-2 rounded-lg border border-line bg-surface text-fg"
              >
                <option :value="null">— No team —</option>
                <option v-for="t in filteredTeams" :key="t.id" :value="t.id">
                  {{ t.name }}
                </option>
              </select>
            </label>

            <label class="flex flex-col gap-1">
              <span
                class="text-xs font-medium text-fg-muted uppercase tracking-wide"
                >Club</span
              >
              <select
                v-model="form.club_id"
                data-testid="edit-club"
                class="px-3 py-2.5 rounded-lg border border-line bg-surface text-fg"
              >
                <option :value="null">— No club —</option>
                <option v-for="c in clubs" :key="c.id" :value="c.id">
                  {{ c.name }}
                </option>
              </select>
            </label>

            <p
              v-if="saveError"
              class="text-sm text-red-500"
              data-testid="save-error"
            >
              {{ saveError }}
            </p>

            <div class="flex gap-2 mt-auto sm:mt-2">
              <button
                type="button"
                class="flex-1 px-4 py-2.5 rounded-lg border border-line text-fg"
                @click="closeEditor"
              >
                Cancel
              </button>
              <button
                type="button"
                class="flex-1 px-4 py-2.5 rounded-lg bg-brand-600 text-white font-medium disabled:opacity-50"
                data-testid="save-user"
                :disabled="saving || !isDirty"
                @click="saveUser"
              >
                {{ saving ? 'Saving…' : 'Save' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Login Events Tab -->
    <div v-if="activeTab === 'events'">
      <!-- Filters -->
      <div class="flex flex-wrap gap-3 mb-4">
        <input
          v-model="filterUsername"
          @input="debouncedFetch"
          type="text"
          placeholder="Filter by username..."
          class="px-3 py-1.5 text-sm bg-card text-fg border border-line rounded w-48 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        <select
          v-model="filterSuccess"
          @change="fetchLoginEvents"
          class="px-3 py-1.5 text-sm bg-card text-fg border border-line rounded focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          <option value="">All results</option>
          <option value="true">Success only</option>
          <option value="false">Failures only</option>
        </select>
      </div>

      <div v-if="loading" class="text-center py-8 text-fg-muted">
        Loading events...
      </div>
      <div
        v-else-if="events.length === 0"
        class="text-center py-8 text-fg-muted"
      >
        No login events found.
      </div>
      <div v-else>
        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead>
              <tr class="text-left text-fg-muted border-b border-line">
                <th class="pb-2 pr-4 font-medium">Time</th>
                <th class="pb-2 pr-4 font-medium">Username</th>
                <th class="pb-2 pr-4 font-medium">Result</th>
                <th class="pb-2 pr-4 font-medium">IP Address</th>
                <th class="pb-2 font-medium">Role</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-line">
              <tr
                v-for="ev in events"
                :key="ev.id"
                class="hover:bg-surface-alt"
              >
                <td class="py-2 pr-4 text-fg-muted whitespace-nowrap">
                  {{ formatDate(ev.created_at) }}
                </td>
                <td class="py-2 pr-4 font-mono text-fg">
                  {{ ev.username }}
                </td>
                <td class="py-2 pr-4">
                  <span
                    v-if="ev.success"
                    class="text-green-700 bg-green-50 px-2 py-0.5 rounded text-xs font-medium"
                    >Success</span
                  >
                  <span
                    v-else
                    class="text-red-700 bg-red-50 px-2 py-0.5 rounded text-xs font-medium"
                  >
                    Failed{{
                      ev.failure_reason ? ` (${ev.failure_reason})` : ''
                    }}
                  </span>
                </td>
                <td class="py-2 pr-4 font-mono text-fg-muted text-xs">
                  {{ ev.client_ip || '—' }}
                </td>
                <td class="py-2 text-fg-muted text-xs">{{ ev.role || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div
          class="flex items-center justify-between mt-4 text-sm text-fg-muted"
        >
          <span>Showing {{ events.length }} of {{ eventTotal }} events</span>
          <div class="flex gap-2">
            <button
              @click="prevPage"
              :disabled="currentPage === 0"
              class="px-3 py-1 border border-line rounded disabled:opacity-40 hover:bg-surface-alt"
            >
              Previous
            </button>
            <button
              @click="nextPage"
              :disabled="(currentPage + 1) * pageSize >= eventTotal"
              class="px-3 py-1 border border-line rounded disabled:opacity-40 hover:bg-surface-alt"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';

export default {
  name: 'AdminUsers',
  setup() {
    const authStore = useAuthStore();
    const loading = ref(false);
    const error = ref(null);
    const activeTab = ref('users');

    const users = ref([]);
    const userTotal = ref(0);

    const events = ref([]);
    const eventTotal = ref(0);
    const currentPage = ref(0);
    const pageSize = 100;
    const filterUsername = ref('');
    const filterSuccess = ref('');

    let debounceTimer = null;

    const fetchUsers = async () => {
      loading.value = true;
      error.value = null;
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/users`,
          { method: 'GET' }
        );
        users.value = data.users || [];
        userTotal.value = data.total || 0;
      } catch (err) {
        error.value = err.message || 'Failed to fetch users';
      } finally {
        loading.value = false;
      }
    };

    // --- SB-803: editing ---
    // Written in the hyphen convention; the backend accepts both spellings and
    // roles.js normalizes. Do not introduce a third form here.
    const ROLE_OPTIONS = [
      'admin',
      'club_manager',
      'club-fan',
      'team-manager',
      'team-player',
      'team-fan',
    ];

    const editing = ref(null);
    const form = ref({ role: null, team_id: null, club_id: null });
    const saving = ref(false);
    const saveError = ref(null);
    const teams = ref([]);
    const clubs = ref([]);
    const teamSearch = ref('');

    // 183 teams in a phone-sized list is unusable, so the list is filtered
    // rather than scrolled.
    const filteredTeams = computed(() => {
      const q = teamSearch.value.trim().toLowerCase();
      const list = q
        ? teams.value.filter(t => (t.name || '').toLowerCase().includes(q))
        : teams.value;
      return list.slice(0, 50);
    });

    const isDirty = computed(() => {
      if (!editing.value) return false;
      return (
        form.value.role !== editing.value.role ||
        form.value.team_id !== (editing.value.team_id ?? null) ||
        form.value.club_id !== (editing.value.club_id ?? null)
      );
    });

    // Flag an affiliation the role implies but the account lacks. This is the
    // state four real accounts are in, and it was invisible before.
    const affiliationClass = (user, kind) => {
      const role = (user.role || '').replace(/_/g, '-');
      const expectsTeam = role.startsWith('team-') && role !== 'team-fan';
      const expectsClub = role.startsWith('club-');
      const missing =
        (kind === 'team' && expectsTeam && !user.team_id) ||
        (kind === 'club' && expectsClub && !user.club_id);
      return missing ? 'text-amber-600 font-medium' : 'text-fg-muted';
    };

    const loadPickerData = async () => {
      if (teams.value.length && clubs.value.length) return;
      try {
        const [teamData, clubData] = await Promise.all([
          authStore.apiRequest(`${getApiBaseUrl()}/api/teams`, {
            method: 'GET',
          }),
          authStore.apiRequest(`${getApiBaseUrl()}/api/clubs`, {
            method: 'GET',
          }),
        ]);
        const t = Array.isArray(teamData) ? teamData : teamData?.teams || [];
        const c = Array.isArray(clubData) ? clubData : clubData?.clubs || [];
        teams.value = [...t].sort((a, b) =>
          (a.name || '').localeCompare(b.name || '')
        );
        clubs.value = [...c].sort((a, b) =>
          (a.name || '').localeCompare(b.name || '')
        );
      } catch (err) {
        saveError.value = err.message || 'Failed to load teams and clubs';
      }
    };

    const openEditor = async user => {
      saveError.value = null;
      teamSearch.value = '';
      editing.value = user;
      form.value = {
        role: user.role,
        team_id: user.team_id ?? null,
        club_id: user.club_id ?? null,
      };
      await loadPickerData();
    };

    const closeEditor = () => {
      editing.value = null;
      saveError.value = null;
    };

    const saveUser = async () => {
      if (!editing.value || !isDirty.value) return;
      saving.value = true;
      saveError.value = null;
      try {
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/users/${editing.value.id}`,
          {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(form.value),
          }
        );
        closeEditor();
        await fetchUsers();
      } catch (err) {
        // Guardrail rejections (last admin, own role) arrive here as the
        // message the user needs to read, so surface it rather than a generic.
        saveError.value = err.message || 'Failed to save';
      } finally {
        saving.value = false;
      }
    };

    const fetchLoginEvents = async () => {
      loading.value = true;
      error.value = null;
      try {
        const params = new URLSearchParams({
          limit: pageSize,
          offset: currentPage.value * pageSize,
        });
        if (filterUsername.value) params.set('username', filterUsername.value);
        if (filterSuccess.value !== '')
          params.set('success', filterSuccess.value);

        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/users/login-events?${params}`,
          { method: 'GET' }
        );
        events.value = data.events || [];
        eventTotal.value = data.total || 0;
      } catch (err) {
        error.value = err.message || 'Failed to fetch login events';
      } finally {
        loading.value = false;
      }
    };

    const debouncedFetch = () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        currentPage.value = 0;
        fetchLoginEvents();
      }, 400);
    };

    const prevPage = () => {
      if (currentPage.value > 0) {
        currentPage.value--;
        fetchLoginEvents();
      }
    };

    const nextPage = () => {
      currentPage.value++;
      fetchLoginEvents();
    };

    const formatDate = iso => {
      if (!iso) return '—';
      return new Date(iso).toLocaleString();
    };

    const roleBadgeClass = role => {
      const map = {
        admin:
          'bg-purple-100 text-purple-800 px-2 py-0.5 rounded text-xs font-medium',
        club_manager:
          'bg-brand-100 text-brand-800 px-2 py-0.5 rounded text-xs font-medium',
        team_manager:
          'bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded text-xs font-medium',
        'team-manager':
          'bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded text-xs font-medium',
        team_player:
          'bg-green-100 text-green-800 px-2 py-0.5 rounded text-xs font-medium',
        'team-player':
          'bg-green-100 text-green-800 px-2 py-0.5 rounded text-xs font-medium',
      };
      return (
        map[role] ||
        'bg-gray-100 text-gray-700 px-2 py-0.5 rounded text-xs font-medium'
      );
    };

    onMounted(fetchUsers);

    return {
      // SB-803 editing
      ROLE_OPTIONS,
      editing,
      form,
      saving,
      saveError,
      teams,
      clubs,
      teamSearch,
      filteredTeams,
      isDirty,
      affiliationClass,
      openEditor,
      closeEditor,
      saveUser,
      loading,
      error,
      activeTab,
      users,
      userTotal,
      events,
      eventTotal,
      currentPage,
      pageSize,
      filterUsername,
      filterSuccess,
      fetchUsers,
      fetchLoginEvents,
      debouncedFetch,
      prevPage,
      nextPage,
      formatDate,
      roleBadgeClass,
    };
  },
};
</script>
