<template>
  <transition name="update-fade">
    <div
      v-if="needsRefresh"
      class="update-banner"
      role="dialog"
      aria-label="App update available"
    >
      <button
        @click="dismiss"
        class="update-dismiss"
        aria-label="Dismiss update banner"
      >
        ×
      </button>
      <div class="update-body">
        <span class="update-icon" aria-hidden="true">✨</span>
        <span class="update-text">
          <strong>A new version of MT is ready.</strong>
          <span>Reload to get the latest.</span>
        </span>
        <button @click="onReload" class="update-reload">Reload</button>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, watch } from 'vue';
import { usePwaUpdate } from '../composables/usePwaUpdate';

const { needsRefresh: rawNeedsRefresh, reload } = usePwaUpdate();

// Local ref so the user can dismiss; if a *newer* version comes in later,
// rawNeedsRefresh fires again and we re-show.
const dismissed = ref(false);
const needsRefresh = ref(false);

watch(
  rawNeedsRefresh,
  newVal => {
    if (newVal) {
      dismissed.value = false;
      needsRefresh.value = true;
    } else {
      needsRefresh.value = false;
    }
  },
  { immediate: true }
);

function dismiss() {
  needsRefresh.value = false;
  dismissed.value = true;
}

function onReload() {
  // Defer the visible state flip slightly so the banner doesn't snap-disappear
  // before the page actually reloads.
  needsRefresh.value = false;
  reload();
}
</script>

<style scoped>
.update-banner {
  position: fixed;
  left: 12px;
  right: 12px;
  bottom: calc(env(safe-area-inset-bottom, 0px) + 12px);
  z-index: 1050;
  background: #0257fe;
  color: white;
  border-radius: 12px;
  padding: 12px 40px 12px 14px;
  box-shadow:
    0 10px 25px -5px rgba(0, 0, 0, 0.25),
    0 4px 6px -2px rgba(0, 0, 0, 0.15);
  font-size: 14px;
  line-height: 1.35;
  max-width: 480px;
  margin: 0 auto;
}

.update-body {
  display: flex;
  align-items: center;
  gap: 12px;
}

.update-icon {
  font-size: 20px;
  line-height: 1;
  flex-shrink: 0;
}

.update-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.update-text strong {
  font-weight: 700;
}

.update-reload {
  flex-shrink: 0;
  padding: 8px 14px;
  border-radius: 8px;
  background: white;
  color: #0257fe;
  font-weight: 600;
  font-size: 13px;
  border: none;
  cursor: pointer;
  min-height: 36px;
}

.update-reload:hover,
.update-reload:focus-visible {
  background: #f0f6ff;
  outline: none;
}

.update-dismiss {
  position: absolute;
  top: 6px;
  right: 8px;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: white;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  border-radius: 6px;
}

.update-dismiss:hover,
.update-dismiss:focus-visible {
  background: rgba(255, 255, 255, 0.15);
  outline: none;
}

.update-fade-enter-active,
.update-fade-leave-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s ease;
}

.update-fade-enter-from,
.update-fade-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
</style>
