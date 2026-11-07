<template>
  <!-- Admin editor for the "Why" list (SB-1577). The parent owns the save. -->
  <div class="motw-editor" data-testid="motw-reasons-editor">
    <span class="motw-editor-label">Why this is the Match of the Week</span>
    <ol class="rows">
      <li
        v-for="(row, i) in rows"
        :key="row.key"
        class="row"
        data-testid="motw-reason-row"
      >
        <select
          v-model="row.kind"
          class="kind"
          :aria-label="`Reason ${i + 1} kind`"
          data-testid="motw-reason-kind"
        >
          <option value="">—</option>
          <option v-for="k in REASON_KINDS" :key="k.value" :value="k.value">
            {{ k.icon }} {{ k.label }}
          </option>
        </select>
        <input
          v-model="row.text"
          class="text"
          type="text"
          :maxlength="REASON_TEXT_MAX"
          :aria-label="`Reason ${i + 1}`"
          placeholder="1st vs 3rd, two points apart"
          data-testid="motw-reason-input"
          @keydown.esc.stop="$emit('cancel')"
        />
        <button
          type="button"
          class="icon"
          :disabled="i === 0"
          :aria-label="`Move reason ${i + 1} up`"
          data-testid="motw-reason-up"
          @click="move(i, -1)"
        >
          ↑
        </button>
        <button
          type="button"
          class="icon"
          :disabled="i === rows.length - 1"
          :aria-label="`Move reason ${i + 1} down`"
          data-testid="motw-reason-down"
          @click="move(i, 1)"
        >
          ↓
        </button>
        <button
          type="button"
          class="icon"
          :aria-label="`Remove reason ${i + 1}`"
          data-testid="motw-reason-remove"
          @click="remove(i)"
        >
          ✕
        </button>
      </li>
    </ol>
    <div class="motw-editor-foot">
      <button
        type="button"
        class="add"
        :disabled="rows.length >= REASONS_MAX"
        data-testid="motw-reason-add"
        @click="add"
      >
        + Add reason
      </button>
      <span class="count" data-testid="motw-reasons-count"
        >{{ rows.length }}/{{ REASONS_MAX }}</span
      >
      <button
        type="button"
        class="motw-button motw-button--quiet"
        data-testid="motw-reasons-cancel"
        @click="$emit('cancel')"
      >
        Cancel
      </button>
      <button
        type="button"
        class="motw-button motw-button--primary"
        data-testid="motw-reasons-save"
        :disabled="saving"
        @click="$emit('save', cleanReasons(rows))"
      >
        {{ saving ? 'Saving…' : 'Save reasons' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import {
  REASON_KINDS,
  REASON_TEXT_MAX,
  REASONS_MAX,
  cleanReasons,
} from '@/utils/featuredReasons';

const props = defineProps({
  reasons: { type: Array, default: null },
  saving: { type: Boolean, default: false },
});
defineEmits(['save', 'cancel']);

let seq = 0;
const toRow = r => ({ key: ++seq, text: r?.text ?? '', kind: r?.kind ?? '' });

// Opening with nothing written gives one blank row to type into.
const rows = ref(
  props.reasons && props.reasons.length
    ? props.reasons.map(toRow)
    : [toRow(null)]
);

const add = () => {
  if (rows.value.length < REASONS_MAX) rows.value.push(toRow(null));
};
const remove = i => rows.value.splice(i, 1);
const move = (i, delta) => {
  const j = i + delta;
  if (j < 0 || j >= rows.value.length) return;
  const next = rows.value.slice();
  [next[i], next[j]] = [next[j], next[i]];
  rows.value = next;
};
</script>

<style scoped>
.motw-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 62ch;
}
.motw-editor-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgb(var(--color-fg-muted));
}
.rows {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.row {
  display: flex;
  gap: 6px;
  align-items: center;
}
.kind,
.text {
  min-height: 36px;
  border-radius: 6px;
  border: 1px solid rgb(var(--color-line));
  background: rgb(var(--color-card));
  color: rgb(var(--color-fg));
  font-size: 14px;
  padding: 0 8px;
}
.kind {
  flex-shrink: 0;
  max-width: 9.5rem;
}
.text {
  flex: 1;
  min-width: 0;
}
.icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: 1px solid rgb(var(--color-line));
  background: rgb(var(--color-surface-alt));
  color: rgb(var(--color-fg));
  cursor: pointer;
}
.icon:disabled {
  opacity: 0.35;
  cursor: default;
}
.motw-editor-foot {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.add {
  border: 0;
  background: none;
  padding: 0;
  font-size: 13px;
  font-weight: 600;
  color: #b45309;
  cursor: pointer;
}
:global(.dark .add) {
  color: #f59e0b;
}
.add:disabled {
  opacity: 0.4;
  cursor: default;
}
.count {
  margin-right: auto;
  font-size: 12px;
  color: rgb(var(--color-fg-muted));
}
.motw-button {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  border: 1px solid rgb(var(--color-line));
  background: rgb(var(--color-surface-alt));
  color: rgb(var(--color-fg));
  cursor: pointer;
}
.motw-button--primary {
  background: #f59e0b;
  border-color: #f59e0b;
  color: #1f1300;
}
@media (max-width: 480px) {
  .row {
    flex-wrap: wrap;
  }
  .text {
    flex-basis: 100%;
    order: -1;
  }
}
</style>
