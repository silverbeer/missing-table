<template>
  <div
    class="fixed inset-0 z-50 bg-black/60 overflow-y-auto"
    data-testid="whats-new-overlay"
    @click.self="$emit('close')"
  >
    <div class="min-h-full flex items-start justify-center p-3 sm:p-6">
      <div
        class="relative w-full max-w-2xl bg-white rounded-lg shadow-2xl"
        @click.stop
      >
        <button
          type="button"
          aria-label="Close what's new"
          data-testid="whats-new-close"
          class="absolute top-3 right-3 z-10 inline-flex items-center justify-center w-8 h-8 rounded-full text-gray-500 hover:text-gray-900 hover:bg-gray-100"
          @click="$emit('close')"
        >
          ✕
        </button>

        <div class="p-5 sm:p-7">
          <h2 class="text-xl font-bold text-gray-900 mb-1">✨ What's New</h2>
          <p class="text-sm text-gray-500 mb-5">
            New features and improvements in Missing Table.
          </p>

          <p v-if="error" class="text-sm text-red-700">
            Couldn't load the changelog: {{ error }}
          </p>
          <p
            v-else-if="loaded && !releases.length"
            class="text-sm text-gray-500"
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
              <h3 class="text-base font-semibold text-gray-900">
                {{ r.version }}
              </h3>
              <span v-if="r.title" class="text-sm text-gray-600">{{
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
  border-top: 1px solid #f3f4f6;
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
  color: #374151;
  line-height: 1.5;
}
/* Lightweight markdown styling (no prose plugin dependency) */
.changelog-body :deep(h3) {
  font-size: 14px;
  font-weight: 700;
  margin: 12px 0 4px;
  color: #111827;
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
  color: #0257fe;
  text-decoration: underline;
}
.changelog-body :deep(code) {
  background: #f3f4f6;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
}
.changelog-body :deep(strong) {
  font-weight: 600;
  color: #111827;
}
</style>
