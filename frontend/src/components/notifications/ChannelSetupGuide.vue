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
          <p class="lead">{{ START.lead }}</p>
          <div class="decisions">
            <button
              v-for="d in START.decisions"
              :key="d.tab"
              class="decision"
              :data-testid="`guide-decision-${d.tab}`"
              @click="go(d.tab, d.platform)"
            >
              <span class="who">{{ d.who }}</span>
              <span class="pick">{{ d.pick }}</span>
              <span class="why">{{ d.why }}</span>
            </button>
          </div>
          <p class="both" data-testid="guide-both">{{ START.both }}</p>
          <p class="example">{{ START.example }}</p>

          <h3>Then set up</h3>
          <ol>
            <li v-for="n in START.next" :key="n.tab">
              <button class="link-btn" @click="go(n.tab)">
                {{ tabLabel(n.tab) }}
              </button>
              — {{ n.text }}
            </li>
          </ol>

          <details class="good" data-testid="guide-good-to-know">
            <summary>Good to know</summary>
            <ul>
              <li v-for="(line, i) in START.goodToKnow" :key="i">{{ line }}</li>
            </ul>
          </details>
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

          <button
            v-if="entry.unavailable"
            class="link-btn use-instead"
            data-testid="guide-use-discord"
            @click="platform = 'discord'"
          >
            Show the Discord steps
          </button>

          <template v-else>
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
          </template>
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

const tabLabel = id => TABS.find(t => t.id === id)?.label || id;

function go(nextTab, nextPlatform) {
  tab.value = nextTab;
  if (nextPlatform) platform.value = nextPlatform;
}
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

.lead {
  margin: 0 0 12px;
}

.decisions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.decision {
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid rgb(var(--color-line));
  background: rgb(var(--color-card));
  color: rgb(var(--color-fg));
  cursor: pointer;
}

.decision:hover {
  border-color: rgb(37 99 235);
}

.who {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: rgb(var(--color-fg-muted));
}

.pick {
  font-size: 20px;
  font-weight: 700;
  color: rgb(37 99 235);
}

.why {
  font-size: 13px;
}

.both {
  margin: 12px 0 4px;
}

.example {
  margin: 0;
  color: rgb(var(--color-fg-muted));
}

.good {
  margin-top: 16px;
}

.good summary {
  font-weight: 700;
  cursor: pointer;
}

.good ul {
  margin-top: 6px;
}

.use-instead {
  margin-top: 10px;
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
