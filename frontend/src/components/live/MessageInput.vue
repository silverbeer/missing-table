<template>
  <div class="message-input-container">
    <div class="input-wrapper">
      <input
        v-model="message"
        type="text"
        placeholder="Type a message..."
        class="message-input"
        :disabled="disabled"
        @keyup.enter="sendMessage"
        maxlength="500"
      />
      <button
        @click="sendMessage"
        :disabled="disabled || !message.trim()"
        class="send-button"
      >
        <span class="send-icon">&#10148;</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['send']);

const message = ref('');

function sendMessage() {
  if (!message.value.trim() || props.disabled) return;

  emit('send', message.value.trim());
  message.value = '';
}
</script>

<style scoped>
.message-input-container {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #16213e;
  padding: 12px 16px;
  border-top: 1px solid #333;
  z-index: 100;
}

.input-wrapper {
  display: flex;
  gap: 12px;
  max-width: 640px;
  margin: 0 auto;
}

.message-input {
  flex: 1;
  padding: 12px 16px;
  border: 2px solid #333;
  border-radius: 24px;
  background: #1a1a2e;
  color: white;
  font-size: 16px;
  min-height: 48px;
}

.message-input:focus {
  outline: none;
  border-color: #2196f3;
}

.message-input::placeholder {
  color: #666;
}

.message-input:disabled {
  opacity: 0.5;
}

.send-button {
  width: 48px;
  height: 48px;
  border: none;
  border-radius: 50%;
  background: #2196f3;
  color: white;
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
}

.send-button:hover:not(:disabled) {
  background: #1e88e5;
}

.send-button:disabled {
  background: #444;
  cursor: not-allowed;
}

.send-icon {
  transform: rotate(-45deg);
}

/* Responsive */
@media (min-width: 640px) {
  .message-input-container {
    padding: 16px;
  }
}

@media (min-width: 1024px) {
  .input-wrapper {
    max-width: 800px;
  }
}
</style>
