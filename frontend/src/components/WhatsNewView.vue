<template>
  <div
    class="fixed inset-0 z-50 bg-black/60 overflow-y-auto"
    data-testid="whats-new-overlay"
    @click.self="$emit('close')"
  >
    <div class="min-h-full flex items-start justify-center p-3 sm:p-6">
      <div
        class="relative w-full max-w-2xl bg-card rounded-lg shadow-2xl"
        @click.stop
      >
        <button
          type="button"
          aria-label="Close what's new"
          data-testid="whats-new-close"
          class="absolute top-3 right-3 z-10 inline-flex items-center justify-center w-8 h-8 rounded-full text-fg-muted hover:text-fg hover:bg-surface-alt"
          @click="$emit('close')"
        >
          ✕
        </button>

        <div class="p-5 sm:p-7">
          <h2 class="text-xl font-bold text-fg mb-1">✨ What's New</h2>
          <p class="text-sm text-fg-muted mb-5">
            New features and improvements in Missing Table.
          </p>

          <p v-if="error" class="text-sm text-red-700">
            Couldn't load the changelog: {{ error }}
          </p>
          <p
            v-else-if="loaded && !releases.length"
            class="text-sm text-fg-muted"
          >
            No release notes yet — check back after the next update.
          </p>

          <div
            v-for="r in releases"
            :key="r.version"
            class="changelog-release"
            :data-testid="`changelog-release-${r.version}`"
          >
            <div class="flex items-baseline gap-2 flex-wrap">
              <h3 class="text-base font-semibold text-fg">
                {{ r.version }}
              </h3>
              <span v-if="r.title" class="text-sm text-fg-muted">{{
                r.title
              }}</span>
              <span
                v-if="isNew(r.version)"
                class="changelog-new-chip"
                data-testid="changelog-new-chip"
                >New</span
              >
            </div>
            <!-- Content is repo-authored (trusted); rendered from CHANGELOG.md -->
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div class="changelog-body prose-sm" v-html="r.bodyHtml"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import { useChangelog } from '../composables/useChangelog';

defineEmits(['close']);

const { releases, loaded, error, load, isNew, markAllSeen } = useChangelog();

onMounted(async () => {
  await load();
  // Opening the page counts as seeing the latest release.
  markAllSeen();
});
</script>

<style scoped>
.changelog-release {
  padding: 14px 0;
  border-top: 1px solid rgb(var(--color-line));
}
.changelog-release:first-of-type {
  border-top: none;
}
.changelog-new-chip {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 999px;
  background: #10b981;
  color: white;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.changelog-body {
  margin-top: 6px;
  font-size: 14px;
  color: rgb(var(--color-fg));
  line-height: 1.5;
}
/* Lightweight markdown styling (no prose plugin dependency) */
.changelog-body :deep(h3) {
  font-size: 14px;
  font-weight: 700;
  margin: 12px 0 4px;
  color: rgb(var(--color-fg));
}
.changelog-body :deep(ul) {
  list-style: disc;
  padding-left: 20px;
  margin: 6px 0;
}
.changelog-body :deep(li) {
  margin: 3px 0;
}
.changelog-body :deep(a) {
  color: #1e40af;
  text-decoration: underline;
}
:global(.dark) .changelog-body :deep(a) {
  color: #779edb;
}
.changelog-body :deep(code) {
  background: rgb(var(--color-surface-alt));
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
}
.changelog-body :deep(strong) {
  font-weight: 600;
  color: rgb(var(--color-fg));
}
</style>
