<template>
  <div class="color-input">
    <label v-if="label" class="color-label">{{ label }}</label>
    <div class="color-controls">
      <input
        :value="modelValue"
        type="color"
        class="color-picker"
        @input="$emit('update:modelValue', $event.target.value)"
      />
      <input
        :value="modelValue"
        type="text"
        class="color-text"
        placeholder="#3B82F6"
        maxlength="7"
        @input="handleTextInput"
      />
    </div>
    <p v-if="helpText" class="color-help">{{ helpText }}</p>
  </div>
</template>

<script>
export default {
  name: 'ColorInput',
  props: {
    modelValue: {
      type: String,
      default: '#3B82F6',
    },
    label: {
      type: String,
      default: '',
    },
    helpText: {
      type: String,
      default: '',
    },
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const handleTextInput = event => {
      let value = event.target.value;
      // Ensure it starts with #
      if (value && !value.startsWith('#')) {
        value = '#' + value;
      }
      // Only emit if it's a valid hex color or partial
      if (/^#[0-9A-Fa-f]{0,6}$/.test(value)) {
        emit('update:modelValue', value);
      }
    };

    return {
      handleTextInput,
    };
  },
};
</script>

<style scoped>
.color-input {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.color-label {
  font-weight: 600;
  color: #374151;
  font-size: 14px;
}

.color-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.color-picker {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  cursor: pointer;
  border: 2px solid #e5e7eb;
  padding: 2px;
}

.color-picker:hover {
  border-color: #9ca3af;
}

.color-text {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-family: monospace;
  font-size: 14px;
  text-transform: uppercase;
}

.color-text:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.color-help {
  font-size: 12px;
  color: #6b7280;
  margin: 0;
}
</style>
