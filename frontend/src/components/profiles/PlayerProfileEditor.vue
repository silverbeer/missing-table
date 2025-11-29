<template>
  <div class="player-profile-editor">
    <!-- Header -->
    <div class="editor-header">
      <h2>Edit Profile</h2>
      <div class="header-actions">
        <button type="button" class="btn btn-secondary" @click="handleCancel">
          Cancel
        </button>
        <button
          type="button"
          class="btn btn-primary"
          :disabled="!hasChanges || saving"
          @click="handlePublish"
        >
          {{ saving ? 'Saving...' : 'Publish' }}
        </button>
      </div>
    </div>

    <!-- Unsaved changes warning -->
    <div v-if="hasChanges" class="unsaved-warning">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
      >
        <path
          fill-rule="evenodd"
          d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
          clip-rule="evenodd"
        />
      </svg>
      <span>You have unsaved changes</span>
    </div>

    <!-- Main content -->
    <div class="editor-content">
      <!-- Preview Column -->
      <div class="preview-column">
        <div class="preview-card">
          <h3>Preview</h3>
          <div class="preview-photo">
            <PlayerPhotoOverlay
              :photo-url="previewPhotoUrl"
              :number="localState.player_number"
              :position="primaryPosition"
              :overlay-style="localState.overlay_style"
              :primary-color="localState.primary_color"
              :text-color="localState.text_color"
              :accent-color="localState.accent_color"
            />
          </div>
          <p class="preview-hint">This is how your profile photo will appear</p>
        </div>
      </div>

      <!-- Settings Column -->
      <div class="settings-column">
        <!-- Photo Upload Section -->
        <div class="settings-section">
          <PlayerPhotoUpload
            :photo1-url="localState.photo_1_url"
            :photo2-url="localState.photo_2_url"
            :photo3-url="localState.photo_3_url"
            :profile-photo-slot="localState.profile_photo_slot"
            :player-number="localState.player_number"
            :player-position="primaryPosition"
            :overlay-style="localState.overlay_style"
            :primary-color="localState.primary_color"
            :text-color="localState.text_color"
            :accent-color="localState.accent_color"
            @update="handlePhotoUpdate"
          />
        </div>

        <!-- Quick Actions -->
        <div class="settings-section">
          <button
            v-if="teamColors"
            type="button"
            class="btn btn-team-colors"
            @click="applyTeamColors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a1 1 0 110 2h-3a1 1 0 01-1-1v-2a1 1 0 00-1-1H9a1 1 0 00-1 1v2a1 1 0 01-1 1H4a1 1 0 110-2V4zm3 1h2v2H7V5zm2 4H7v2h2V9zm2-4h2v2h-2V5zm2 4h-2v2h2V9z"
              />
            </svg>
            Use Team Colors
          </button>
        </div>

        <!-- Overlay Style -->
        <div class="settings-section">
          <h3>Overlay Style</h3>
          <div class="style-options">
            <label
              v-for="style in overlayStyles"
              :key="style.value"
              class="style-option"
              :class="{ selected: localState.overlay_style === style.value }"
            >
              <input
                type="radio"
                :value="style.value"
                v-model="localState.overlay_style"
                class="sr-only"
              />
              <span class="style-icon">{{ style.icon }}</span>
              <span class="style-label">{{ style.label }}</span>
            </label>
          </div>
        </div>

        <!-- Colors -->
        <div class="settings-section">
          <h3>Colors</h3>
          <div class="color-settings">
            <ColorPalette
              v-model="localState.primary_color"
              label="Primary Color"
            />
            <ColorPalette v-model="localState.text_color" label="Text Color" />
            <ColorPalette
              v-model="localState.accent_color"
              label="Accent Color"
            />
          </div>
        </div>

        <!-- Player Info -->
        <div class="settings-section">
          <h3>Player Information</h3>
          <div class="player-info-inputs">
            <div class="form-group">
              <label for="playerNumber">Jersey Number</label>
              <input
                id="playerNumber"
                type="text"
                v-model="localState.player_number"
                placeholder="e.g., 10"
                maxlength="3"
                class="form-input"
              />
            </div>
            <div class="form-group">
              <label for="playerPosition">Primary Position</label>
              <select
                id="playerPosition"
                v-model="selectedPosition"
                class="form-select"
              >
                <option value="">Select position...</option>
                <option
                  v-for="pos in availablePositions"
                  :key="pos.abbreviation"
                  :value="pos.abbreviation"
                >
                  {{ pos.abbreviation }} - {{ pos.full_name }}
                </option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Error toast -->
    <div v-if="error" class="error-toast">
      <span>{{ error }}</span>
      <button type="button" @click="error = null">&times;</button>
    </div>

    <!-- Success toast -->
    <div v-if="success" class="success-toast">
      <span>{{ success }}</span>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';
import ColorPalette from './ColorPalette.vue';
import PlayerPhotoOverlay from './PlayerPhotoOverlay.vue';
import PlayerPhotoUpload from './PlayerPhotoUpload.vue';

export default {
  name: 'PlayerProfileEditor',
  components: {
    ColorPalette,
    PlayerPhotoOverlay,
    PlayerPhotoUpload,
  },
  emits: ['close', 'saved'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const saving = ref(false);
    const error = ref(null);
    const success = ref(null);
    const availablePositions = ref([]);

    // Overlay style options
    const overlayStyles = [
      { value: 'badge', label: 'Badge', icon: '🏅' },
      { value: 'jersey', label: 'Jersey', icon: '👕' },
      { value: 'caption', label: 'Caption', icon: '📝' },
      { value: 'none', label: 'None', icon: '🚫' },
    ];

    // Initialize local state from profile
    const getInitialState = () => {
      const profile = authStore.state.profile || {};
      return {
        photo_1_url: profile.photo_1_url || null,
        photo_2_url: profile.photo_2_url || null,
        photo_3_url: profile.photo_3_url || null,
        profile_photo_slot: profile.profile_photo_slot || null,
        overlay_style: profile.overlay_style || 'badge',
        primary_color: profile.primary_color || '#3B82F6',
        text_color: profile.text_color || '#FFFFFF',
        accent_color: profile.accent_color || '#1D4ED8',
        player_number: profile.player_number || '',
        positions: profile.positions || [],
      };
    };

    const localState = ref(getInitialState());
    const savedState = ref(JSON.stringify(getInitialState()));

    // Track if there are unsaved changes
    const hasChanges = computed(() => {
      return JSON.stringify(localState.value) !== savedState.value;
    });

    // Get preview photo URL (profile photo or first available)
    const previewPhotoUrl = computed(() => {
      const slot = localState.value.profile_photo_slot;
      if (slot && localState.value[`photo_${slot}_url`]) {
        return localState.value[`photo_${slot}_url`];
      }
      // Fall back to first available photo
      for (let i = 1; i <= 3; i++) {
        if (localState.value[`photo_${i}_url`]) {
          return localState.value[`photo_${i}_url`];
        }
      }
      return null;
    });

    // Selected primary position
    const selectedPosition = computed({
      get: () => {
        const positions = localState.value.positions;
        return positions && positions.length > 0 ? positions[0] : '';
      },
      set: value => {
        if (value) {
          localState.value.positions = [value];
        } else {
          localState.value.positions = [];
        }
      },
    });

    // Primary position for display
    const primaryPosition = computed(() => {
      const positions = localState.value.positions;
      return positions && positions.length > 0 ? positions[0] : null;
    });

    // Team colors
    const teamColors = computed(() => {
      const team = authStore.state.profile?.team;
      const club = team?.club;
      if (club?.primary_color) {
        return {
          primary: club.primary_color,
          secondary: club.secondary_color || '#1D4ED8',
          text: '#FFFFFF',
        };
      }
      return null;
    });

    // Apply team colors
    const applyTeamColors = () => {
      if (teamColors.value) {
        localState.value.primary_color = teamColors.value.primary;
        localState.value.accent_color = teamColors.value.secondary;
        localState.value.text_color = teamColors.value.text;
      }
    };

    // Handle photo upload update
    const handlePhotoUpdate = profile => {
      if (profile) {
        localState.value.photo_1_url = profile.photo_1_url;
        localState.value.photo_2_url = profile.photo_2_url;
        localState.value.photo_3_url = profile.photo_3_url;
        localState.value.profile_photo_slot = profile.profile_photo_slot;
        // Update saved state for photo changes (they're already saved)
        savedState.value = JSON.stringify(localState.value);
      }
    };

    // Fetch available positions
    const fetchPositions = async () => {
      try {
        const response = await fetch(`${getApiBaseUrl()}/api/positions`);
        if (response.ok) {
          availablePositions.value = await response.json();
        }
      } catch (err) {
        console.error('Error fetching positions:', err);
      }
    };

    // Handle cancel
    const handleCancel = () => {
      if (hasChanges.value) {
        if (
          !confirm('You have unsaved changes. Are you sure you want to cancel?')
        ) {
          return;
        }
      }
      emit('close');
    };

    // Handle publish
    const handlePublish = async () => {
      try {
        saving.value = true;
        error.value = null;

        // Build customization update
        const customization = {
          overlay_style: localState.value.overlay_style,
          primary_color: localState.value.primary_color,
          text_color: localState.value.text_color,
          accent_color: localState.value.accent_color,
          player_number: localState.value.player_number || null,
          positions: localState.value.positions,
        };

        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/auth/profile/customization`,
          {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(customization),
          }
        );

        // Refresh profile
        await authStore.fetchProfile();

        // Update saved state
        savedState.value = JSON.stringify(localState.value);

        // Show success message
        success.value = 'Profile saved successfully!';
        setTimeout(() => {
          success.value = null;
        }, 3000);

        emit('saved');
      } catch (err) {
        console.error('Save error:', err);
        error.value =
          err.message || 'Failed to save profile. Please try again.';
      } finally {
        saving.value = false;
      }
    };

    // Warn on navigation if unsaved changes
    const handleBeforeUnload = e => {
      if (hasChanges.value) {
        e.preventDefault();
        e.returnValue = '';
      }
    };

    onMounted(() => {
      fetchPositions();
      window.addEventListener('beforeunload', handleBeforeUnload);
    });

    onBeforeUnmount(() => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    });

    // Watch for profile changes from auth store
    watch(
      () => authStore.state.profile,
      () => {
        // Only update if we haven't made changes
        if (!hasChanges.value) {
          localState.value = getInitialState();
          savedState.value = JSON.stringify(localState.value);
        }
      },
      { deep: true }
    );

    return {
      localState,
      saving,
      error,
      success,
      hasChanges,
      previewPhotoUrl,
      primaryPosition,
      selectedPosition,
      teamColors,
      overlayStyles,
      availablePositions,
      applyTeamColors,
      handlePhotoUpdate,
      handleCancel,
      handlePublish,
    };
  },
};
</script>

<style scoped>
.player-profile-editor {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.editor-header h2 {
  margin: 0;
  font-size: 24px;
  color: #1f2937;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s ease;
  border: none;
}

.btn-secondary {
  background-color: #f3f4f6;
  color: #374151;
}

.btn-secondary:hover {
  background-color: #e5e7eb;
}

.btn-primary {
  background-color: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #2563eb;
}

.btn-primary:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

.unsaved-warning {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background-color: #fef3c7;
  border: 1px solid #f59e0b;
  border-radius: 8px;
  margin-bottom: 20px;
  color: #92400e;
  font-size: 14px;
}

.unsaved-warning svg {
  width: 20px;
  height: 20px;
  color: #f59e0b;
}

.editor-content {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 30px;
}

@media (max-width: 768px) {
  .editor-content {
    grid-template-columns: 1fr;
  }
}

.preview-column {
  position: sticky;
  top: 20px;
  height: fit-content;
}

.preview-card {
  background-color: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
}

.preview-card h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  color: #374151;
}

.preview-photo {
  width: 100%;
  max-width: 260px;
  margin: 0 auto;
}

.preview-hint {
  text-align: center;
  color: #6b7280;
  font-size: 12px;
  margin: 12px 0 0 0;
}

.settings-column {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.settings-section {
  background-color: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
}

.settings-section h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  color: #1f2937;
  font-weight: 600;
}

.btn-team-colors {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 12px;
  background-color: #ecfdf5;
  color: #059669;
  border: 1px solid #a7f3d0;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-team-colors:hover {
  background-color: #d1fae5;
}

.btn-team-colors svg {
  width: 20px;
  height: 20px;
}

.style-options {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

@media (max-width: 480px) {
  .style-options {
    grid-template-columns: repeat(2, 1fr);
  }
}

.style-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 12px;
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.style-option:hover {
  border-color: #3b82f6;
  background-color: #eff6ff;
}

.style-option.selected {
  border-color: #3b82f6;
  background-color: #eff6ff;
}

.style-icon {
  font-size: 24px;
}

.style-label {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

.color-settings {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.player-info-inputs {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 16px;
}

@media (max-width: 480px) {
  .player-info-inputs {
    grid-template-columns: 1fr;
  }
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.form-input,
.form-select {
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.15s ease;
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.error-toast,
.success-toast {
  position: fixed;
  bottom: 20px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  animation: slideIn 0.3s ease;
  z-index: 1000;
}

@keyframes slideIn {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.error-toast {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
}

.success-toast {
  background-color: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #059669;
}

.error-toast button,
.success-toast button {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: inherit;
  line-height: 1;
}
</style>
