<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Clubs Management</h3>
      <button
        @click="showAddModal = true"
        class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium"
      >
        Add Club
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center py-8">
      <div
        class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"
      ></div>
    </div>

    <!-- Error State -->
    <div
      v-if="error"
      class="bg-red-50 border border-red-200 rounded-md p-4 mb-4"
    >
      <div class="text-red-800">{{ error }}</div>
    </div>

    <!-- Clubs Grid -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="club in clubs"
        :key="club.id"
        class="bg-white shadow-md rounded-lg overflow-hidden hover:shadow-lg transition-shadow"
        :style="{
          border: `3px solid ${club.primary_color || '#3B82F6'}`,
        }"
      >
        <!-- Club Header with brand colors -->
        <div
          class="px-6 py-4"
          :style="{
            background: `linear-gradient(to right, ${club.primary_color || '#3B82F6'}, ${club.secondary_color || '#2563EB'})`,
          }"
        >
          <div class="flex items-center gap-3">
            <img
              v-if="club.logo_url"
              :src="club.logo_url"
              :alt="`${club.name} logo`"
              class="w-10 h-10 rounded-full object-cover bg-white"
            />
            <div>
              <h4 class="text-xl font-bold text-white">{{ club.name }}</h4>
              <p class="text-white text-opacity-80 text-sm">{{ club.city }}</p>
            </div>
          </div>
        </div>

        <!-- Club Body -->
        <div class="px-6 py-4">
          <!-- Pro Academy Badge -->
          <div
            v-if="club.pro_academy"
            class="mb-3 inline-flex items-center px-3 py-1.5 rounded-md text-sm font-bold bg-yellow-400 text-gray-900 border-2 border-yellow-500"
          >
            <svg class="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
              <path
                d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"
              />
            </svg>
            PRO ACADEMY
          </div>

          <div class="mb-4">
            <div
              class="flex items-center justify-between text-sm text-gray-600 mb-2"
            >
              <span class="font-medium">Teams:</span>
              <div class="flex items-center gap-2">
                <span
                  class="bg-blue-100 text-blue-800 px-2 py-1 rounded-full font-semibold"
                >
                  {{ club.team_count }}
                </span>
                <button
                  type="button"
                  class="text-xs font-medium text-blue-600 hover:text-blue-800"
                  @click="toggleClubTeams(club.id)"
                >
                  {{ expandedClubIds[club.id] ? 'Hide teams' : 'Show teams' }}
                </button>
              </div>
            </div>
          </div>

          <!-- Teams List (lazy-loaded) -->
          <div v-if="expandedClubIds[club.id]" class="space-y-2">
            <div
              v-if="loadingTeams[club.id]"
              class="text-sm text-gray-500 italic"
            >
              Loading teams...
            </div>
            <div
              v-else-if="teamsByClubId[club.id] && teamsByClubId[club.id].length"
              class="space-y-2"
            >
              <div
                v-for="team in teamsByClubId[club.id]"
                :key="team.id"
                class="text-sm text-gray-700 pl-2 py-2 hover:bg-gray-50 rounded border-b border-gray-100 last:border-0"
              >
                <div class="flex items-center mb-1">
                  <svg
                    class="w-3 h-3 mr-2 text-gray-400 flex-shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z"
                    />
                  </svg>
                  <span class="font-medium">{{ team.name }}</span>
                </div>
                <div class="ml-5 flex flex-wrap gap-1">
                  <!-- Show league badge based on league name -->
                  <span
                    v-if="team.league_name === 'Academy'"
                    class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800"
                  >
                    Academy
                  </span>
                  <span
                    v-if="team.league_name === 'Homegrown'"
                    class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800"
                  >
                    Homegrown
                  </span>

                  <!-- Show additional leagues if team has mappings -->
                  <span
                    v-for="leagueName in team.mapping_league_names || []"
                    :key="leagueName"
                    class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
                  >
                    {{ leagueName }}
                  </span>
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-gray-500 italic">
              No teams in this club yet
            </div>
          </div>
        </div>

        <!-- Club Footer -->
        <div class="bg-gray-50 px-6 py-3 flex justify-end space-x-2">
          <button
            @click="viewClubDetails(club)"
            class="text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            View Details
          </button>
          <button
            @click="deleteClub(club)"
            class="text-red-600 hover:text-red-800 text-sm font-medium"
          >
            Delete
          </button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-if="!loading && clubs.length === 0"
      class="text-center py-12 bg-gray-50 rounded-lg"
    >
      <svg
        class="mx-auto h-12 w-12 text-gray-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
        />
      </svg>
      <h3 class="mt-2 text-sm font-medium text-gray-900">No clubs</h3>
      <p class="mt-1 text-sm text-gray-500">
        Get started by creating a new club.
      </p>
      <div class="mt-6">
        <button
          @click="showAddModal = true"
          class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
        >
          Add Club
        </button>
      </div>
    </div>

    <!-- Add Club Modal -->
    <div
      v-if="showAddModal"
      class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50"
    >
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-medium text-gray-900">Add Club</h3>
        </div>

        <form @submit.prevent="createClub" class="px-6 py-4 space-y-4">
          <!-- Error Display Inside Modal -->
          <div
            v-if="error"
            class="bg-red-50 border border-red-200 rounded-md p-4"
          >
            <div class="text-red-800">{{ error }}</div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">
              Club Name *
            </label>
            <input
              v-model="newClub.name"
              type="text"
              required
              class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="e.g., IFA"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">
              City *
            </label>
            <input
              v-model="newClub.city"
              type="text"
              required
              class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="e.g., Weymouth, MA"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">
              Website
            </label>
            <input
              v-model="newClub.website"
              type="url"
              class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="e.g., https://ifasoccer.com"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              v-model="newClub.description"
              rows="3"
              class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="Brief description of the club"
            ></textarea>
          </div>

          <!-- Pro Academy Checkbox -->
          <div class="flex items-center">
            <input
              v-model="newClub.pro_academy"
              type="checkbox"
              id="new_pro_academy"
              class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <label
              for="new_pro_academy"
              class="ml-2 block text-sm font-medium text-gray-700"
            >
              Professional Academy
            </label>
          </div>

          <div class="bg-blue-50 border border-blue-200 rounded-md p-3">
            <p class="text-sm text-blue-800">
              <strong>Note:</strong> After creating a club, you can link teams
              to it in the Teams Management section.
            </p>
          </div>

          <div class="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              @click="cancelAdd"
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="saving"
              class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {{ saving ? 'Creating...' : 'Create Club' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Edit Club Modal -->
    <div
      v-if="showEditModal"
      class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50"
    >
      <div
        class="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto"
      >
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-medium text-gray-900">Edit Club</h3>
        </div>

        <form @submit.prevent="updateClub" class="px-6 py-4 space-y-4">
          <!-- Error Display Inside Modal -->
          <div
            v-if="editError"
            class="bg-red-50 border border-red-200 rounded-md p-4"
          >
            <div class="text-red-800">{{ editError }}</div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">
              Club Name *
            </label>
            <input
              v-model="editClub.name"
              type="text"
              required
              class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">
              City *
            </label>
            <input
              v-model="editClub.city"
              type="text"
              required
              class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">
              Website
            </label>
            <input
              v-model="editClub.website"
              type="url"
              class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              v-model="editClub.description"
              rows="3"
              class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            ></textarea>
          </div>

          <!-- Pro Academy Checkbox -->
          <div class="flex items-center">
            <input
              v-model="editClub.pro_academy"
              type="checkbox"
              id="pro_academy"
              class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <label
              for="pro_academy"
              class="ml-2 block text-sm font-medium text-gray-700"
            >
              Professional Academy
            </label>
          </div>

          <!-- Logo Upload Section -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Club Logo
            </label>
            <div class="flex items-center gap-4">
              <!-- Logo Preview -->
              <div class="flex-shrink-0">
                <img
                  v-if="editClub.logo_url || logoPreview"
                  :src="logoPreview || editClub.logo_url"
                  alt="Club logo preview"
                  class="w-16 h-16 rounded-full object-cover border-2 border-gray-200"
                />
                <div
                  v-else
                  class="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center"
                >
                  <svg
                    class="w-8 h-8 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                    />
                  </svg>
                </div>
              </div>
              <!-- Upload Button -->
              <div class="flex-1">
                <input
                  type="file"
                  ref="logoInput"
                  @change="handleLogoSelect"
                  accept="image/png,image/jpeg,image/jpg"
                  class="hidden"
                />
                <button
                  type="button"
                  @click="$refs.logoInput.click()"
                  :disabled="uploadingLogo"
                  class="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                >
                  {{ uploadingLogo ? 'Uploading...' : 'Choose Image' }}
                </button>
                <p class="mt-1 text-xs text-gray-500">PNG or JPG, max 2MB</p>
              </div>
            </div>
          </div>

          <!-- Color Pickers Section -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Primary Color
              </label>
              <div class="flex items-center gap-2">
                <input
                  v-model="editClub.primary_color"
                  type="color"
                  class="w-10 h-10 rounded cursor-pointer border border-gray-300"
                />
                <input
                  v-model="editClub.primary_color"
                  type="text"
                  class="flex-1 border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm font-mono"
                  placeholder="#6B7280"
                />
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Secondary Color
              </label>
              <div class="flex items-center gap-2">
                <input
                  v-model="editClub.secondary_color"
                  type="color"
                  class="w-10 h-10 rounded cursor-pointer border border-gray-300"
                />
                <input
                  v-model="editClub.secondary_color"
                  type="text"
                  class="flex-1 border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm font-mono"
                  placeholder="#374151"
                />
              </div>
            </div>
          </div>

          <!-- Color Preview -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Color Preview
            </label>
            <div
              class="h-12 rounded-md"
              :style="{
                background: `linear-gradient(to right, ${editClub.primary_color || '#6B7280'}, ${editClub.secondary_color || '#374151'})`,
              }"
            ></div>
          </div>

          <div class="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              @click="cancelEdit"
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="saving"
              class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {{ saving ? 'Saving...' : 'Save Changes' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { getApiBaseUrl } from '../../config/api';

export default {
  name: 'AdminClubs',
  setup() {
    const authStore = useAuthStore();
    const clubs = ref([]);
    const loading = ref(true);
    const error = ref(null);
    const showAddModal = ref(false);
    const saving = ref(false);
    const expandedClubIds = ref({});
    const teamsByClubId = ref({});
    const loadingTeams = ref({});

    // Edit modal state
    const showEditModal = ref(false);
    const editError = ref(null);
    const logoPreview = ref(null);
    const uploadingLogo = ref(false);
    const selectedClubId = ref(null);
    const selectedLogoFile = ref(null);

    const newClub = ref({
      name: '',
      city: '',
      website: '',
      description: '',
      pro_academy: false,
    });

    const editClub = ref({
      name: '',
      city: '',
      website: '',
      description: '',
      logo_url: '',
      primary_color: '#6B7280',
      secondary_color: '#374151',
      pro_academy: false,
    });

    const fetchClubs = async () => {
      loading.value = true;
      error.value = null;
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/clubs?include_teams=false`
        );
        clubs.value = data.sort((a, b) => a.name.localeCompare(b.name));
        expandedClubIds.value = {};
        teamsByClubId.value = {};
        loadingTeams.value = {};
      } catch (err) {
        console.error('Error fetching clubs:', err);
        error.value = err.message || 'Failed to load clubs';
      } finally {
        loading.value = false;
      }
    };

    const loadClubTeams = async clubId => {
      loadingTeams.value = { ...loadingTeams.value, [clubId]: true };
      try {
        const teams = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/clubs/${clubId}/teams?include_stats=false`
        );
        teamsByClubId.value = { ...teamsByClubId.value, [clubId]: teams };
      } catch (err) {
        console.error('Error fetching club teams:', err);
        error.value = err.message || 'Failed to load club teams';
      } finally {
        loadingTeams.value = { ...loadingTeams.value, [clubId]: false };
      }
    };

    const toggleClubTeams = async clubId => {
      const isExpanded = !!expandedClubIds.value[clubId];
      expandedClubIds.value = {
        ...expandedClubIds.value,
        [clubId]: !isExpanded,
      };

      if (!isExpanded && !teamsByClubId.value[clubId]) {
        await loadClubTeams(clubId);
      }
    };

    const createClub = async () => {
      if (!newClub.value.name || !newClub.value.city) {
        return;
      }

      saving.value = true;
      error.value = null;

      try {
        await authStore.apiRequest(`${getApiBaseUrl()}/api/clubs`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(newClub.value),
        });

        // Success! Refresh clubs list
        await fetchClubs();

        // Reset form and close modal only on success
        newClub.value = { name: '', city: '', website: '', description: '' };
        showAddModal.value = false;
        error.value = null; // Clear any previous errors
      } catch (err) {
        console.error('Error creating club:', err);
        error.value = err.message || 'Failed to create club';
        // Don't close modal on error - user needs to see the error and retry
      } finally {
        saving.value = false;
      }
    };

    const openEditModal = club => {
      selectedClubId.value = club.id;
      editClub.value = {
        name: club.name || '',
        city: club.city || '',
        website: club.website || '',
        description: club.description || '',
        logo_url: club.logo_url || '',
        primary_color: club.primary_color || '#6B7280',
        secondary_color: club.secondary_color || '#374151',
        pro_academy: club.pro_academy || false,
      };
      logoPreview.value = null;
      selectedLogoFile.value = null;
      editError.value = null;
      showEditModal.value = true;
    };

    const handleLogoSelect = event => {
      const file = event.target.files[0];
      if (!file) return;

      // Validate file type
      const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg'];
      if (!allowedTypes.includes(file.type)) {
        editError.value =
          'Invalid file type. Please select a PNG or JPG image.';
        return;
      }

      // Validate file size (2MB max)
      const maxSize = 2 * 1024 * 1024;
      if (file.size > maxSize) {
        editError.value = `File too large. Maximum size is 2MB. Your file: ${(file.size / 1024 / 1024).toFixed(2)}MB`;
        return;
      }

      // Store file for upload
      selectedLogoFile.value = file;

      // Create preview
      const reader = new FileReader();
      reader.onload = e => {
        logoPreview.value = e.target.result;
      };
      reader.readAsDataURL(file);
      editError.value = null;
    };

    const uploadLogo = async () => {
      if (!selectedLogoFile.value || !selectedClubId.value) return;

      uploadingLogo.value = true;
      try {
        const formData = new FormData();
        formData.append('file', selectedLogoFile.value);

        // Use fetch directly for file upload - don't set Content-Type
        // (browser sets it automatically with multipart boundary)
        const token = localStorage.getItem('auth_token');
        const fetchResponse = await fetch(
          `${getApiBaseUrl()}/api/clubs/${selectedClubId.value}/logo`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
            },
            body: formData,
          }
        );

        if (!fetchResponse.ok) {
          const errorData = await fetchResponse.json();
          throw new Error(errorData.detail || 'Failed to upload logo');
        }

        const response = await fetchResponse.json();

        // Update the logo URL in editClub
        editClub.value.logo_url = response.logo_url;
        logoPreview.value = null;
        selectedLogoFile.value = null;

        return response;
      } catch (err) {
        console.error('Error uploading logo:', err);
        throw err;
      } finally {
        uploadingLogo.value = false;
      }
    };

    const updateClub = async () => {
      if (!editClub.value.name || !editClub.value.city) {
        editError.value = 'Club name and city are required.';
        return;
      }

      saving.value = true;
      editError.value = null;

      try {
        // Upload logo first if one was selected
        if (selectedLogoFile.value) {
          await uploadLogo();
        }

        // Update club data
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/clubs/${selectedClubId.value}`,
          {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(editClub.value),
          }
        );

        // Success! Refresh clubs list
        await fetchClubs();

        // Close modal
        showEditModal.value = false;
        editError.value = null;
      } catch (err) {
        console.error('Error updating club:', err);
        editError.value = err.message || 'Failed to update club';
      } finally {
        saving.value = false;
      }
    };

    const cancelEdit = () => {
      showEditModal.value = false;
      editError.value = null;
      logoPreview.value = null;
      selectedLogoFile.value = null;
    };

    // Keep viewClubDetails as alias for openEditModal
    const viewClubDetails = openEditModal;

    const deleteClub = async club => {
      if (
        !confirm(
          `Are you sure you want to delete "${club.name}"?\n\nThis will only delete the club. Teams will become independent teams.`
        )
      ) {
        return;
      }

      try {
        await authStore.apiRequest(`${getApiBaseUrl()}/api/clubs/${club.id}`, {
          method: 'DELETE',
        });

        // Refresh clubs list
        await fetchClubs();
      } catch (err) {
        console.error('Error deleting club:', err);
        error.value = err.message || 'Failed to delete club';
      }
    };

    const cancelAdd = () => {
      newClub.value = { name: '', city: '', website: '', description: '' };
      showAddModal.value = false;
    };

    onMounted(() => {
      fetchClubs();
    });

    return {
      clubs,
      loading,
      error,
      showAddModal,
      newClub,
      saving,
      createClub,
      viewClubDetails,
      deleteClub,
      cancelAdd,
      expandedClubIds,
      teamsByClubId,
      loadingTeams,
      toggleClubTeams,
      // Edit modal
      showEditModal,
      editClub,
      editError,
      logoPreview,
      uploadingLogo,
      openEditModal,
      handleLogoSelect,
      updateClub,
      cancelEdit,
    };
  },
};
</script>
