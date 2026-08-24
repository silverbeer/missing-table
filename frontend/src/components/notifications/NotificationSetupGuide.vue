<template>
  <transition name="setup-guide-fade">
    <div
      v-if="guideOpen"
      class="setup-overlay"
      data-testid="notification-setup-guide"
      @click.self="onClose"
    >
      <div
        class="setup-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="setup-guide-title"
      >
        <button
          class="setup-close"
          aria-label="Close"
          data-testid="setup-close"
          @click="onClose"
        >
          ×
        </button>

        <header class="setup-header">
          <h2 id="setup-guide-title">{{ heading }}</h2>
          <p class="setup-sub">{{ subheading }}</p>
        </header>

        <!-- Progress checklist: all three steps, always, so the user can see
             how far the whole job goes rather than discovering it one wall
             at a time. -->
        <ol class="setup-steps" data-testid="setup-checklist">
          <li
            v-for="(step, i) in steps"
            :key="step.key"
            class="setup-step"
            :class="{
              'is-done': step.done,
              'is-current': !step.done && step.key === currentStep,
            }"
            :data-testid="`setup-step-${step.key}`"
          >
            <span class="setup-step-marker" aria-hidden="true">
              {{ step.done ? '✓' : i + 1 }}
            </span>
            <span class="setup-step-label">{{ step.label }}</span>
            <span v-if="step.done" class="setup-step-state">Done</span>
          </li>
        </ol>

        <!-- ===== Current step detail ===== -->

        <!-- Install (iOS only). No button can do this: iOS exposes no install
             API to web pages, so the whole job here is pointing accurately at
             the browser's own control. -->
        <section
          v-if="currentStep === 'install'"
          class="setup-detail"
          data-testid="setup-detail-install"
        >
          <h3>Add Missing Table to your home screen</h3>
          <p class="setup-why">
            iPhones only allow notifications from apps on your home screen — a
            Safari tab can’t receive them. This takes about 15 seconds and is a
            one-time thing.
          </p>
          <ol v-if="install" class="setup-instructions">
            <li
              v-for="(s, i) in install.steps"
              :key="i"
              :class="{ 'is-emphasis': s.emphasis }"
            >
              <strong>{{ s.title }}</strong>
              <span>{{ s.detail }}</span>
            </li>
          </ol>
          <p class="setup-foot">
            Instructions for <strong>{{ install?.browserLabel }}</strong
            >. Once it’s installed, open Missing Table from the home-screen icon
            and come back here to finish.
          </p>
        </section>

        <!-- Enable -->
        <section
          v-else-if="currentStep === 'enable'"
          class="setup-detail"
          data-testid="setup-detail-enable"
        >
          <h3>Turn on notifications</h3>
          <p class="setup-why">
            Your phone will ask for permission. Tap <strong>Allow</strong> —
            that’s what lets us send you goals and full-time scores.
          </p>
          <button
            class="setup-primary"
            :disabled="loading"
            data-testid="setup-enable-button"
            @click="onEnable"
          >
            {{ loading ? 'Turning on…' : 'Turn on notifications' }}
          </button>
          <p v-if="lastError" class="setup-error">{{ lastError }}</p>
        </section>

        <!-- Permission denied -->
        <section
          v-else-if="currentStep === 'blocked'"
          class="setup-detail"
          data-testid="setup-detail-blocked"
        >
          <h3>Notifications are blocked</h3>
          <p class="setup-why">
            Your phone is set to block notifications from Missing Table, so we
            can’t ask again from here — it has to be changed in Settings.
          </p>
          <ol class="setup-instructions">
            <li>
              <strong>Open Settings on your iPhone</strong>
              <span>Then scroll down to Missing Table.</span>
            </li>
            <li>
              <strong>Tap Notifications</strong>
              <span>Switch "Allow Notifications" on, then come back here.</span>
            </li>
          </ol>
        </section>

        <!-- Follow -->
        <section
          v-else-if="currentStep === 'follow'"
          class="setup-detail"
          data-testid="setup-detail-follow"
        >
          <h3>Follow a team</h3>
          <p class="setup-why">
            Notifications are on for this device. The last step is choosing who
            to hear about — we only send alerts for teams you follow.
          </p>
          <p class="setup-foot">
            Open a team’s page and tap <strong>Follow</strong>. You can follow
            as many as you like, and change what you get notified about in your
            profile.
          </p>
        </section>

        <!-- Done -->
        <section
          v-else-if="currentStep === 'done'"
          class="setup-detail"
          data-testid="setup-detail-done"
        >
          <h3>You’re all set</h3>
          <p class="setup-why">
            You’ll get a push when a team you follow kicks off, scores, reaches
            halftime, or finishes. Send yourself a test from your profile if
            you’d like to see one now.
          </p>
        </section>

        <!-- Push genuinely unavailable. Deliberately NOT shown for an iOS tab:
             iOS hides PushManager outside standalone mode, which reads as
             "unsupported" when the honest answer is "install it first". -->
        <section
          v-else
          class="setup-detail"
          data-testid="setup-detail-unsupported"
        >
          <h3>This browser can’t do notifications</h3>
          <p class="setup-why">
            Try Chrome, Edge, Firefox, or Safari 16.4 and later. On iPhone,
            you’ll also need Missing Table on your home screen.
          </p>
        </section>

        <footer class="setup-footer">
          <button
            class="setup-secondary"
            data-testid="setup-dismiss"
            @click="onClose"
          >
            {{ isComplete ? 'Close' : 'Not now' }}
          </button>
        </footer>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed, watch } from 'vue';
import { useNotificationSetup } from '../../composables/useNotificationSetup';
import { usePushNotifications } from '../../composables/usePushNotifications';
import { getInstallSteps } from '../../utils/pwa';

const {
  guideOpen,
  guideReason,
  steps,
  currentStep,
  isComplete,
  close,
  dismissPrompt,
  ensureFollowsLoaded,
} = useNotificationSetup();

const { enable, loading, lastError, listSubscriptions } =
  usePushNotifications();

// Recomputed on open rather than at import time — a user can install mid-session
// and reopen the guide, and the standalone check has to reflect that.
const install = computed(() => (guideOpen.value ? getInstallSteps() : null));

const heading = computed(() => {
  if (isComplete.value) return 'Notifications are on';
  if (guideReason.value === 'follow') return 'One more step to get alerts';
  return 'Get live match alerts';
});

const subheading = computed(() => {
  if (isComplete.value) {
    return 'Nothing left to do — alerts will arrive on this device.';
  }
  if (guideReason.value === 'follow') {
    return 'Following a team saves it to your list. Getting a push takes a bit more.';
  }
  return 'Goals, kickoff, halftime and full-time — pushed to your phone as they happen.';
});

async function onEnable() {
  const result = await enable();
  if (result.success) {
    // Re-read the authoritative backend state rather than trusting the local
    // flag, so the checklist can't tick a step the server didn't record (SB-52).
    await listSubscriptions();
  }
}

function onClose() {
  // Closing an unfinished guide is a "leave me alone" signal — record it so
  // the unprompted first-login version doesn't reappear on the next visit.
  if (isComplete.value) close();
  else dismissPrompt();
}

watch(guideOpen, open => {
  if (!open) return;
  ensureFollowsLoaded();
  // The push subscription list is the only trustworthy source for whether
  // "enable" is really done; permission alone lies (SB-52).
  listSubscriptions();
});
</script>

<style scoped>
.setup-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 0;
}

.setup-sheet {
  position: relative;
  width: 100%;
  max-width: 480px;
  max-height: 88vh;
  overflow-y: auto;
  background: rgb(var(--color-card));
  color: rgb(var(--color-fg));
  border-radius: 18px 18px 0 0;
  padding: 22px 20px calc(env(safe-area-inset-bottom, 0px) + 20px);
  box-shadow: 0 -8px 30px rgba(0, 0, 0, 0.28);
}

@media (min-width: 640px) {
  .setup-overlay {
    align-items: center;
    padding: 20px;
  }
  .setup-sheet {
    border-radius: 16px;
    padding-bottom: 20px;
  }
}

.setup-close {
  position: absolute;
  top: 10px;
  right: 12px;
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  color: rgb(var(--color-fg-muted));
  font-size: 26px;
  line-height: 1;
  border-radius: 8px;
  cursor: pointer;
}

.setup-close:hover,
.setup-close:focus-visible {
  background: rgb(var(--color-line));
  outline: none;
}

.setup-header h2 {
  margin: 0 36px 4px 0;
  font-size: 19px;
  font-weight: 800;
}

.setup-sub {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.45;
  color: rgb(var(--color-fg-muted));
}

.setup-steps {
  list-style: none;
  margin: 18px 0;
  padding: 0;
  border: 1px solid rgb(var(--color-line));
  border-radius: 12px;
  overflow: hidden;
}

.setup-step {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 13px;
  font-size: 14px;
  border-bottom: 1px solid rgb(var(--color-line));
}

.setup-step:last-child {
  border-bottom: none;
}

.setup-step-marker {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  background: rgb(var(--color-line));
  color: rgb(var(--color-fg-muted));
}

.setup-step-label {
  flex: 1;
}

.setup-step-state {
  font-size: 11.5px;
  font-weight: 700;
  color: rgb(5, 150, 105);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.setup-step.is-done .setup-step-marker {
  background: rgb(16, 185, 129);
  color: white;
}

.setup-step.is-done .setup-step-label {
  color: rgb(var(--color-fg-muted));
}

.setup-step.is-current {
  background: rgba(30, 64, 175, 0.07);
}

.setup-step.is-current .setup-step-marker {
  background: #1e40af;
  color: white;
}

.setup-step.is-current .setup-step-label {
  font-weight: 700;
}

.setup-detail h3 {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 800;
}

.setup-why {
  margin: 0 0 14px;
  font-size: 13.5px;
  line-height: 1.5;
  color: rgb(var(--color-fg-muted));
}

.setup-instructions {
  margin: 0 0 14px;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.setup-instructions li {
  font-size: 13.5px;
  line-height: 1.45;
}

.setup-instructions strong {
  display: block;
  font-weight: 700;
  margin-bottom: 2px;
}

.setup-instructions span {
  color: rgb(var(--color-fg-muted));
}

/* The share-sheet scroll step is where people conclude the option doesn't
   exist and give up, so it gets visual weight the others don't. */
.setup-instructions li.is-emphasis {
  background: rgba(245, 158, 11, 0.12);
  border-left: 3px solid rgb(245, 158, 11);
  border-radius: 0 8px 8px 0;
  padding: 9px 11px;
  margin-left: -8px;
}

.setup-primary {
  width: 100%;
  min-height: 48px;
  border: none;
  border-radius: 10px;
  background: #1e40af;
  color: white;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}

.setup-primary:disabled {
  opacity: 0.65;
  cursor: progress;
}

.setup-foot {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.45;
  color: rgb(var(--color-fg-muted));
}

.setup-error {
  margin: 10px 0 0;
  font-size: 13px;
  color: rgb(220, 38, 38);
}

.setup-footer {
  margin-top: 18px;
  display: flex;
  justify-content: center;
}

.setup-secondary {
  min-height: 44px;
  padding: 0 18px;
  border: 1px solid rgb(var(--color-line));
  border-radius: 10px;
  background: transparent;
  color: rgb(var(--color-fg-muted));
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.setup-guide-fade-enter-active,
.setup-guide-fade-leave-active {
  transition: opacity 0.2s ease;
}

.setup-guide-fade-enter-from,
.setup-guide-fade-leave-to {
  opacity: 0;
}
</style>
