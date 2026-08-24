<template>
  <transition name="install-banner-fade">
    <div v-if="visible" class="install-banner" data-testid="install-banner">
      <button
        class="install-dismiss"
        aria-label="Dismiss"
        data-testid="install-banner-dismiss"
        @click.stop="dismiss"
      >
        ×
      </button>
      <div class="install-body">
        <span class="install-icon" aria-hidden="true">🔔</span>
        <div class="install-text">
          <strong>Want live match alerts?</strong>
          <span>
            iPhones can only send them from a home-screen app. Takes about 15
            seconds.
          </span>
        </div>
      </div>
      <!-- The old version of this banner was a filled blue card with no click
           handler at all — users tapped it, nothing happened, and they gave up
           (SB-810). Now the action is an explicit, labelled button. -->
      <button
        class="install-action"
        data-testid="install-banner-action"
        @click="openGuide"
      >
        Show me how
      </button>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { isIosNonStandalone } from '../utils/pwa';
import {
  openSetupGuide,
  useNotificationSetup,
} from '../composables/useNotificationSetup';

const eligible = ref(false);
// Same dismissal record the guide writes: the banner and the guide are two
// faces of one nag, so "not now" in either silences both — including a
// dismissal that happens in the guide while this banner sits behind it.
const { dismissPrompt, promptDismissed } = useNotificationSetup();

const visible = computed(() => eligible.value && !promptDismissed.value);

function dismiss() {
  dismissPrompt();
}

function openGuide() {
  // Don't record a dismissal here — they said yes, not "not now". The banner
  // stays eligible so it returns if they close the guide without finishing.
  openSetupGuide('install');
}

onMounted(() => {
  // Every iOS browser, not just Safari: they all share WebKit, so they all
  // need the home-screen install before Web Push works. The Safari-only check
  // this replaced meant iPhone users on Chrome saw nothing at all (SB-810).
  if (!isIosNonStandalone()) return;
  eligible.value = true;
});
</script>

<style scoped>
.install-banner {
  position: fixed;
  left: 12px;
  right: 12px;
  bottom: calc(env(safe-area-inset-bottom, 0px) + 12px);
  z-index: 1000;
  max-width: 480px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgb(var(--color-card));
  color: rgb(var(--color-fg));
  border: 1px solid rgb(var(--color-line));
  border-left: 4px solid #1e40af;
  border-radius: 12px;
  padding: 12px 34px 12px 14px;
  box-shadow:
    0 10px 25px -5px rgba(0, 0, 0, 0.25),
    0 4px 6px -2px rgba(0, 0, 0, 0.15);
  font-size: 13.5px;
  line-height: 1.35;
}

.install-body {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.install-icon {
  font-size: 20px;
  line-height: 1;
  flex-shrink: 0;
}

.install-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.install-text strong {
  font-weight: 700;
}

.install-text span {
  color: rgb(var(--color-fg-muted));
  font-size: 12.5px;
}

.install-action {
  flex-shrink: 0;
  min-height: 40px;
  padding: 0 14px;
  border: none;
  border-radius: 8px;
  background: #1e40af;
  color: white;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
}

.install-action:hover,
.install-action:focus-visible {
  background: #1d4ed8;
  outline: none;
}

.install-dismiss {
  position: absolute;
  top: 4px;
  right: 6px;
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  color: rgb(var(--color-fg-muted));
  font-size: 19px;
  line-height: 1;
  cursor: pointer;
  border-radius: 6px;
}

.install-dismiss:hover,
.install-dismiss:focus-visible {
  background: rgb(var(--color-line));
  outline: none;
}

@media (max-width: 380px) {
  .install-banner {
    flex-wrap: wrap;
  }
  .install-action {
    width: 100%;
  }
}

.install-banner-fade-enter-active,
.install-banner-fade-leave-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s ease;
}

.install-banner-fade-enter-from,
.install-banner-fade-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
</style>
