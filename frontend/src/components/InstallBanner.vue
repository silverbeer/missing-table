<template>
  <transition name="install-banner-fade">
    <div
      v-if="visible"
      class="install-banner"
      data-testid="install-banner"
      :data-mode="mode"
    >
      <button
        class="install-dismiss"
        aria-label="Dismiss"
        data-testid="install-banner-dismiss"
        @click.stop="dismiss"
      >
        ×
      </button>
      <div class="install-body">
        <span class="install-icon" aria-hidden="true">{{
          mode === 'ios' ? '🔔' : '⚽'
        }}</span>
        <div class="install-text">
          <strong>{{ headline }}</strong>
          <span>{{ subline }}</span>
        </div>
      </div>
      <!-- iOS gets instructions because Apple ships no install API; everywhere
           else gets the real thing. The old version of this banner was a filled
           blue card with no click handler at all — users tapped it, nothing
           happened, and they gave up (SB-810). -->
      <button
        v-if="mode === 'ios'"
        class="install-action"
        data-testid="install-banner-action"
        @click="openGuide"
      >
        Show me how
      </button>
      <button
        v-else
        class="install-action"
        :disabled="prompting"
        data-testid="install-banner-install"
        @click="onInstall"
      >
        {{ prompting ? 'Installing…' : 'Install' }}
      </button>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { isIosNonStandalone, isTouchDevice } from '../utils/pwa';
import {
  openSetupGuide,
  useNotificationSetup,
} from '../composables/useNotificationSetup';
import { useInstallPrompt } from '../composables/useInstallPrompt';

const iosEligible = ref(false);
// Same dismissal record the guide writes: the banner and the guide are two
// faces of one nag, so "not now" in either silences both — including a
// dismissal that happens in the guide while this banner sits behind it.
const { dismissPrompt, promptDismissed } = useNotificationSetup();
const { canInstall, prompting, promptInstall } = useInstallPrompt();

// Phones only. Chromium offers beforeinstallprompt on desktop too, but a
// fixed bottom banner on a laptop is noise — the guide still carries the
// optional install offer there for anyone who wants it.
const nativeEligible = computed(() => canInstall.value && isTouchDevice());

/**
 * 'ios'    — no install API exists; the banner routes to instructions
 * 'native' — Chromium handed us a real prompt; the banner fires it
 */
const mode = computed(() => {
  if (iosEligible.value) return 'ios';
  if (nativeEligible.value) return 'native';
  return null;
});

const visible = computed(() => mode.value !== null && !promptDismissed.value);

// The pitch differs because the platforms differ. On iPhone, installing is the
// only way to get notifications at all. On Android notifications already work
// in a tab, so claiming otherwise would be inventing a barrier Google doesn't
// impose — there the honest pitch is the home-screen icon itself.
const headline = computed(() =>
  mode.value === 'ios'
    ? 'Want live match alerts?'
    : 'Add Missing Table to your phone'
);

const subline = computed(() =>
  mode.value === 'ios'
    ? 'iPhones can only send them from a home-screen app. Takes about 15 seconds.'
    : 'One tap to put it on your home screen — scores and alerts without hunting for a tab.'
);

function dismiss() {
  dismissPrompt();
}

async function onInstall() {
  const { outcome } = await promptInstall();
  // A dismissed native dialog is not a "leave me alone" — the user may just
  // have mis-tapped, and Chromium may offer the event again. Only record a
  // dismissal when they dismiss OUR banner.
  if (outcome === 'accepted') iosEligible.value = false;
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
  // iOS is decided at mount (a UA + display-mode check, stable for the
  // session). The native path is event-driven, so it stays reactive.
  if (isIosNonStandalone()) iosEligible.value = true;
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

.install-action:hover:not(:disabled),
.install-action:focus-visible {
  background: #1d4ed8;
  outline: none;
}

.install-action:disabled {
  opacity: 0.65;
  cursor: progress;
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
