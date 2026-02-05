<template>
  <div v-if="show" class="modal-overlay" @click="$emit('cancel')">
    <div class="modal-content" @click.stop>
      <div class="p-6">
        <!-- Header -->
        <div class="flex items-start mb-4">
          <div
            v-if="variant === 'warning'"
            class="flex-shrink-0 w-10 h-10 rounded-full bg-yellow-100 flex items-center justify-center mr-4"
          >
            <svg
              class="w-6 h-6 text-yellow-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <div
            v-else-if="variant === 'danger'"
            class="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 flex items-center justify-center mr-4"
          >
            <svg
              class="w-6 h-6 text-red-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <div
            v-else
            class="flex-shrink-0 w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center mr-4"
          >
            <svg
              class="w-6 h-6 text-blue-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
          <div>
            <h3 class="text-lg font-medium text-gray-900">{{ title }}</h3>
            <p v-if="message" class="mt-1 text-sm text-gray-500">
              {{ message }}
            </p>
          </div>
        </div>

        <!-- Slot for custom content -->
        <div v-if="$slots.default" class="mb-4">
          <slot></slot>
        </div>

        <!-- Actions -->
        <div class="flex justify-end space-x-3">
          <button
            type="button"
            @click="$emit('cancel')"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
          >
            {{ cancelText }}
          </button>
          <button
            type="button"
            @click="$emit('confirm')"
            :disabled="loading"
            :class="confirmButtonClass"
          >
            {{ loading ? loadingText : confirmText }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { computed } from 'vue';

export default {
  name: 'ConfirmModal',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    title: {
      type: String,
      default: 'Confirm Action',
    },
    message: {
      type: String,
      default: '',
    },
    confirmText: {
      type: String,
      default: 'Confirm',
    },
    cancelText: {
      type: String,
      default: 'Cancel',
    },
    loadingText: {
      type: String,
      default: 'Processing...',
    },
    loading: {
      type: Boolean,
      default: false,
    },
    variant: {
      type: String,
      default: 'info', // 'info', 'warning', 'danger'
      validator: value => ['info', 'warning', 'danger'].includes(value),
    },
  },
  emits: ['confirm', 'cancel'],
  setup(props) {
    const confirmButtonClass = computed(() => {
      const base =
        'px-4 py-2 text-sm font-medium text-white rounded-md disabled:opacity-50';
      if (props.variant === 'danger') {
        return `${base} bg-red-600 hover:bg-red-700`;
      }
      if (props.variant === 'warning') {
        return `${base} bg-yellow-600 hover:bg-yellow-700`;
      }
      return `${base} bg-blue-600 hover:bg-blue-700`;
    });

    return {
      confirmButtonClass,
    };
  },
};
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 0.5rem;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  max-width: 480px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}
</style>
