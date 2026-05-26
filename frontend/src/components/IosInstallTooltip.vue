<template>
  <transition name="ios-install-fade">
    <div
      v-if="shouldShow"
      class="ios-install-banner"
      role="dialog"
      aria-label="Install Missing Table"
    >
      <button
        @click="dismiss"
        class="ios-install-close"
        aria-label="Dismiss install tip"
      >
        ×
      </button>
      <div class="ios-install-body">
        <span class="ios-install-icon" aria-hidden="true">📲</span>
        <div class="ios-install-text">
          <strong>Install Missing Table</strong>
          <span>
            Tap
            <svg
              class="ios-install-share"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                fill="currentColor"
                d="M12 2 7 7l1.4 1.4L11 5.8V16h2V5.8l2.6 2.6L17 7zM5 20v-9h3v2H7v5h10v-5h-1v-2h3v9z"
              />
            </svg>
            then <strong>Add to Home Screen</strong>.
          </span>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, onMounted } from 'vue';

const STORAGE_KEY = 'mt.iosInstallTooltip.dismissedAt';
const RESHOW_DAYS = 30;

const shouldShow = ref(false);

function isIosSafari() {
  if (typeof window === 'undefined' || typeof navigator === 'undefined')
    return false;
  const ua = navigator.userAgent;
  const isIos =
    /iPad|iPhone|iPod/.test(ua) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  if (!isIos) return false;
  const isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
  return isSafari;
}

function isStandalone() {
  if (typeof window === 'undefined') return false;
  // navigator.standalone is iOS-Safari-specific; matchMedia covers other PWAs.
  return (
    window.matchMedia?.('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  );
}

function wasRecentlyDismissed() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    const dismissedAt = Number(raw);
    if (!Number.isFinite(dismissedAt)) return false;
    const ageDays = (Date.now() - dismissedAt) / (1000 * 60 * 60 * 24);
    return ageDays < RESHOW_DAYS;
  } catch {
    return false;
  }
}

function dismiss() {
  shouldShow.value = false;
  try {
    localStorage.setItem(STORAGE_KEY, String(Date.now()));
  } catch {
    // localStorage unavailable (private mode etc.) — fine, just don't persist.
  }
}

onMounted(() => {
  if (!isIosSafari()) return;
  if (isStandalone()) return;
  if (wasRecentlyDismissed()) return;
  shouldShow.value = true;
});
</script>

<style scoped>
.ios-install-banner {
  position: fixed;
  left: 12px;
  right: 12px;
  bottom: calc(env(safe-area-inset-bottom, 0px) + 12px);
  z-index: 1000;
  background: #0257fe;
  color: white;
  border-radius: 12px;
  padding: 12px 40px 12px 14px;
  box-shadow:
    0 10px 25px -5px rgba(0, 0, 0, 0.25),
    0 4px 6px -2px rgba(0, 0, 0, 0.15);
  font-size: 14px;
  line-height: 1.35;
}

.ios-install-body {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ios-install-icon {
  font-size: 22px;
  line-height: 1;
  flex-shrink: 0;
}

.ios-install-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ios-install-text strong {
  font-weight: 700;
}

.ios-install-share {
  width: 14px;
  height: 14px;
  vertical-align: -2px;
  margin: 0 2px;
}

.ios-install-close {
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

.ios-install-close:hover,
.ios-install-close:focus-visible {
  background: rgba(255, 255, 255, 0.15);
  outline: none;
}

.ios-install-fade-enter-active,
.ios-install-fade-leave-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s ease;
}

.ios-install-fade-enter-from,
.ios-install-fade-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
</style>
