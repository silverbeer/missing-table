<template>
  <transition name="offline-fade">
    <div
      v-if="!isOnline"
      class="offline-indicator"
      role="status"
      aria-live="polite"
    >
      <span class="offline-dot" aria-hidden="true"></span>
      <span class="offline-text">
        <strong>Offline</strong> — showing last-loaded data
      </span>
    </div>
  </transition>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';

const isOnline = ref(true);

function update() {
  if (typeof navigator === 'undefined') return;
  isOnline.value = navigator.onLine;
}

function handleOnline() {
  isOnline.value = true;
}

function handleOffline() {
  isOnline.value = false;
}

onMounted(() => {
  update();
  window.addEventListener('online', handleOnline);
  window.addEventListener('offline', handleOffline);
});

onBeforeUnmount(() => {
  window.removeEventListener('online', handleOnline);
  window.removeEventListener('offline', handleOffline);
});
</script>

<style scoped>
.offline-indicator {
  position: fixed;
  top: calc(env(safe-area-inset-top, 0px) + 8px);
  left: 50%;
  transform: translateX(-50%);
  z-index: 1100;
  background: #1f2937;
  color: white;
  font-size: 13px;
  line-height: 1.2;
  padding: 8px 14px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 6px 16px -4px rgba(0, 0, 0, 0.35);
  pointer-events: none;
  max-width: calc(100vw - 24px);
}

.offline-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.25);
  flex-shrink: 0;
}

.offline-text strong {
  font-weight: 700;
}

.offline-fade-enter-active,
.offline-fade-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.offline-fade-enter-from,
.offline-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px);
}
</style>
