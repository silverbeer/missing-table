<template>
  <a
    v-if="hasAssignment"
    href="#"
    @click.prevent="scroll"
    :class="['live-updates-teaser', variant]"
  >
    📡 Want live match updates? →
  </a>
</template>

<script>
import { computed } from 'vue';
import { useAuthStore } from '@/stores/auth';

export default {
  name: 'LiveUpdatesTeaser',
  props: {
    // 'hero' = white text on dark hero card  |  'light' = blue link on light bg
    variant: { type: String, default: 'light' },
  },
  setup() {
    const authStore = useAuthStore();

    const hasAssignment = computed(
      () =>
        !!(authStore.state.profile?.team_id || authStore.state.profile?.club_id)
    );

    const scroll = () => {
      document
        .getElementById('live-updates-section')
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    return { hasAssignment, scroll };
  },
};
</script>

<style scoped>
.live-updates-teaser {
  display: inline-block;
  font-size: 13px;
  text-decoration: none;
  cursor: pointer;
  transition:
    color 0.15s,
    border-color 0.15s;
}

/* On a dark hero card */
.live-updates-teaser.hero {
  color: rgba(255, 255, 255, 0.85);
  border-bottom: 1px dashed rgba(255, 255, 255, 0.5);
}
.live-updates-teaser.hero:hover {
  color: white;
  border-bottom-color: white;
}

/* On a light background */
.live-updates-teaser.light {
  color: #0ea5e9;
  border-bottom: 1px dashed #7dd3fc;
}
.live-updates-teaser.light:hover {
  color: #0284c7;
  border-bottom-color: #0284c7;
}
</style>
