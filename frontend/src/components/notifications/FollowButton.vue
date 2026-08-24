<template>
  <div v-if="visible" class="follow-wrap">
    <button
      type="button"
      class="follow-button"
      :class="[
        `follow-button--${variant}`,
        { 'is-following': following, 'is-busy': busy },
      ]"
      :disabled="busy"
      :aria-pressed="following"
      :aria-label="
        following
          ? `Unfollow ${teamName || 'team'}`
          : `Follow ${teamName || 'team'}`
      "
      data-testid="follow-button"
      @click="onClick"
    >
      <svg
        v-if="!following"
        class="follow-icon"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        aria-hidden="true"
      >
        <path
          d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
        />
      </svg>
      <svg
        v-else
        class="follow-icon"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        aria-hidden="true"
      >
        <path
          fill-rule="evenodd"
          d="M16.704 5.293a1 1 0 010 1.414l-7.5 7.5a1 1 0 01-1.414 0l-3.5-3.5a1 1 0 011.414-1.414L8.5 12.086l6.79-6.793a1 1 0 011.414 0z"
          clip-rule="evenodd"
        />
      </svg>
      <span class="follow-label">{{ label }}</span>
    </button>

    <!-- Following a team only saves it to a list — it does NOT turn on push.
         Before SB-810 nothing said so, so users tapped Follow, saw green, and
         waited for alerts that were never coming. -->
    <button
      v-if="following && !alertsLive"
      type="button"
      class="follow-hint"
      data-testid="follow-alerts-hint"
      @click="openGuide"
    >
      <span class="follow-hint-dot" aria-hidden="true"></span>
      Alerts aren’t on yet — set up
    </button>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useTeamFollows } from '../../composables/useTeamFollows';
import {
  useNotificationSetup,
  openSetupGuide,
} from '../../composables/useNotificationSetup';

const props = defineProps({
  teamId: { type: [Number, String], required: true },
  teamName: { type: String, default: '' },
  // 'dark' = sits on dark/colored team-header gradient (default, SB-55 placement).
  // 'light' = sits on a normal light page background (SB-56 placement on MatchesView).
  variant: {
    type: String,
    default: 'dark',
    validator: v => ['dark', 'light'].includes(v),
  },
});

const authStore = useAuthStore();
const { isFollowing, toggle, ensureLoaded, loaded, follows } = useTeamFollows();
const { isComplete, shouldPromptUnprompted } = useNotificationSetup();

// "Live" means a push would actually arrive: installed where required,
// permission granted, and a subscription registered on the backend.
const alertsLive = computed(() => isComplete.value);

const busy = ref(false);

// Hide entirely when unauthenticated (v1 decision — no login funnel).
const visible = computed(() => authStore.isAuthenticated.value);

const following = computed(() => isFollowing(props.teamId));

const label = computed(() => {
  if (busy.value) return following.value ? 'Following…' : 'Following…';
  return following.value ? 'Following' : 'Follow';
});

function openGuide() {
  openSetupGuide('follow');
}

async function onClick() {
  if (busy.value) return;
  const wasFollowing = following.value;
  // Their very first follow is the one moment where the gap between "saved to
  // a list" and "a push will reach me" is both invisible and freshly relevant.
  // Later follows get the persistent hint chip instead — opening a modal on
  // every follow would be nagging, not teaching.
  const isFirstEverFollow = !wasFollowing && follows.value.length === 0;
  busy.value = true;
  try {
    const result = await toggle(props.teamId);
    if (
      isFirstEverFollow &&
      result?.success !== false &&
      shouldPromptUnprompted.value
    ) {
      openSetupGuide('follow');
    }
  } finally {
    busy.value = false;
  }
}

onMounted(() => {
  if (visible.value && !loaded.value) ensureLoaded();
});
</script>

<style scoped>
.follow-wrap {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 5px;
}

.follow-hint {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border: none;
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.15);
  color: rgb(180, 83, 9);
  font-size: 11px;
  font-weight: 700;
  line-height: 1.3;
  cursor: pointer;
  white-space: nowrap;
}

.follow-hint:hover,
.follow-hint:focus-visible {
  background: rgba(245, 158, 11, 0.28);
  outline: none;
}

.follow-hint-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgb(245, 158, 11);
  flex-shrink: 0;
}

.follow-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  min-height: 44px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.01em;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease,
    transform 0.05s ease;
}

.follow-button:active:not(:disabled) {
  transform: translateY(0);
}

/* Dark variant — sits on the team-header gradient (SB-55). */
.follow-button--dark {
  background: rgba(255, 255, 255, 0.95);
  color: #1f2937;
  border: 1.5px solid rgba(255, 255, 255, 0.95);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.follow-button--dark:hover:not(:disabled) {
  background: white;
  transform: translateY(-1px);
}

.follow-button--dark:focus-visible {
  outline: 2px solid #ffffff;
  outline-offset: 2px;
}

/* Light variant — sits on normal page background (SB-56 on MatchesView). */
.follow-button--light {
  background: white;
  color: #1e40af;
  border: 1.5px solid #1e40af;
}

.follow-button--light:hover:not(:disabled) {
  background: rgba(30, 64, 175, 0.08);
  transform: translateY(-1px);
}

.follow-button--light:focus-visible {
  outline: 2px solid #1e40af;
  outline-offset: 2px;
}

.follow-button.is-following {
  background: rgba(16, 185, 129, 0.95);
  border-color: rgba(16, 185, 129, 0.95);
  color: white;
}

.follow-button.is-following:hover:not(:disabled) {
  background: rgb(5, 150, 105);
  border-color: rgb(5, 150, 105);
}

.follow-button.is-busy {
  opacity: 0.7;
  cursor: progress;
}

.follow-button:disabled {
  cursor: not-allowed;
}

.follow-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.follow-label {
  white-space: nowrap;
}

@media (max-width: 480px) {
  .follow-button {
    padding: 8px 12px;
    font-size: 12px;
  }
}
</style>
