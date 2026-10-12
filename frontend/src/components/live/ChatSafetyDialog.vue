<template>
  <div
    v-if="mode"
    class="dialog-overlay"
    data-testid="chat-safety-dialog"
    @click.self="$emit('close')"
  >
    <div class="dialog" role="dialog" aria-modal="true" :aria-label="title">
      <h3 class="dialog-title">{{ title }}</h3>

      <!-- Report: pick a reason -->
      <template v-if="mode === 'report'">
        <p class="dialog-text">Why are you reporting this message?</p>
        <div class="reason-list">
          <button
            v-for="reason in REPORT_REASONS"
            :key="reason.value"
            type="button"
            class="reason-button"
            :data-testid="`report-reason-${reason.value}`"
            :disabled="busy"
            @click="$emit('report', reason.value)"
          >
            {{ reason.label }}
          </button>
        </div>
        <div class="dialog-actions">
          <button type="button" class="secondary" @click="$emit('close')">
            Cancel
          </button>
        </div>
      </template>

      <!-- Block: confirm -->
      <template v-else-if="mode === 'block'">
        <p class="dialog-text">
          You won't see their messages anymore. You can unblock them in Profile.
        </p>
        <div class="dialog-actions">
          <button type="button" class="secondary" @click="$emit('close')">
            Cancel
          </button>
          <button
            type="button"
            class="danger"
            data-testid="confirm-block"
            :disabled="busy"
            @click="$emit('block')"
          >
            Block
          </button>
        </div>
      </template>

      <!-- Report sent -->
      <template v-else-if="mode === 'reported'">
        <p class="dialog-text">
          Thanks — we review reports within 24 hours. You won't see messages
          from this user anymore.
        </p>
        <div class="dialog-actions">
          <button type="button" class="primary" @click="$emit('close')">
            OK
          </button>
        </div>
      </template>

      <!-- Chat rules: once, before the first post -->
      <template v-else-if="mode === 'rules'">
        <p class="dialog-text">{{ CHAT_RULES_TEXT }}</p>
        <div class="dialog-actions">
          <button type="button" class="secondary" @click="$emit('close')">
            Cancel
          </button>
          <button
            type="button"
            class="primary"
            data-testid="agree-chat-rules"
            @click="$emit('agree')"
          >
            Agree
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { REPORT_REASONS, CHAT_RULES_TEXT } from '../../utils/chatSafety';

// Live chat safety dialogs (SB-1324); wording matches the iOS app.
const props = defineProps({
  // 'report' | 'block' | 'reported' | 'rules' | null (closed)
  mode: {
    type: String,
    default: null,
  },
  username: {
    type: String,
    default: '',
  },
  busy: {
    type: Boolean,
    default: false,
  },
});

defineEmits(['close', 'report', 'block', 'agree']);

const title = computed(() => {
  switch (props.mode) {
    case 'report':
      return 'Report Message';
    case 'block':
      return `Block ${props.username || 'this user'}?`;
    case 'reported':
      return 'Report Sent';
    case 'rules':
      return 'Chat Rules';
    default:
      return '';
  }
});
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 200;
}

.dialog {
  width: 100%;
  max-width: 400px;
  background: #16213e;
  color: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
}

.dialog-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px;
}

.dialog-text {
  font-size: 14px;
  color: #ccc;
  margin: 0 0 16px;
  line-height: 1.5;
}

.reason-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.reason-button {
  width: 100%;
  min-height: 44px;
  padding: 10px 14px;
  text-align: left;
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: 8px;
  color: white;
  font-size: 15px;
  cursor: pointer;
}

.reason-button:hover:not(:disabled) {
  border-color: #2196f3;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.dialog-actions button {
  min-height: 40px;
  padding: 8px 16px;
  border-radius: 8px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.dialog-actions button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.secondary {
  background: #333;
  color: white;
}

.primary {
  background: #2196f3;
  color: white;
}

.danger {
  background: #d32f2f;
  color: white;
}
</style>
