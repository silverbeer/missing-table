<template>
  <div class="player-photo-upload">
    <div class="upload-header">
      <h3>Profile Photos</h3>
      <button type="button" class="help-btn" @click="showHelp = !showHelp">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          width="18"
          height="18"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        Help
      </button>
    </div>

    <!-- Help Panel -->
    <div v-if="showHelp" class="help-panel">
      <h4>Photo Requirements</h4>
      <ul>
        <li><strong>Max size:</strong> 500KB per photo</li>
        <li><strong>Formats:</strong> JPG, PNG, or WebP</li>
        <li><strong>Tip:</strong> Square photos look best!</li>
      </ul>

      <h4>iPhone: How to Resize Photos</h4>
      <ol>
        <li>Open the <strong>Photos</strong> app</li>
        <li>Select your photo and tap <strong>Edit</strong></li>
        <li>Tap the <strong>crop</strong> icon (square with arrows)</li>
        <li>Choose <strong>Square</strong> aspect ratio</li>
        <li>Tap <strong>Done</strong></li>
        <li>
          To reduce file size: Use the <strong>Shortcuts</strong> app with
          "Resize Image"
        </li>
      </ol>

      <button type="button" class="close-help" @click="showHelp = false">
        Got it!
      </button>
    </div>

    <!-- Photo Grid -->
    <div class="photo-grid">
      <div
        v-for="slot in [1, 2, 3]"
        :key="slot"
        class="photo-slot"
        :class="{
          'is-profile': profilePhotoSlot === slot,
          'has-photo': photos[slot],
          uploading: uploadingSlot === slot,
        }"
      >
        <!-- Profile indicator -->
        <div v-if="profilePhotoSlot === slot" class="profile-indicator">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"
            />
          </svg>
        </div>

        <!-- Photo with overlay or empty state -->
        <div
          class="photo-content"
          @click="photos[slot] ? null : triggerUpload(slot)"
        >
          <PlayerPhotoOverlay
            v-if="photos[slot]"
            :photo-url="photos[slot]"
            :number="playerNumber"
            :position="playerPosition"
            :overlay-style="overlayStyle"
            :primary-color="primaryColor"
            :text-color="textColor"
            :accent-color="accentColor"
          />
          <div v-else class="empty-slot">
            <div class="upload-icon">
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
                  d="M12 6v6m0 0v6m0-6h6m-6 0H6"
                />
              </svg>
            </div>
            <span class="slot-label">Photo {{ slot }}</span>
          </div>
        </div>

        <!-- Upload progress -->
        <div v-if="uploadingSlot === slot" class="upload-progress">
          <div class="spinner"></div>
          <span>Uploading...</span>
        </div>

        <!-- Actions -->
        <div
          v-if="photos[slot] && uploadingSlot !== slot"
          class="photo-actions"
        >
          <button
            v-if="profilePhotoSlot !== slot"
            type="button"
            class="action-btn set-profile"
            title="Set as profile photo"
            @click="setAsProfile(slot)"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"
              />
            </svg>
          </button>
          <button
            type="button"
            class="action-btn delete"
            title="Delete photo"
            @click="deletePhoto(slot)"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fill-rule="evenodd"
                d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z"
                clip-rule="evenodd"
              />
            </svg>
          </button>
        </div>

        <!-- Hidden file input -->
        <input
          :ref="el => (fileInputs[slot] = el)"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          class="hidden-input"
          @change="handleFileSelect($event, slot)"
        />
      </div>
    </div>

    <!-- Error message -->
    <div v-if="error" class="error-message">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
      >
        <path
          fill-rule="evenodd"
          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
          clip-rule="evenodd"
        />
      </svg>
      <span>{{ error }}</span>
      <button type="button" class="dismiss-error" @click="error = null">
        &times;
      </button>
    </div>
  </div>
</template>

<script>
import { ref, watch } from 'vue';
import PlayerPhotoOverlay from './PlayerPhotoOverlay.vue';
import { getApiBaseUrl } from '../../config/api';
import { useAuthStore } from '@/stores/auth';

export default {
  name: 'PlayerPhotoUpload',
  components: {
    PlayerPhotoOverlay,
  },
  props: {
    photo1Url: {
      type: String,
      default: null,
    },
    photo2Url: {
      type: String,
      default: null,
    },
    photo3Url: {
      type: String,
      default: null,
    },
    profilePhotoSlot: {
      type: Number,
      default: null,
    },
    playerNumber: {
      type: [String, Number],
      default: null,
    },
    playerPosition: {
      type: String,
      default: null,
    },
    overlayStyle: {
      type: String,
      default: 'badge',
    },
    primaryColor: {
      type: String,
      default: '#3B82F6',
    },
    textColor: {
      type: String,
      default: '#FFFFFF',
    },
    accentColor: {
      type: String,
      default: '#1D4ED8',
    },
  },
  emits: ['update', 'error'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const fileInputs = ref({});
    const uploadingSlot = ref(null);
    const error = ref(null);
    const showHelp = ref(false);

    // Reactive photos object
    const photos = ref({
      1: props.photo1Url,
      2: props.photo2Url,
      3: props.photo3Url,
    });

    // Watch for prop changes
    watch(
      () => [props.photo1Url, props.photo2Url, props.photo3Url],
      ([p1, p2, p3]) => {
        photos.value = { 1: p1, 2: p2, 3: p3 };
      }
    );

    const triggerUpload = slot => {
      if (fileInputs.value[slot]) {
        fileInputs.value[slot].click();
      }
    };

    const handleFileSelect = async (event, slot) => {
      const file = event.target.files[0];
      if (!file) return;

      // Reset file input
      event.target.value = '';

      // Validate file type
      const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
      if (!validTypes.includes(file.type)) {
        error.value = 'Invalid file type. Please use JPG, PNG, or WebP.';
        emit('error', error.value);
        return;
      }

      // Validate file size (500KB)
      const maxSize = 500 * 1024;
      if (file.size > maxSize) {
        error.value = `File too large (${(file.size / 1024).toFixed(0)}KB). Maximum is 500KB.`;
        emit('error', error.value);
        return;
      }

      // Upload
      try {
        uploadingSlot.value = slot;
        error.value = null;

        const formData = new FormData();
        formData.append('file', file);

        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/auth/profile/photo/${slot}`,
          {
            method: 'POST',
            body: formData,
          },
          true // Skip JSON content-type
        );

        // Update local state
        photos.value[slot] = response.photo_url;

        // Emit update event with full profile
        emit('update', response.profile);
      } catch (err) {
        console.error('Upload error:', err);
        error.value =
          err.message || 'Failed to upload photo. Please try again.';
        emit('error', error.value);
      } finally {
        uploadingSlot.value = null;
      }
    };

    const deletePhoto = async slot => {
      if (!confirm('Delete this photo?')) return;

      try {
        uploadingSlot.value = slot;
        error.value = null;

        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/auth/profile/photo/${slot}`,
          {
            method: 'DELETE',
          }
        );

        // Update local state
        photos.value[slot] = null;

        // Emit update event
        emit('update', response.profile);
      } catch (err) {
        console.error('Delete error:', err);
        error.value =
          err.message || 'Failed to delete photo. Please try again.';
        emit('error', error.value);
      } finally {
        uploadingSlot.value = null;
      }
    };

    const setAsProfile = async slot => {
      try {
        error.value = null;

        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/auth/profile/photo/profile-slot`,
          {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ slot }),
          }
        );

        // Emit update event
        emit('update', response.profile);
      } catch (err) {
        console.error('Set profile error:', err);
        error.value =
          err.message || 'Failed to set profile photo. Please try again.';
        emit('error', error.value);
      }
    };

    return {
      photos,
      fileInputs,
      uploadingSlot,
      error,
      showHelp,
      triggerUpload,
      handleFileSelect,
      deletePhoto,
      setAsProfile,
    };
  },
};
</script>

<style scoped>
.player-photo-upload {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.upload-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.help-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  font-size: 13px;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.15s ease;
}

.help-btn:hover {
  background-color: #f3f4f6;
  color: #374151;
}

.help-panel {
  background-color: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  padding: 16px;
  font-size: 14px;
}

.help-panel h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #1e40af;
}

.help-panel ul,
.help-panel ol {
  margin: 0 0 16px 0;
  padding-left: 20px;
  color: #374151;
}

.help-panel li {
  margin-bottom: 4px;
}

.close-help {
  background-color: #3b82f6;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: background-color 0.15s ease;
}

.close-help:hover {
  background-color: #2563eb;
}

.photo-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

@media (max-width: 480px) {
  .photo-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.photo-slot {
  position: relative;
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
  background-color: #f3f4f6;
  border: 2px dashed #d1d5db;
  transition: all 0.15s ease;
}

.photo-slot.has-photo {
  border-style: solid;
  border-color: #e5e7eb;
}

.photo-slot.is-profile {
  border-color: #f59e0b;
  box-shadow: 0 0 0 2px #fef3c7;
}

.photo-slot:not(.has-photo):hover {
  border-color: #3b82f6;
  background-color: #eff6ff;
}

.profile-indicator {
  position: absolute;
  top: -1px;
  left: -1px;
  background-color: #f59e0b;
  color: white;
  padding: 4px 8px;
  border-radius: 0 0 8px 0;
  z-index: 10;
}

.profile-indicator svg {
  width: 14px;
  height: 14px;
}

.photo-content {
  width: 100%;
  height: 100%;
  cursor: pointer;
}

.photo-slot.has-photo .photo-content {
  cursor: default;
}

.empty-slot {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #9ca3af;
}

.upload-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-icon svg {
  width: 24px;
  height: 24px;
}

.slot-label {
  font-size: 12px;
  font-weight: 500;
}

.upload-progress {
  position: absolute;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: white;
  font-size: 12px;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.photo-actions {
  position: absolute;
  bottom: 8px;
  right: 8px;
  display: flex;
  gap: 4px;
}

.action-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.action-btn svg {
  width: 16px;
  height: 16px;
}

.action-btn.set-profile {
  background-color: rgba(255, 255, 255, 0.9);
  color: #f59e0b;
}

.action-btn.set-profile:hover {
  background-color: #f59e0b;
  color: white;
}

.action-btn.delete {
  background-color: rgba(255, 255, 255, 0.9);
  color: #dc2626;
}

.action-btn.delete:hover {
  background-color: #dc2626;
  color: white;
}

.hidden-input {
  display: none;
}

.error-message {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #dc2626;
  font-size: 14px;
}

.error-message svg {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.dismiss-error {
  margin-left: auto;
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #dc2626;
  line-height: 1;
}
</style>
