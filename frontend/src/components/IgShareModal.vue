<template>
  <!-- SB-32: Instagram share modal. Generates a 1080×1080 PNG via html2canvas
       from <IgShareCard>, uploads the source photo to R2 for persistence. -->
  <div
    v-if="open"
    class="ig-modal-backdrop"
    data-testid="ig-share-modal"
    @click.self="onClose"
  >
    <div class="ig-modal-panel" role="dialog" aria-modal="true">
      <header class="ig-modal-header">
        <h2 class="ig-modal-title">Share to Instagram</h2>
        <button
          @click="onClose"
          data-testid="ig-close-button"
          class="ig-modal-close"
          aria-label="Close"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="w-5 h-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </header>

      <div class="ig-modal-body">
        <!-- Mode toggle (only meaningful if both modes are available) -->
        <div v-if="canPickMode" class="ig-mode-toggle" role="tablist">
          <button
            role="tab"
            :aria-selected="mode === 'preview'"
            data-testid="ig-mode-preview"
            class="ig-mode-button"
            :class="{ 'ig-mode-active': mode === 'preview' }"
            @click="mode = 'preview'"
          >
            Preview
          </button>
          <button
            role="tab"
            :aria-selected="mode === 'result'"
            data-testid="ig-mode-result"
            class="ig-mode-button"
            :class="{ 'ig-mode-active': mode === 'result' }"
            @click="mode = 'result'"
          >
            Result
          </button>
        </div>

        <!-- Photo picker -->
        <label class="ig-file-picker" data-testid="ig-file-picker">
          <input
            ref="fileInput"
            type="file"
            accept="image/jpeg,image/png"
            class="sr-only"
            data-testid="ig-file-input"
            @change="onFileChange"
          />
          <span class="ig-file-picker-cta">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M3 16v2a2 2 0 002 2h14a2 2 0 002-2v-2M16 8l-4-4m0 0L8 8m4-4v12"
              />
            </svg>
            <span>{{ photoFile ? 'Replace photo' : 'Choose photo' }}</span>
          </span>
          <span
            v-if="photoFile"
            class="ig-file-meta"
            data-testid="ig-file-meta"
          >
            {{ photoFile.name }} ({{ formatBytes(photoFile.size) }})
          </span>
        </label>

        <p v-if="fileError" class="ig-error" data-testid="ig-file-error">
          {{ fileError }}
        </p>

        <!-- Scaled preview (visible) -->
        <div class="ig-preview-frame">
          <div class="ig-preview-scaler">
            <IgShareCard
              :match="match"
              :photo-src="localPhotoUrl"
              :mode="mode"
              data-testid="ig-preview-card"
            />
          </div>
        </div>

        <p v-if="uploadError" class="ig-error" data-testid="ig-upload-error">
          {{ uploadError }}
        </p>

        <!-- Actions -->
        <div class="ig-actions">
          <button
            class="ig-action-button ig-action-secondary"
            data-testid="ig-copy-button"
            :disabled="busy"
            @click="onCopy"
          >
            <span v-if="status === 'copying'">Copying…</span>
            <span v-else-if="status === 'copied'">Copied!</span>
            <span v-else>Copy to clipboard</span>
          </button>
          <button
            class="ig-action-button ig-action-primary"
            data-testid="ig-download-button"
            :disabled="busy"
            @click="onDownload"
          >
            <span v-if="status === 'downloading'">Generating…</span>
            <span v-else>Download PNG</span>
          </button>
        </div>

        <p class="ig-hint">
          The card is generated at 1080×1080 — Instagram's square size. Paste it
          into a new post.
        </p>
      </div>
    </div>

    <!-- Offscreen full-size card used for html2canvas capture.
         Kept in the DOM so html2canvas can read computed styles, but
         translated offscreen so it doesn't affect layout. -->
    <div class="ig-capture-host" aria-hidden="true">
      <IgShareCard
        ref="captureCard"
        :match="match"
        :photo-src="localPhotoUrl"
        :mode="mode"
        data-testid="ig-capture-card"
      />
    </div>
  </div>
</template>

<script>
import { computed, ref, watch } from 'vue';
import html2canvas from 'html2canvas';
import IgShareCard from './IgShareCard.vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../config/api';

const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
const ACCEPTED_TYPES = ['image/jpeg', 'image/png'];

const formatBytes = bytes => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

export default {
  name: 'IgShareModal',
  components: { IgShareCard },
  props: {
    open: { type: Boolean, default: false },
    match: { type: Object, required: true },
  },
  emits: ['close', 'photo-uploaded'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const fileInput = ref(null);
    const captureCard = ref(null);

    const photoFile = ref(null);
    const localPhotoUrl = ref(null);
    const fileError = ref(null);
    const uploadError = ref(null);
    const status = ref(null); // 'downloading' | 'copying' | 'copied'
    const uploadedKey = ref(null);

    const isCompleted = computed(
      () => props.match?.match_status === 'completed'
    );
    const canPickMode = computed(() => isCompleted.value);

    const mode = ref('preview');

    watch(
      () => props.open,
      isOpen => {
        if (!isOpen) return;
        // Reset transient state on open, but keep defaults sensible.
        fileError.value = null;
        uploadError.value = null;
        status.value = null;
        mode.value = isCompleted.value ? 'result' : 'preview';
      },
      { immediate: true }
    );

    const revokeLocalUrl = () => {
      if (localPhotoUrl.value) {
        URL.revokeObjectURL(localPhotoUrl.value);
        localPhotoUrl.value = null;
      }
    };

    const onFileChange = e => {
      const file = e.target.files?.[0];
      if (!file) return;
      fileError.value = null;
      uploadError.value = null;

      if (!ACCEPTED_TYPES.includes(file.type)) {
        fileError.value = 'Photo must be a JPEG or PNG.';
        return;
      }
      if (file.size > MAX_PHOTO_BYTES) {
        fileError.value = `Photo is too large (max 5 MB). Got ${formatBytes(file.size)}.`;
        return;
      }

      revokeLocalUrl();
      photoFile.value = file;
      localPhotoUrl.value = URL.createObjectURL(file);
    };

    // Upload the source photo to R2 so it's persisted on the match. Returns
    // true on success, false on graceful failure (we still let the user
    // download the card).
    const ensurePhotoUploaded = async () => {
      if (!photoFile.value || uploadedKey.value) return true;

      const formData = new FormData();
      formData.append('file', photoFile.value);

      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/matches/${props.match.id}/photo`,
          { method: 'POST', body: formData }
        );
        uploadedKey.value = data?.photo_key || null;
        emit('photo-uploaded', data);
        return true;
      } catch (err) {
        // apiRequest surfaces the FastAPI `detail` as err.message — we lose
        // the HTTP code, so match known phrases to give a useful UI.
        // Either way we don't block card generation; user still gets a PNG.
        const msg = err?.message || '';
        if (msg.includes('Cloudflare R2 is not configured')) {
          uploadError.value =
            'Photo storage is not configured. Card will download but the photo will not be saved to the match.';
        } else if (msg.includes('permission')) {
          uploadError.value =
            'You do not have permission to save a photo for this match. Card will download but not be saved.';
        } else {
          uploadError.value =
            'Failed to upload photo to storage. Card will still download.';
        }
        return false;
      }
    };

    const captureBlob = async () => {
      const el = captureCard.value?.root;
      if (!el) throw new Error('Capture card not mounted');

      const canvas = await html2canvas(el, {
        backgroundColor: '#0f172a',
        scale: 1, // Already rendered at 1080x1080.
        useCORS: true,
        allowTaint: false,
        logging: false,
        width: 1080,
        height: 1080,
        windowWidth: 1080,
        windowHeight: 1080,
      });

      return await new Promise(resolve => {
        canvas.toBlob(blob => resolve(blob), 'image/png');
      });
    };

    const busy = computed(() => status.value !== null);

    const onDownload = async () => {
      if (busy.value) return;
      status.value = 'downloading';
      try {
        await ensurePhotoUploaded();
        const blob = await captureBlob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `match-${props.match.id}-${mode.value}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        status.value = null;
      } catch (err) {
        console.error('Failed to generate share card:', err);
        uploadError.value = 'Failed to generate the share card. Try again.';
        status.value = null;
      }
    };

    const onCopy = async () => {
      if (busy.value) return;
      status.value = 'copying';
      try {
        await ensurePhotoUploaded();
        const blob = await captureBlob();
        await navigator.clipboard.write([
          new ClipboardItem({ 'image/png': blob }),
        ]);
        status.value = 'copied';
        setTimeout(() => {
          if (status.value === 'copied') status.value = null;
        }, 2000);
      } catch (err) {
        console.error('Failed to copy share card:', err);
        uploadError.value =
          'Failed to copy to clipboard. Try Download PNG instead.';
        status.value = null;
      }
    };

    const onClose = () => {
      revokeLocalUrl();
      photoFile.value = null;
      uploadedKey.value = null;
      emit('close');
    };

    return {
      fileInput,
      captureCard,
      photoFile,
      localPhotoUrl,
      fileError,
      uploadError,
      status,
      mode,
      isCompleted,
      canPickMode,
      busy,
      onFileChange,
      onDownload,
      onCopy,
      onClose,
      formatBytes,
    };
  },
};
</script>

<style scoped>
.ig-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 16px;
  overflow-y: auto;
}

.ig-modal-panel {
  background: #ffffff;
  border-radius: 12px;
  width: 100%;
  max-width: 560px;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.ig-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
}

.ig-modal-title {
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
}

.ig-modal-close {
  background: transparent;
  border: none;
  cursor: pointer;
  color: #64748b;
  padding: 6px;
  border-radius: 6px;
}

.ig-modal-close:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.ig-modal-body {
  padding: 16px 20px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ig-mode-toggle {
  display: inline-flex;
  border-radius: 8px;
  background: #f1f5f9;
  padding: 4px;
  align-self: flex-start;
  gap: 2px;
}

.ig-mode-button {
  border: none;
  background: transparent;
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  border-radius: 6px;
  cursor: pointer;
}

.ig-mode-active {
  background: #ffffff;
  color: #0f172a;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.ig-file-picker {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  cursor: pointer;
}

.ig-file-picker-cta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 8px;
  background: #0f172a;
  color: white;
  font-size: 13px;
  font-weight: 600;
}

.ig-file-meta {
  font-size: 12px;
  color: #475569;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

.ig-error {
  color: #b91c1c;
  font-size: 13px;
  margin: 0;
}

/* Preview frame: shows the IgShareCard scaled to fit modal width.
   The card itself is rendered at 1080×1080 and scaled visually via
   CSS transform — the offscreen capture card stays at full size. */
.ig-preview-frame {
  width: 100%;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  border-radius: 8px;
  background: #0f172a;
  position: relative;
}

.ig-preview-scaler {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1080px;
  transform-origin: top left;
  /* The actual scale is set per-element in CSS via container query.
     For typical modal widths (~480px) this is roughly 0.44. */
  transform: scale(0.44);
}

@media (min-width: 600px) {
  .ig-preview-scaler {
    transform: scale(0.48);
  }
}

.ig-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.ig-action-button {
  padding: 10px 18px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
}

.ig-action-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ig-action-primary {
  background: #0f172a;
  color: white;
}

.ig-action-primary:hover:not(:disabled) {
  background: #1e293b;
}

.ig-action-secondary {
  background: white;
  color: #0f172a;
  border-color: #cbd5e1;
}

.ig-action-secondary:hover:not(:disabled) {
  background: #f8fafc;
}

.ig-hint {
  font-size: 12px;
  color: #64748b;
  margin: 0;
}

/* Offscreen host for the full-size capture card. Positioned far offscreen
   but kept in normal flow so html2canvas can read computed styles. */
.ig-capture-host {
  position: fixed;
  top: 0;
  left: -10000px;
  width: 1080px;
  height: 1080px;
  pointer-events: none;
}
</style>
