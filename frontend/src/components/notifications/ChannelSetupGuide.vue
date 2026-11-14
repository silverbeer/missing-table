<template>
  <ModalOverlay
    label="Chat channel setup guide"
    max-width="max-w-3xl"
    @close="$emit('close')"
  >
    <div class="guide" data-testid="channel-guide">
      <header class="guide-head">
        <h2 id="channel-guide-title">Chat channel setup guide</h2>
      </header>

      <nav class="tabs" role="tablist">
        <button
          v-for="t in TABS"
          :key="t.id"
          role="tab"
          :aria-selected="tab === t.id"
          :class="['tab', { active: tab === t.id }]"
          :data-testid="`guide-tab-${t.id}`"
          @click="tab = t.id"
        >
          {{ t.label }}
        </button>
      </nav>

      <div class="guide-body">
        <!-- Start here -->
        <section v-if="tab === 'start'" data-testid="guide-start">
          <p>{{ START.intro }}</p>
          <h3>Three kinds of room</h3>
          <ul class="types">
            <li v-for="t in START.types" :key="t.tab">
              <button class="link-btn" @click="tab = t.tab">
                {{ t.title }}
              </button>
              — {{ t.text }}
            </li>
          </ul>
          <h3>Example: IFA</h3>
          <ul>
            <li v-for="(line, i) in START.example" :key="i">{{ line }}</li>
          </ul>
          <h3>Good to know</h3>
          <ul>
            <li v-for="(line, i) in START.advice" :key="i">{{ line }}</li>
          </ul>
          <h3>In order</h3>
          <ol>
            <li v-for="(line, i) in START.order" :key="i">{{ line }}</li>
          </ol>
        </section>

        <!-- One channel type, per platform -->
        <section v-else :data-testid="`guide-${tab}`">
          <div class="platforms" role="tablist">
            <button
              v-for="p in PLATFORMS"
              :key="p.id"
              role="tab"
              :aria-selected="platform === p.id"
              :class="['pill', { active: platform === p.id }]"
              :data-testid="`guide-platform-${p.id}`"
              @click="platform = p.id"
            >
              {{ p.label }}
            </button>
          </div>

          <p class="summary" data-testid="guide-summary">{{ entry.summary }}</p>

          <h3>1. Create the room</h3>
          <ol>
            <li v-for="(s, i) in entry.steps" :key="i">{{ s }}</li>
          </ol>

          <h3>2. Connect Missing Table</h3>
          <ol>
            <li v-for="(s, i) in entry.connect" :key="i">{{ s }}</li>
          </ol>

          <h3>3. Make an invite link</h3>
          <ol>
            <li v-for="(s, i) in entry.invite" :key="i">{{ s }}</li>
          </ol>

          <h3>4. Add it in Missing Table</h3>
          <ol data-testid="guide-register">
            <li v-for="(s, i) in registerSteps(tab)" :key="i">{{ s }}</li>
          </ol>

          <div
            v-if="entry.notes?.length"
            class="notes"
            data-testid="guide-notes"
          >
            <p v-for="(n, i) in entry.notes" :key="i">{{ n }}</p>
          </div>
        </section>
      </div>
    </div>
  </ModalOverlay>
</template>

<script setup>
/**
 * How a club manager sets up chat rooms (SB-1672): a tab per channel type
 * (club announcements, fan chat, players), each with Slack, Telegram and
 * Discord steps. Words live in channelGuide.js.
 */
import { computed, ref } from 'vue';
import ModalOverlay from '@/components/ui/ModalOverlay.vue';
import {
  GUIDE,
  PLATFORMS,
  START,
  TABS,
  registerSteps,
} from './channelGuide.js';

const props = defineProps({
  initialTab: { type: String, default: 'start' },
  initialPlatform: { type: String, default: 'slack' },
});
defineEmits(['close']);

const tab = ref(
  TABS.some(t => t.id === props.initialTab) ? props.initialTab : 'start'
);
const platform = ref(
  PLATFORMS.some(p => p.id === props.initialPlatform)
    ? props.initialPlatform
    : 'slack'
);

const entry = computed(() => GUIDE[tab.value]?.[platform.value] || {});
</script>

<style scoped>
.guide {
  color: rgb(var(--color-fg));
}

.guide-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px 8px;
}

.guide-head h2 {
  font-size: 18px;
  font-weight: 700;
  margin: 0;
}

.tabs {
  display: flex;
  gap: 4px;
  padding: 0 20px;
  border-bottom: 1px solid rgb(var(--color-line));
  overflow-x: auto;
}

.tab {
  padding: 8px 12px;
  font-size: 14px;
  white-space: nowrap;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: rgb(var(--color-fg-muted));
  cursor: pointer;
}

.tab.active {
  color: rgb(var(--color-fg));
  border-bottom-color: rgb(37 99 235);
  font-weight: 600;
}

.guide-body {
  padding: 16px 20px 20px;
  font-size: 14px;
  line-height: 1.5;
}

.guide-body h3 {
  font-size: 14px;
  font-weight: 700;
  margin: 16px 0 6px;
}

.guide-body ol,
.guide-body ul {
  padding-left: 20px;
  margin: 0;
}

.guide-body ol {
  list-style: decimal;
}

.guide-body ul {
  list-style: disc;
}

.guide-body li {
  margin: 4px 0;
}

.types {
  list-style: none !important;
  padding-left: 0 !important;
}

.platforms {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
}

.pill {
  padding: 4px 12px;
  font-size: 13px;
  border-radius: 999px;
  border: 1px solid rgb(var(--color-line));
  background: rgb(var(--color-card));
  color: rgb(var(--color-fg));
  cursor: pointer;
}

.pill.active {
  background: rgb(37 99 235);
  border-color: rgb(37 99 235);
  color: #fff;
}

.summary {
  font-weight: 500;
  margin: 0;
}

.notes {
  margin-top: 16px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgb(234 179 8 / 0.12);
  font-size: 13px;
}

.notes p {
  margin: 2px 0;
}

.link-btn {
  background: none;
  border: none;
  padding: 0;
  color: rgb(37 99 235);
  font-weight: 600;
  cursor: pointer;
}
</style>
