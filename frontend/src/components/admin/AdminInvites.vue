<template>
  <div class="p-6">
    <h2 class="text-2xl font-bold mb-6">Invite Management</h2>

    <!-- Create Invite Section -->
    <div class="bg-white rounded-lg shadow p-6 mb-6">
      <h3 class="text-lg font-semibold mb-4">Create New Invite</h3>

      <form @submit.prevent="createInvite" class="space-y-4">
        <!-- Invite Type Selection -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2"
            >Invite Type</label
          >
          <select
            v-model="newInvite.inviteType"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select type...</option>
            <option value="club_manager">Club Manager</option>
            <option value="club_fan">Club Fan</option>
            <option value="team_manager">Team Manager</option>
            <option value="team_player">Team Player</option>
          </select>
        </div>

        <!-- Club Selection (for club-level invites) -->
        <div
          v-if="
            newInvite.inviteType === 'club_manager' ||
            newInvite.inviteType === 'club_fan'
          "
        >
          <label class="block text-sm font-medium text-gray-700 mb-2"
            >Club</label
          >
          <select
            v-model="newInvite.clubId"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select club...</option>
            <option v-for="club in clubs" :key="club.id" :value="club.id">
              {{ club.name }}
            </option>
          </select>
        </div>

        <!-- Team Selection (for team-level invites) -->
        <div
          v-if="
            newInvite.inviteType &&
            newInvite.inviteType !== 'club_manager' &&
            newInvite.inviteType !== 'club_fan'
          "
        >
          <label class="block text-sm font-medium text-gray-700 mb-2"
            >Team</label
          >
          <select
            v-model="newInvite.teamId"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select team...</option>
            <option v-for="team in teams" :key="team.id" :value="team.id">
              {{ team.name }}
            </option>
          </select>
        </div>

        <!-- Age Group Selection (for team-level invites) -->
        <div
          v-if="
            newInvite.inviteType &&
            newInvite.inviteType !== 'club_manager' &&
            newInvite.inviteType !== 'club_fan'
          "
        >
          <label class="block text-sm font-medium text-gray-700 mb-2"
            >Age Group</label
          >
          <select
            v-model="newInvite.ageGroupId"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select age group...</option>
            <option
              v-for="ageGroup in ageGroups"
              :key="ageGroup.id"
              :value="ageGroup.id"
            >
              {{ ageGroup.name }}
            </option>
          </select>
        </div>

        <!-- Email (Optional) -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2"
            >Email (Optional)</label
          >
          <input
            v-model="newInvite.email"
            type="email"
            placeholder="Pre-fill email for recipient"
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <!-- Submit Button -->
        <button
          type="submit"
          :disabled="loading"
          class="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
        >
          {{ loading ? 'Creating...' : 'Create Invite' }}
        </button>
      </form>

      <!-- Success Message -->
      <div
        v-if="createdInvite"
        class="mt-4 p-4 bg-green-50 border border-green-200 rounded-md"
      >
        <h4 class="font-semibold text-green-800 mb-2">
          Invite Created Successfully!
        </h4>
        <div class="space-y-2 text-sm">
          <p>
            <span class="font-medium">Invite Code:</span>
            <code class="bg-gray-100 px-2 py-1 rounded text-lg font-mono">{{
              createdInvite.invite_code
            }}</code>
          </p>
          <p>
            <span class="font-medium">Type:</span>
            {{ formatInviteType(createdInvite.invite_type) }}
          </p>
          <p v-if="createdInvite.club_id">
            <span class="font-medium">Club:</span>
            {{ getClubName(createdInvite.club_id) }}
          </p>
          <p v-if="createdInvite.team_id">
            <span class="font-medium">Team:</span>
            {{ getTeamName(createdInvite.team_id) }}
          </p>
          <p v-if="createdInvite.age_group_id">
            <span class="font-medium">Age Group:</span>
            {{ getAgeGroupName(createdInvite.age_group_id) }}
          </p>
          <p>
            <span class="font-medium">Expires:</span>
            {{ formatDate(createdInvite.expires_at) }}
          </p>
          <p class="text-gray-600 mt-2">
            Share this registration link:<br />
            <code class="text-xs break-all"
              >{{ currentOrigin }}/register?code={{
                createdInvite.invite_code
              }}</code
            >
          </p>
        </div>
        <button
          @click="copyInviteLink(createdInvite.invite_code)"
          class="mt-3 text-sm bg-gray-200 hover:bg-gray-300 px-3 py-1 rounded"
        >
          Copy Registration Link
        </button>
      </div>
    </div>

    <!-- Existing Invites -->
    <div class="bg-white rounded-lg shadow p-6">
      <h3 class="text-lg font-semibold mb-4">Existing Invites</h3>

      <!-- Filter -->
      <div class="mb-4">
        <select
          v-model="statusFilter"
          @change="fetchInvites"
          class="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Invites</option>
          <option value="pending">Pending</option>
          <option value="used">Used</option>
          <option value="expired">Expired</option>
        </select>
      </div>

      <!-- Invites Table -->
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Code
              </th>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Type
              </th>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Club/Team
              </th>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Status
              </th>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Created
              </th>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Actions
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="invite in invites" :key="invite.id">
              <td class="px-6 py-4 whitespace-nowrap text-sm font-mono">
                {{ invite.invite_code }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                {{ formatInviteType(invite.invite_type) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                <template v-if="invite.club_id">
                  {{ invite.clubs?.name || 'Club ' + invite.club_id }}
                </template>
                <template v-else>
                  {{ invite.teams?.name }} - {{ invite.age_groups?.name }}
                </template>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span
                  :class="{
                    'bg-yellow-100 text-yellow-800':
                      invite.status === 'pending',
                    'bg-green-100 text-green-800': invite.status === 'used',
                    'bg-red-100 text-red-800': invite.status === 'expired',
                  }"
                  class="px-2 py-1 text-xs rounded-full"
                >
                  {{ invite.status }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ formatDate(invite.created_at) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                <button
                  v-if="invite.status === 'pending'"
                  @click="cancelInvite(invite.id)"
                  class="text-red-600 hover:text-red-900"
                >
                  Cancel
                </button>
                <span v-else class="text-gray-400">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';

const authStore = useAuthStore();

// State
const teams = ref([]);
const ageGroups = ref([]);
const clubs = ref([]);
const invites = ref([]);
const loading = ref(false);
const createdInvite = ref(null);
const statusFilter = ref('');

// Safely get the current origin
const currentOrigin = computed(() => {
  if (typeof window !== 'undefined' && window.location) {
    return window.location.origin;
  }
  return 'http://localhost:8080'; // fallback for SSR or when window is undefined
});

const newInvite = ref({
  inviteType: '',
  clubId: '',
  teamId: '',
  ageGroupId: '',
  email: '',
});

// Fetch teams, age groups, and clubs
const fetchReferenceData = async () => {
  try {
    const headers = authStore.getAuthHeaders();

    // Fetch teams
    const teamsResponse = await fetch(`${getApiBaseUrl()}/api/teams`, {
      headers,
    });
    teams.value = await teamsResponse.json();

    // Fetch age groups
    const ageGroupsResponse = await fetch(`${getApiBaseUrl()}/api/age-groups`, {
      headers,
    });
    ageGroups.value = await ageGroupsResponse.json();

    // Fetch clubs
    const clubsResponse = await fetch(`${getApiBaseUrl()}/api/clubs`, {
      headers,
    });
    clubs.value = await clubsResponse.json();
  } catch (error) {
    console.error('Error fetching reference data:', error);
  }
};

// Fetch invites
const fetchInvites = async () => {
  try {
    const headers = authStore.getAuthHeaders();
    let url = `${getApiBaseUrl()}/api/invites/my-invites`;
    if (statusFilter.value) {
      url += `?status=${statusFilter.value}`;
    }

    const response = await fetch(url, { headers });
    invites.value = await response.json();
  } catch (error) {
    console.error('Error fetching invites:', error);
  }
};

// Create invite
const createInvite = async () => {
  loading.value = true;
  createdInvite.value = null;

  try {
    const headers = {
      ...authStore.getAuthHeaders(),
      'Content-Type': 'application/json',
    };

    // Determine endpoint and body based on invite type
    let endpoint = '/api/invites/admin/';
    let body;

    if (newInvite.value.inviteType === 'club_manager') {
      endpoint += 'club-manager';
      body = JSON.stringify({
        club_id: parseInt(newInvite.value.clubId),
        email: newInvite.value.email || null,
      });
    } else if (newInvite.value.inviteType === 'club_fan') {
      endpoint += 'club-fan';
      body = JSON.stringify({
        club_id: parseInt(newInvite.value.clubId),
        email: newInvite.value.email || null,
      });
    } else {
      if (newInvite.value.inviteType === 'team_manager') {
        endpoint += 'team-manager';
      } else if (newInvite.value.inviteType === 'team_player') {
        endpoint += 'team-player';
      }
      body = JSON.stringify({
        invite_type: newInvite.value.inviteType,
        team_id: parseInt(newInvite.value.teamId),
        age_group_id: parseInt(newInvite.value.ageGroupId),
        email: newInvite.value.email || null,
      });
    }

    const response = await fetch(`${getApiBaseUrl()}${endpoint}`, {
      method: 'POST',
      headers,
      body,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to create invite');
    }

    createdInvite.value = await response.json();

    // Reset form
    newInvite.value = {
      inviteType: '',
      clubId: '',
      teamId: '',
      ageGroupId: '',
      email: '',
    };

    // Refresh invites list
    await fetchInvites();
  } catch (error) {
    console.error('Error creating invite:', error);
    alert(`Failed to create invite: ${error.message}`);
  } finally {
    loading.value = false;
  }
};

// Cancel invite
const cancelInvite = async inviteId => {
  if (!confirm('Are you sure you want to cancel this invite?')) return;

  try {
    const headers = authStore.getAuthHeaders();
    const response = await fetch(`${getApiBaseUrl()}/api/invites/${inviteId}`, {
      method: 'DELETE',
      headers,
    });

    if (!response.ok) {
      throw new Error('Failed to cancel invite');
    }

    await fetchInvites();
  } catch (error) {
    console.error('Error cancelling invite:', error);
    alert('Failed to cancel invite. Please try again.');
  }
};

// Utility functions
const formatInviteType = type => {
  const types = {
    club_manager: 'Club Manager',
    club_fan: 'Club Fan',
    team_manager: 'Team Manager',
    team_player: 'Team Player',
    team_fan: 'Team Fan',
  };
  return types[type] || type;
};

const getClubName = clubId => {
  const club = clubs.value.find(c => c.id === clubId);
  return club?.name || 'Unknown';
};

const formatDate = dateString => {
  return new Date(dateString).toLocaleString();
};

const getTeamName = teamId => {
  const team = teams.value.find(t => t.id === teamId);
  return team?.name || 'Unknown';
};

const getAgeGroupName = ageGroupId => {
  const ageGroup = ageGroups.value.find(ag => ag.id === ageGroupId);
  return ageGroup?.name || 'Unknown';
};

const copyInviteLink = code => {
  const link = `${currentOrigin.value}/register?code=${code}`;
  navigator.clipboard.writeText(link);
  alert('Registration link copied to clipboard!');
};

// Lifecycle
onMounted(async () => {
  await fetchReferenceData();
  await fetchInvites();
});
</script>
