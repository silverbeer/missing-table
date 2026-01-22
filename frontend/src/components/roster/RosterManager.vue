<template>
  <div
    class="modal-overlay"
    @click="$emit('close')"
    data-testid="roster-manager-overlay"
  >
    <div
      class="modal-content roster-modal"
      @click.stop
      data-testid="roster-manager"
    >
      <!-- Header -->
      <div
        class="p-4 border-b border-gray-200 flex justify-between items-center"
      >
        <h3 class="text-lg font-semibold text-gray-900">
          Roster: {{ teamName }}
        </h3>
        <button
          @click="$emit('close')"
          class="text-gray-400 hover:text-gray-600"
          data-testid="close-roster-button"
        >
          <svg
            class="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <!-- Action Bar -->
      <div
        class="p-4 border-b border-gray-200 flex justify-between items-center"
      >
        <div class="text-sm text-gray-600">
          {{ roster.length }} player{{ roster.length !== 1 ? 's' : '' }}
        </div>
        <div class="flex space-x-2">
          <button
            @click="showBulkImportModal = true"
            class="px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
            data-testid="bulk-import-button"
          >
            Bulk Import
          </button>
          <button
            @click="showAddModal = true"
            class="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md"
            data-testid="add-player-button"
          >
            + Add Player
          </button>
        </div>
      </div>

      <!-- Loading State -->
      <div
        v-if="loading"
        class="flex justify-center py-12"
        data-testid="roster-loading"
      >
        <div
          class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"
        ></div>
      </div>

      <!-- Error State -->
      <div
        v-else-if="error"
        class="m-4 bg-red-50 border border-red-200 rounded-md p-4"
        data-testid="roster-error"
      >
        <div class="text-red-800">{{ error }}</div>
      </div>

      <!-- Empty State -->
      <div
        v-else-if="roster.length === 0"
        class="p-8 text-center text-gray-500"
        data-testid="roster-empty"
      >
        <div class="text-4xl mb-2">👤</div>
        <p>No players on roster yet</p>
        <p class="text-sm mt-1">Add players individually or use bulk import</p>
      </div>

      <!-- Roster Table -->
      <div v-else class="overflow-x-auto" data-testid="roster-table-container">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th
                class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-16"
              >
                #
              </th>
              <th
                class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Name
              </th>
              <th
                class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-20"
              >
                Account
              </th>
              <th
                class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Positions
              </th>
              <th
                class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider w-40"
              >
                Actions
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr
              v-for="player in roster"
              :key="player.id"
              :data-testid="`roster-row-${player.id}`"
            >
              <td
                class="px-4 py-3 whitespace-nowrap text-sm font-bold text-gray-900"
              >
                {{ player.jersey_number }}
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                {{ player.display_name }}
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-center">
                <span
                  v-if="player.has_account"
                  class="text-green-600"
                  title="Linked to account"
                >
                  ✓
                </span>
                <span v-else class="text-gray-300">—</span>
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="pos in player.positions || []"
                    :key="pos"
                    class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800"
                  >
                    {{ pos }}
                  </span>
                </div>
              </td>
              <td
                class="px-4 py-3 whitespace-nowrap text-right text-sm font-medium space-x-2"
              >
                <button
                  @click="openEditModal(player)"
                  class="text-blue-600 hover:text-blue-900"
                  title="Edit name/positions"
                  data-testid="edit-player-button"
                >
                  Edit
                </button>
                <button
                  @click="openChangeNumberModal(player)"
                  class="text-gray-600 hover:text-gray-900"
                  title="Change jersey number"
                  data-testid="change-number-button"
                >
                  #
                </button>
                <button
                  v-if="!player.has_account"
                  @click="createInvite(player)"
                  class="text-green-600 hover:text-green-900"
                  title="Send invite"
                  data-testid="send-invite-button"
                >
                  ✉
                </button>
                <button
                  @click="deletePlayer(player)"
                  class="text-red-600 hover:text-red-900"
                  title="Remove from roster"
                  data-testid="delete-player-button"
                >
                  ✕
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Add Player Modal -->
      <div
        v-if="showAddModal"
        class="modal-overlay inner-modal"
        @click="closeInnerModals"
        data-testid="add-player-modal-overlay"
      >
        <div
          class="modal-content inner-modal-content"
          @click.stop
          data-testid="add-player-modal"
        >
          <div class="p-6">
            <h4 class="text-lg font-medium text-gray-900 mb-4">Add Player</h4>
            <form @submit.prevent="addPlayer" data-testid="add-player-form">
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Jersey Number <span class="text-red-500">*</span>
                </label>
                <input
                  v-model.number="addForm.jersey_number"
                  type="number"
                  min="1"
                  max="99"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="1-99"
                  data-testid="jersey-number-input"
                />
              </div>
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >First Name</label
                >
                <input
                  v-model="addForm.first_name"
                  type="text"
                  maxlength="100"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Optional"
                  data-testid="first-name-input"
                />
              </div>
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >Last Name</label
                >
                <input
                  v-model="addForm.last_name"
                  type="text"
                  maxlength="100"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Optional"
                  data-testid="last-name-input"
                />
              </div>
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >Positions</label
                >
                <div class="flex flex-wrap gap-2">
                  <label
                    v-for="pos in availablePositions"
                    :key="pos"
                    class="inline-flex items-center"
                  >
                    <input
                      type="checkbox"
                      :value="pos"
                      v-model="addForm.positions"
                      class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span class="ml-1 text-sm text-gray-700">{{ pos }}</span>
                  </label>
                </div>
              </div>
              <div class="flex justify-end space-x-3">
                <button
                  type="button"
                  @click="closeInnerModals"
                  class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  :disabled="formLoading"
                  class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50"
                  data-testid="save-player-button"
                >
                  {{ formLoading ? 'Adding...' : 'Add Player' }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>

      <!-- Edit Player Modal -->
      <div
        v-if="showEditModal"
        class="modal-overlay inner-modal"
        @click="closeInnerModals"
        data-testid="edit-player-modal-overlay"
      >
        <div
          class="modal-content inner-modal-content"
          @click.stop
          data-testid="edit-player-modal"
        >
          <div class="p-6">
            <h4 class="text-lg font-medium text-gray-900 mb-4">
              Edit Player #{{ editingPlayer?.jersey_number }}
            </h4>
            <form @submit.prevent="updatePlayer" data-testid="edit-player-form">
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >First Name</label
                >
                <input
                  v-model="editForm.first_name"
                  type="text"
                  maxlength="100"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  data-testid="edit-first-name-input"
                />
              </div>
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >Last Name</label
                >
                <input
                  v-model="editForm.last_name"
                  type="text"
                  maxlength="100"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  data-testid="edit-last-name-input"
                />
              </div>
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >Positions</label
                >
                <div class="flex flex-wrap gap-2">
                  <label
                    v-for="pos in availablePositions"
                    :key="pos"
                    class="inline-flex items-center"
                  >
                    <input
                      type="checkbox"
                      :value="pos"
                      v-model="editForm.positions"
                      class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span class="ml-1 text-sm text-gray-700">{{ pos }}</span>
                  </label>
                </div>
              </div>
              <div class="flex justify-end space-x-3">
                <button
                  type="button"
                  @click="closeInnerModals"
                  class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  :disabled="formLoading"
                  class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50"
                  data-testid="update-player-button"
                >
                  {{ formLoading ? 'Saving...' : 'Save Changes' }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>

      <!-- Change Number Modal -->
      <div
        v-if="showChangeNumberModal"
        class="modal-overlay inner-modal"
        @click="closeInnerModals"
        data-testid="change-number-modal-overlay"
      >
        <div
          class="modal-content inner-modal-content"
          @click.stop
          data-testid="change-number-modal"
        >
          <div class="p-6">
            <h4 class="text-lg font-medium text-gray-900 mb-4">
              Change Jersey Number
            </h4>
            <p class="text-sm text-gray-600 mb-4">
              Current: #{{ editingPlayer?.jersey_number }} ({{
                editingPlayer?.display_name
              }})
            </p>
            <form
              @submit.prevent="changeJerseyNumber"
              data-testid="change-number-form"
            >
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  New Number <span class="text-red-500">*</span>
                </label>
                <input
                  v-model.number="newJerseyNumber"
                  type="number"
                  min="1"
                  max="99"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  data-testid="new-jersey-number-input"
                />
              </div>
              <div class="flex justify-end space-x-3">
                <button
                  type="button"
                  @click="closeInnerModals"
                  class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  :disabled="formLoading"
                  class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50"
                  data-testid="confirm-change-number-button"
                >
                  {{ formLoading ? 'Changing...' : 'Change Number' }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>

      <!-- Bulk Import Modal -->
      <div
        v-if="showBulkImportModal"
        class="modal-overlay inner-modal"
        @click="closeInnerModals"
        data-testid="bulk-import-modal-overlay"
      >
        <div
          class="modal-content inner-modal-content"
          @click.stop
          data-testid="bulk-import-modal"
        >
          <div class="p-6">
            <h4 class="text-lg font-medium text-gray-900 mb-4">
              Bulk Import Players
            </h4>
            <p class="text-sm text-gray-600 mb-4">
              Enter jersey numbers, one per line. Players will be created with
              just the number.
            </p>
            <form @submit.prevent="bulkImport" data-testid="bulk-import-form">
              <div class="mb-4">
                <textarea
                  v-model="bulkImportText"
                  rows="8"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                  placeholder="1&#10;7&#10;10&#10;11&#10;23"
                  data-testid="bulk-import-textarea"
                ></textarea>
              </div>
              <div class="flex justify-end space-x-3">
                <button
                  type="button"
                  @click="closeInnerModals"
                  class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  :disabled="formLoading || !bulkImportText.trim()"
                  class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50"
                  data-testid="confirm-bulk-import-button"
                >
                  {{ formLoading ? 'Importing...' : 'Import Players' }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>

      <!-- Invite Created Modal -->
      <div
        v-if="showInviteModal"
        class="modal-overlay inner-modal"
        @click="closeInnerModals"
        data-testid="invite-created-modal-overlay"
      >
        <div
          class="modal-content inner-modal-content"
          @click.stop
          data-testid="invite-created-modal"
        >
          <div class="p-6 text-center">
            <div class="text-4xl mb-4">✉️</div>
            <h4 class="text-lg font-medium text-gray-900 mb-2">
              Invite Created!
            </h4>
            <p class="text-sm text-gray-600 mb-4">
              Share this code with #{{ invitePlayer?.jersey_number }}:
            </p>
            <div class="bg-gray-100 rounded-lg p-4 mb-4">
              <code class="text-lg font-mono font-bold text-blue-600">{{
                inviteCode
              }}</code>
            </div>
            <button
              @click="copyInviteCode"
              class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md mr-2"
            >
              Copy Code
            </button>
            <button
              @click="closeInnerModals"
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import { POSITION_ABBREVIATIONS } from '@/constants/positions';

export default {
  name: 'RosterManager',
  props: {
    teamId: {
      type: Number,
      required: true,
    },
    teamName: {
      type: String,
      required: true,
    },
    seasonId: {
      type: Number,
      required: true,
    },
    ageGroupId: {
      type: Number,
      default: null,
    },
  },
  emits: ['close'],
  setup(props) {
    const authStore = useAuthStore();

    // State
    const roster = ref([]);
    const loading = ref(false);
    const formLoading = ref(false);
    const error = ref(null);

    // Modal states
    const showAddModal = ref(false);
    const showEditModal = ref(false);
    const showChangeNumberModal = ref(false);
    const showBulkImportModal = ref(false);
    const showInviteModal = ref(false);

    // Form data
    const addForm = ref({
      jersey_number: null,
      first_name: '',
      last_name: '',
      positions: [],
    });

    const editForm = ref({
      first_name: '',
      last_name: '',
      positions: [],
    });

    const editingPlayer = ref(null);
    const newJerseyNumber = ref(null);
    const bulkImportText = ref('');
    const inviteCode = ref('');
    const invitePlayer = ref(null);

    // Available positions
    const availablePositions = POSITION_ABBREVIATIONS;

    // Fetch roster data
    const fetchRoster = async () => {
      try {
        loading.value = true;
        error.value = null;
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams/${props.teamId}/roster?season_id=${props.seasonId}`,
          { method: 'GET' }
        );
        roster.value = response.roster || [];
      } catch (err) {
        error.value = err.message || 'Failed to load roster';
        console.error('Error fetching roster:', err);
      } finally {
        loading.value = false;
      }
    };

    // Add a single player
    const addPlayer = async () => {
      try {
        formLoading.value = true;
        error.value = null;

        const playerData = {
          jersey_number: addForm.value.jersey_number,
          first_name: addForm.value.first_name || null,
          last_name: addForm.value.last_name || null,
          positions:
            addForm.value.positions.length > 0 ? addForm.value.positions : null,
          season_id: props.seasonId,
        };

        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams/${props.teamId}/roster`,
          {
            method: 'POST',
            body: JSON.stringify(playerData),
          }
        );

        await fetchRoster();
        closeInnerModals();
        resetAddForm();
      } catch (err) {
        error.value = err.message || 'Failed to add player';
      } finally {
        formLoading.value = false;
      }
    };

    // Update player name/positions
    const updatePlayer = async () => {
      if (!editingPlayer.value) return;

      try {
        formLoading.value = true;
        error.value = null;

        const updateData = {
          first_name: editForm.value.first_name || null,
          last_name: editForm.value.last_name || null,
          positions:
            editForm.value.positions.length > 0
              ? editForm.value.positions
              : null,
        };

        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams/${props.teamId}/roster/${editingPlayer.value.id}`,
          {
            method: 'PUT',
            body: JSON.stringify(updateData),
          }
        );

        await fetchRoster();
        closeInnerModals();
      } catch (err) {
        error.value = err.message || 'Failed to update player';
      } finally {
        formLoading.value = false;
      }
    };

    // Change jersey number
    const changeJerseyNumber = async () => {
      if (!editingPlayer.value || !newJerseyNumber.value) return;

      try {
        formLoading.value = true;
        error.value = null;

        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams/${props.teamId}/roster/${editingPlayer.value.id}/number`,
          {
            method: 'PUT',
            body: JSON.stringify({ new_number: newJerseyNumber.value }),
          }
        );

        await fetchRoster();
        closeInnerModals();
      } catch (err) {
        error.value = err.message || 'Failed to change jersey number';
      } finally {
        formLoading.value = false;
      }
    };

    // Delete player
    const deletePlayer = async player => {
      if (
        !confirm(
          `Remove #${player.jersey_number} (${player.display_name}) from roster?`
        )
      ) {
        return;
      }

      try {
        error.value = null;
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams/${props.teamId}/roster/${player.id}`,
          { method: 'DELETE' }
        );
        await fetchRoster();
      } catch (err) {
        error.value = err.message || 'Failed to remove player';
      }
    };

    // Bulk import players
    const bulkImport = async () => {
      try {
        formLoading.value = true;
        error.value = null;

        // Parse jersey numbers from text
        const numbers = bulkImportText.value
          .split('\n')
          .map(line => parseInt(line.trim()))
          .filter(num => !isNaN(num) && num >= 1 && num <= 99);

        if (numbers.length === 0) {
          error.value = 'No valid jersey numbers found';
          formLoading.value = false;
          return;
        }

        const players = numbers.map(num => ({ jersey_number: num }));

        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams/${props.teamId}/roster/bulk`,
          {
            method: 'POST',
            body: JSON.stringify({
              season_id: props.seasonId,
              players: players,
            }),
          }
        );

        const created = response.created_count || 0;
        const skipped = response.skipped_count || 0;

        if (skipped > 0) {
          alert(
            `Imported ${created} players. Skipped ${skipped} (already exist).`
          );
        }

        await fetchRoster();
        closeInnerModals();
        bulkImportText.value = '';
      } catch (err) {
        error.value = err.message || 'Failed to import players';
      } finally {
        formLoading.value = false;
      }
    };

    // Create invite for a player
    const createInvite = async player => {
      try {
        error.value = null;

        const inviteData = {
          invite_type: 'team_player',
          team_id: props.teamId,
          age_group_id: props.ageGroupId,
          player_id: player.id,
        };

        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/invites/team-manager/team-player`,
          {
            method: 'POST',
            body: JSON.stringify(inviteData),
          }
        );

        inviteCode.value = response.invite_code;
        invitePlayer.value = player;
        showInviteModal.value = true;
      } catch (err) {
        error.value = err.message || 'Failed to create invite';
      }
    };

    // Copy invite code to clipboard
    const copyInviteCode = async () => {
      try {
        await navigator.clipboard.writeText(inviteCode.value);
        alert('Invite code copied!');
      } catch (err) {
        console.error('Failed to copy:', err);
      }
    };

    // Modal helpers
    const openEditModal = player => {
      editingPlayer.value = player;
      editForm.value = {
        first_name: player.first_name || '',
        last_name: player.last_name || '',
        positions: player.positions ? [...player.positions] : [],
      };
      showEditModal.value = true;
    };

    const openChangeNumberModal = player => {
      editingPlayer.value = player;
      newJerseyNumber.value = player.jersey_number;
      showChangeNumberModal.value = true;
    };

    const closeInnerModals = () => {
      showAddModal.value = false;
      showEditModal.value = false;
      showChangeNumberModal.value = false;
      showBulkImportModal.value = false;
      showInviteModal.value = false;
      editingPlayer.value = null;
      newJerseyNumber.value = null;
    };

    const resetAddForm = () => {
      addForm.value = {
        jersey_number: null,
        first_name: '',
        last_name: '',
        positions: [],
      };
    };

    // Initialize
    onMounted(() => {
      fetchRoster();
    });

    return {
      roster,
      loading,
      formLoading,
      error,
      showAddModal,
      showEditModal,
      showChangeNumberModal,
      showBulkImportModal,
      showInviteModal,
      addForm,
      editForm,
      editingPlayer,
      newJerseyNumber,
      bulkImportText,
      inviteCode,
      invitePlayer,
      availablePositions,
      fetchRoster,
      addPlayer,
      updatePlayer,
      changeJerseyNumber,
      deletePlayer,
      bulkImport,
      createInvite,
      copyInviteCode,
      openEditModal,
      openChangeNumberModal,
      closeInnerModals,
    };
  },
};
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  max-width: 800px;
  width: 95%;
  max-height: 90vh;
  overflow-y: auto;
}

.roster-modal {
  max-width: 900px;
}

.inner-modal {
  z-index: 1100;
}

.inner-modal-content {
  max-width: 500px;
}
</style>
