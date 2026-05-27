<template>
  <button
    v-if="visible"
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
</template>

<script setup>
import { computed, ref, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useTeamFollows } from '../../composables/useTeamFollows';

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
const { isFollowing, toggle, ensureLoaded, loaded } = useTeamFollows();

const busy = ref(false);

// Hide entirely when unauthenticated (v1 decision — no login funnel).
const visible = computed(() => authStore.isAuthenticated.value);

const following = computed(() => isFollowing(props.teamId));

const label = computed(() => {
  if (busy.value) return following.value ? 'Following…' : 'Following…';
  return following.value ? 'Following' : 'Follow';
});

async function onClick() {
  if (busy.value) return;
  busy.value = true;
  try {
    await toggle(props.teamId);
  } finally {
    busy.value = false;
  }
}

onMounted(() => {
  if (visible.value && !loaded.value) ensureLoaded();
});
</script>

<style scoped>
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
  color: #0257fe;
  border: 1.5px solid #0257fe;
}

.follow-button--light:hover:not(:disabled) {
  background: rgba(2, 87, 254, 0.08);
  transform: translateY(-1px);
}

.follow-button--light:focus-visible {
  outline: 2px solid #0257fe;
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
